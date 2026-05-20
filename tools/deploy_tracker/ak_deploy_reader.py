import concurrent.futures
import os
import struct

import pymem
import pymem.exception
import pymem.memory


DIRECTION_NAMES = {0: "UP", 1: "RIGHT", 2: "DOWN", 3: "LEFT", 4: "NONE"}
OP_NAMES = {0: "SPAWN", 1: "WITHDRAW", 2: "SKILL", 3: "CHEAT"}

LOGITEM_SIZE = 0x30
LOGITEM_STRUCT = "<f4xI4xQiiiiQ"


def _scan_chunk_for_op_dir(handle, base, size, needle):
    """返回 [op, direction] 模式匹配的所有地址 (op 字段位置)。"""
    try:
        data = pymem.memory.read_bytes(handle, base, size)
    except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
        return set()

    results = set()
    offset = 0
    while True:
        idx = data.find(needle, offset)
        if idx == -1:
            break
        results.add(base + idx)
        offset = idx + 8
    return results


class DeployTrackerReader:
    def __init__(self, pm: pymem.Pymem):
        self._pm = pm
        self._bc_addr = None
        self._logger_addr = None
        self._logs_list_addr = None
        self._status_callback = None

        # 增量扫描状态
        self._stable: set[int] = set()
        self._round: int = 0
        self._scan_direction: int = 0

    def set_status_callback(self, cb):
        self._status_callback = cb

    def _status(self, msg):
        print(f"[INFO] {msg}")
        if self._status_callback:
            self._status_callback(msg)

    # ---- 增量多步扫描 ----

    def start_scan(self, direction: int) -> int:
        """第一步：部署第一个干员后扫描，返回匹配数量。"""
        self._scan_direction = direction
        self._stable = self._do_scan()  # S1
        self._round = 1
        self._status(f"第 1 次扫描: {len(self._stable)} 个匹配")
        return len(self._stable)

    def scan_again(self) -> str:
        """再次部署后扫描，交集+相邻过滤。

        Returns:
            "found"  — 找到 BattleController
            "more"   — 需要再部署
            "failed" — 失败
        """
        self._round += 1
        handle = self._pm.process_handle
        needle = struct.pack("<ii", 0, self._scan_direction)

        if self._round <= 2:
            # 前两步：全盘扫描
            fresh = self._do_scan()
        else:
            # 第3步起：快速增量扫描
            # ① 验证稳定地址中哪些仍然匹配
            verified = set()
            for addr in self._stable:
                try:
                    val = pymem.memory.read_bytes(handle, addr, 8)
                    if val == needle:
                        verified.add(addr)
                except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
                    pass

            # ② 扫描稳定地址所在的内存页，找新出现的
            PAGE_SIZE = 0x1000
            PAGE_MASK = ~(PAGE_SIZE - 1)
            fresh = set(verified)
            scanned_pages = set()

            for addr in self._stable:
                page = addr & PAGE_MASK
                if page in scanned_pages:
                    continue
                scanned_pages.add(page)
                try:
                    data = pymem.memory.read_bytes(handle, page, PAGE_SIZE)
                except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
                    continue
                offset = 0
                while True:
                    idx = data.find(needle, offset)
                    if idx == -1:
                        break
                    fresh.add(page + idx)
                    offset = idx + 8

            self._status(f"快速扫描: {len(scanned_pages)} 页, 命中 {len(fresh)}")

        # 1. 取交集
        common = self._stable & fresh
        self._status(f"交集: {len(common)} (剔除 {len(self._stable) - len(common)})")

        # 2. 收缩
        self._stable = common

        # 3. 新出现
        new_only = fresh - common
        self._status(f"新出现: {len(new_only)}")

        if not new_only:
            self._status("无新出现地址")
            return "failed"

        # 4. 相邻过滤 + 深度验证
        # 快速相邻检查
        adjacent = []
        for addr in new_only:
            neighbor = addr - LOGITEM_SIZE
            if neighbor in common:
                adjacent.append((neighbor, addr))

        self._status(f"相邻候选: {len(adjacent)}")

        # 深度验证：读 LogItem 结构，验证 uniqueId 连续、timestamp 递增
        candidates = set()
        for prev_op, cur_op in adjacent:
            if self._validate_logitem_pair(prev_op - 0x18, cur_op - 0x18):
                candidates.add(cur_op)

        self._status(f"深度过滤后: {len(candidates)}")

        if not candidates:
            self._status("无相邻候选")
            return "failed"

        if len(candidates) == 1:
            addr = next(iter(candidates))
            logitem_base = addr - 0x18
            self._status(f"锁定 @ {hex(logitem_base)}")
            bc = self._trace_logitem_to_battle_controller(logitem_base)
            if bc is not None:
                self._bc_addr = bc
                self._refresh_chain()
                return "found"
            self._status("逆向追踪失败")
            return "failed"

        self._stable = candidates
        self._status(f"剩余 {len(candidates)} 个候选, 请再部署一次")
        return "more"

    def _do_scan(self) -> set[int]:
        """全盘扫描 [op=SPAWN, dir=self._scan_direction]。"""
        needle = struct.pack("<ii", 0, self._scan_direction)
        direction_name = DIRECTION_NAMES.get(self._scan_direction, str(self._scan_direction))
        self._status(f"扫描 [SPAWN + {direction_name}] ...")

        regions = self._collect_readable_regions()
        total = len(regions)
        handle = self._pm.process_handle
        all_hits = set()

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 4) * 2)) as executor:
            futures = [
                executor.submit(_scan_chunk_for_op_dir, handle, base, size, needle)
                for base, size in regions
            ]
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                res = future.result()
                if res:
                    all_hits.update(res)
                if (i + 1) % 20 == 0:
                    self._status(f"  扫描... {int((i + 1) / total * 100)}%")

        return all_hits

    def _validate_logitem_pair(self, li1: int, li2: int) -> bool:
        """验证两个 LogItem 是否为真实的连续部署记录。

        Args:
            li1, li2: LogItem 基址 (li2 应在 li1 + 0x30)
        Returns:
            True 如果 timestamp 递增、uniqueId 连续、charId 指针有效
        """
        handle = self._pm.process_handle
        try:
            # 读取两个 LogItem 的头部 (timestamp + uniqueId + padding + charId 指针)
            # 0x00~0x17: 24 bytes
            raw1 = pymem.memory.read_bytes(handle, li1, 24)
            raw2 = pymem.memory.read_bytes(handle, li2, 24)

            ts1, uid1, charid1 = struct.unpack_from("<f4xI4xQ", raw1, 0)
            ts2, uid2, charid2 = struct.unpack_from("<f4xI4xQ", raw2, 0)

            # 时间戳有效且递增
            if not (0.0 <= ts1 <= 100000.0 and 0.0 <= ts2 <= 100000.0):
                return False
            if not (ts2 > ts1):
                return False

            # uniqueId 必须连续 (配对: 前一个的 uid = N, 后一个 = N+1)
            if not (uid2 == uid1 + 1):
                return False

            # charId 指针必须有效
            if charid1 < 0x10000 or charid2 < 0x10000:
                return False

            return True
        except (struct.error, pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            return False

    # ---- 内存区域枚举 ----

    def _collect_readable_regions(self):
        regions = []
        curr = 0
        handle = self._pm.process_handle
        while True:
            try:
                mbi = pymem.memory.virtual_query(handle, curr)
                curr += mbi.RegionSize
                if mbi.State == 0x1000 and (mbi.Protect & 0x66) and mbi.RegionSize >= 1024:
                    regions.append((mbi.BaseAddress, mbi.RegionSize))
            except Exception:
                break
        if regions:
            regions.sort(key=lambda r: r[0])
            merged = []
            buf_base, buf_size = regions[0]
            for base, size in regions[1:]:
                if base == buf_base + buf_size:
                    buf_size += size
                else:
                    merged.append((buf_base, buf_size))
                    buf_base, buf_size = base, size
            merged.append((buf_base, buf_size))
            regions = merged
        return regions

    # ---- 指针链追踪 ----

    def _refresh_chain(self) -> bool:
        try:
            self._logger_addr = self._pm.read_longlong(self._bc_addr + 0x100)
            if self._logger_addr == 0:
                return False
            self._logs_list_addr = self._pm.read_longlong(self._logger_addr + 0x20)
            if self._logs_list_addr == 0:
                return False
            return True
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            return False

    def _trace_logitem_to_battle_controller(self, logitem_addr: int):
        handle = self._pm.process_handle

        # 1. 确定数组基址
        array_base = None
        for N in range(256):
            candidate_arr = logitem_addr - 0x20 - N * LOGITEM_SIZE
            try:
                length = self._pm.read_longlong(candidate_arr + 0x18)
                if N < length < 50000:
                    if (logitem_addr - candidate_arr - 0x20) % LOGITEM_SIZE == 0:
                        array_base = candidate_arr
                        break
            except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
                continue
        if array_base is None:
            return None

        # 2. 搜索 List._items 指针
        logs_list_addr = None
        for region_base, region_size in self._collect_readable_regions():
            try:
                region_data = pymem.memory.read_bytes(handle, region_base, region_size)
            except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
                continue
            offset = 0
            needle = struct.pack("<Q", array_base)
            while True:
                idx = region_data.find(needle, offset)
                if idx == -1:
                    break
                list_candidate = region_base + idx - 0x10
                try:
                    mbi = pymem.memory.virtual_query(handle, list_candidate)
                    if mbi.State != 0x1000:
                        offset = idx + 8
                        continue
                    _size = self._pm.read_int(list_candidate + 0x18)
                    _version = self._pm.read_int(list_candidate + 0x1C)
                    if 0 <= _size <= length and _version >= 0:
                        logs_list_addr = list_candidate
                        break
                except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
                    pass
                offset = idx + 8
            if logs_list_addr is not None:
                break
        if logs_list_addr is None:
            return None

        # 3. BattleLogger → BattleController
        battle_logger = logs_list_addr - 0x20
        try:
            battle_controller = self._pm.read_longlong(battle_logger + 0x18)
            if battle_controller == 0 or battle_controller < 0x10000:
                return None
            verify_logger = self._pm.read_longlong(battle_controller + 0x100)
            if verify_logger != battle_logger:
                return None
            return battle_controller
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            return None

    # ---- 读取部署事件 ----

    def get_events(self):
        if not self._logs_list_addr or not self._refresh_chain():
            return []
        try:
            items_ptr = self._pm.read_longlong(self._logs_list_addr + 0x10)
            size = self._pm.read_int(self._logs_list_addr + 0x18)
            max_len = self._pm.read_longlong(items_ptr + 0x18)
            count = min(size, max_len)
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            return []
        count = max(0, min(count, 50000))

        events = []
        try:
            raw = self._pm.read_bytes(items_ptr + 0x20, count * LOGITEM_SIZE)
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            return events

        for i in range(count):
            try:
                vals = struct.unpack_from(LOGITEM_STRUCT, raw, i * LOGITEM_SIZE)
                ts, unique_id, char_ptr, op, direction, grid_row, grid_col, extra_ptr = vals
                char_id = self._read_string(char_ptr) if char_ptr else ""
                extra = self._read_string(extra_ptr) if extra_ptr else ""
            except (struct.error, UnicodeDecodeError):
                continue
            events.append({
                "timestamp": round(ts, 6), "uniqueId": unique_id, "charId": char_id,
                "op": op, "opName": OP_NAMES.get(op, f"UNKNOWN({op})"),
                "direction": direction,
                "directionName": DIRECTION_NAMES.get(direction, str(direction)),
                "gridRow": grid_row, "gridCol": grid_col, "extraInfo": extra,
            })
        return events

    def get_spawn_events(self):
        return [e for e in self.get_events() if e["op"] == 0]

    def is_battle_active(self) -> bool:
        try:
            logger = self._pm.read_longlong(self._bc_addr + 0x100)
            return logger != 0
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError):
            return False

    def _read_string(self, ptr):
        if ptr == 0:
            return ""
        try:
            length = self._pm.read_int(ptr + 0x10)
            if length <= 0 or length > 4096:
                return ""
            raw = self._pm.read_bytes(ptr + 0x14, length * 2)
            return raw.decode("utf-16-le", errors="replace")
        except (pymem.exception.MemoryReadError, pymem.exception.WinAPIError, UnicodeDecodeError):
            return ""
