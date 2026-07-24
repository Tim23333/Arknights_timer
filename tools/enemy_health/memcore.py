"""
ADB 内存读取底层 (明日方舟 @ MuMu 模拟器)

- 通过 adb exec-out dd 读取 Android 进程 /proc/<pid>/mem
- 大块读取: 头/尾 4MB 不对齐部分走 4KB 页对齐, 中部走 4MB 块
  (dd 起点/终点落在区域外未映射洞会 EIO 整块丢失, 必须避开)
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


def _config_file() -> str:
    """adb 路径配置持久化位置: 打包模式放 exe 旁 (_MEIPASS 是临时目录,
    写进去重启即丢); 开发模式放模块目录"""
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'enemy_adb_config.json')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def save_adb_path(path: str) -> None:
    """持久化手动选择的 adb 路径 (下次启动直接生效)"""
    import json
    try:
        with open(_config_file(), 'w', encoding='utf-8') as f:
            json.dump({'adb_path': path}, f)
    except Exception:
        pass


def find_mumu_adb() -> Optional[str]:
    """查找 adb.exe: 配置缓存 -> PATH -> ANDROID_HOME -> 多盘符常见路径 -> 注册表"""
    import json
    import shutil
    try:
        cfg_file = _config_file()
        if os.path.isfile(cfg_file):
            with open(cfg_file, 'r', encoding='utf-8') as f:
                saved = json.load(f).get("adb_path")
            if saved and os.path.isfile(saved):
                return saved
    except Exception:
        pass
    p = shutil.which("adb")
    if p:
        return p
    # Android SDK platform-tools
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        home = os.environ.get(env)
        if home:
            q = os.path.join(home, "platform-tools", "adb.exe")
            if os.path.isfile(q):
                return q
    # 常见 MuMu 安装布局 x 各盘符
    patterns = [
        os.path.join("MuMu9", "emulator", "MuMuPlayer-12.0", "shell", "adb.exe"),
        os.path.join("Netease", "MuMuPlayer-12.0", "shell", "adb.exe"),
        os.path.join("MuMuPlayer-12.0", "shell", "adb.exe"),
        os.path.join("MuMu Player 12", "shell", "adb.exe"),
        os.path.join("MuMuPlayer", "shell", "adb.exe"),
        os.path.join("MuMu", "shell", "adb.exe"),
    ]
    for drive in "CDEFG":
        for base in (f"{drive}:\\Program Files", f"{drive}:\\Program Files (x86)",
                     f"{drive}:\\"):
            for pat in patterns:
                q = os.path.join(base, pat)
                if os.path.isfile(q):
                    return q
    try:
        import winreg
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for kp in (r"SOFTWARE\Netease\MuMuPlayer", r"SOFTWARE\Netease\MuMuPlayer-12.0",
                       r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MuMuPlayer-12.0",
                       r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\MuMuPlayer-12.0"):
                try:
                    key = winreg.OpenKey(root, kp)
                    install = None
                    for val in ("InstallDir", "InstallLocation", "DisplayIcon"):
                        try:
                            install = winreg.QueryValueEx(key, val)[0]
                            break
                        except Exception:
                            continue
                    if not install:
                        continue
                    install = install.strip('"')
                    if os.path.isfile(install):        # DisplayIcon 指向 exe
                        install = os.path.dirname(install)
                    adb = os.path.join(install, "shell", "adb.exe")
                    if os.path.isfile(adb):
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
    BANNER_V1 = b"AKMSRV1\n"   # 仅读取
    BANNER_V2 = b"AKMSRV2\n"   # 读取 + 设备侧扫描 (memsrv.c v2)
    BANNER = BANNER_V1          # 兼容旧引用
    SCAN_MAGIC = 0xFFFFFFFFFFFFFFFF

    def __init__(self, mc: 'MemCore', read_timeout: float = 5.0):
        self.mc = mc
        self.read_timeout = read_timeout
        self.sock: Optional[socket.socket] = None
        self.mode: Optional[str] = None   # 'srv' | 'sh'
        self.srv_version = 0              # 1=读取, 2=读取+扫描
        self._memsrv_restarted = False    # 本次 _push_memsrv 是否重推并杀了旧服务
        self._lock = threading.Lock()   # 同一时间只允许一个 batch_read

    # ---------- 服务部署 ----------

    def _push_memsrv(self) -> bool:
        """推送 memsrv 二进制 + 包装脚本到设备 (幂等; 大小不同视为版本变更重推)"""
        self._memsrv_restarted = False
        try:
            local = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'bin', 'memsrv')
            if not os.path.exists(local):
                return False
            local_size = os.path.getsize(local)
            out = self.mc.shell(f"stat -c %s {self.SRV_DIR}/memsrv 2>/dev/null").strip()
            if out != str(local_size):
                self.mc.adb('push', local, f'{self.SRV_DIR}/memsrv')
                self.mc.shell(f"chmod 755 {self.SRV_DIR}/memsrv")
                # 版本变更: 杀掉旧 nc 强制下次连接重建服务
                self.mc.shell("kill $(pidof nc) 2>/dev/null")
                self._memsrv_restarted = True
            # 包装脚本每次重写: 每次连接都用 pidof 动态解析 PID (游戏重启自愈)
            self.mc.shell(
                f"printf '#!/system/bin/sh\\nexec {self.SRV_DIR}/memsrv "
                f"$(pidof {self.mc.package})\\n' > {self.SRV_DIR}/memsrv.sh")
            self.mc.shell(f"chmod 755 {self.SRV_DIR}/memsrv.sh")
            return True
        except Exception:
            return False

    def _server_up(self) -> bool:
        """端口可连 (注意: nc 活着但服务程序 exec 失败的半死状态也返回 True)"""
        try:
            socket.create_connection(("127.0.0.1", self.PORT), timeout=2).close()
            return True
        except OSError:
            return False

    def _start_service(self):
        """启动设备侧 nc -L 服务 (memsrv 优先, 否则 sh; setsid 防 adb 会话退出时被杀)"""
        if self._push_memsrv():
            self.mc.shell(f"setsid nc -L -p {self.PORT} "
                          f"{self.SRV_DIR}/memsrv.sh </dev/null >/dev/null 2>&1 &")
        else:
            self.mc.shell(f"setsid nc -L -p {self.PORT} sh </dev/null >/dev/null 2>&1 &")
        time.sleep(0.5)

    def _ensure_server(self):
        """启动设备侧服务并建立 adb forward (幂等; 5555 是 adbd 占用, 避开)。
        每次连接都先查版本: 二进制变更时 _push_memsrv 会杀旧服务, 此处负责重启。"""
        self.mc.adb("forward", f"tcp:{self.PORT}", f"tcp:{self.PORT}")
        if not self._push_memsrv():
            # 无本地二进制: 只能依赖现有服务或 sh 兜底
            if self._server_up():
                return
            self._start_service()
            return
        if self._memsrv_restarted:
            time.sleep(0.3)           # 等旧 nc 退出
            self._start_service()
            return
        if self._server_up():
            return   # forward 已有, 服务已在
        self._start_service()

    # ---------- 连接 ----------

    def open(self):
        self.close()
        self._ensure_server()
        try:
            self._connect_once()
            return
        except (IOError, OSError):
            self.close()
        # 半死状态 (端口可连但协议不通, 如服务程序 exec 失败): 杀掉 nc 强制重启再试
        try:
            self.mc.shell("kill $(pidof nc) 2>/dev/null", timeout=10)
        except Exception:
            pass
        time.sleep(0.3)
        self._start_service()
        self._connect_once()   # 再失败自然抛出, 由调用方回退慢速 read()

    def _connect_once(self):
        self.sock = socket.create_connection(("127.0.0.1", self.PORT), timeout=10)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # 模式探测: memsrv 会主动发 8 字节横幅; sh 不会主动发任何字节
        self.sock.settimeout(1.0)
        try:
            b = self._read_exact(8)
        except (socket.timeout, OSError):
            b = b''
        self.sock.settimeout(self.read_timeout)
        if b == self.BANNER_V2:
            self.mode = 'srv'
            self.srv_version = 2
            return
        if b == self.BANNER_V1:
            self.mode = 'srv'
            self.srv_version = 1
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
            if b not in (self.BANNER_V1, self.BANNER_V2):
                self.close()
                raise IOError("memsrv 升级后握手失败")
            self.mode = 'srv'
            self.srv_version = 2 if b == self.BANNER_V2 else 1

    # ---------- 设备侧扫描 (srv v2) ----------

    def scan(self, addr: int, size: int, needles: List[bytes]) -> Optional[dict]:
        """设备侧模式扫描: 在 [addr, addr+size) 内搜索全部 needle,
        返回 {needle: [命中绝对地址...]}; 仅 srv v2 可用, 否则返回 None。
        命中地址数单针上限 65536 (memsrv MAX_HITS)。"""
        if self.mode != 'srv' or self.srv_version < 2:
            return None
        with self._lock:
            if not self.sock:
                self.open()
            if self.srv_version < 2:
                return None
            try:
                hdr = struct.pack('<Q', self.SCAN_MAGIC)
                hdr += struct.pack('<QQI', addr, size, len(needles))
                for nd in needles:
                    if not (0 < len(nd) <= 64):
                        raise ValueError("needle 长度须为 1..64")
                    hdr += struct.pack('<I', len(nd)) + nd
                self.sock.sendall(hdr)
                out = {}
                for nd in needles:
                    (cnt,) = struct.unpack('<q', self._read_exact(8))
                    if cnt < 0:
                        out[nd] = []
                        continue
                    data = self._read_exact(cnt * 8)
                    out[nd] = list(struct.unpack('<%dQ' % cnt, data))
                return out
            except Exception:
                self.close()
                raise

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
        # 注意: 此处不强制要求 adb 存在 — 延迟到真正使用时 (_require_adb) 报错,
        # 避免找不到 adb 时整个程序无法启动
        self.package = package
        self.pid: Optional[int] = None
        # maps
        self.regions: List[Tuple[int, int, str, str]] = []
        self._rw_starts: List[int] = []
        self._rw_ends: List[int] = []

    def _require_adb(self) -> str:
        """返回可用的 adb 路径, 找不到时重新探测一次再报错"""
        if not self.adb_path or not os.path.isfile(self.adb_path):
            self.adb_path = find_mumu_adb()
        if not self.adb_path:
            raise RuntimeError("找不到 adb.exe (MuMu 安装目录 shell\\adb.exe)")
        return self.adb_path

    # ---------- adb ----------

    # Windows 下主程序打包为无控制台 (windowed) 后, 每次调 adb.exe 都会
    # 弹出控制台窗口; CREATE_NO_WINDOW 抑制之
    _NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0

    def adb(self, *args, timeout=30) -> bytes:
        return subprocess.run([self._require_adb()] + list(args),
                              capture_output=True, timeout=timeout,
                              creationflags=self._NO_WINDOW).stdout

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
        """读取 addr 处 size 字节 (小块走 4KB 页对齐, 大块头尾 4KB + 中部 4MB)"""
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
        # 大块: dd 起点/终点若落在区域外的未映射洞会 EIO 整块丢失 (确定性!),
        # 因此头/尾 4MB 不对齐部分走 4KB 页对齐, 中部整 4MB 块保证全在区域内
        body0 = (addr + BS - 1) & ~(BS - 1)      # 第一个 4MB 边界
        body1 = (addr + size) & ~(BS - 1)        # 末端向下 4MB 边界
        if body0 >= body1:
            return self._read_pages(addr, size, timeout)
        out = bytearray()
        if addr < body0:
            d = self._read_pages(addr, body0 - addr, timeout)
            if d is None:
                return None
            out += d
        data = self.adb("exec-out",
                        f"dd if=/proc/{self.pid}/mem bs={BS} skip={body0 // BS} count={(body1 - body0) // BS} 2>/dev/null",
                        timeout=timeout)
        if len(data) < body1 - body0:
            return None
        out += data[:body1 - body0]
        if body1 < addr + size:
            d = self._read_pages(body1, addr + size - body1, timeout)
            if d is None:
                return None
            out += d
        return bytes(out)

    def _read_pages(self, addr: int, size: int, timeout=30) -> Optional[bytes]:
        """4KB 页对齐精确读取 (addr/size 须 4KB 对齐, 调用方保证在映射区域内)"""
        data = self.adb("exec-out",
                        f"dd if=/proc/{self.pid}/mem bs=4096 skip={addr // 4096} count={size // 4096} 2>/dev/null",
                        timeout=timeout)
        return data if len(data) >= size else None

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
