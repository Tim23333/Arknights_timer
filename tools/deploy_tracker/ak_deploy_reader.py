import json
import os
import struct
from pathlib import Path

import pymem
import pymem.exception
import pymem.memory
import pymem.process


CACHE_FILE = Path(__file__).resolve().parent / "offset_cache.json"

DIRECTION_NAMES = {0: "DOWN", 1: "LEFT", 2: "UP", 3: "RIGHT", 4: "NONE"}
OP_NAMES = {0: "SPAWN", 1: "WITHDRAW", 2: "SKILL", 3: "CHEAT"}

LOGITEM_SIZE = 0x30  # 48 bytes
LOGITEM_STRUCT = "<f4xI4xQiiiiQ"

# Il2Cpp class metadata offsets (from il2cpp.h)
IL2CPP_CLASS_1_SIZE = 0xB8
IL2CPP_C_STATIC_FIELDS = 0xB8   # _c.static_fields offset
IL2CPP_CLASS_PARENT = 0x58      # Il2CppClass_1.parent offset
IL2CPP_CLASS_NAME = 0x10        # Il2CppClass_1.name offset (char*)

SCAN_CHUNK = 0x40000  # 256KB


class DeployTrackerReader:
    """读取 Arknights 战斗中干员部署时间轴。"""

    def __init__(self, pm: pymem.Pymem, play_time_addr: int):
        self._pm = pm
        self._play_time_addr = play_time_addr
        self._bc_addr = None
        self._logger_addr = None
        self._logs_list_addr = None
        self._status_callback = None

    def set_status_callback(self, cb):
        """设置状态回调 cb(msg: str)，用于 UI 更新进度。"""
        self._status_callback = cb

    def _status(self, msg):
        if self._status_callback:
            self._status_callback(msg)

    def discover(self) -> bool:
        """发现并验证 BattleController 实例。成功返回 True。"""
        self._bc_addr = self._discover_battle_controller(self._play_time_addr)
        if self._bc_addr is None:
            return False
        return self._refresh_chain()

    def _refresh_chain(self) -> bool:
        """刷新指针链。成功返回 True。"""
        try:
            self._logger_addr = self._pm.read_longlong(self._bc_addr + 0x100)
            if self._logger_addr == 0:
                return False
            self._logs_list_addr = self._pm.read_longlong(self._logger_addr + 0x20)
            if self._logs_list_addr == 0:
                return False
            return True
        except pymem.exception.MemoryReadError:
            return False

    # ---- 发现 BattleController 实例（Il2Cpp 类元数据链） ----

    def _discover_battle_controller(self, play_time_addr):
        # 策略 A：缓存偏移（直接存 s_instance 静态存储地址的偏移）
        cached_offset = self._load_cached_offset()
        if cached_offset is not None:
            sm_static_addr = play_time_addr + cached_offset
            try:
                ptr = self._pm.read_longlong(sm_static_addr)
                if self._validate_battle_controller_ptr(ptr):
                    self._status("缓存偏移命中")
                    return ptr
            except pymem.exception.MemoryReadError:
                pass
            self._status("缓存偏移失效，通过类元数据定位...")

        # 策略 B：通过 Il2Cpp 类元数据链定位
        return self._locate_via_class_metadata(play_time_addr)

    def _locate_via_class_metadata(self, play_time_addr):
        """通过 GameAssembly.dll 中的类元数据追踪 s_instance。"""
        # 1. 算 BattleController 静态数据基址
        bc_static_base = play_time_addr - 0x28

        # 2. 获取 GameAssembly.dll 范围
        try:
            mod = pymem.process.module_from_name(self._pm.process_handle, "GameAssembly.dll")
        except pymem.exception.ProcessError:
            self._status("错误：无法获取 GameAssembly.dll")
            return None

        dll_base = mod.lpBaseOfDll
        dll_end = dll_base + mod.SizeOfImage

        self._status(f"DLL: {dll_base:#x} - {dll_end:#x} ({mod.SizeOfImage // 1048576}MB)")

        # 3. 在 DLL 数据段中搜索指向 bc_static_base 的指针
        needle = struct.pack("<Q", bc_static_base)

        pos = dll_base
        while pos < dll_end:
            chunk_size = min(SCAN_CHUNK, dll_end - pos)
            try:
                data = self._pm.read_bytes(pos, chunk_size)
            except pymem.exception.MemoryReadError:
                pos += chunk_size
                continue

            # 搜索所有匹配位置
            start = 0
            while True:
                idx = data.find(needle, start)
                if idx == -1:
                    break
                match_addr = pos + idx

                # 尝试将此位置解释为 _c.static_fields（往前 0xB8 到 _c 基址）
                bc_c_addr = match_addr - IL2CPP_C_STATIC_FIELDS

                sm_static = self._resolve_parent_static_fields(bc_c_addr)
                if sm_static is not None:
                    ptr = self._pm.read_longlong(sm_static)  # s_instance
                    if self._validate_battle_controller_ptr(ptr):
                        offset = sm_static - play_time_addr
                        self._save_cached_offset(offset)
                        self._status(f"找到，偏移 {offset}")
                        return ptr

                start = idx + 8

            del data
            pos += chunk_size

        self._status("在 DLL 数据段中未找到")
        return None

    def _resolve_parent_static_fields(self, class_c_addr):
        """验证 class_c_addr 是有效的 _c 结构体，沿 parent → static_fields 读取。

        返回 SingletonMonoBehaviour_StaticFields 地址（可直接读 s_instance），
        或 None（验证失败）。
        """
        try:
            # 检查 _c 地址在已提交内存中
            mbi = pymem.memory.virtual_query(self._pm.process_handle, class_c_addr)
            if mbi.State != 0x1000:
                return None

            # 读 parent（偏移 0x58 在 Il2CppClass_1 中）
            parent = self._pm.read_longlong(class_c_addr + IL2CPP_CLASS_PARENT)
            if parent == 0:
                return None
            mbi2 = pymem.memory.virtual_query(self._pm.process_handle, parent)
            if mbi2.State != 0x1000:
                return None

            # 快速校验：读 parent 的 name 指针
            name_ptr = self._pm.read_longlong(parent + IL2CPP_CLASS_NAME)
            if name_ptr == 0:
                return None

            # 读 parent.static_fields
            parent_sf = self._pm.read_longlong(parent + IL2CPP_C_STATIC_FIELDS)
            if parent_sf == 0:
                return None
            mbi3 = pymem.memory.virtual_query(self._pm.process_handle, parent_sf)
            if mbi3.State != 0x1000:
                return None

            # parent_sf[0] = s_instance（8 字节）
            s_instance = self._pm.read_longlong(parent_sf)
            if s_instance == 0 or s_instance < 0x10000:
                return None

            return parent_sf
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            return None

    def _validate_battle_controller_ptr(self, ptr):
        """验证 ptr 是否指向有效的 BattleController 对象。"""
        if ptr is None or ptr == 0 or ptr < 0x10000:
            return False
        try:
            mbi = pymem.memory.virtual_query(self._pm.process_handle, ptr)
            if mbi.State != 0x1000:
                return False
            logger = self._pm.read_longlong(ptr + 0x100)
            if logger == 0:
                return False
            mbi2 = pymem.memory.virtual_query(self._pm.process_handle, logger)
            if mbi2.State != 0x1000:
                return False
            logs_list = self._pm.read_longlong(logger + 0x20)
            if logs_list == 0:
                return False
            mbi3 = pymem.memory.virtual_query(self._pm.process_handle, logs_list)
            if mbi3.State != 0x1000:
                return False
            size = self._pm.read_int(logs_list + 0x18)
            if 0 <= size <= 100000:
                return True
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            pass
        return False

    # ---- 偏移缓存 ----

    def _load_cached_offset(self):
        if not CACHE_FILE.exists():
            return None
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if data.get("process_id") == self._pm.process_id:
                return data.get("offset")
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _save_cached_offset(self, offset):
        try:
            CACHE_FILE.write_text(
                json.dumps(
                    {"process_id": self._pm.process_id, "offset": offset},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    # ---- 读取部署事件 ----

    def get_events(self):
        """返回所有操作事件列表。调用前确保发现成功。"""
        if not self._logs_list_addr or not self._refresh_chain():
            return []

        try:
            items_ptr = self._pm.read_longlong(self._logs_list_addr + 0x10)
            size = self._pm.read_int(self._logs_list_addr + 0x18)
            max_len = self._pm.read_longlong(items_ptr + 0x18)
            count = min(size, max_len)
        except pymem.exception.MemoryReadError:
            return []

        count = max(0, min(count, 50000))

        events = []
        try:
            raw = self._pm.read_bytes(items_ptr + 0x20, count * LOGITEM_SIZE)
        except pymem.exception.MemoryReadError:
            return events

        for i in range(count):
            try:
                vals = struct.unpack_from(LOGITEM_STRUCT, raw, i * LOGITEM_SIZE)
                ts, unique_id, char_ptr, op, direction, grid_row, grid_col, extra_ptr = vals

                char_id = self._read_string(char_ptr) if char_ptr else ""
                extra = self._read_string(extra_ptr) if extra_ptr else ""
            except (struct.error, UnicodeDecodeError):
                continue

            events.append(
                {
                    "timestamp": round(ts, 6),
                    "uniqueId": unique_id,
                    "charId": char_id,
                    "op": op,
                    "opName": OP_NAMES.get(op, f"UNKNOWN({op})"),
                    "direction": direction,
                    "directionName": DIRECTION_NAMES.get(direction, str(direction)),
                    "gridRow": grid_row,
                    "gridCol": grid_col,
                    "extraInfo": extra,
                }
            )

        return events

    def get_spawn_events(self):
        """返回仅 SPAWN（部署）事件。"""
        return [e for e in self.get_events() if e["op"] == 0]

    def is_battle_active(self) -> bool:
        """检查是否在战斗中。"""
        try:
            logger = self._pm.read_longlong(self._bc_addr + 0x100)
            return logger != 0
        except pymem.exception.MemoryReadError:
            return False

    # ---- 字符串读取 ----

    def _read_string(self, ptr):
        if ptr == 0:
            return ""
        try:
            length = self._pm.read_int(ptr + 0x10)
            if length <= 0 or length > 4096:
                return ""
            raw = self._pm.read_bytes(ptr + 0x14, length * 2)
            return raw.decode("utf-16-le", errors="replace")
        except (pymem.exception.MemoryReadError, UnicodeDecodeError):
            return ""
