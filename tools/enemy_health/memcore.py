"""
ADB 内存读取底层 (明日方舟 @ MuMu 模拟器)

- 通过 adb exec-out dd 读取 Android 进程 /proc/<pid>/mem
- 4MB 大块对齐读取 (比 bs=1 快几个数量级)
- /proc/<pid>/maps 解析与指针有效性校验
- Il2CppString / C 字符串读取
- TcpChannel: 设备侧常驻 TCP 通道 (adb forward)。优先使用自编译的
  memsrv 服务 (memsrv.c, 打开 /proc/<pid>/mem 一次后每次读取仅一个
  pread64, 单批 ~2-5ms); 不可用时回退 nc -L sh + dd 模式 (~45ms/请求)
"""

import subprocess
import struct
import re
import os
import time
import bisect
import socket
import threading
from typing import Optional, List, Tuple

try:
    from .game_structs import Il2CppString
except ImportError:  # 允许作为独立脚本直接运行
    from game_structs import Il2CppString

DEFAULT_PKG = "com.hypergryph.arknights"
BS = 4 * 1024 * 1024  # dd 块大小


def find_mumu_adb() -> Optional[str]:
    """查找 MuMu adb.exe: 配置缓存 -> PATH -> 常见路径 -> 注册表"""
    import os
    import json
    cfg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        if os.path.isfile(cfg_file):
            with open(cfg_file, 'r', encoding='utf-8') as f:
                saved = json.load(f).get("adb_path")
            if saved and os.path.isfile(saved):
                return saved
    except Exception:
        pass
    import shutil
    p = shutil.which("adb")
    if p:
        return p
    import os as _os
    quick = [
        r"D:\Program Files\MuMu9\emulator\MuMuPlayer-12.0\shell\adb.exe",
        r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
        r"D:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
        r"C:\Program Files\MuMu\shell\adb.exe",
        r"D:\MuMu\shell\adb.exe",
    ]
    for q in quick:
        if _os.path.isfile(q):
            return q
    try:
        import winreg
        for kp in (r"SOFTWARE\Netease\MuMuPlayer", r"SOFTWARE\Netease\MuMuPlayer-12.0"):
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, kp)
                adb = _os.path.join(winreg.QueryValueEx(key, "InstallDir")[0], "shell", "adb.exe")
                if _os.path.isfile(adb):
                    return adb
            except Exception:
                pass
    except Exception:
        pass
    return None


class TcpChannel:
    """设备侧常驻读取服务 (adb forward TCP 长连接)。

    两种模式 (open() 自动探测):
    - 'srv': 自编译 memsrv (tools/enemy_health/memsrv.c -> bin/memsrv,
      aarch64 静态)。nc -L 以其为服务程序, 启动即打开 /proc/<pid>/mem,
      之后每请求仅一个 pread64。协议: 8 字节横幅 "AKMSRV1\\n"; 请求
      u64 N + N*{u64 addr, u64 size}; 响应 i64 n + n 字节 (n<0 为 -errno,
      n<size 为短读)。单批 ~2-5ms, 准实时首选。
    - 'sh':  nc -L sh + 每请求 fork dd (~33-45ms/请求), 作为兜底。
      协议: 每请求 "M<i>" 行 + 页对齐 dd 原始数据 + "E<i>" 行, 末尾 "END"。

    任何读取异常都会关闭 socket 并抛出, 由调用方回退慢速 read()。"""

    PORT = 27271
    SRV_DIR = '/data/local/tmp'
    BANNER = b"AKMSRV1\n"

    def __init__(self, mc: 'MemCore', read_timeout: float = 5.0):
        self.mc = mc
        self.read_timeout = read_timeout
        self.sock: Optional[socket.socket] = None
        self.mode: Optional[str] = None   # 'srv' | 'sh'
        self._lock = threading.Lock()   # 同一时间只允许一个 batch_read

    # ---------- 服务部署 ----------

    def _push_memsrv(self) -> bool:
        """推送 memsrv 二进制 + 包装脚本到设备 (幂等)"""
        try:
            out = self.mc.shell(f"ls {self.SRV_DIR}/memsrv 2>/dev/null")
            if 'memsrv' not in out:
                local = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     'bin', 'memsrv')
                if not os.path.exists(local):
                    return False
                self.mc.adb('push', local, f'{self.SRV_DIR}/memsrv')
                self.mc.shell(f"chmod 755 {self.SRV_DIR}/memsrv")
            # 包装脚本每次重写: 每次连接都用 pidof 动态解析 PID (游戏重启自愈)
            self.mc.shell(
                f"printf '#!/system/bin/sh\\nexec {self.SRV_DIR}/memsrv "
                f"$(pidof {self.mc.package})\\n' > {self.SRV_DIR}/memsrv.sh")
            self.mc.shell(f"chmod 755 {self.SRV_DIR}/memsrv.sh")
            return True
        except Exception:
            return False

    def _ensure_server(self):
        """启动设备侧服务并建立 adb forward (幂等)"""
        try:
            socket.create_connection(("127.0.0.1", self.PORT), timeout=2).close()
            return   # 服务与 forward 均已在
        except OSError:
            pass
        self.mc.adb("forward", f"tcp:{self.PORT}", f"tcp:{self.PORT}")
        try:
            socket.create_connection(("127.0.0.1", self.PORT), timeout=2).close()
            return   # forward 已有, 服务已在
        except OSError:
            pass
        # 启动服务 (setsid 防 adb 会话退出时被杀; 5555 是 adbd 占用, 避开)
        if self._push_memsrv():
            self.mc.shell(f"setsid nc -L -p {self.PORT} "
                          f"{self.SRV_DIR}/memsrv.sh </dev/null >/dev/null 2>&1 &")
        else:
            self.mc.shell(f"setsid nc -L -p {self.PORT} sh </dev/null >/dev/null 2>&1 &")
        time.sleep(0.5)

    # ---------- 连接 ----------

    def open(self):
        self.close()
        self._ensure_server()
        self.sock = socket.create_connection(("127.0.0.1", self.PORT), timeout=10)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # 模式探测: memsrv 会主动发 8 字节横幅; sh 不会主动发任何字节
        self.sock.settimeout(1.0)
        try:
            b = self._read_exact(8)
        except (socket.timeout, OSError):
            b = b''
        self.sock.settimeout(self.read_timeout)
        if b == self.BANNER:
            self.mode = 'srv'
            return
        # sh 模式 (或 memsrv 启动失败): 尝试 sh 同步
        self.mode = None
        self.sock.sendall(b"echo AKCHAN_READY\n")
        for _ in range(20):
            if self._read_line() == b"AKCHAN_READY":
                self.mode = 'sh'
                break
        if self.mode is None:
            self.close()
            raise IOError("TCP 通道同步失败")
        # sh 模式且 memsrv 可部署 -> 升级: 杀掉 sh 版 nc, 换 memsrv 版 (每进程只试一次)
        if not getattr(self.mc, '_memsrv_upgrade_tried', False) and self._push_memsrv():
            self.mc._memsrv_upgrade_tried = True
            self.close()
            self.mc.shell("kill $(pidof nc) 2>/dev/null")
            time.sleep(0.3)
            self.mc.shell(f"setsid nc -L -p {self.PORT} "
                          f"{self.SRV_DIR}/memsrv.sh </dev/null >/dev/null 2>&1 &")
            time.sleep(0.5)
            self.sock = socket.create_connection(("127.0.0.1", self.PORT), timeout=10)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.settimeout(self.read_timeout)
            b = self._read_exact(8)
            if b != self.BANNER:
                self.close()
                raise IOError("memsrv 升级后握手失败")
            self.mode = 'srv'

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _read_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            c = self.sock.recv(n - len(buf))
            if not c:
                raise IOError("TCP 通道 EOF")
            buf += c
        return bytes(buf)

    def _read_line(self) -> bytes:
        buf = bytearray()
        while True:
            c = self.sock.recv(1)
            if not c:
                raise IOError("TCP 通道 EOF")
            buf += c
            if c == b"\n":
                return bytes(buf).rstrip(b"\r\n")

    # ---------- 批量读取 ----------

    def batch_read(self, requests: List[Tuple[int, int]]) -> List[Optional[bytes]]:
        """批量读取 [(addr, size), ...]; 返回与请求等长的数据列表 (短读/失败为 None)"""
        with self._lock:
            if not self.sock:
                self.open()
            try:
                if self.mode == 'srv':
                    return self._batch_srv(requests)
                return self._batch_sh(requests)
            except Exception:
                self.close()
                raise

    def _batch_srv(self, requests: List[Tuple[int, int]]) -> List[Optional[bytes]]:
        hdr = struct.pack('<Q', len(requests)) + b''.join(
            struct.pack('<QQ', a, s) for a, s in requests)
        self.sock.sendall(hdr)
        out: List[Optional[bytes]] = []
        for addr, size in requests:
            (got,) = struct.unpack('<q', self._read_exact(8))
            if got <= 0:
                out.append(None)   # got<0 为 -errno; got==0 为空读
                continue
            data = self._read_exact(got)
            out.append(data if got >= size else None)
        return out

    def _batch_sh(self, requests: List[Tuple[int, int]]) -> List[Optional[bytes]]:
        pid = self.mc.pid
        parts = []
        metas = []   # (addr, size, aligned_off, aligned_len)
        for i, (addr, size) in enumerate(requests):
            a0 = addr & ~0xFFF
            a1 = (addr + size + 0xFFF) & ~0xFFF
            cnt = (a1 - a0) // 4096
            parts.append(f"printf 'M{i}\\n'; dd if=/proc/{pid}/mem bs=4096 "
                         f"skip={a0 // 4096} count={cnt} 2>/dev/null; printf 'E{i}\\n'")
            metas.append((addr, size, addr - a0, cnt * 4096))
        parts.append("printf 'END\\n'")
        self.sock.sendall(("; ".join(parts) + "\n").encode())
        out: List[Optional[bytes]] = []
        for i, (addr, size, off, alen) in enumerate(metas):
            if self._read_line() != f"M{i}".encode():
                raise IOError(f"TCP 通道乱序: 期望 M{i}")
            raw = self._read_exact(alen)
            if self._read_line() != f"E{i}".encode():
                raise IOError(f"TCP 通道乱序: 期望 E{i} (dd 短读?)")
            out.append(raw[off:off + size] if len(raw) >= off + size else None)
        if self._read_line() != b"END":
            raise IOError("TCP 通道乱序: 末尾无 END")
        return out

    __del__ = close


class MemCore:
    """ADB 内存读取核心"""

    def __init__(self, adb_path: Optional[str] = None, package: str = DEFAULT_PKG):
        self.adb_path = adb_path or find_mumu_adb()
        if not self.adb_path:
            raise RuntimeError("找不到 adb.exe, 请用 --adb 指定")
        self.package = package
        self.pid: Optional[int] = None
        # maps
        self.regions: List[Tuple[int, int, str, str]] = []
        self._rw_starts: List[int] = []
        self._rw_ends: List[int] = []

    # ---------- adb ----------

    def adb(self, *args, timeout=30) -> bytes:
        return subprocess.run([self.adb_path] + list(args),
                              capture_output=True, timeout=timeout).stdout

    def shell(self, cmd: str, timeout=30) -> str:
        return self.adb("shell", cmd, timeout=timeout).decode('utf-8', errors='replace')

    def connect(self) -> int:
        """连接模拟器并定位游戏 PID"""
        out = self.adb("devices").decode('utf-8', errors='replace')
        if '\tdevice' not in out:
            for port in (16384, 16416, 7555):
                r = self.adb("connect", f"127.0.0.1:{port}", timeout=5).decode(errors='replace').lower()
                if "connected" in r or "already" in r:
                    break
        self.adb("root")
        time.sleep(1)
        pid_s = self.shell(f"pidof {self.package}").strip()
        if not pid_s:
            raise RuntimeError(f"找不到游戏进程: {self.package}")
        self.pid = int(pid_s.split()[0])
        self.reload_maps()
        return self.pid

    # ---------- 内存读取 ----------

    def read(self, addr: int, size: int, timeout=30) -> Optional[bytes]:
        """读取 addr 处 size 字节 (小块走 4KB 页对齐, 大块走 4MB 对齐)"""
        if size <= 0x10000:
            a0 = addr & ~0xFFF
            a1 = (addr + size + 0xFFF) & ~0xFFF
            data = self.adb("exec-out",
                            f"dd if=/proc/{self.pid}/mem bs=4096 skip={a0 // 4096} count={(a1 - a0) // 4096} 2>/dev/null",
                            timeout=timeout)
            off = addr - a0
            if len(data) < off + size:
                return None
            return data[off:off + size]
        a0 = addr & ~(BS - 1)
        a1 = (addr + size + BS - 1) & ~(BS - 1)
        data = self.adb("exec-out",
                        f"dd if=/proc/{self.pid}/mem bs={BS} skip={a0 // BS} count={(a1 - a0) // BS} 2>/dev/null",
                        timeout=timeout)
        off = addr - a0
        if len(data) < off + size:
            return None
        return data[off:off + size]

    def read_ptr(self, addr: int) -> Optional[int]:
        d = self.read(addr, 8)
        return struct.unpack('<Q', d)[0] if d else None

    def read_int32(self, addr: int) -> Optional[int]:
        d = self.read(addr, 4)
        return struct.unpack('<i', d)[0] if d else None

    def read_float(self, addr: int) -> Optional[float]:
        d = self.read(addr, 4)
        return struct.unpack('<f', d)[0] if d else None

    # ---------- maps / 指针校验 ----------

    def reload_maps(self):
        maps = self.shell(f"cat /proc/{self.pid}/maps", timeout=30)
        self.regions = []
        for line in maps.split('\n'):
            m = re.match(r'^([0-9a-f]+)-([0-9a-f]+)\s+(\S+)\s+\S+\s+\S+\s+\S+\s*(.*)$', line)
            if not m:
                continue
            self.regions.append((int(m.group(1), 16), int(m.group(2), 16),
                                 m.group(3), m.group(4).strip()))
        rw = sorted([(s, e) for s, e, p, n in self.regions if 'rw' in p])
        self._rw_starts = [s for s, e in rw]
        self._rw_ends = [e for s, e in rw]

    def is_ptr(self, v: int) -> bool:
        """值是否落在某个 rw 内存区域内"""
        if not v or v < 0x10000:
            return False
        i = bisect.bisect_right(self._rw_starts, v) - 1
        return i >= 0 and v < self._rw_ends[i]

    def scan_targets(self, min_addr: int = 0x10000000000) -> List[Tuple[int, int]]:
        """可扫描的匿名 rw 区域 (GC 堆), 排除 scudo/dalvik/jit/stack"""
        out = []
        for s, e, p, n in self.regions:
            if 'rw' not in p or e - s < 0x10000:
                continue
            if s < min_addr:
                continue
            if n and '[anon' not in n:
                continue
            if any(k in n for k in ('scudo', 'dalvik', 'jit', 'stack')):
                continue
            out.append((s, e))
        return out

    def iter_chunks(self, targets=None, cap=32 * 1024 * 1024):
        if targets is None:
            targets = self.scan_targets()
        for s, e in targets:
            a = s
            while a < e:
                yield a, min(a + cap, e)
                a += cap

    # ---------- 字符串 ----------

    def read_ustring(self, addr: int) -> Optional[str]:
        """读取 Il2CppString (UTF-16LE)"""
        d = self.read(addr, 0x80)
        if not d:
            return None
        ln = struct.unpack_from('<i', d, Il2CppString.LENGTH)[0]
        if ln <= 0 or ln > 128:
            return None
        if len(d) < Il2CppString.CHARS + ln * 2:
            d = self.read(addr, Il2CppString.CHARS + ln * 2)
            if not d:
                return None
        try:
            return d[Il2CppString.CHARS:Il2CppString.CHARS + ln * 2].decode('utf-16-le')
        except Exception:
            return None

    def read_cstring(self, addr: int, maxlen: int = 64) -> Optional[str]:
        """读取 C 字符串 (ASCII)"""
        d = self.read(addr, maxlen)
        if not d:
            return None
        end = d.find(b'\x00')
        if end <= 0:
            return None
        try:
            s = d[:end].decode('ascii')
        except Exception:
            return None
        return s if all(32 <= ord(c) < 127 for c in s) else None

    def read_klass_name(self, obj_addr: int) -> Optional[str]:
        """读取 IL2CPP 对象的类名 (obj -> klass -> +0x10 name char*)"""
        klass = self.read_ptr(obj_addr)
        if not klass or not self.is_ptr(klass):
            return None
        name_p = self.read_ptr(klass + 0x10)
        if not name_p or not self.is_ptr(name_p):
            return None
        return self.read_cstring(name_p)
