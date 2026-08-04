"""模拟器进程发现：已知名单精确匹配 + 名称/路径特征兜底，供寻址工具定位
持有游戏内存的虚拟机容器进程。

背景：MuMu 模拟器12 5.0 (2026) 起设备进程改为 MuMuNxDevice.exe
(nx_device 目录)，旧版为 MuMuVMMHeadless.exe (MuMuVMMVbox/Hypervisor)。
名单之外的未来新进程靠 (模拟器家族特征 + 容器特征) 双条件兜底识别；
仍识别不到时由 UI 让用户手动选择进程。
"""
import ctypes
import ctypes.wintypes as wt

# 已知模拟器「虚拟机容器」进程名 (游戏内存所在进程)，按优先级排列，
# 即自动附加的尝试顺序
EMULATOR_PROCESS_NAMES = (
    'MuMuVMMHeadless.exe',   # MuMu 12 旧版 (VirtualBox 内核)
    'MuMuNxDevice.exe',      # MuMu 12 5.0+ 新版设备进程
    'NemuHeadless.exe',      # 旧版 MuMu (nemu 内核)
    'Ld9BoxHeadless.exe',    # 雷电 9
    'LdBoxHeadless.exe',     # 雷电
    'dnplayer.exe',          # 雷电 (旧)
    'NoxVMMHeadless.exe',    # 夜神
    'HD-Player.exe',         # 蓝叠
    'MEmuHeadless.exe',      # 逍遥
)

# 家族特征：出现在进程名或安装路径中即认为属于某模拟器
EMULATOR_FAMILY_HINTS = (
    'mumu', 'nemu', 'ldplayer', 'ldvbox', 'dnplayer', 'nox',
    'memu', 'bluestacks', 'hd-player',
)
# 容器特征：进程名含其中之一才可能是「持有游戏内存的虚拟机进程」，
# 避免把 MuMuPlayer.exe 之类的界面进程误判为扫描目标
EMULATOR_CONTAINER_HINTS = ('vmm', 'headless', 'nxdevice', 'boxheadless')
# 名称含这些片段的一定不是游戏内存所在进程 (服务/更新/管理工具)
_PROCESS_NAME_EXCLUDES = ('svc', 'service', 'updater', 'manager')


def _list_processes_psutil():
    """用 psutil 枚举 [(名称, pid, 路径)]；psutil 不可用时返回 None。"""
    try:
        import psutil
    except ImportError:
        return None
    result = []
    for proc in psutil.process_iter(('name', 'exe')):
        try:
            name = proc.info.get('name') or ''
            if name:
                result.append((name, proc.pid, proc.info.get('exe') or ''))
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            continue
    return result


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ('dwSize', wt.DWORD),
        ('cntUsage', wt.DWORD),
        ('th32ProcessID', wt.DWORD),
        ('th32DefaultHeapID', ctypes.c_size_t),
        ('th32ModuleID', wt.DWORD),
        ('cntThreads', wt.DWORD),
        ('th32ParentProcessID', wt.DWORD),
        ('pcPriClassBase', ctypes.c_long),
        ('dwFlags', wt.DWORD),
        ('szExeFile', wt.WCHAR * wt.MAX_PATH),
    ]


def _list_processes_toolhelp():
    """无 psutil 时的兜底：Win32 Toolhelp32 枚举 (只有 名称/pid，路径留空)。"""
    if not hasattr(ctypes, 'windll'):
        return []
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    invalid = wt.HANDLE(-1).value
    if not snapshot or snapshot == invalid:
        return []
    try:
        result = []
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            result.append((entry.szExeFile, entry.th32ProcessID, ''))
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        return result
    finally:
        kernel32.CloseHandle(snapshot)


def list_processes():
    """枚举当前进程，返回 [(名称, pid, 路径)]；psutil 缺失时退化为 Toolhelp32。"""
    result = _list_processes_psutil()
    if result is not None:
        return result
    return _list_processes_toolhelp()


def find_emulator_processes(processes=None):
    """从进程列表中找出模拟器虚拟机容器进程，返回 [(名称, pid, 路径)]。

    顺序即尝试附加的顺序：已知名单按优先级先行，之后是 (家族特征 + 容器
    特征) 匹配到的名单外进程。界面/服务类进程 (MuMuPlayer.exe、
    MuMuVMMSVC.exe 等) 不会持有游戏内存，一律排除。processes 参数供离线
    测试注入，格式同为 (名称, pid, 路径)。
    """
    processes = list_processes() if processes is None else list(processes)
    found, seen = [], set()

    def _add(name, pid, path):
        key = (name or '').lower()
        if key and key not in seen:
            seen.add(key)
            found.append((name, pid, path))

    by_name = {}
    for name, pid, path in processes:
        by_name.setdefault((name or '').lower(), (name, pid, path))
    for wanted in EMULATOR_PROCESS_NAMES:
        hit = by_name.get(wanted.lower())
        if hit:
            _add(*hit)

    for name, pid, path in processes:
        key = (name or '').lower()
        if not key or key in seen:
            continue
        if any(ex in key for ex in _PROCESS_NAME_EXCLUDES):
            continue
        haystack = f'{name} {path}'.lower()
        if any(h in haystack for h in EMULATOR_FAMILY_HINTS) and \
                any(h in key for h in EMULATOR_CONTAINER_HINTS):
            _add(name, pid, path)
    return found
