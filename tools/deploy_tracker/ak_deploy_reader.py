"""明日方舟 代理作战序列 / 实时操作日志 内存读取器

内存通道: tools/enemy_health/memcore.py (adb + memsrv v4 读 Android 进程
/proc/<pid>/mem)。游戏指针是 Android 进程虚拟地址, 必须在设备侧读取,
宿主机直接读模拟器进程内存无法解引用指针 (旧 pymem 方案不可行的根因)。

数据来源 (基于 Ark_data/dump.cs 2.7.x 逆向分析):

  BattleLogger.LogItem (0x30 字节, dump.cs:329958)
    +0x00 float  timestamp          战斗时间(秒)
    +0x08 Signiture                 { uint uniqueId@0x0, string charId@0x8 }
    +0x18 int    op                 PlayerOperationType: 0=SPAWN 1=WITHDRAW 2=SKILL 3=CHEAT
    +0x1C int    direction          SharedConsts.Direction: 0=UP 1=RIGHT 2=DOWN 3=LEFT 4=NONE
    +0x20 int    pos.row / +0x24 int pos.col
    +0x28 string extraInfo

  BattleLogger (dump.cs:330259)            —— 手动/代理战斗的实时操作记录
    +0x18 BattleController m_controller
    +0x20 List<LogItem>  m_logs
    +0x28 List<CharInfo> m_squad

  BattleController.ReplayController (dump.cs:316953) —— 代理作战(回放)的完整序列
    +0x18 Journal m_journal (inline 结构)
          +0x00 Metadata { float standardPlayTime, int gameResult, DateTime saveTime@0x8,
                           int remainingCost@0x10, int remainingLifePoint@0x14,
                           int killedEnemiesCnt@0x18, int missedEnemiesCnt@0x1C,
                           string levelId@0x20, string stageId@0x28, ... }
          +0x38 List<CharInfo> squad   (=> ReplayController + 0x50)
          +0x40 List<LogItem>  logs    (=> ReplayController + 0x58)

  BattleLogger.CharInfo (0x50 字节, dump.cs:329934)
    +0x00 int charInstId (= LogItem.uniqueId)
    +0x08 string skinId / +0x10 string tmplId / +0x18 string skillId
    +0x20 int skillIndex / +0x24 skillLvl / +0x28 level / +0x2C phase / +0x30 potentialRank

  BattleController 现网实测标量偏移 (tools/enemy_health/game_structs.py, 2026-07 验证):
    +0x220 int State (0=NONE 1=INITED 2=PLAYING 3=FINISHED)
    +0x228 int SpeedLevel / +0x284 float realPlayTime

定位策略 (全自动, 支持进入关卡后 0 条操作记录):
  1. 设备侧共享扫描 BattleInOut / BattleController，两类对象只扫一遍大内存
  2. 先从 BattleInOut.input.stageInfo 发布关卡信息，再读取操作链
  3. 优先读取现网实测 BattleController.m_logger, 并以
     BattleLogger.m_controller 反向指针、List<LogItem> 结构完成强校验
  4. 若当前版本字段漂移, 在 BC 小范围字段区内搜索 BattleLogger
5. 类扫描未定位到对象时，才使用 memsrv v4 完整 GC 堆快照算法

后端嵌入:
  reader.set_stage_callback(on_stage)  # 阶段 1 完成即回调 dict
  ok = reader.locate()                 # 随后完成阶段 2；ok 表示操作链可用
  state = reader.get_state()           # stage + battle + squad + events
"""

import bisect
import concurrent.futures
import json
import mmap
import os
import re
import struct
import tempfile
import threading
import time

try:
    import numpy as _np
except ImportError:  # 可选加速
    _np = None

from tools.enemy_health.game_structs import BattleControllerFields
from tools.enemy_health.memcore import MemCore, TcpChannel


DIRECTION_NAMES = {0: "UP", 1: "RIGHT", 2: "DOWN", 3: "LEFT", 4: "NONE"}
OP_NAMES = {0: "SPAWN", 1: "WITHDRAW", 2: "SKILL", 3: "CHEAT"}
BATTLE_STATE_NAMES = {0: "NONE", 1: "INITED", 2: "PLAYING", 3: "FINISHED"}

LOGITEM_SIZE = 0x30
LOGITEM_STRUCT = "<f4xI4xQiiiiQ"
CHARINFO_SIZE = 0x50
CHAR_ID_RE = re.compile(r"^(char|trap|token)_\w+$")
STAGE_ID_RE = re.compile(r"^[A-Za-z0-9_\-#]+$")
LEVEL_ID_RE = re.compile(r"^[A-Za-z0-9_./\-#]+$")

# BattleController 现网实测偏移 (enemy_health 2026-07 验证)。统一引用
# game_structs，避免 deploy_tracker 与 enemy_health 各自维护后再次漂移。
BC_LOGGER = BattleControllerFields.M_LOGGER
BC_LEVEL_DATA = BattleControllerFields.LEVEL_DATA
BC_STATE = BattleControllerFields.M_STATE
BC_SPEED_LEVEL = BattleControllerFields.M_SPEED_LEVEL
BC_REAL_PLAY_TIME = BattleControllerFields.M_REAL_PLAY_TIME
UNITY_CACHED_PTR = 0x10

# BattleLogger 字段 (当前 dump 与现网一致)
LOGGER_CONTROLLER = 0x18
LOGGER_LOGS = 0x20
LOGGER_SQUAD = 0x28

# BattleInOut.input (inline InParams @ +0x10) / BattleStageInfo 布局。
# 与操作日志相互独立，因此刚进关卡、日志列表仍为空时也能读取。
BATTLE_IN_OUT_INPUT = 0x10
IN_PARAMS_LEVEL_DATA = 0x08
IN_PARAMS_STAGE_INFO = 0x18
IN_PARAMS_IS_PRACTICE = 0x88
IN_PARAMS_IS_AUTO_BATTLE = 0x89
IN_PARAMS_IS_FAST_BATTLE = 0x8A
STAGE_INFO_STAGE_ID = 0x00
STAGE_INFO_CODE = 0x08
STAGE_INFO_NAME = 0x10
STAGE_INFO_LEVEL_ID = 0x18
STAGE_INFO_ZONE_ID = 0x20
STAGE_INFO_CAN_BATTLE_REPLAY = 0x28
STAGE_INFO_DIFFICULTY = 0x2C
STAGE_INFO_AP_COST = 0x30

# LevelData.levelId；仅用于确认 BattleInOut 属于当前 BattleController，
# 以及在 BattleInOut 不可用时提供不含 stageId/name 的降级结果。
LEVEL_DATA_LEVEL_ID = 0x18

# IL2CPP 布局
LIST_ITEMS = 0x10
LIST_SIZE = 0x18
ARRAY_MAX_LENGTH = 0x18
ARRAY_ITEMS = 0x20
STR_LENGTH = 0x10
STR_CHARS = 0x14

SCAN_CAP = 32 * 1024 * 1024   # 单次读取上限 32MB
SCAN_WORKERS = 4              # adb 并发 (4 路即饱和)
DEVICE_SCAN_CAP = 256 * 1024 * 1024


# ============================================================
# 堆快照 (扫描期一次性传输落盘, 支持随机访问)
# ============================================================
class _HeapSnap:
    """GC 堆快照: write() 追加区域, read() 按 guest VA 随机访问。"""

    def __init__(self):
        fd, self.path = tempfile.mkstemp(prefix="ak_deploy_heap_", suffix=".bin")
        self.fd = fd
        self.size = 0
        self.ranges = []          # (base, file_off, size)
        self._sorted = []         # 排序后的 ranges
        self._starts = []
        self._mmap = None
        self._lock = threading.Lock()

    def write(self, base: int, data: bytes):
        with self._lock:
            off = self.size
            view = memoryview(data)
            while view:
                n = os.write(self.fd, view)
                view = view[n:]
            self.size += len(data)
            self.ranges.append((base, off, len(data)))

    def finish(self):
        self._sorted = sorted(self.ranges)
        self._starts = [b for b, _, _ in self._sorted]
        self._mmap = mmap.mmap(self.fd, 0, access=mmap.ACCESS_READ)

    def read(self, addr: int, size: int):
        """随机读取 (完全落在某个区域内才返回, 否则 None)"""
        i = bisect.bisect_right(self._starts, addr) - 1
        if i < 0:
            return None
        base, off, rsize = self._sorted[i]
        if addr < base or addr + size > base + rsize:
            return None
        p = off + (addr - base)
        return self._mmap[p:p + size]

    def read_u64(self, addr: int):
        d = self.read(addr, 8)
        return struct.unpack("<Q", d)[0] if d else None

    def read_ustring(self, addr: int):
        """就地解引用 il2cpp 字符串 (UTF-16LE)"""
        d = self.read(addr, 0x60)
        if not d:
            return None
        ln = struct.unpack_from("<i", d, STR_LENGTH)[0]
        if ln <= 0 or ln > 64:
            return None
        if len(d) < STR_CHARS + ln * 2:
            d = self.read(addr, STR_CHARS + ln * 2)
            if not d:
                return None
        try:
            s = d[STR_CHARS:STR_CHARS + ln * 2].decode("utf-16-le")
        except UnicodeDecodeError:
            return None
        return s if s.isprintable() else None

    def iter_chunks(self):
        with open(self.path, "rb", buffering=1024 * 1024) as f:
            for base, off, size in self._sorted:
                f.seek(off)
                yield base, f.read(size)

    def discard(self):
        try:
            if self._mmap is not None:
                self._mmap.close()
        except Exception:
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        try:
            os.remove(self.path)
        except OSError:
            pass


def _numeric_filter_chunk(base, data):
    """LogItem 数值预过滤 (8 字节对齐): op/direction/grid/timestamp/uniqueId/指针范围。"""
    hits = []
    if _np is not None:
        a = _np.frombuffer(data, dtype="<u4")
        n = a.size
        if n < 12:
            return []
        f = a.view("<f4")
        j = _np.arange(0, n - 11, 2)
        m = a[j + 6] <= 3                        # op
        m &= a[j + 7] <= 4                       # direction
        m &= a[j + 2] >= 1                       # uniqueId (全局计数器, 可能很大, 不设上限)
        row = a[j + 8].view("<i4")
        col = a[j + 9].view("<i4")
        m &= (row >= 0) & (row <= 31) & (col >= 0) & (col <= 31)
        ts = f[j]
        m &= (ts > 0.0) & (ts < 100000.0)
        m &= a[j + 5] >= 0x100                   # charId 指针高 32 位 (>=1TB 用户态)
        m &= a[j + 5] < 0x10000
        m &= (a[j + 11] == 0) | ((a[j + 11] >= 0x100) & (a[j + 11] < 0x10000))  # extraInfo
        hits = [base + int(j[k]) * 4 for k in _np.nonzero(m)[0]]
    else:
        for off in range(0, len(data) - LOGITEM_SIZE, 8):
            if data[off + 0x19] or data[off + 0x1A] or data[off + 0x1B]:
                continue
            if data[off + 0x18] > 3:
                continue
            if data[off + 0x1D] or data[off + 0x1E] or data[off + 0x1F]:
                continue
            if data[off + 0x1C] > 4:
                continue
            ts, uid, cptr, _op, _d, r, c, ext = struct.unpack_from(LOGITEM_STRUCT, data, off)
            if uid < 1:
                continue
            if not (0.0 < ts < 100000.0):
                continue
            if not (0 <= r <= 31 and 0 <= c <= 31):
                continue
            if not (0x10000000000 <= cptr < 0x1000000000000):
                continue
            if ext != 0 and not (0x10000000000 <= ext < 0x1000000000000):
                continue
            hits.append(base + off)
    return hits


class DeployTrackerReader:
    def __init__(self, mc: MemCore):
        self.mc = mc
        self._bc_addr = 0
        self._logger_addr = 0
        self._logs_list_addr = 0
        self._replay_addr = 0
        self._journal_logs_list_addr = 0
        self._squad_list_addr = 0        # BattleLogger.m_squad
        self._journal_squad_list_addr = 0
        self._journal_meta = {}
        self._battle_in_out_addr = 0
        self._stage_info = {}
        self._status_callback = None
        self._stage_callback = None
        self._char_names = None          # charId -> 中文名 (ark_parser/characters.json)
        self._channel = None             # TcpChannel 快速批量读取
        self._class_scan_failure_reason = ""
        self._last_logger_reject_reason = ""

    # ---------------- 基础 ----------------

    def set_status_callback(self, cb):
        self._status_callback = cb

    def set_stage_callback(self, cb):
        """设置关卡信息回调；阶段 1 定位成功后、操作链扫描前立即调用。"""
        self._stage_callback = cb

    def close(self):
        """关闭本读取器独占的 memsrv TCP 通道；供后端停止/替换实例时调用。"""
        channel, self._channel = self._channel, None
        if channel is not None:
            try:
                channel.close()
            except Exception:
                pass

    def _status(self, msg):
        print(f"[INFO] {msg}", flush=True)
        if self._status_callback:
            self._status_callback(msg)

    def _publish_stage_info(self, info):
        """保存关卡信息并通知嵌入方；相同结果不重复回调。"""
        info = dict(info or {})
        if not info or info == self._stage_info:
            return
        self._stage_info = info
        if self._stage_callback:
            self._stage_callback(dict(info))

    def _read(self, addr, size):
        return self.mc.read(addr, size)

    def _ptr(self, addr):
        d = self._read(addr, 8)
        return struct.unpack("<Q", d)[0] if d else 0

    def _i32(self, addr):
        d = self._read(addr, 4)
        return struct.unpack("<i", d)[0] if d else 0

    def _read_string(self, ptr):
        if not self.mc.is_ptr(ptr):
            return ""
        try:
            return self.mc.read_ustring(ptr) or ""
        except Exception:
            return ""

    def _klass_name(self, obj):
        if not self.mc.is_ptr(obj):
            return None
        try:
            return self.mc.read_klass_name(obj)
        except Exception:
            return None

    def _get_channel(self):
        """返回部署追踪器独占的 memsrv v4 批量读取通道。
        端口 27273: 与敌人监控 (27271) / RNG (27272) 通道共存时互不干扰。"""
        if self._channel is None:
            ch = TcpChannel(self.mc, read_timeout=30.0, port=27273)
            ch.open()
            if ch.srv_version != 4:
                ch.close()
                raise RuntimeError("部署追踪仅支持 memsrv v4")
            self._channel = ch
        return self._channel

    def _read_many(self, requests):
        """通过 memsrv v4 批量读取 [(addr, size)]；通道异常直接上抛。"""
        ch = self._get_channel()
        return ch.batch_read(requests)

    def _klass_names_batch(self, objs):
        """批量解析一组对象的 klass 名 {addr: name} (TCP 通道三轮批量读)。"""
        objs = [o for o in objs if self.mc.is_ptr(o)]
        if not objs:
            return {}
        klasses = {}
        for o, d in zip(objs, self._read_many([(o, 8) for o in objs])):
            if d:
                k = struct.unpack("<Q", d)[0]
                if self.mc.is_ptr(k):
                    klasses[o] = k
        name_ptrs = {}
        items = list(klasses.items())
        for o, d in zip([o for o, _ in items],
                        self._read_many([(k + 0x10, 8) for _, k in items])):
            if d:
                np_ = struct.unpack("<Q", d)[0]
                if self.mc.is_ptr(np_):
                    name_ptrs[o] = np_
        out = {}
        items = list(name_ptrs.items())
        for o, d in zip([o for o, _ in items],
                        self._read_many([(p, 48) for _, p in items])):
            if not d:
                continue
            end = d.find(b"\x00")
            if end > 0:
                try:
                    s = d[:end].decode("ascii")
                    if all(32 <= ord(c) < 127 for c in s):
                        out[o] = s
                except UnicodeDecodeError:
                    pass
        return out

    def _read_cstring(self, addr, max_len=128):
        if not self.mc.is_ptr(addr):
            return ""
        d = self._read(addr, max_len)
        if not d:
            return ""
        end = d.find(b"\x00")
        if end < 0:
            return ""
        try:
            return d[:end].decode("ascii")
        except UnicodeDecodeError:
            return ""

    def _device_scan_regions(self, regions, needles):
        """使用 memsrv v4 在设备侧扫描，只回传命中地址。"""
        ch = self._get_channel()
        needles = list(dict.fromkeys(needles))
        out = {nd: [] for nd in needles}
        for start, end in regions:
            addr = start
            while addr < end:
                size = min(DEVICE_SCAN_CAP, end - addr)
                found = ch.scan(addr, size, needles)
                for nd in needles:
                    out[nd].extend(found.get(nd) or [])
                addr += size
        return out

    def _scan_class_objects(self, class_names):
        """一次设备侧扫描返回多个 Torappu.Battle 类的对象地址。

        多个类共用三遍大范围扫描（类名、Il2CppClass 引用、对象 klass 指针），
        既让关卡信息先产出，又避免随后定位操作记录时重新扫描数 GB 内存。
        """
        rw_regions = [(s, e) for s, e, perms, _name in self.mc.regions if "rw" in perms]
        if not rw_regions:
            self._class_scan_failure_reason = (
                "读取到的进程内存映射中没有任何 rw 区域，无法搜索 IL2CPP 类名")
            self._status("  主路径失败: " + self._class_scan_failure_reason)
            return None
        t0 = time.time()
        class_names = tuple(dict.fromkeys(class_names))
        class_needles = {name: name.encode("ascii") + b"\x00" for name in class_names}
        self._status("共享扫描: 设备侧搜索 " + " / ".join(class_names) + " klass ...")
        name_scan = self._device_scan_regions(rw_regions, list(class_needles.values()))
        if name_scan is None:
            self._class_scan_failure_reason = "设备侧类名扫描没有返回结果"
            self._status("  主路径失败: " + self._class_scan_failure_reason)
            return None

        names_by_addr = {}
        for name, needle in class_needles.items():
            for addr in name_scan.get(needle, []):
                prev = self._read(addr - 1, 1)
                if not prev or prev == b"\x00":
                    names_by_addr[addr] = name
        name_counts = {
            name: sum(1 for value in names_by_addr.values() if value == name)
            for name in class_names
        }
        self._status("  类名命中 " + ", ".join(
            f"{name}={name_counts[name]}" for name in class_names))
        if not names_by_addr:
            self._class_scan_failure_reason = (
                "所有 rw 区域均未找到 BattleInOut/BattleController 类名字符串；"
                "可能未进入游戏进程、IL2CPP 元数据布局变化或扫描区域不完整")
            self._status("  主路径失败: " + self._class_scan_failure_reason)
            return {name: set() for name in class_names}

        name_needles = {addr: struct.pack("<Q", addr) for addr in names_by_addr}
        ref_scan = self._device_scan_regions(rw_regions, list(name_needles.values()))
        if ref_scan is None:
            self._class_scan_failure_reason = "设备侧 Il2CppClass.name 引用扫描没有返回结果"
            self._status("  主路径失败: " + self._class_scan_failure_reason)
            return None
        klass_names = {}
        for addr, needle in name_needles.items():
            for ref in ref_scan.get(needle, []):
                klass = ref - 0x10  # Il2CppClass.name
                if self._ptr(klass + 0x10) != addr:
                    continue
                namespace = self._read_cstring(self._ptr(klass + 0x18))
                if namespace == "Torappu.Battle":
                    klass_names[klass] = names_by_addr[addr]
        klass_counts = {
            name: sum(1 for value in klass_names.values() if value == name)
            for name in class_names
        }
        self._status("  Torappu.Battle Il2CppClass 命中 " + ", ".join(
            f"{name}={klass_counts[name]}" for name in class_names))
        if not klass_names:
            found_names = ", ".join(sorted(set(names_by_addr.values())))
            self._class_scan_failure_reason = (
                f"已找到类名字符串 ({found_names})，但没有解析出 namespace="
                "Torappu.Battle 的 Il2CppClass；Il2CppClass.name/namespace 偏移可能已漂移")
            self._status("  主路径失败: " + self._class_scan_failure_reason)
            return {name: set() for name in class_names}
        if "BattleController" in class_names and not klass_counts.get("BattleController"):
            self._class_scan_failure_reason = (
                f"类名扫描命中 BattleController={name_counts.get('BattleController', 0)}，"
                "但没有解析出 Torappu.Battle.BattleController 的 Il2CppClass；"
                "Il2CppClass.name/namespace 偏移可能已漂移")

        gc_regions = self.mc.scan_targets()
        klass_needles = {klass: struct.pack("<Q", klass) for klass in klass_names}
        obj_scan = self._device_scan_regions(gc_regions, list(klass_needles.values()))
        if obj_scan is None:
            self._class_scan_failure_reason = "设备侧对象 klass 指针扫描没有返回结果"
            self._status("  主路径失败: " + self._class_scan_failure_reason)
            return None
        objects = {name: set() for name in class_names}
        for klass, needle in klass_needles.items():
            for obj in obj_scan.get(needle, []):
                if not (obj & 7):
                    objects[klass_names[klass]].add(obj)
        counts = ", ".join(f"{name}={len(objects[name])}" for name in class_names)
        self._status(f"  klass {len(klass_names)} 个, 对象命中 {counts} "
                     f"({time.time() - t0:.1f}s)")
        return objects

    def _battle_controller_candidates(self, objects):
        """用战斗标量指纹过滤 klass 指针命中的 BattleController 对象。"""
        candidates = set()
        for obj in objects:
            d = self._read(obj, BC_REAL_PLAY_TIME + 4)
            if not d:
                continue
            state = struct.unpack_from("<i", d, BC_STATE)[0]
            speed = struct.unpack_from("<i", d, BC_SPEED_LEVEL)[0]
            play_time = struct.unpack_from("<f", d, BC_REAL_PLAY_TIME)[0]
            if (state in (1, 2, 3) and 0 <= speed <= 8
                    and 0.0 <= play_time < 100000.0):
                candidates.add(obj)
        return candidates

    def _rank_live_battle_controllers(self, candidates):
        state_rank = {2: 0, 1: 1, 3: 2}
        ranked = []
        for bc in set(candidates):
            cached_ptr = self._ptr(bc + UNITY_CACHED_PTR)
            if not self.mc.is_ptr(cached_ptr):
                continue
            state = self._i32(bc + BC_STATE)
            ranked.append((state_rank.get(state, 9), bc))
        ranked.sort()
        return [bc for _rank, bc in ranked]

    def _level_data_id(self, level_data):
        if not self.mc.is_ptr(level_data) or self._klass_name(level_data) != "LevelData":
            return ""
        level_id = self._read_string(self._ptr(level_data + LEVEL_DATA_LEVEL_ID))
        return level_id if level_id and LEVEL_ID_RE.match(level_id) else ""

    def _read_stage_info_candidate(self, battle_in_out):
        """解析一个 BattleInOut.input.stageInfo，并用其 LevelData 交叉校验。"""
        base = battle_in_out + BATTLE_IN_OUT_INPUT
        raw = self._read(base, IN_PARAMS_IS_FAST_BATTLE + 1)
        if not raw:
            return None
        try:
            level_data = struct.unpack_from("<Q", raw, IN_PARAMS_LEVEL_DATA)[0]
            string_ptrs = [
                struct.unpack_from("<Q", raw, IN_PARAMS_STAGE_INFO + xoff)[0]
                for xoff in (STAGE_INFO_STAGE_ID, STAGE_INFO_CODE, STAGE_INFO_NAME,
                             STAGE_INFO_LEVEL_ID, STAGE_INFO_ZONE_ID)
            ]
            can_replay = bool(raw[IN_PARAMS_STAGE_INFO + STAGE_INFO_CAN_BATTLE_REPLAY])
            difficulty = struct.unpack_from(
                "<i", raw, IN_PARAMS_STAGE_INFO + STAGE_INFO_DIFFICULTY)[0]
            ap_cost = struct.unpack_from(
                "<i", raw, IN_PARAMS_STAGE_INFO + STAGE_INFO_AP_COST)[0]
        except (IndexError, struct.error):
            return None
        stage_id, code, name, level_id, zone_id = map(self._read_string, string_ptrs)
        if not (stage_id and STAGE_ID_RE.match(stage_id)):
            return None
        if not (level_id and LEVEL_ID_RE.match(level_id)):
            return None
        if not (code and code.isprintable() and name and name.isprintable()):
            return None
        if zone_id and not STAGE_ID_RE.match(zone_id):
            return None
        level_data_id = self._level_data_id(level_data)
        if not level_data_id or level_data_id != level_id:
            return None
        return {
            "stageId": stage_id,
            "code": code,
            "name": name,
            "levelId": level_id,
            "zoneId": zone_id,
            "canBattleReplay": can_replay,
            "difficulty": difficulty,
            "apCost": ap_cost,
            "isPractice": bool(raw[IN_PARAMS_IS_PRACTICE]),
            "isAutoBattle": bool(raw[IN_PARAMS_IS_AUTO_BATTLE]),
            "isFastBattle": bool(raw[IN_PARAMS_IS_FAST_BATTLE]),
            "source": "battleInOut",
        }, level_data

    def _locate_stage_from_objects(self, battle_in_out_objects, bc_candidates):
        """从对象命中中选出与当前 BattleController.LevelData 一致的关卡。"""
        live_bcs = self._rank_live_battle_controllers(bc_candidates)
        live_levels = []
        for bc in live_bcs:
            level_data = self._ptr(bc + BC_LEVEL_DATA)
            level_id = self._level_data_id(level_data)
            if level_id:
                live_levels.append((level_data, level_id))
        live_level_ptrs = {p for p, _level_id in live_levels}
        live_level_ids = {level_id for _p, level_id in live_levels}

        decoded = []
        for obj in battle_in_out_objects:
            result = self._read_stage_info_candidate(obj)
            if result is None:
                continue
            info, level_data = result
            rank = (0 if level_data in live_level_ptrs else
                    1 if info["levelId"] in live_level_ids else 2)
            decoded.append((rank, obj, info))
        decoded.sort(key=lambda item: (item[0], item[1]))

        # 有 BC 时必须与当前 LevelData 对上，防止读取 GC 堆中的上一关 BattleInOut。
        # 没有 BC 时仅在唯一候选的情况下接受，避免多份残留对象之间猜测。
        if decoded and ((live_levels and decoded[0][0] <= 1)
                        or (not live_levels and len(decoded) == 1)):
            _rank, obj, info = decoded[0]
            self._battle_in_out_addr = obj
            self._publish_stage_info(info)
            self._status(f"  关卡 {info['code']} {info['name']} "
                         f"({info['stageId']})")
            return True

        # 降级路径只报告明确读到的 levelId，不推导 stageId；同一 levelId 可能对应
        # 普通/突袭等多个 stageId，猜测会产生错误的关卡身份。
        if live_levels:
            self._publish_stage_info({
                "stageId": "",
                "code": "",
                "name": "",
                "levelId": live_levels[0][1],
                "zoneId": "",
                "source": "battleController.levelData",
            })
            self._status(f"  仅定位到 levelId={live_levels[0][1]} (关卡详情降级)")
        else:
            self._status("  未找到可确认属于当前战斗的关卡信息")
        return False

    def _locate_via_device_class_scan(self) -> bool:
        """快速主路径：阶段 1 产出关卡信息，阶段 2 再绑定操作日志。"""
        objects = self._scan_class_objects(("BattleInOut", "BattleController"))
        if objects is None:
            if not self._class_scan_failure_reason:
                self._class_scan_failure_reason = "设备侧类/对象扫描不可用，未返回候选集合"
            return False
        bc_candidates = self._battle_controller_candidates(objects["BattleController"])
        self._status(f"  BattleController 标量候选 {len(bc_candidates)} 个")

        self._status("[阶段 1/2] 解析当前关卡信息 ...")
        self._locate_stage_from_objects(objects["BattleInOut"], bc_candidates)

        self._status("[阶段 2/2] 定位关卡内操作记录 ...")
        if not bc_candidates:
            if self._class_scan_failure_reason:
                self._status("  主路径失败: " + self._class_scan_failure_reason)
                return False
            object_count = len(objects["BattleController"])
            if object_count:
                self._class_scan_failure_reason = (
                    f"klass 扫描命中 {object_count} 个 BattleController 对象，但没有对象通过"
                    f"战斗标量校验 (state@{hex(BC_STATE)}=1..3, "
                    f"speedLevel@{hex(BC_SPEED_LEVEL)}=0..8, "
                    f"realPlayTime@{hex(BC_REAL_PLAY_TIME)}=0..100000)；"
                    "相关字段偏移可能已漂移，或当前不在作战中")
            else:
                self._class_scan_failure_reason = (
                    "已解析 BattleController 的 Il2CppClass，但在可扫描匿名 GC 堆中"
                    "没有找到以该 klass 指针开头的对象；对象可能不在当前扫描区域或尚未创建")
            self._status("  主路径失败: " + self._class_scan_failure_reason)
            return False

        ok = self._bind_battle_controller_candidates(bc_candidates)
        if not ok and not self._class_scan_failure_reason:
            self._class_scan_failure_reason = "BattleController 候选存在，但未能绑定有效操作日志链"
        return ok

    # ---------------- 定位流程 ----------------

    def locate(self) -> bool:
        """两阶段定位。

        阶段 1 先发布关卡信息（可通过 set_stage_callback 实时接收），阶段 2 再
        定位 BattleLogger / ReplayController。返回值保持兼容：True 表示操作链可用。
        """
        self._bc_addr = self._logger_addr = self._logs_list_addr = 0
        self._replay_addr = self._journal_logs_list_addr = 0
        self._squad_list_addr = self._journal_squad_list_addr = 0
        self._journal_meta = {}
        self._battle_in_out_addr = 0
        self._stage_info = {}
        self._class_scan_failure_reason = ""
        self._last_logger_reject_reason = ""

        try:
            self.mc.reload_maps()
        except Exception as exc:
            self._status(f"读取 maps 失败: {exc}")
            return False

        # memsrv v4 可在设备侧按 klass 指针精确扫描，通常十几秒即可定位，且
        # 零日志可用。类扫描没有找到有效对象时，再换用完整堆快照定位算法。
        try:
            if self._locate_via_device_class_scan():
                return True
        except Exception as exc:
            # 保持既有语义：设备扫描协议/连接异常直接上抛。完整堆回退同样依赖
            # 内存通道，此时盲目继续通常只会掩盖真正的 I/O 错误。
            self._status(
                f"设备侧类扫描异常，未进入堆快照回退: {type(exc).__name__}: {exc}")
            raise
        reason = self._class_scan_failure_reason or "设备侧类扫描未定位到有效操作链（未知原因）"
        self._status(f"类扫描主路径失败原因: {reason}")
        self._status("触发完整 GC 堆快照回退：主路径已正常完成，但没有绑定有效的当前操作链")

        # ---- 第 1 遍: 堆快照 + LogItem 数值候选 ----
        targets = self.mc.scan_targets()
        total = sum(e - s for s, e in targets)
        self._status(f"第 1 遍: 堆扫描 ({total / 1024 / 1024:.0f} MB) + LogItem 预过滤 ...")
        snap = _HeapSnap()
        candidates = []
        done = [0]
        lock = threading.Lock()
        t0 = time.time()
        sem = threading.Semaphore(SCAN_WORKERS)

        def job(a, b):
            try:
                try:
                    d = self.mc.read(a, b - a, timeout=30)
                except Exception:
                    d = None
                if d is not None:
                    snap.write(a, d)
                    candidates.extend(_numeric_filter_chunk(a, d))
                with lock:
                    done[0] += b - a
                    pct = done[0] * 100 // total
                    if pct // 10 != (done[0] - (b - a)) * 100 // total // 10:
                        self._status(f"  堆扫描 {pct}% ({time.time() - t0:.0f}s)")
            finally:
                sem.release()

        with concurrent.futures.ThreadPoolExecutor(max_workers=SCAN_WORKERS) as ex:
            for s, e in targets:
                a = s
                while a < e:
                    b = min(a + SCAN_CAP, e)
                    sem.acquire()
                    ex.submit(job, a, b)
                    a = b
        snap.finish()
        self._status(f"  数值候选 {len(candidates)} 个 ({time.time() - t0:.0f}s), 校验 charId ...")

        # 当前 BattleController 是零日志和有日志场景共同的可靠根节点。优先走这条链，
        # 避免当前战斗尚无操作时被 GC 堆中上一局遗留的 LogItem/Logger 误导。
        self._status("[阶段 1/2] 从当前 BattleController 读取关卡 levelId (降级路径) ...")
        self._status("[阶段 2/2] 优先按 BattleController 定位当前 BattleLogger ...")
        if self._locate_via_battle_controller(snap):
            snap.discard()
            return True
        self._status("BattleController 链定位未通过, 回退 LogItem 反向定位 ...")

        # ---- charId 字符串校验 (快照内就地解引用) ----
        valid = []
        for addr in candidates:
            cptr = snap.read_u64(addr + 0x10)
            if cptr is None:
                continue
            s = snap.read_ustring(cptr)
            if s and CHAR_ID_RE.match(s):
                valid.append(addr)
        self._status(f"  字符串校验后剩余 {len(valid)} 个")
        if not valid:
            snap.discard()
            self._status("定位失败 — 已进入关卡但未找到有效的当前 BattleController")
            return False

        # ---- 反推 items 数组 (快照内) ----
        arrays = set()
        for addr in valid:
            arr = self._find_items_array(snap, addr)
            if arr:
                arrays.add(arr)
        self._status(f"  反推出 {len(arrays)} 个 items 数组")
        if not arrays:
            snap.discard()
            return False

        # ---- 第 2 遍 (快照本地): 数组 -> List<LogItem> ----
        self._status("第 2 遍: 查找持有数组的 List<LogItem> ...")
        raw_lists = {}  # list_addr -> array_base
        for lst, arr in self._snap_find_refs(snap, arrays, back=LIST_ITEMS):
            d = snap.read(lst, 0x20)
            if not d or struct.unpack_from("<Q", d, LIST_ITEMS)[0] != arr:
                continue
            size = struct.unpack_from("<i", d, LIST_SIZE)[0]
            if not (0 < size <= 50000):
                continue
            raw_lists[lst] = arr
        # 批量 klass 名校验 (避免逐个 adb 往返)
        list_names = self._klass_names_batch(list(raw_lists))
        lists = {lst: arr for lst, arr in raw_lists.items()
                 if list_names.get(lst, "").startswith("List")}
        self._status(f"  有效 List<LogItem>: {len(lists)} 个")
        if not lists:
            snap.discard()
            return False

        # ---- 第 3 遍 (快照本地): List -> 持有者 (批量解析 klass 名) ----
        self._status("第 3 遍: 识别 List 持有者 ...")
        t3 = time.time()
        refs = self._snap_find_refs(snap, set(lists), back=None)  # [(list_addr, hit_addr)]
        self._status(f"  引用 {len(refs)} 处 ({time.time() - t3:.0f}s)")
        owner_cands = {hit - xoff: (lst, xoff)
                       for lst, hit in refs for xoff in range(0x10, 0x90, 8)}
        # 快照侧预过滤: owner 的 klass 指针必须是有效 VA (避免对垃圾候选逐个 adb 读)
        owners = [o for o in owner_cands
                  if (v := snap.read_u64(o)) is not None
                  and 0x10000000000 <= v < 0x1000000000000]
        self._status(f"  owner 候选 {len(owners)} 个, 批量解析 klass 名 ...")
        names = self._klass_names_batch(owners)
        self._status(f"  klass 名解析完成 ({time.time() - t3:.0f}s)")
        found_logger = False
        for owner, name in names.items():
            if name != "BattleLogger":
                continue
            lst, xoff = owner_cands[owner]
            bc = self._resolve_battle_controller(owner)
            state = self._i32(bc + BC_STATE) if bc else 0
            cached_ptr = self._ptr(bc + UNITY_CACHED_PTR) if bc else 0
            if (bc and state in (1, 2, 3) and self.mc.is_ptr(cached_ptr)
                    and self._bind_battle_logger(bc, owner, xoff)):
                # 反推得到的 List 必须和 Logger 自身的 m_logs 一致。
                if self._logs_list_addr != lst:
                    self._bc_addr = self._logger_addr = self._logs_list_addr = 0
                    continue
                found_logger = True
                self._status(f"  BattleController @ {hex(bc)} "
                             f"(state={BATTLE_STATE_NAMES.get(state, state)})")
                break
        snap.discard()

        if found_logger:
            self._squad_list_addr = self._find_squad_list(self._logger_addr, 0x20, 0x50)
            # 代理指挥: 从 BattleController 字段区找 ReplayController (手动模式没有)
            self._resolve_replay_controller()

        ok = found_logger or bool(self._replay_addr)
        if not ok:
            self._status("定位失败: 未找到 BattleLogger / ReplayController")
        return ok

    def _validate_log_list_detail(self, list_addr):
        """校验 List<LogItem>，返回 ``(是否有效, 失败原因)``。"""
        if not self.mc.is_ptr(list_addr):
            return False, f"m_logs={hex(list_addr) if list_addr else 'NULL'} 不是有效 rw 指针"
        name = self._klass_name(list_addr)
        if not (name and name.startswith("List")):
            return False, f"m_logs klass={name!r}，不是 List"
        d = self._read(list_addr, 0x20)
        if not d:
            return False, "无法读取 m_logs 的 List 头"
        items = struct.unpack_from("<Q", d, LIST_ITEMS)[0]
        size = struct.unpack_from("<i", d, LIST_SIZE)[0]
        if not (0 <= size <= 50000):
            return False, f"m_logs._size={size} 超出 0..50000"
        # 空 List 在不同运行时中可能使用共享空数组，也可能暂时为 NULL。
        if size == 0:
            if items == 0 or self.mc.is_ptr(items):
                return True, ""
            return False, f"空 m_logs 的 _items={hex(items)} 既非 NULL 也不是有效 rw 指针"
        if not self.mc.is_ptr(items):
            return False, f"m_logs._items={hex(items)} 不是有效 rw 指针"
        max_d = self._read(items + ARRAY_MAX_LENGTH, 4)
        if not max_d:
            return False, "无法读取 m_logs._items.max_length"
        max_len = struct.unpack("<i", max_d)[0]
        if not (size <= max_len <= 50000):
            return False, f"m_logs 容量关系无效: _size={size}, max_length={max_len}"
        return True, ""

    def _validate_log_list(self, list_addr) -> bool:
        """校验 List<LogItem> 容器；size==0 是刚进关卡时的正常状态。"""
        ok, _reason = self._validate_log_list_detail(list_addr)
        return ok

    def _bind_battle_logger(self, bc_addr, logger_addr, field_offset) -> bool:
        """强校验并绑定 BC -> BattleLogger -> m_logs 链。"""
        logger_name = self._klass_name(logger_addr)
        if logger_name != "BattleLogger":
            self._last_logger_reject_reason = f"klass={logger_name!r}，不是 BattleLogger"
            return False
        # 防止命中上一局仍滞留在 GC 堆中的 Logger。
        controller = self._ptr(logger_addr + LOGGER_CONTROLLER)
        if controller != bc_addr:
            self._last_logger_reject_reason = (
                f"m_controller={hex(controller) if controller else 'NULL'}，"
                f"未反向指回候选 BattleController {hex(bc_addr)}")
            return False
        logs = self._ptr(logger_addr + LOGGER_LOGS)
        list_ok, list_reason = self._validate_log_list_detail(logs)
        if not list_ok:
            self._last_logger_reject_reason = list_reason
            return False

        self._last_logger_reject_reason = ""
        self._bc_addr = bc_addr
        self._logger_addr = logger_addr
        self._logs_list_addr = logs
        size = self._i32(logs + LIST_SIZE)
        self._status(f"  BattleLogger @ {hex(logger_addr)} (BC +{hex(field_offset)}), "
                     f"m_logs @ {hex(logs)} ({size} 条)")
        return True

    def _bind_battle_controller_candidates(self, bc_list) -> bool:
        """从候选中选出仍绑定 Unity 原生对象的当前 BC，并解析 Logger。"""
        state_rank = {2: 0, 1: 1, 3: 2}
        ranked = []
        for bc in set(bc_list):
            state = self._i32(bc + BC_STATE)
            cached_ptr = self._ptr(bc + UNITY_CACHED_PTR)
            # UnityEngine.Object.m_CachedPtr 在对象销毁后变为 0。它比残留的
            # state/playTime 更能区分当前关卡和 GC 尚未回收的上一局对象。
            native_rank = 0 if self.mc.is_ptr(cached_ptr) else 1
            ranked.append((native_rank, state_rank.get(state, 9), bc, state))
        ranked.sort()
        live_native = sum(1 for native_rank, _sr, _bc, _st in ranked if native_rank == 0)
        self._status(f"  找到 {len(ranked)} 个 BattleController 候选, "
                     f"其中 {live_native} 个仍绑定 Unity 原生对象")
        if not ranked:
            self._class_scan_failure_reason = "BattleController 标量候选列表为空"
            self._status("  主路径失败: " + self._class_scan_failure_reason)
            return False
        if not live_native:
            states = ", ".join(
                f"{hex(bc)}:{BATTLE_STATE_NAMES.get(state, state)}"
                for _nr, _sr, bc, state in ranked[:8])
            self._class_scan_failure_reason = (
                f"{len(ranked)} 个 BattleController 候选的 m_CachedPtr@"
                f"{hex(UNITY_CACHED_PTR)} 均无效，判定为已销毁/残留对象"
                + (f"；候选状态 {states}" if states else ""))
            self._status("  主路径失败: " + self._class_scan_failure_reason)
            return False

        # 当前实测偏移优先；其余范围仅作版本漂移兜底，并覆盖旧 dump 的 0x100。
        xoffs = [BC_LOGGER] + [x for x in range(0xC0, 0x148, 8) if x != BC_LOGGER]
        logger_class_hits = 0
        logger_rejections = []
        valid_field_ptrs = 0
        for native_rank, _state_rank, bc, state in ranked:
            if native_rank:
                continue
            ptrs = {}
            for xoff, d in zip(xoffs, self._read_many([(bc + x, 8) for x in xoffs])):
                if d:
                    p = struct.unpack("<Q", d)[0]
                    if self.mc.is_ptr(p):
                        ptrs[xoff] = p
            valid_field_ptrs += len(ptrs)
            names = self._klass_names_batch(list(ptrs.values()))
            for xoff in xoffs:
                logger = ptrs.get(xoff, 0)
                if not logger or names.get(logger) != "BattleLogger":
                    continue
                logger_class_hits += 1
                if not self._bind_battle_logger(bc, logger, xoff):
                    detail = self._last_logger_reject_reason or "未知强校验失败"
                    logger_rejections.append(
                        f"BC {hex(bc)} +{hex(xoff)} -> {hex(logger)}: {detail}")
                    self._status(f"  排除 BattleLogger 候选: {logger_rejections[-1]}")
                    continue
                self._status(f"  BattleController @ {hex(bc)} "
                             f"(state={BATTLE_STATE_NAMES.get(state, state)}, "
                             f"m_CachedPtr={hex(self._ptr(bc + UNITY_CACHED_PTR))})")
                self._squad_list_addr = self._find_squad_list(
                    self._logger_addr, LOGGER_LOGS, 0x50)
                self._resolve_replay_controller()
                return True

        if logger_class_hits == 0:
            self._class_scan_failure_reason = (
                f"{live_native} 个存活 BattleController 的字段区 "
                f"(+{hex(min(xoffs))}..+{hex(max(xoffs))}，优先 +{hex(BC_LOGGER)})"
                f"共解析 {valid_field_ptrs} 个有效指针，但没有一个对象的 klass 是 BattleLogger；"
                "m_logger 字段范围可能已漂移或 Logger 尚未创建")
        else:
            unique_rejections = list(dict.fromkeys(logger_rejections))
            detail = "；".join(unique_rejections[:6])
            if len(unique_rejections) > 6:
                detail += f"；另有 {len(unique_rejections) - 6} 个失败候选"
            self._class_scan_failure_reason = (
                f"找到 {logger_class_hits} 个 BattleLogger klass 候选，但全部未通过"
                f"BC 反向指针/List<LogItem> 强校验：{detail}")
        self._status("  主路径失败: " + self._class_scan_failure_reason)
        return False

    def _locate_via_battle_controller(self, snap) -> bool:
        """用 BattleController 指纹定位当前战斗，支持 m_logs.size == 0。

        优先读取现网实测 m_logger 偏移；若版本字段漂移，再小范围扫描。所有
        BattleLogger 候选都必须反向指回同一个 BC，并拥有结构有效的日志 List。
        """
        # ---- 快照内向量化指纹扫描 (含 klass 指针预过滤) ----
        cands = []
        st_lo, st_hi = 1, 3
        if _np is not None:
            for base, d in snap.iter_chunks():
                a = _np.frombuffer(d, dtype="<u4")
                n = a.size
                if n < (BC_REAL_PLAY_TIME + 4) // 4 + 2:
                    continue
                f = a.view("<f4")
                j = _np.arange(0, n - (BC_REAL_PLAY_TIME + 4) // 4, 2)  # 8 字节对齐
                m = (a[j + BC_STATE // 4] >= st_lo) & (a[j + BC_STATE // 4] <= st_hi)
                m &= a[j + BC_SPEED_LEVEL // 4] <= 8
                pt = f[j + BC_REAL_PLAY_TIME // 4]
                m &= (pt >= 0.0) & (pt < 100000.0)
                m &= a[j + 1] >= 0x100      # klass 指针高 32 位 (>=1TB 用户态)
                m &= a[j + 1] < 0x10000
                cands += [base + int(k) * 4 for k in j[_np.nonzero(m)[0]]]
        else:
            for base, d in snap.iter_chunks():
                for off in range(0, len(d) - (BC_REAL_PLAY_TIME + 4), 8):
                    kp = struct.unpack_from("<Q", d, off)[0]
                    if not (0x10000000000 <= kp < 0x1000000000000):
                        continue
                    state = struct.unpack_from("<i", d, off + BC_STATE)[0]
                    if not (st_lo <= state <= st_hi):
                        continue
                    if not (0 <= struct.unpack_from("<i", d, off + BC_SPEED_LEVEL)[0] <= 8):
                        continue
                    pt = struct.unpack_from("<f", d, off + BC_REAL_PLAY_TIME)[0]
                    if 0.0 <= pt < 100000.0:
                        cands.append(base + off)
        self._status(f"  BC 指纹候选 {len(cands)} 个, klass 指针去重 ...")

        # ---- klass 指针快照内提取 + 去重 (只解析唯一 klass 的名字) ----
        klass_of = {}
        for addr in cands:
            kp = snap.read_u64(addr)
            if kp is not None and self.mc.is_ptr(kp):
                klass_of[addr] = kp
        uniq = sorted(set(klass_of.values()))
        self._status(f"  唯一 klass {len(uniq)} 个, 批量解析名字 ...")
        klass_names = {}
        name_ptrs = {}
        for k, d in zip(uniq, self._read_many([(k + 0x10, 8) for k in uniq])):
            if d:
                p = struct.unpack("<Q", d)[0]
                if self.mc.is_ptr(p):
                    name_ptrs[k] = p
        items = list(name_ptrs.items())
        for k, d in zip([k for k, _ in items],
                        self._read_many([(p, 48) for _, p in items])):
            if not d:
                continue
            end = d.find(b"\x00")
            if end > 0:
                try:
                    s = d[:end].decode("ascii")
                    if all(32 <= ord(c) < 127 for c in s):
                        klass_names[k] = s
                except UnicodeDecodeError:
                    pass
        bc_list = sorted(a for a, kp in klass_of.items()
                         if klass_names.get(kp) == "BattleController")
        if not bc_list:
            self._status("  未找到 BattleController (不在关卡中?)")
            return False
        if not self._stage_info:
            self._locate_stage_from_objects((), bc_list)
        return self._bind_battle_controller_candidates(bc_list)

    def _resolve_replay_controller(self):
        """在 BattleController 字段区找 ReplayController (仅代理指挥模式存在)。
        找到后解析 journal.logs / journal.squad / metadata。"""
        if not self._bc_addr:
            return
        # 批量取 BC 字段区指针
        xoffs = list(range(0xD0, 0x170, 8))
        ptrs = {}
        for xoff, d in zip(xoffs, self._read_many([(self._bc_addr + x, 8) for x in xoffs])):
            if d:
                p = struct.unpack("<Q", d)[0]
                if self.mc.is_ptr(p):
                    ptrs[xoff] = p
        names = self._klass_names_batch(list(ptrs.values()))
        for xoff, p in ptrs.items():
            if names.get(p) != "ReplayController":
                continue
            self._replay_addr = p
            self._status(f"  ReplayController @ {hex(p)} (BC +{hex(xoff)})")
            # journal.logs: 首元素像 LogItem 的 List
            for l_off in range(0x40, 0x78, 8):
                lst = self._ptr(p + l_off)
                if not self.mc.is_ptr(lst):
                    continue
                if not (self._klass_name(lst) or "").startswith("List"):
                    continue
                items = self._ptr(lst + LIST_ITEMS)
                size = self._i32(lst + LIST_SIZE)
                if not (self.mc.is_ptr(items) and 0 < size <= 50000):
                    continue
                d = self._read(items + ARRAY_ITEMS, LOGITEM_SIZE)
                if not d:
                    continue
                ts, uid, cptr, op, _dir, row, col, _ext = struct.unpack_from(
                    LOGITEM_STRUCT, d, 0)
                s = self._read_string(cptr)
                if (0.0 < ts < 100000.0 and uid >= 1 and 0 <= op <= 3
                        and 0 <= row <= 31 and 0 <= col <= 31
                        and s and CHAR_ID_RE.match(s)):
                    self._journal_logs_list_addr = lst
                    self._status(f"  journal.logs @ {hex(lst)} (ReplayController +{hex(l_off)}, "
                                 f"{size} 条)")
                    break
            self._journal_squad_list_addr = self._find_squad_list(p, 0x40, 0x70)
            self._journal_meta = self._read_journal_meta(p)
            self._merge_stage_from_journal()
            return

    def _merge_stage_from_journal(self):
        """代理序列 metadata 只补缺失字段，不覆盖 BattleInOut 的精确信息。"""
        stage_id = self._journal_meta.get("stageId", "")
        level_id = self._journal_meta.get("levelId", "")
        if not (stage_id or level_id):
            return
        info = dict(self._stage_info)
        changed = False
        for key, value in (("stageId", stage_id), ("levelId", level_id)):
            if value and not info.get(key):
                info[key] = value
                changed = True
        if not info.get("source"):
            info["source"] = "journal"
            changed = True
        elif changed and "journal" not in info["source"]:
            info["source"] += "+journal"
        if changed:
            self._publish_stage_info(info)

    def _snap_find_refs(self, snap, targets, back):
        """在快照中找指向 targets 中任一地址的 8 字节引用。
        back 为整数时返回 (target - back 修正前的对象基址, target), 即 (hit - back, target);
        back 为 None 时返回 (target, hit_addr) 原样对。"""
        out = []
        if _np is not None:
            narr = _np.array(sorted(targets), dtype="<u8")
            for base, d in snap.iter_chunks():
                q = _np.frombuffer(d, dtype="<u8")
                for k in _np.nonzero(_np.isin(q, narr))[0]:
                    v = int(q[int(k)])
                    haddr = base + int(k) * 8
                    out.append((haddr - back, v) if back is not None else (v, haddr))
        else:
            tset = set(targets)
            for base, d in snap.iter_chunks():
                for off in range(0, len(d) - 8, 8):
                    v = struct.unpack_from("<Q", d, off)[0]
                    if v in tset:
                        haddr = base + off
                        out.append((haddr - back, v) if back is not None else (v, haddr))
        return out

    def _resolve_battle_controller(self, logger_addr):
        """BattleLogger.m_controller 正常在 +0x18, 漂移时小范围搜索。"""
        for xoff in range(0x10, 0x30, 8):
            bc = self._ptr(logger_addr + xoff)
            if self._klass_name(bc) == "BattleController":
                return bc
        return 0

    def _find_items_array(self, snap, logitem_addr):
        """由 LogItem 地址反推所属 items 数组头 (数组数据起于 +0x20)。
        max_length 是 int32@+0x18 (+0x1C 的 4 字节填充可能是垃圾, 不可按 int64 读)。"""
        for k in range(300):
            arr = logitem_addr - ARRAY_ITEMS - k * LOGITEM_SIZE
            if arr < 0x10000:
                break
            d = snap.read(arr + ARRAY_MAX_LENGTH, 4)
            if not d:
                continue
            length = struct.unpack("<i", d)[0]
            if k < length < 50000:
                return arr
        return 0

    def _find_squad_list(self, owner_addr, lo, hi):
        """在持有者字段区查找 List<CharInfo>。
        判别: 首元素 tmplId/skinId 是 char_/trap_ 前缀, 且 skillId 以 "sk" 开头
        (排除 m_logs — LogItem 的 charId 也在 +0x10, 但 +0x18 是 int op 非字符串)。"""
        for xoff in range(lo, hi, 8):
            lst = self._ptr(owner_addr + xoff)
            if not self.mc.is_ptr(lst):
                continue
            if lst in (self._logs_list_addr, self._journal_logs_list_addr):
                continue
            name = self._klass_name(lst)
            if not (name and name.startswith("List")):
                continue
            items = self._ptr(lst + LIST_ITEMS)
            size = self._i32(lst + LIST_SIZE)
            if not (self.mc.is_ptr(items) and 0 < size <= 64):
                continue
            d = self._read(items + ARRAY_ITEMS, CHARINFO_SIZE)
            if not d:
                continue
            tmpl_ptr, skill_ptr = struct.unpack_from("<QQ", d, 0x10)
            s = self._read_string(tmpl_ptr)
            if not (s and CHAR_ID_RE.match(s)):
                # tmplId 现网常为 NULL, 回退校验 skinId (+0x8)
                skin_ptr = struct.unpack_from("<Q", d, 0x8)[0]
                s = self._read_string(skin_ptr)
                if not (s and CHAR_ID_RE.match(s.split("#", 1)[0])):
                    continue
            skill = self._read_string(skill_ptr)
            if not skill.startswith("sk"):
                continue
            return lst
        return 0

    def _read_journal_meta(self, replay_addr):
        """读取 ReplayController.m_journal.metadata (inline @ +0x18, 漂移时扫描字符串)。"""
        meta = {}
        base = replay_addr + 0x18
        d = self._read(base, 0x38)
        if not d:
            return meta
        standard_play_time, game_result = struct.unpack_from("<fi", d, 0)
        save_time_raw, remaining_cost, life_pt, killed, missed = struct.unpack_from("<qiiii", d, 0x8)
        meta.update({
            "standardPlayTime": round(standard_play_time, 3),
            "gameResult": game_result,
            "saveTimeRaw": save_time_raw,
            "remainingCost": remaining_cost,
            "remainingLifePoint": life_pt,
            "killedEnemiesCnt": killed,
            "missedEnemiesCnt": missed,
        })
        # levelId @ +0x20 / stageId @ +0x28 (相对 metadata 基址); 校验失败则小范围搜索
        level_id = self._read_string(self._ptr(base + 0x20))
        stage_id = self._read_string(self._ptr(base + 0x28))
        if not (level_id and LEVEL_ID_RE.match(level_id)):
            level_id = ""
        if not (stage_id and STAGE_ID_RE.match(stage_id)):
            stage_id = ""
        if not stage_id:
            for xoff in range(0x18, 0x38, 8):
                s = self._read_string(self._ptr(base + xoff))
                if s and "_" in s and STAGE_ID_RE.match(s):
                    stage_id = s
                    break
        meta["levelId"] = level_id
        meta["stageId"] = stage_id
        return meta

    # ---------------- 链有效性 ----------------

    def is_chain_valid(self) -> bool:
        """廉价校验已定位的链是否仍有效 (不触发重扫)。"""
        if (self._bc_addr and self._logger_addr
                and self._klass_name(self._bc_addr) == "BattleController"
                and self.mc.is_ptr(self._ptr(self._bc_addr + UNITY_CACHED_PTR))
                and self._klass_name(self._logger_addr) == "BattleLogger"
                and self._ptr(self._logger_addr + LOGGER_CONTROLLER) == self._bc_addr):
            logs = self._ptr(self._logger_addr + LOGGER_LOGS)
            if logs == self._logs_list_addr and self._validate_log_list(logs):
                return True
        return bool(self._replay_addr and
                    self._klass_name(self._replay_addr) == "ReplayController")

    def ensure_located(self) -> bool:
        """验证已定位的链仍然有效, 失效时自动重新定位。"""
        if self._logs_list_addr or self._journal_logs_list_addr:
            if self.is_chain_valid():
                return True
        return self.locate()

    # ---------------- 数据读取 ----------------

    def _read_log_list(self, list_addr):
        """读取 List<LogItem> 全部元素。"""
        if not list_addr:
            return []
        d = self._read(list_addr, 0x20)
        if not d:
            return []
        items = struct.unpack_from("<Q", d, LIST_ITEMS)[0]
        size = struct.unpack_from("<i", d, LIST_SIZE)[0]
        if not self.mc.is_ptr(items) or size <= 0:
            return []
        d = self._read(items + ARRAY_MAX_LENGTH, 4)
        max_len = struct.unpack("<i", d)[0] if d else 0
        count = max(0, min(size, max_len, 50000))
        if count == 0:
            return []
        raw = self._read(items + ARRAY_ITEMS, count * LOGITEM_SIZE)
        if not raw:
            return []
        # 先批量取全部字符串指针, 再批量读字符串
        reqs = []
        metas = []
        for i in range(count):
            try:
                ts, uid, cptr, op, direction, row, col, ext = struct.unpack_from(
                    LOGITEM_STRUCT, raw, i * LOGITEM_SIZE)
            except struct.error:
                continue
            metas.append((ts, uid, cptr, op, direction, row, col, ext))
            reqs.append((cptr, 0x60))
            if ext:
                reqs.append((ext, 0x60))
        blobs = self._read_many(reqs) if reqs else []
        strings = {}
        for (addr, _s), blob in zip(reqs, blobs):
            if not blob:
                continue
            ln = struct.unpack_from("<i", blob, STR_LENGTH)[0]
            if 0 < ln <= 64 and len(blob) >= STR_CHARS + ln * 2:
                try:
                    strings[addr] = blob[STR_CHARS:STR_CHARS + ln * 2].decode("utf-16-le")
                except UnicodeDecodeError:
                    pass
        events = []
        for ts, uid, cptr, op, direction, row, col, ext in metas:
            char_id = strings.get(cptr, "")
            extra = strings.get(ext, "") if ext else ""
            inst_id = uid & 0x7FFFFFFF   # 高位是 PlayerSide 标志位
            events.append({
                # 保留 float32 的微秒级十进制精度，主程序会用它匹配
                # BattleController.s_fixedPlayTimeFloat 对应的逻辑帧缓存。
                "timestamp": round(ts, 6),
                "frame": None,
                "uniqueId": uid,
                "charInstId": inst_id,
                "charId": char_id,
                "charName": self._lookup_char_name(char_id),
                "op": op,
                "opName": OP_NAMES.get(op, f"UNKNOWN({op})"),
                "direction": direction,
                "directionName": DIRECTION_NAMES.get(direction, str(direction)),
                "gridRow": row,
                "gridCol": col,
                "extraInfo": extra,
            })
        return events

    def _read_squad(self, list_addr):
        """读取 List<CharInfo> 编队信息。"""
        if not list_addr:
            return []
        items = self._ptr(list_addr + LIST_ITEMS)
        size = self._i32(list_addr + LIST_SIZE)
        if not (self.mc.is_ptr(items) and 0 < size <= 64):
            return []
        raw = self._read(items + ARRAY_ITEMS, size * CHARINFO_SIZE)
        if not raw:
            return []
        reqs = []
        for i in range(size):
            try:
                skin_ptr, tmpl_ptr, skill_ptr = struct.unpack_from(
                    "<QQQ", raw, i * CHARINFO_SIZE + 0x8)
            except struct.error:
                continue
            reqs += [(skin_ptr, 0x60), (tmpl_ptr, 0x60), (skill_ptr, 0x60)]
        blobs = self._read_many(reqs) if reqs else []
        strings = {}
        for (addr, _s), blob in zip(reqs, blobs):
            if not blob:
                continue
            ln = struct.unpack_from("<i", blob, STR_LENGTH)[0]
            if 0 < ln <= 128 and len(blob) >= STR_CHARS + ln * 2:
                try:
                    strings[addr] = blob[STR_CHARS:STR_CHARS + ln * 2].decode("utf-16-le")
                except UnicodeDecodeError:
                    pass
        squad = []
        for i in range(size):
            try:
                inst_id = struct.unpack_from("<i", raw, i * CHARINFO_SIZE)[0]
                skin_ptr, tmpl_ptr, skill_ptr = struct.unpack_from(
                    "<QQQ", raw, i * CHARINFO_SIZE + 0x8)
                skill_index, skill_lvl, level, phase, potential = struct.unpack_from(
                    "<iiiii", raw, i * CHARINFO_SIZE + 0x20)
            except struct.error:
                continue
            tmpl_id = strings.get(tmpl_ptr, "")
            if not tmpl_id:
                # 现网 tmplId 为空, 从 skinId 推导 (char_4228_closur#2 -> char_4228_closur)
                tmpl_id = strings.get(skin_ptr, "").split("#", 1)[0]
            squad.append({
                "charInstId": inst_id,
                "charId": tmpl_id,
                "charName": self._lookup_char_name(tmpl_id),
                "skinId": strings.get(skin_ptr, ""),
                "skillId": strings.get(skill_ptr, ""),
                "skillIndex": skill_index,
                "skillLvl": skill_lvl,
                "level": level,
                "phase": phase,
                "potentialRank": potential,
            })
        return squad

    # ---------------- 名称解析 ----------------

    def _load_char_names(self):
        if self._char_names is not None:
            return
        self._char_names = {}
        try:
            from tools.deploy_tracker.char_names import load_char_names
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            self._char_names = load_char_names(root)
        except Exception:
            pass

    def _lookup_char_name(self, char_id):
        if not char_id:
            return ""
        self._load_char_names()
        # 编队中的 charId 可能带皮肤后缀 (char_2025_shu@nian), 去掉再查
        return self._char_names.get(char_id.split("@", 1)[0], "")

    # ---------------- 对外接口 ----------------

    def get_events(self):
        """实时操作日志 (BattleLogger.m_logs)。"""
        return self._read_log_list(self._logs_list_addr)

    def get_spawn_events(self):
        return [e for e in self.get_events() if e["op"] == 0]

    def get_journal_events(self):
        """代理作战完整序列 (ReplayController.m_journal.logs), 非代理作战返回 []。"""
        return self._read_log_list(self._journal_logs_list_addr)

    def get_squad(self):
        """编队信息 (优先代理序列中的完整编队)。"""
        squad = self._read_squad(self._journal_squad_list_addr)
        if squad:
            return squad
        return self._read_squad(self._squad_list_addr)

    def get_stage_info(self):
        """返回阶段 1 已定位的关卡信息副本，适合后端直接序列化。"""
        return dict(self._stage_info)

    def get_battle_state(self):
        """BattleController 状态: state/speedLevel/playTime。"""
        if not self._bc_addr:
            return {}
        d = self._read(self._bc_addr + BC_STATE, 0x90)
        if not d:
            return {}
        state = struct.unpack_from("<i", d, 0)[0]
        speed = struct.unpack_from("<i", d, BC_SPEED_LEVEL - BC_STATE)[0]
        play_time = struct.unpack_from("<f", d, BC_REAL_PLAY_TIME - BC_STATE)[0]
        if not (0 <= state <= 3 and 0.0 <= play_time < 100000.0):
            return {}
        return {
            "state": state,
            "stateName": BATTLE_STATE_NAMES.get(state, str(state)),
            "speedLevel": speed,
            "playTime": round(play_time, 3),
        }

    def is_battle_active(self) -> bool:
        st = self.get_battle_state()
        if st:
            return st["state"] in (1, 2)
        return bool(self._replay_addr and
                    self._klass_name(self._replay_addr) == "ReplayController")

    def get_state(self):
        """聚合当前全部可读信息 (供 Web API / 导出使用)。"""
        live = self.get_events()
        journal = self.get_journal_events()
        squad = self.get_squad()
        # 用编队表补充 charId -> 中文名映射 (覆盖 trap/token 等不在 characters.json 的)
        inst_names = {c["charInstId"]: c["charName"] for c in squad if c.get("charName")}
        id_names = {c["charId"]: c["charName"] for c in squad if c.get("charName")}
        for ev in live + journal:
            if not ev["charName"]:
                ev["charName"] = (inst_names.get(ev["uniqueId"])
                                  or id_names.get(ev["charId"], ""))
        stage = self.get_stage_info()
        stage_id = stage.get("stageId") or self._journal_meta.get("stageId", "")
        level_id = stage.get("levelId") or self._journal_meta.get("levelId", "")
        return {
            "located": bool(self._logs_list_addr or self._journal_logs_list_addr),
            "stageLocated": bool(stage_id or level_id),
            "battle": self.get_battle_state(),
            "battleActive": self.is_battle_active(),
            "source": ("journal" if journal else
                       ("live" if self._logs_list_addr else "")),
            # 保留 stageId / levelId 顶层字段，兼容旧调用方；新代码优先使用 stage。
            "stageId": stage_id,
            "levelId": level_id,
            "stageCode": stage.get("code", ""),
            "stageName": stage.get("name", ""),
            "zoneId": stage.get("zoneId", ""),
            "stage": stage,
            "journalMeta": self._journal_meta,
            "squad": squad,
            "events": live,
            "journalEvents": journal,
        }
