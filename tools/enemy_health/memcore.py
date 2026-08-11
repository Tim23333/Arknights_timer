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
import glob
from typing import Optional, List, Tuple

try:
    from .game_structs import Il2CppString
except ImportError:  # 允许作为独立脚本直接运行
    from game_structs import Il2CppString

DEFAULT_PKG = "com.hypergryph.arknights"
KNOWN_GAME_PACKAGES = (
    DEFAULT_PKG,
    'com.hypergryph.arknights.bilibili',
    'com.YoStarEN.Arknights',
    'com.YoStarJP.Arknights',
    'com.YoStarKR.Arknights',
    'tw.txwy.and.arknights',
)
# MuMu 12 预设端口表: 16384 起步步进 32 覆盖实例 0-6 (与 MAA 兜底表一致);
# 7555 为旧版 MuMu6 残留端口
KNOWN_MUMU_SERIALS = tuple(
    [f'127.0.0.1:{16384 + 32 * i}' for i in range(7)] + ['127.0.0.1:7555'])
BS = 4 * 1024 * 1024  # dd 块大小


def _config_file() -> str:
    """adb 路径配置持久化位置: 打包模式放 exe 旁 (_MEIPASS 是临时目录,
    写进去重启即丢); 开发模式放模块目录"""
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'enemy_adb_config.json')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def load_adb_config() -> dict:
    import json
    try:
        with open(_config_file(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_adb_config(path: str, serial: str = '') -> bool:
    """持久化 ADB 程序和目标设备；列表参数调用无需手工转义路径。"""
    import json
    try:
        with open(_config_file(), 'w', encoding='utf-8') as f:
            json.dump({'adb_path': path, 'adb_serial': serial}, f,
                      ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def save_adb_path(path: str) -> bool:
    """兼容旧调用：更新路径，同时保留已经选择的设备地址。"""
    return save_adb_config(path, load_adb_config().get('adb_serial', ''))


def query_adb_devices(adb_path: str, connect_known: bool = False,
                      connect_serial: str = '') -> list:
    """查询指定 ADB server 的设备，并可主动连接填写地址或 MuMu 常见本地端口。"""
    if not adb_path or not os.path.isfile(adb_path):
        return []
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0

    def run(*args, timeout=8):
        try:
            return subprocess.run(
                [adb_path, *args], capture_output=True, timeout=timeout,
                creationflags=flags)
        except (OSError, subprocess.TimeoutExpired):
            return None

    targets = []
    if connect_serial and ':' in connect_serial:
        targets.append(connect_serial)
    if connect_known:
        targets.extend(KNOWN_MUMU_SERIALS)
    for serial in dict.fromkeys(targets):
        if serial:
            run('connect', serial, timeout=3)
    result = run('devices', '-l')
    if result is None:
        return []
    rows = []
    text = result.stdout.decode('utf-8', errors='replace')
    for line in text.replace('\r', '').split('\n')[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        if state not in ('device', 'offline', 'unauthorized'):
            continue
        rows.append({
            'serial': serial,
            'state': state,
            'description': ' '.join(parts[2:]),
        })
    return rows


def find_mumu_adb() -> Optional[str]:
    """查找 adb.exe: 配置缓存 -> 运行中模拟器 -> PATH -> ANDROID_HOME -> 多盘符常见路径 -> 注册表"""
    import shutil
    saved = load_adb_config().get('adb_path')
    if saved and os.path.isfile(saved):
        return saved
    # 优先使用正在运行的模拟器自带的 adb (参考 MAA 探测链: 新版 MuMu 的 adb
    # 在 nx_main/ 下, 且只有它自己的 adb server 会自报 127.0.0.1:16384 之类
    # 的设备地址; PATH/SDK 里的其它 adb 可能认不出模拟器设备)
    running = find_running_emulator_adbs()
    if running:
        return running[0]['adb_path']
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
        os.path.join("MuMu Player 12", "nx_main", "adb.exe"),
        os.path.join("MuMuPlayer-12.0", "nx_main", "adb.exe"),
        os.path.join("MuMu Player 12", "vmonitor", "bin", "adb_server.exe"),
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
                    for sub in (os.path.join("nx_main", "adb.exe"),
                                os.path.join("shell", "adb.exe")):
                        adb = os.path.join(install, sub)
                        if os.path.isfile(adb):
                            return adb
                except Exception:
                    pass
    except Exception:
        pass
    return None


_EMULATOR_PROCESS_HINTS = (
    'mumu', 'nemu', 'mumunx', 'dnplayer', 'ldplayer', 'ldvboxheadless',
    'nox', 'memu', 'bluestacks', 'hd-player', 'hd-agent',
)
_EMULATOR_ADB_RELATIVE_PATHS = (
    # 新版 MuMu 12 首选: adb 已移至 nx_main (MAA 探测链第一候选)
    os.path.join('nx_main', 'adb.exe'),
    # 新版 MuMu 12 备选: vmonitor 自带的 adb_server
    os.path.join('vmonitor', 'bin', 'adb_server.exe'),
    'adb.exe',
    os.path.join('shell', 'adb.exe'),
    os.path.join('nx_device', '12.0', 'shell', 'adb.exe'),
    os.path.join('emulator', 'MuMuPlayer-12.0', 'shell', 'adb.exe'),
    os.path.join('MuMuPlayer-12.0', 'shell', 'adb.exe'),
    os.path.join('platform-tools', 'adb.exe'),
    'nox_adb.exe',
    'HD-Adb.exe',
)


def _running_process_paths():
    """返回 (进程名, 可执行文件路径)；权限不足的单个进程直接跳过。"""
    try:
        import psutil
    except ImportError:
        return []
    result = []
    for proc in psutil.process_iter(('name', 'exe')):
        try:
            name = proc.info.get('name') or ''
            exe = proc.info.get('exe') or ''
            if name and exe:
                result.append((name, exe))
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            continue
    return result


def find_running_emulator_adbs(processes=None):
    """从正在运行的模拟器进程路径反推安装目录中的 ADB 候选。

    返回 [{'adb_path', 'process_name', 'process_path'}]。processes 参数供离线
    测试注入，格式同样为 (name, executable_path)。这里只做浅层固定路径匹配，
    不递归扫描整块磁盘。
    """
    processes = _running_process_paths() if processes is None else list(processes)
    found = []
    seen = set()
    for process_name, process_path in processes:
        process_name = str(process_name or '')
        process_path = os.path.normpath(str(process_path or ''))
        fingerprint = f'{process_name} {process_path}'.lower()
        if not process_path or not any(hint in fingerprint for hint in _EMULATOR_PROCESS_HINTS):
            continue

        roots = []
        root = os.path.dirname(process_path)
        for _ in range(5):
            if not root or root in roots or os.path.dirname(root) == root:
                break
            roots.append(root)
            root = os.path.dirname(root)

        candidates = []
        for base in roots:
            candidates.extend(os.path.join(base, rel)
                              for rel in _EMULATOR_ADB_RELATIVE_PATHS)
            candidates.extend(glob.glob(os.path.join(base, '*', 'shell', 'adb.exe')))
            candidates.extend(glob.glob(os.path.join(base, '*', '*', 'shell', 'adb.exe')))
        for candidate in candidates:
            candidate = os.path.normpath(candidate)
            key = os.path.normcase(os.path.abspath(candidate))
            if key in seen or not os.path.isfile(candidate):
                continue
            seen.add(key)
            found.append({
                'adb_path': candidate,
                'process_name': process_name,
                'process_path': process_path,
            })
    return found


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

    PORT = 27271   # 默认端口; 多通道共存时 (如敌人监控 27271 + RNG 27272) 用 port 参数隔离
    SRV_DIR = '/data/local/tmp'
    BANNER_V1 = b"AKMSRV1\n"   # 仅读取
    BANNER_V2 = b"AKMSRV2\n"   # 读取 + 设备侧扫描 (memsrv.c v2)
    BANNER = BANNER_V1          # 兼容旧引用
    SCAN_MAGIC = 0xFFFFFFFFFFFFFFFF

    def __init__(self, mc: 'MemCore', read_timeout: float = 5.0, port: int = None):
        self.mc = mc
        self.read_timeout = read_timeout
        self.port = port or self.PORT
        self.sock: Optional[socket.socket] = None
        self.mode: Optional[str] = None   # 'srv' | 'sh'
        self.srv_version = 0              # 1=读取, 2=读取+扫描
        self._memsrv_restarted = False    # 本次 _push_memsrv 是否重推并杀了旧服务
        self._lock = threading.Lock()   # 同一时间只允许一个 batch_read
        self._stats_lock = threading.Lock()
        self._frame_stats = self._new_frame_stats()

    @staticmethod
    def _new_frame_stats() -> dict:
        return {
            'batches': 0,
            'requests': 0,
            'requested_bytes': 0,
            'returned_bytes': 0,
            'io_ms': 0.0,
            'max_batch_ms': 0.0,
        }

    def reset_frame_stats(self) -> None:
        """开始一个逻辑采样帧的 I/O 统计。

        高频主通道只有 EnemyPollWorker 使用；详情页使用独立端口，因此这里
        不会把详情读取混进主帧指标。
        """
        with self._stats_lock:
            self._frame_stats = self._new_frame_stats()

    def frame_stats(self) -> dict:
        with self._stats_lock:
            return dict(self._frame_stats)

    def _record_batch_stats(self, requests, results, elapsed_ms: float) -> None:
        requested = sum(max(0, int(size)) for _addr, size in requests)
        returned = sum(len(data) for data in (results or ()) if data)
        with self._stats_lock:
            stats = self._frame_stats
            stats['batches'] += 1
            stats['requests'] += len(requests)
            stats['requested_bytes'] += requested
            stats['returned_bytes'] += returned
            stats['io_ms'] += elapsed_ms
            stats['max_batch_ms'] = max(stats['max_batch_ms'], elapsed_ms)

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
            socket.create_connection(("127.0.0.1", self.port), timeout=2).close()
            return True
        except OSError:
            return False

    def _start_service(self):
        """启动设备侧 nc -L 服务 (memsrv 优先, 否则 sh; setsid 防 adb 会话退出时被杀)"""
        if self._push_memsrv():
            self.mc.shell(f"setsid nc -L -p {self.port} "
                          f"{self.SRV_DIR}/memsrv.sh </dev/null >/dev/null 2>&1 &")
        else:
            self.mc.shell(f"setsid nc -L -p {self.port} sh </dev/null >/dev/null 2>&1 &")
        time.sleep(0.5)

    def _kill_own_nc(self):
        """只杀本端口的 nc -L 进程 (其他端口的共存服务不受影响)"""
        self.mc.shell(
            f"for p in $(pidof nc); do "
            f"tr '\\0' ' ' </proc/$p/cmdline 2>/dev/null | "
            f"grep -q -- '-p {self.port}' && kill $p 2>/dev/null; done",
            timeout=10)

    def _ensure_server(self):
        """启动设备侧服务并建立 adb forward (幂等; 5555 是 adbd 占用, 避开)。
        每次连接都先查版本: 二进制变更时 _push_memsrv 会杀旧服务, 此处负责重启。"""
        self.mc.adb("forward", f"tcp:{self.port}", f"tcp:{self.port}")
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
        # 半死状态 (端口可连但协议不通, 如服务程序 exec 失败): 杀掉本端口 nc 强制重启再试
        try:
            self._kill_own_nc()
        except Exception:
            pass
        time.sleep(0.3)
        self._start_service()
        self._connect_once()   # 再失败自然抛出, 由调用方回退慢速 read()

    def _connect_once(self):
        self.sock = socket.create_connection(("127.0.0.1", self.port), timeout=10)
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
            self._kill_own_nc()
            time.sleep(0.3)
            self.mc.shell(f"setsid nc -L -p {self.port} "
                          f"{self.SRV_DIR}/memsrv.sh </dev/null >/dev/null 2>&1 &")
            time.sleep(0.5)
            self.sock = socket.create_connection(("127.0.0.1", self.port), timeout=10)
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
        started = time.perf_counter()
        results = None
        with self._lock:
            if not self.sock:
                self.open()
            try:
                if self.mode == 'srv':
                    results = self._batch_srv(requests)
                else:
                    results = self._batch_sh(requests)
            except Exception:
                self.close()
                raise
        self._record_batch_stats(
            requests, results, (time.perf_counter() - started) * 1000.0)
        return results

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

    def __init__(self, adb_path: Optional[str] = None, package: str = DEFAULT_PKG,
                 adb_serial: Optional[str] = None):
        config = load_adb_config()
        self.adb_path = adb_path or find_mumu_adb()
        self.adb_serial = adb_serial if adb_serial is not None \
            else str(config.get('adb_serial') or '')
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

    def _adb_result(self, *args, timeout=30, use_target=True):
        command = [self._require_adb()]
        if use_target and self.adb_serial:
            command += ['-s', self.adb_serial]
        command += list(args)
        return subprocess.run(command, capture_output=True, timeout=timeout,
                              creationflags=self._NO_WINDOW)

    def adb(self, *args, timeout=30) -> bytes:
        return self._adb_result(*args, timeout=timeout, use_target=True).stdout

    def adb_host(self, *args, timeout=30) -> bytes:
        """执行 devices/connect 等 ADB server 命令，不绑定具体设备。"""
        return self._adb_result(*args, timeout=timeout, use_target=False).stdout

    def shell(self, cmd: str, timeout=30) -> str:
        return self.adb("shell", cmd, timeout=timeout).decode('utf-8', errors='replace')

    def _device_rows(self, connect_known=False):
        return query_adb_devices(
            self._require_adb(), connect_known=connect_known,
            connect_serial=self.adb_serial)

    def _pid_for_known_package(self):
        packages = []
        for package in (self.package, *KNOWN_GAME_PACKAGES):
            if package and package not in packages:
                packages.append(package)
        for package in packages:
            pid_s = self.shell(f'pidof {package}', timeout=8).strip()
            if pid_s:
                return package, int(pid_s.split()[0])
        return '', 0

    def _select_device(self) -> None:
        rows = self._device_rows(connect_known=True)
        states = {row['serial']: row['state'] for row in rows}
        if self.adb_serial:
            if states.get(self.adb_serial) != 'device':
                # TCP 设备可能尚未注册到当前 adb server，按用户填写地址连接一次。
                if ':' in self.adb_serial:
                    self.adb_host('connect', self.adb_serial, timeout=5)
                    rows = self._device_rows(connect_known=False)
                    states = {row['serial']: row['state'] for row in rows}
            if states.get(self.adb_serial) != 'device':
                visible = ', '.join(f"{s}({st})" for s, st in states.items()) or '无'
                raise RuntimeError(
                    f'ADB 目标 {self.adb_serial} 不在线；当前设备: {visible}')
            return

        online = [row['serial'] for row in rows if row['state'] == 'device']
        if not online:
            raise RuntimeError(
                'ADB 未发现在线模拟器；请在“选择 ADB”中选择与 MAA 相同的连接地址')
        if len(online) == 1:
            self.adb_serial = online[0]
            return

        # 多设备时先寻找真正运行明日方舟的目标，避免 adb shell 报 more than one device。
        original = self.adb_serial
        matches = []
        for serial in online:
            self.adb_serial = serial
            package, pid = self._pid_for_known_package()
            if pid:
                matches.append((serial, package))
        self.adb_serial = original
        if len(matches) == 1:
            self.adb_serial, self.package = matches[0]
            return
        visible = ', '.join(online)
        raise RuntimeError(
            f'ADB 同时存在多个在线设备: {visible}；请在“选择 ADB”中指定连接地址')

    def _ensure_root(self) -> None:
        result = self._adb_result('root', timeout=10)
        message = (result.stdout + result.stderr).decode('utf-8', errors='replace').strip()
        uid = ''
        # adb root 会重启 adbd；MuMu 忙时一秒内未必重新上线，短轮询避免误报无 root。
        for attempt in range(8):
            if attempt:
                time.sleep(0.5)
            if ':' in self.adb_serial:
                try:
                    self.adb_host('connect', self.adb_serial, timeout=4)
                except Exception:
                    pass
            try:
                uid = self.shell('id -u', timeout=5).strip()
            except Exception:
                uid = ''
            if uid == '0':
                return
            # adbd 没有发生重启时无需无意义等待。
            if attempt == 0 and 'restarting adbd as root' not in message.lower():
                break
        extra = f'（adb root: {message}）' if message else ''
        raise RuntimeError(
            'ADB 可以连接/截图，但当前 adbd 没有 root 权限，无法读取游戏进程内存。'
            '截图只需要普通 ADB 权限；请在 MuMu 设置中开启 Root 权限并重启模拟器。' + extra)

    def connect(self) -> int:
        """绑定指定模拟器、确认 root，并自动定位不同渠道服的游戏 PID。"""
        self._select_device()
        self._ensure_root()
        package, pid = self._pid_for_known_package()
        if not pid:
            tried = ', '.join(dict.fromkeys((self.package, *KNOWN_GAME_PACKAGES)))
            raise RuntimeError(
                f'ADB 设备 {self.adb_serial} 已连接且具备 root，但找不到游戏进程。'
                f'已尝试包名: {tried}')
        self.package = package
        self.pid = pid
        self.reload_maps()
        if not self.regions:
            raise RuntimeError(
                f'已找到游戏进程 {self.package} (PID {pid})，但无法读取 /proc/{pid}/maps。'
                '请确认 MuMu Root 权限已经开启并在开启后重启过模拟器。')
        # maps 可读不等于 /proc/<pid>/mem 可读；在正式全盘扫描前给出明确诊断。
        readable = False
        for start, end, perms, _name in self.regions[:32]:
            if 'r' not in perms or end - start < 0x1000:
                continue
            if self.read(start, 1, timeout=8) is not None:
                readable = True
                break
        if not readable:
            raise RuntimeError(
                f'ADB 和游戏进程均已找到，但 /proc/{pid}/mem 无法读取。'
                'MAA 截图正常不代表具备进程内存权限；请开启 MuMu Root 权限并重启模拟器。')
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
