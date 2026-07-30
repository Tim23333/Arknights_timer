# -*- coding: utf-8 -*-
"""敌人读取器（2026-07-30 运行时关卡序列 + 实例生命周期）。

工作原理:
  bootstrap（一次性，结果缓存磁盘）:
    1. 设备侧扫描 Il2CppClass，定位当前 BattleController；
    2. BattleController -> Scheduler -> m_managedWaveEnemies，零敌人也可定位；
    3. BattleController -> LevelData.waves，开局解析本关固定 SPAWN 顺序；
    4. 旧版 enemy_/HP 特征全堆扫描仅作为版本漂移兜底。
  poll_fast（准实时）:
    当前 List<Enemy> 实例与计划项绑定，统一返回 pending/active/departed；
    条件分支或召唤等未出现在固定 waves 中的动态敌人会在首次出现时追加。
"""

import os
import sys
import time
import pickle
import struct
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

try:
    import numpy as np
except ImportError:
    np = None

from .memcore import MemCore, TcpChannel
from . import game_structs as gs
from .enemy_db import load_enemy_db

NEEDLE_ENEMY = 'enemy_'.encode('utf-16-le')   # UTF-16LE "enemy_"
HP_MIN, HP_MAX = 50, 1_000_000                # HP 签名高32位范围
SCAN_CAP = 32 * 1024 * 1024                   # 每块 32MB
DETAIL_TCP_PORT = 27274                        # 与敌人主轮询/RNG/部署通道隔离

if getattr(sys, 'frozen', False):
    # 打包模式: _MEIPASS 是每次启动重建的临时目录, 缓存放 exe 旁以便跨启动复用
    CACHE_FILE = os.path.join(os.path.dirname(sys.executable), 'enemy_cache.pkl')
else:
    CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'enemy_cache.pkl')


def _u64(b, o):
    return struct.unpack_from('<Q', b, o)[0]


def _i32(b, o):
    return struct.unpack_from('<i', b, o)[0]


def _f32x2(b, o):
    return struct.unpack_from('<2f', b, o)


class _HeapSnapshot:
    """首次扫描的堆快照: 第 1 遍扫描边扫边落盘, 后续各遍从本地磁盘读。

    adb 隧道聚合带宽 ~20MB/s 且 4 路并发即饱和, 5 遍全量扫描 = 传 5 份堆;
    快照把传输压到 1 份 (耗时 ~堆大小/带宽), 其余 4 遍本地读盘 (GB/s 级)。
    IL2CPP Boehm GC 不移动对象, 扫描窗口 (~1 分钟) 内长寿命对象地址稳定,
    快照自洽。临时文件用完即删。"""

    def __init__(self):
        fd, self.path = tempfile.mkstemp(prefix='ak_heap_', suffix='.bin')
        self.fd = fd
        self.size = 0
        self.ranges = []          # (base, file_off, size), 写入顺序
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

    def iter_chunks(self):
        """按基址升序产出 (base, bytes)"""
        with open(self.path, 'rb', buffering=1024 * 1024) as f:
            for base, off, size in sorted(self.ranges):
                f.seek(off)
                yield base, f.read(size)

    def discard(self):
        try:
            os.close(self.fd)
        except OSError:
            pass
        try:
            os.remove(self.path)
        except OSError:
            pass


class EnemyInfo:
    __slots__ = ('addr', 'eid', 'name', 'code', 'hp', 'max_hp', 'atk', 'def_', 'res',
                 'mspd', 'aspd', 'direction', 'finish', 'alive', 'id_ptr', 'attr_ptr',
                 'pos_x', 'pos_y', 'blk_x', 'blk_y', 'spawn_row', 'spawn_col', 'skills',
                 'state_ptr', 'state_id', 'ep_ptr', 'ep_controller_ptr',
                 'shield_controller_ptr', 'es', 'shield',
                 'ep_remaining', 'ep_break_recovery', 'buff_container_ptr',
                 'attributes', 'raw_attributes', 'abnormal_flags', 'abnormal_immunes',
                 'abnormal_antis', 'abnormal_combos', 'abnormal_combo_immunes',
                 'buffs', 'global_buffs', 'roster_id', 'spawn_order', 'wave_index',
                 'fragment_index', 'action_index', 'spawn_index', 'route_index',
                 'lifecycle', 'planned', 'spawn_eta', 'spawn_condition',
                 'spawn_kind', 'spawn_source', 'is_summon', 'action_ptr')

    def __init__(self, addr):
        self.addr = addr
        self.eid = ''
        self.name = ''
        self.code = ''
        self.hp = 0.0
        self.max_hp = 0.0
        self.atk = 0.0
        self.def_ = 0.0
        self.res = 0.0
        self.mspd = 0.0
        self.aspd = 0.0
        self.direction = 0
        self.finish = 0
        self.alive = True
        self.id_ptr = 0
        self.attr_ptr = 0
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.blk_x = 0.0
        self.blk_y = 0.0
        self.spawn_row = 0
        self.spawn_col = 0
        self.skills = []          # [(prefabKey, remaining, period), ...]
        self.state_ptr = 0
        self.state_id = gs.EnemyState.DEFAULT
        self.ep_ptr = 0
        self.ep_controller_ptr = 0
        self.shield_controller_ptr = 0
        self.es = 0.0
        self.shield = 0.0
        self.ep_remaining = {}    # ElementType -> 剩余损伤容量
        self.ep_break_recovery = False
        self.buff_container_ptr = 0
        self.attributes = {}      # AttributeType -> 最终值 (cachedData)
        self.raw_attributes = {}  # AttributeType -> 原始值 (rawData), 详情读取
        self.abnormal_flags = [0] * gs.AbnormalFlag.E_NUM
        self.abnormal_immunes = [0] * gs.AbnormalFlag.E_NUM
        self.abnormal_antis = [0] * gs.AbnormalFlag.E_NUM
        self.abnormal_combos = [0] * gs.AbnormalCombo.E_NUM
        self.abnormal_combo_immunes = [0] * gs.AbnormalCombo.E_NUM
        self.buffs = []
        self.global_buffs = []
        self.roster_id = addr
        self.spawn_order = 0
        self.wave_index = -1
        self.fragment_index = -1
        self.action_index = -1
        self.spawn_index = -1
        self.route_index = -1
        self.lifecycle = 'active' if addr else 'pending'
        self.planned = False
        self.spawn_eta = None       # 距出场秒数；条件尚未满足时为 None
        self.spawn_condition = ''  # 无法给出秒数时的等待条件
        self.spawn_kind = 'dynamic'
        self.spawn_source = ''
        self.is_summon = False
        self.action_ptr = 0

    def attribute(self, index, default=0.0):
        return self.attributes.get(index, default)

    @property
    def status_resistance(self):
        """游戏保存的是 1 - 状态抗性；界面对外展示实际状态抗性。"""
        return 1.0 - self.attribute(gs.AttributeType.ONE_MINUS_STATUS_RESISTANCE, 1.0)

    def active_status_names(self):
        names = [gs.ABNORMAL_FLAG_CN_NAMES.get(i, str(i))
                 for i, count in enumerate(self.abnormal_flags) if count > 0]
        names.extend(gs.ABNORMAL_COMBO_CN_NAMES.get(i, str(i))
                     for i, count in enumerate(self.abnormal_combos) if count > 0)
        # 状态机是另一条独立数据链。有些极短状态先切状态机、后更新计数，合并显示。
        state_status = {
            gs.EnemyState.STUN: '眩晕', gs.EnemyState.FROZEN: '冻结',
            gs.EnemyState.LEVITATE: '浮空', gs.EnemyState.PALSY: '麻痹',
            gs.EnemyState.UNBALANCE: '失衡',
        }.get(self.state_id)
        if state_status and state_status not in names:
            names.append(state_status)
        return names

    def status_text(self):
        names = self.active_status_names()
        return '、'.join(names) if names else '正常'

    def element_damage(self, element_type):
        # MAX_EP is the base attribute, but some runtime entity subclasses
        # override Entity.maxEp (giant bosses are one example).  The game
        # initializes the unused NONE slot in m_epArray with that effective
        # maxEp, so it is the authoritative live capacity for every concrete
        # elemental-damage bar.  Keep the attribute as a fallback for pending
        # enemies and older layouts where the runtime array is unavailable.
        base_maximum = max(0.0, self.attribute(gs.AttributeType.MAX_EP, 0.0))
        runtime_maximum = max(
            0.0, self.ep_remaining.get(gs.ElementType.NONE, 0.0))
        maximum = max(base_maximum, runtime_maximum)
        remaining = max(0.0, self.ep_remaining.get(element_type, maximum))
        damage = max(0.0, maximum - remaining)
        return damage, remaining, maximum


class EnemyReader:
    def __init__(self, adb_path=None, package='com.hypergryph.arknights',
                 cache_file=CACHE_FILE, with_bc=True, log=print, workers=8, mc=None,
                 adb_serial=None):
        self.mc = mc if mc is not None else MemCore(
            adb_path, package, adb_serial=adb_serial)
        self.cache_file = cache_file
        self.with_bc = with_bc
        self.log = log
        self.workers = workers          # 扫描并发 adb 流数
        self.progress = None            # 可选回调 progress(pct:int, desc:str)
        # 发现的地址
        self.enemy_addrs = []
        self.items_addr = 0
        self.list_addr = 0
        self.sched_addr = 0
        self.bc_addr = 0
        self.unit_manager_addr = 0
        self.unit_enemies_addr = 0
        # 轮询缓存
        self._names = {}          # enemy addr -> (eid, name, code)
        self._attr_cache = {}     # enemy addr -> cachedData 数组地址
        self._db = None
        self._stale_cnt = 0
        self._last_bootstrap = 0.0
        self._merge_lock = threading.Lock()  # 并行扫描合并锁
        # 准实时轮询 (常驻 TCP 通道)
        self._chan = None             # TcpChannel, 惰性打开
        self._detail_chan = None      # 详情独立通道，避免重读取阻塞主轮询
        self._detail_context = threading.local()
        self._fast_tick = 0
        self._attr_snapshot = {}      # enemy addr -> {AttributeType: 最终属性值}
        self._runtime_snapshot = {}   # enemy addr -> 状态/损伤条/异常计数
        self._runtime_ptrs = {}       # enemy addr -> 运行时详情指针缓存
        self._f_items = 0             # 上一帧 items 数组地址 (投机读用)
        self._f_cnt = 0               # 上一帧敌人数量
        self._f_ptrs = []             # 上一帧敌人指针列表
        self._f_version = -1          # 上一帧 List._version (变化即重读 items)
        self._uf_items = 0            # UnitManager.enemies 的 Unit[]
        self._uf_cnt = 0
        self._uf_ptrs = []
        self._bc_snap = None          # BC 块缓存 (state, speed, time_scale, play_time)
        self._scheduler_time_snap = None  # BattleController.s_fixedPlayTime
        self._attr_ptrs = {}          # enemy addr -> Attributes* (属性轮换读取用)
        self._chan_fail = 0           # 通道连续异常计数 (日志节流)
        self._chan_dead_ts = 0.0      # 通道上次失败时间 (冷却期内直接走慢速)
        self._skill_lp = {}           # enemy addr -> m_skills List* (主块内提取)
        self._skill_names = {}        # skill addr -> prefabKey (技能静态名缓存)
        self._skill_cd = {}           # enemy addr -> [(key, remaining, period), ...]
        # 关卡完整出怪表：LevelData.waves 在开局即存在；当前 Enemy 实例按首次出现
        # 映射到计划项，退场后保留最后一帧，未生成项保持 pending。
        self._spawn_plan = []
        self._plan_by_id = {}
        self._roster_last = {}         # roster_id -> EnemyInfo（含已离场）
        self._addr_to_roster = {}      # 当前实例地址 -> roster_id
        self._dynamic_roster_seq = 0
        self._roster_initialized = False
        self._plan_level_id = ''
        # Scheduler 当前片段的运行时 action 队列。静态 waves 只能给出相对延迟，
        # 下一波仍可能等待上一批敌人离场；运行时队列才能给出真实剩余秒数。
        self._runtime_spawn_plan = []
        self._runtime_action_records = {}
        self._action_meta = {}
        self._action_queue_ptr = 0
        self._action_queue_items = 0
        self._action_queue_version = -1
        self._action_queue_entries = []
        self._fragment_start_time = 0.0
        self._wave_start_time = 0.0
        self._current_wave_index = -1
        self._current_fragment_index = -1
        self._bc_static_fields = 0
        self._scheduler_time_snap = None

    @property
    def planned_count(self):
        return len(self._spawn_plan) + len(self._runtime_spawn_plan)

    @property
    def plan_level_id(self):
        return self._plan_level_id

    # ================= 连接 =================

    def connect(self):
        pid = self.mc.connect()
        self.log(f"[连接] 游戏 PID = {pid}")
        return pid

    # ================= 关卡完整出怪序列 =================

    def _read_ptr(self, addr):
        data = self._detail_batch_read([(addr, 8)])[0]
        return _u64(data, 0) if data else 0

    def _read_object_array(self, array_ptr, max_count=4096):
        """读取引用类型 il2cpp 数组，返回非空且看似有效的对象指针。"""
        if not self.mc.is_ptr(array_ptr):
            return []
        head = self._detail_batch_read([(array_ptr, gs.Il2CppArray.ITEMS)])[0]
        if not head:
            return []
        count = _i32(head, gs.Il2CppArray.MAX_LENGTH)
        if not (0 <= count <= max_count):
            return []
        if count == 0:
            return []
        body = self._detail_batch_read(
            [(array_ptr + gs.Il2CppArray.ITEMS, count * 8)])[0]
        if not body:
            return []
        return [ptr for ptr in (_u64(body, idx * 8) for idx in range(count))
                if self.mc.is_ptr(ptr)]

    def _read_ustring_fast(self, ptr, max_chars=256):
        if not self.mc.is_ptr(ptr):
            return ''
        data = self._detail_batch_read(
            [(ptr, gs.Il2CppString.CHARS + max_chars * 2)])[0]
        if not data:
            return ''
        count = _i32(data, gs.Il2CppString.LENGTH)
        if not (0 <= count <= max_chars):
            return ''
        try:
            return data[gs.Il2CppString.CHARS:
                        gs.Il2CppString.CHARS + count * 2].decode('utf-16-le')
        except UnicodeDecodeError:
            return ''

    def _read_listdict_pairs(self, list_ptr, max_count=4096):
        """读取 ListDict<string,T>；其基类是 List<KeyValuePair<string,T>>。"""
        if not self.mc.is_ptr(list_ptr):
            return []
        head = self._detail_batch_read([(list_ptr, 0x20)])[0]
        if not head:
            return []
        items = _u64(head, gs.ListInternal.ITEMS)
        count = _i32(head, gs.ListInternal.SIZE)
        if not (0 <= count <= max_count) or (count and not self.mc.is_ptr(items)):
            return []
        if not count:
            return []
        raw = self._detail_batch_read(
            [(items + gs.Il2CppArray.ITEMS, count * 0x10)])[0]
        if not raw:
            return []
        pairs = []
        for index in range(count):
            key_ptr = _u64(raw, index * 0x10)
            value_ptr = _u64(raw, index * 0x10 + 8)
            key = self._read_ustring_fast(key_ptr)
            if key and self.mc.is_ptr(value_ptr):
                pairs.append((key, value_ptr))
        return pairs

    def _expand_spawn_actions(self, action_ptrs, base_meta, base_delay=0.0):
        """把 ActionData.count 展开为逐实例记录，并按 ActionItem 时间语义排序。"""
        records = []
        for action_index, action_ptr in enumerate(action_ptrs):
            action = self._detail_batch_read(
                [(action_ptr, gs.SpawnActionFields.READ_SIZE)])[0]
            if (not action
                    or _i32(action, gs.SpawnActionFields.ACTION_TYPE)
                    != gs.SpawnActionType.SPAWN
                    or not action[gs.SpawnActionFields.IS_VALID]):
                continue
            count = _i32(action, gs.SpawnActionFields.COUNT)
            key = self._read_ustring_fast(_u64(action, gs.SpawnActionFields.KEY))
            if not key or not (0 < count <= 4096):
                continue
            pre_delay = struct.unpack_from(
                '<f', action, gs.SpawnActionFields.PRE_DELAY)[0]
            interval = struct.unpack_from(
                '<f', action, gs.SpawnActionFields.INTERVAL)[0]
            for spawn_index in range(count):
                record = dict(base_meta)
                record.update({
                    'key': key,
                    'action_ptr': action_ptr,
                    'action_index': action_index,
                    'spawn_index': spawn_index,
                    'route_index': _i32(action, gs.SpawnActionFields.ROUTE_INDEX),
                    'time_offset': (float(base_delay) + pre_delay
                                    + max(0.0, interval) * spawn_index),
                    'managed': bool(action[gs.SpawnActionFields.MANAGED_BY_SCHEDULER]),
                    'hidden_group': self._read_ustring_fast(
                        _u64(action, gs.SpawnActionFields.HIDDEN_GROUP)),
                    'random_spawn_group': self._read_ustring_fast(
                        _u64(action, gs.SpawnActionFields.RANDOM_SPAWN_GROUP)),
                    'not_count_in_total': bool(
                        action[gs.SpawnActionFields.NOT_COUNT_IN_TOTAL]),
                })
                records.append(record)
        records.sort(key=lambda item: (
            item['time_offset'], item['action_index'], item['spawn_index']))
        return records

    def _resolve_battle_clock(self):
        """解析 Scheduler startTime 所使用的 BattleController 静态 FP 时钟。"""
        self._bc_static_fields = 0
        if not self.mc.is_ptr(self.bc_addr):
            return False
        klass = self._read_ptr(self.bc_addr)
        static_fields = self._read_ptr(klass + gs.Il2CppClassFields.STATIC_FIELDS) \
            if self.mc.is_ptr(klass) else 0
        if not self.mc.is_ptr(static_fields):
            return False
        raw = self._detail_batch_read([(
            static_fields + gs.BattleControllerStaticFields.FIXED_PLAY_TIME, 8)])[0]
        if not raw:
            return False
        now = gs.fp_to_float(_u64(raw, 0))
        if not (-1.0 <= now <= 864000.0):
            return False
        self._bc_static_fields = static_fields
        return True

    @staticmethod
    def _decode_battle_clock(raw):
        if not raw or len(raw) < 8:
            return None
        value = gs.fp_to_float(_u64(raw, 0))
        return value if -1.0 <= value <= 864000.0 else None

    def _make_plan_record(self, source, order, roster_id):
        record = dict(source)
        record['roster_id'] = roster_id
        record['spawn_order'] = order
        record['seen'] = False
        record['addr'] = 0
        record.setdefault('spawn_eta', None)
        record.setdefault('spawn_condition', '等待关卡调度')
        record.setdefault('spawn_kind', 'scheduled')
        record.setdefault('spawn_source', '')
        enemy = EnemyInfo(0)
        enemy.roster_id = roster_id
        enemy.spawn_order = order
        enemy.wave_index = record.get('wave_index', -1)
        enemy.fragment_index = record.get('fragment_index', -1)
        enemy.action_index = record.get('action_index', -1)
        enemy.spawn_index = record.get('spawn_index', -1)
        enemy.route_index = record.get('route_index', -1)
        enemy.eid = record.get('key', '')
        db_row = self._db.get(enemy.eid, {})
        enemy.name = db_row.get('name') or enemy.eid
        enemy.code = db_row.get('code') or ''
        enemy.lifecycle = 'pending'
        enemy.planned = True
        enemy.alive = False
        self._copy_plan_metadata(enemy, record, 'pending')
        record['info'] = enemy
        self._plan_by_id[roster_id] = record
        return record

    def _all_plan_records(self):
        return self._spawn_plan + self._runtime_spawn_plan

    def _set_spawn_plan(self, records, level_id=''):
        """重建本局计划表和实例映射；records 已按预定出场顺序排列。"""
        if self._db is None:
            self._db = load_enemy_db()
        self._spawn_plan = []
        self._runtime_spawn_plan = []
        self._runtime_action_records = {}
        self._plan_by_id = {}
        self._roster_last = {}
        self._addr_to_roster = {}
        self._dynamic_roster_seq = 0
        self._roster_initialized = False
        self._plan_level_id = level_id or ''
        self._action_meta = {}
        self._action_queue_ptr = 0
        self._action_queue_items = 0
        self._action_queue_version = -1
        self._action_queue_entries = []
        self._fragment_start_time = 0.0
        self._wave_start_time = 0.0
        self._current_wave_index = -1
        self._current_fragment_index = -1
        self._bc_static_fields = 0
        self._scheduler_time_snap = None
        for order, source in enumerate(records, 1):
            record = self._make_plan_record(source, order, -order)
            self._spawn_plan.append(record)

    def _load_spawn_plan(self):
        """解析固定 waves、条件 branches 和仅由事件/召唤使用的敌人类型。"""
        if not self.bc_addr:
            self._set_spawn_plan([])
            return False
        level_data = self._read_ptr(self.bc_addr + gs.BattleControllerFields.LEVEL_DATA)
        if (not self.mc.is_ptr(level_data)
                or self.mc.read_klass_name(level_data) != 'LevelData'):
            self._set_spawn_plan([])
            return False
        level_id = self._read_ustring_fast(
            self._read_ptr(level_data + gs.LevelDataFields.LEVEL_ID))
        waves_ptr = self._read_ptr(level_data + gs.LevelDataFields.WAVES)
        wave_ptrs = self._read_object_array(waves_ptr, 1024)
        records = []
        for wave_index, wave_ptr in enumerate(wave_ptrs):
            wave = self._detail_batch_read([(wave_ptr, 0x30)])[0]
            if not wave:
                continue
            fragments_ptr = _u64(wave, gs.WaveDataFields.FRAGMENTS)
            fragment_ptrs = self._read_object_array(fragments_ptr, 4096)
            for fragment_index, fragment_ptr in enumerate(fragment_ptrs):
                fragment = self._detail_batch_read([(fragment_ptr, 0x20)])[0]
                if not fragment:
                    continue
                actions_ptr = _u64(fragment, gs.FragmentDataFields.ACTIONS)
                action_ptrs = self._read_object_array(actions_ptr, 8192)
                records.extend(self._expand_spawn_actions(action_ptrs, {
                    'wave_index': wave_index,
                    'fragment_index': fragment_index,
                    'spawn_kind': 'scheduled',
                    'spawn_condition': (
                        f'等待第 {wave_index + 1} 波第 {fragment_index + 1} 段进入调度'),
                    'wave_pre_delay': struct.unpack_from(
                        '<f', wave, gs.WaveDataFields.PRE_DELAY)[0],
                    'wave_max_wait': struct.unpack_from(
                        '<f', wave, gs.WaveDataFields.MAX_WAIT_NEXT)[0],
                }))
        fixed_count = len(records)

        # branches 由敌人技能、死亡事件或关卡脚本触发；触发时间取决于战局，
        # 因而开局展示条件而不伪造绝对秒数。若其中出现 SPAWN，仍预列其实例。
        branches_ptr = self._read_ptr(level_data + gs.LevelDataFields.BRANCHES)
        branch_records = []
        for branch_id, branch_ptr in self._read_listdict_pairs(branches_ptr):
            branch = self._detail_batch_read([(branch_ptr, 0x20)])[0]
            phases_ptr = _u64(branch, gs.BranchDataFields.PHASES) if branch else 0
            for phase_index, phase_ptr in enumerate(
                    self._read_object_array(phases_ptr, 4096)):
                phase = self._detail_batch_read([(phase_ptr, 0x20)])[0]
                if not phase:
                    continue
                action_ptrs = self._read_object_array(
                    _u64(phase, gs.BranchPhaseDataFields.ACTIONS), 8192)
                phase_delay = struct.unpack_from(
                    '<f', phase, gs.BranchPhaseDataFields.PRE_DELAY)[0]
                branch_records.extend(self._expand_spawn_actions(action_ptrs, {
                    'wave_index': -1,
                    'fragment_index': phase_index,
                    'branch_id': branch_id,
                    'spawn_kind': 'conditional',
                    'spawn_source': branch_id,
                    'spawn_condition': f'等待分支「{branch_id}」触发（可能由技能/死亡事件触发）',
                }, phase_delay))
        records.extend(branch_records)

        # 数据库引用中若还有未被 waves/branches 使用的敌人类型，通常来自召唤、
        # 死亡转换或插件事件。数量在触发前不可知，先放一个“潜在实例”占位；
        # 同类额外实例出现时仍会由运行时逻辑继续追加。
        known_keys = {record['key'] for record in records}
        ref_count = 0
        refs_ptr = self._read_ptr(level_data + gs.LevelDataFields.ENEMY_DB_REFS)
        for ref_ptr in self._read_object_array(refs_ptr, 4096):
            ref = self._detail_batch_read([(ref_ptr, 0x28)])[0]
            key = self._read_ustring_fast(_u64(ref, 0x18)) if ref else ''
            if not key or key in known_keys:
                continue
            known_keys.add(key)
            ref_count += 1
            records.append({
                'key': key,
                'wave_index': -1,
                'fragment_index': -1,
                'action_index': -1,
                'spawn_index': 0,
                'route_index': -1,
                'spawn_kind': 'summoned',
                'spawn_source': '关卡敌人数据库引用',
                'spawn_condition': '等待召唤者技能、前置敌人死亡转换或关卡事件触发',
            })
        self._set_spawn_plan(records, level_id)
        self._resolve_battle_clock()
        if records:
            self.log(f"[关卡] {level_id or '当前关卡'} 敌人计划 {len(records)} 个"
                     f"（固定 {fixed_count}，条件分支 {len(branch_records)}，"
                     f"潜在召唤类型 {ref_count}）")
        else:
            self.log(f"[关卡] {level_id or '当前关卡'} 未解析到固定 SPAWN 序列")
        return bool(records)

    @staticmethod
    def _copy_plan_metadata(enemy, record, lifecycle):
        enemy.roster_id = record['roster_id']
        enemy.spawn_order = record['spawn_order']
        enemy.wave_index = record.get('wave_index', -1)
        enemy.fragment_index = record.get('fragment_index', -1)
        enemy.action_index = record.get('action_index', -1)
        enemy.spawn_index = record.get('spawn_index', -1)
        enemy.route_index = record.get('route_index', -1)
        enemy.lifecycle = lifecycle
        enemy.planned = True
        enemy.spawn_eta = record.get('spawn_eta')
        enemy.spawn_condition = record.get('spawn_condition', '')
        enemy.spawn_kind = record.get('spawn_kind', 'scheduled')
        enemy.spawn_source = record.get('spawn_source', '')
        return enemy

    def _bind_plan_enemy(self, enemy, record):
        self._copy_plan_metadata(enemy, record, 'active')
        enemy.spawn_eta = 0.0
        enemy.spawn_condition = '已出场'
        record['seen'] = True
        record['addr'] = enemy.addr
        record['info'] = enemy
        self._addr_to_roster[enemy.addr] = record['roster_id']
        self._roster_last[record['roster_id']] = enemy

    def _bind_dynamic_enemy(self, enemy):
        self._dynamic_roster_seq += 1
        roster_id = 1_000_000 + self._dynamic_roster_seq
        enemy.roster_id = roster_id
        enemy.spawn_order = self.planned_count + self._dynamic_roster_seq
        enemy.lifecycle = 'active'
        enemy.planned = False
        enemy.spawn_kind = 'summoned'
        enemy.spawn_condition = '运行时召唤或关卡条件触发'
        enemy.spawn_eta = 0.0
        self._addr_to_roster[enemy.addr] = roster_id
        self._roster_last[roster_id] = enemy

    def _merge_enemy_roster(self, live_enemies, spawned_count=0):
        """把当前实例合并进开局计划，返回含未出场/场上/已离场的稳定顺序。"""
        # UnitManager 在死亡动画/回收前仍短暂保留对象；HP 归零或 finishReason
        # 非零即应进入“已离场”，不能继续算作场上敌人。
        live_enemies = [enemy for enemy in live_enemies if enemy.alive]
        live_addrs = {enemy.addr for enemy in live_enemies}

        if not self._roster_initialized:
            prefix = min(max(0, int(spawned_count or 0)), len(self._spawn_plan))
            for record in self._spawn_plan[:prefix]:
                info = record['info']
                info.lifecycle = 'departed'
                self._roster_last[record['roster_id']] = info
            # 中途开始监控时无法从同类敌人的对象本身还原精确序号；通常先出场者
            # 先离场，因此按当前 List 顺序映射到已生成前缀中靠后的同类计划项。
            for enemy in reversed(live_enemies):
                candidates = [record for record in self._spawn_plan[:prefix]
                              if not record['seen'] and record['key'] == enemy.eid]
                if candidates:
                    self._bind_plan_enemy(enemy, candidates[-1])
            self._roster_initialized = True

        # 先把上一帧存在、本帧消失的实例固化为已离场。
        for addr in list(self._addr_to_roster):
            if addr in live_addrs:
                continue
            roster_id = self._addr_to_roster.pop(addr)
            old = self._roster_last.get(roster_id)
            if old is not None:
                old.lifecycle = 'departed'
                old.alive = False
            record = self._plan_by_id.get(roster_id)
            if record is not None:
                record['addr'] = 0
                if old is not None:
                    record['info'] = old

        for enemy in live_enemies:
            roster_id = self._addr_to_roster.get(enemy.addr)
            if roster_id is not None:
                record = self._plan_by_id.get(roster_id)
                if record is not None:
                    self._bind_plan_enemy(enemy, record)
                else:
                    enemy.roster_id = roster_id
                    enemy.spawn_order = self._roster_last[roster_id].spawn_order
                    enemy.lifecycle = 'active'
                    enemy.planned = False
                    self._roster_last[roster_id] = enemy
                continue

            # ActionData 指针能精确区分同种敌人的固定波次与运行时召唤；
            # isSummon 则避免召唤物误认领尚未出场的同名固定波次项。
            record = None
            if enemy.action_ptr:
                record = next((item for item in self._all_plan_records()
                               if item.get('action_ptr') == enemy.action_ptr
                               and item['info'].lifecycle == 'pending'), None)
            if record is None and enemy.is_summon:
                record = next((item for item in self._all_plan_records()
                               if item['key'] == enemy.eid
                               and item.get('spawn_kind') in (
                                   'summoned', 'conditional', 'after_death')
                               and item['info'].lifecycle == 'pending'), None)
            if record is None and not enemy.is_summon:
                record = next((item for item in self._all_plan_records()
                               if item['key'] == enemy.eid
                               and item['info'].lifecycle == 'pending'), None)
            if record is None:
                # 初次附着中途战斗时，spawned_count 已把未观测的前缀标成离场；
                # 若实例随后才在 List 中可见，允许认领尚未真正观测过的同类项。
                candidates = [item for item in self._all_plan_records()
                              if item['key'] == enemy.eid
                              and item['info'].lifecycle == 'departed'
                              and not item['seen']]
                record = candidates[-1] if candidates else None
            if record is not None:
                self._bind_plan_enemy(enemy, record)
            else:
                self._bind_dynamic_enemy(enemy)

        rows = [record['info'] for record in self._all_plan_records()]
        dynamic = [enemy for roster_id, enemy in self._roster_last.items()
                   if roster_id not in self._plan_by_id]
        dynamic.sort(key=lambda enemy: enemy.spawn_order)
        for index, enemy in enumerate(dynamic, 1):
            # 运行期间可能补发现条件 Action；动态项始终排在全部可预知项之后，
            # 避免新增计划项与既有动态项共用同一个显示序号。
            enemy.spawn_order = self.planned_count + index
        rows.extend(dynamic)
        return rows

    def _spawned_count(self):
        if not self.sched_addr:
            return 0
        data = self._detail_batch_read([(
            self.sched_addr + gs.SchedulerFields.M_SPAWNED_ENEMIES_CNT, 4)])[0]
        return struct.unpack('<I', data)[0] if data else 0

    def _read_action_meta_chan(self, action_ptrs):
        """批量读取新出现的 ActionData；运行时分支 action 同样能在这里识别。"""
        missing = [ptr for ptr in action_ptrs if ptr not in self._action_meta]
        if not missing:
            return
        for ptr, data in zip(missing, self._chan.batch_read([
                (ptr, gs.SpawnActionFields.READ_SIZE) for ptr in missing])):
            if not data:
                continue
            action_type = _i32(data, gs.SpawnActionFields.ACTION_TYPE)
            key_ptr = _u64(data, gs.SpawnActionFields.KEY)
            self._action_meta[ptr] = {
                'action_type': action_type,
                'key_ptr': key_ptr,
                'count': _i32(data, gs.SpawnActionFields.COUNT),
                'managed': bool(data[gs.SpawnActionFields.MANAGED_BY_SCHEDULER]),
                'route_index': _i32(data, gs.SpawnActionFields.ROUTE_INDEX),
                'hidden_group_ptr': _u64(data, gs.SpawnActionFields.HIDDEN_GROUP),
                'random_group_ptr': _u64(data, gs.SpawnActionFields.RANDOM_SPAWN_GROUP),
            }
        string_reqs, string_keys = [], []
        for ptr in missing:
            meta = self._action_meta.get(ptr)
            if not meta:
                continue
            for field in ('key_ptr', 'hidden_group_ptr', 'random_group_ptr'):
                value = meta.get(field, 0)
                if self.mc.is_ptr(value):
                    string_reqs.append((value, 0x100))
                    string_keys.append((ptr, field[:-4]))
        for (ptr, field), data in zip(
                string_keys, self._chan.batch_read(string_reqs) if string_reqs else []):
            text = ''
            if data and 0 <= _i32(data, gs.Il2CppString.LENGTH) <= 118:
                count = _i32(data, gs.Il2CppString.LENGTH)
                try:
                    text = data[gs.Il2CppString.CHARS:
                                gs.Il2CppString.CHARS + count * 2].decode('utf-16-le')
                except UnicodeDecodeError:
                    pass
            self._action_meta[ptr][field] = text

    def _append_runtime_spawn_records(self, entries):
        """把运行时分支/事件新加入队列的 SPAWN 补进未出场列表。"""
        static_tokens = {
            (record.get('action_ptr'), record.get('spawn_index', 0))
            for record in self._spawn_plan if record.get('action_ptr')
        }
        for entry in entries:
            token = (entry['action_ptr'], entry['occurrence'])
            if token in static_tokens or token in self._runtime_action_records:
                continue
            order = len(self._spawn_plan) + len(self._runtime_spawn_plan) + 1
            roster_id = -(1_000_000 + len(self._runtime_spawn_plan) + 1)
            source = {
                'key': entry['key'],
                'action_ptr': entry['action_ptr'],
                'runtime_token': token,
                'wave_index': self._current_wave_index,
                'fragment_index': self._current_fragment_index,
                'action_index': -1,
                'spawn_index': entry['occurrence'],
                'route_index': entry.get('route_index', -1),
                'time_offset': entry['time_offset'],
                'managed': entry.get('managed', False),
                'spawn_kind': 'conditional',
                'spawn_source': '运行时关卡事件/召唤',
                'spawn_condition': '条件已触发，等待出场',
            }
            record = self._make_plan_record(source, order, roster_id)
            self._runtime_spawn_plan.append(record)
            self._runtime_action_records[token] = record

    def _refresh_action_queue_chan(self, scheduler_data):
        """读取当前 Scheduler.ActionItem 队列并缓存真实运行时出场偏移。"""
        if not scheduler_data:
            return
        self._wave_start_time = gs.fp_to_float(
            _u64(scheduler_data, gs.SchedulerFields.M_WAVE_START_TIME))
        self._fragment_start_time = gs.fp_to_float(
            _u64(scheduler_data, gs.SchedulerFields.M_FRAGMENT_START_TIME))
        queue_ptr = _u64(scheduler_data, gs.SchedulerFields.M_ACTION_QUEUE)
        if not self.mc.is_ptr(queue_ptr):
            self._action_queue_entries = []
            return
        (head,) = self._chan.batch_read([(queue_ptr, 0x20)])
        if not head:
            return
        items = _u64(head, gs.ListInternal.ITEMS)
        count = _i32(head, gs.ListInternal.SIZE)
        version = _i32(head, gs.ListInternal.VERSION)
        if not (0 <= count <= 8192) or (count and not self.mc.is_ptr(items)):
            return
        unchanged = (queue_ptr == self._action_queue_ptr
                     and items == self._action_queue_items
                     and version == self._action_queue_version)
        if unchanged:
            return
        raw = b''
        if count:
            (raw,) = self._chan.batch_read([(
                items + gs.Il2CppArray.ITEMS,
                count * gs.SchedulerActionItemFields.SIZE)])
            if not raw:
                return
        action_ptrs = []
        raw_entries = []
        for idx in range(count):
            off = idx * gs.SchedulerActionItemFields.SIZE
            action_ptr = _u64(raw, off + gs.SchedulerActionItemFields.DATA)
            time_offset = struct.unpack_from(
                '<f', raw, off + gs.SchedulerActionItemFields.TIME_OFFSET)[0]
            if self.mc.is_ptr(action_ptr) and -3600 <= time_offset <= 86400:
                action_ptrs.append(action_ptr)
                raw_entries.append((action_ptr, time_offset))
        self._read_action_meta_chan(sorted(set(action_ptrs)))
        occurrence = {}
        entries = []
        for action_ptr, time_offset in raw_entries:
            meta = self._action_meta.get(action_ptr, {})
            if meta.get('action_type') != gs.SpawnActionType.SPAWN or not meta.get('key'):
                continue
            index = occurrence.get(action_ptr, 0)
            occurrence[action_ptr] = index + 1
            entries.append({
                'action_ptr': action_ptr,
                'occurrence': index,
                'time_offset': time_offset,
                'key': meta['key'],
                'managed': meta.get('managed', False),
                'route_index': meta.get('route_index', -1),
            })
        self._action_queue_ptr = queue_ptr
        self._action_queue_items = items
        self._action_queue_version = version
        self._action_queue_entries = entries

        by_ptr = {record.get('action_ptr'): record for record in self._spawn_plan}
        current = [by_ptr[entry['action_ptr']] for entry in entries
                   if entry['action_ptr'] in by_ptr]
        if current:
            first = min(current, key=lambda record: (
                record.get('wave_index', 1 << 30),
                record.get('fragment_index', 1 << 30)))
            self._current_wave_index = first.get('wave_index', -1)
            self._current_fragment_index = first.get('fragment_index', -1)
        self._append_runtime_spawn_records(entries)

    def _apply_spawn_timing(self, rows, scheduler_time):
        """为 pending 行填充精确 ETA；尚未进入队列的项显示真实等待条件。"""
        entry_map = {
            (entry['action_ptr'], entry['occurrence']): entry
            for entry in self._action_queue_entries
        }
        for record in self._all_plan_records():
            info = record['info']
            if info.lifecycle != 'pending':
                continue
            token = record.get('runtime_token') or (
                record.get('action_ptr'), record.get('spawn_index', 0))
            entry = entry_map.get(token)
            if (entry is not None and self._fragment_start_time >= 0
                    and scheduler_time is not None):
                eta = max(0.0, self._fragment_start_time
                          + entry['time_offset'] - float(scheduler_time))
                record['spawn_eta'] = eta
                record['spawn_condition'] = '按当前调度计时'
            else:
                record['spawn_eta'] = None
                if record.get('hidden_group'):
                    record['spawn_condition'] = '等待隐藏条件启用'
                    record['spawn_kind'] = 'conditional'
                elif record.get('random_spawn_group'):
                    record['spawn_condition'] = '等待随机分支确定'
                    record['spawn_kind'] = 'conditional'
                elif record in self._runtime_spawn_plan:
                    record['spawn_condition'] = record.get(
                        'spawn_condition') or '等待运行时关卡事件/召唤'
                    record['spawn_kind'] = 'conditional'
                elif record.get('spawn_kind') in ('conditional', 'summoned', 'after_death'):
                    # 分支/召唤的触发者没有进入 Scheduler 计时队列前，不存在
                    # 可验证的秒数；保留从关卡数据解析出的真实条件说明。
                    record['spawn_condition'] = record.get(
                        'spawn_condition') or '等待召唤、死亡转换或关卡事件触发'
                elif (self._current_wave_index >= 0
                      and record.get('wave_index', -1) > self._current_wave_index):
                    wait = record.get('wave_max_wait', 0.0)
                    record['spawn_condition'] = '等待上一波清场'
                    if wait and wait > 0:
                        record['spawn_condition'] += f'或最长等待 {wait:g} 秒后进入下一波'
                elif (self._current_fragment_index >= 0
                      and record.get('wave_index', -1) == self._current_wave_index
                      and record.get('fragment_index', -1) > self._current_fragment_index):
                    record['spawn_condition'] = '等待前一片段结束'
                else:
                    record['spawn_condition'] = record.get(
                        'spawn_condition') or '等待关卡调度'
            self._copy_plan_metadata(info, record, 'pending')
        return rows

    # ================= 底层扫描 =================

    def _scan_pass(self, on_chunk, desc, sink=None):
        """对 GC 堆做一次扫描, on_chunk(base, bytes) 回调。
        多路 adb 并行读取 (有界并发, 在飞块数=workers, 内存可控);
        on_chunk 在锁内串行执行, 回调写法与顺序版一致。
        sink 非空时把成功读取的块同时写入 _HeapSnapshot。"""
        targets = self.mc.scan_targets()
        total = sum(e - s for s, e in targets)
        segs = []
        for s, e in targets:
            a = s
            while a < e:
                segs.append((a, min(a + SCAN_CAP, e)))
                a += SCAN_CAP
        done = [0]
        miss = [0]
        t0 = time.time()
        lock = threading.Lock()
        sem = threading.Semaphore(self.workers)   # 有界提交: 在飞任务 ≤ workers

        def job(a, b):
            try:
                try:
                    d = self.mc.read(a, b - a, timeout=30)
                except Exception:
                    d = None   # dd 偶发卡死/超时: 跳过该块, 不让整遍扫描崩
                if d is None:
                    with lock:
                        miss[0] += b - a
                else:
                    if sink is not None:
                        sink.write(a, d)
                    on_chunk(a, d)   # 无锁调用; 各回调用 _merge_lock 自行合并
                with lock:
                    done[0] += b - a
                    el = time.time() - t0
                    pct = done[0] * 100 // total
                    msg = (f"[扫描] {desc} {pct}% ({done[0]/1e6:.0f}/{total/1e6:.0f} MB, "
                           f"{done[0]/1e6/(el+0.01):.0f} MB/s)")
                    print(f"\r{msg}   ", end='', flush=True)
                    if self.progress:
                        self.progress(pct, desc)
            finally:
                sem.release()

        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = []
            for a, b in segs:
                sem.acquire()
                futs.append(ex.submit(job, a, b))
            for f in futs:
                f.result()
        print()
        if miss[0]:
            self.log(f"[扫描] 警告: {miss[0]/1e6:.1f} MB 读取失败被跳过 ({desc})")

    def _scan_pass_local(self, snap, on_chunk, desc):
        """从堆快照重放一次扫描 (零 adb, 磁盘 GB/s 级)"""
        t0 = time.time()
        for base, d in snap.iter_chunks():
            on_chunk(base, d)
        self.log(f"[扫描] {desc} (快照) {time.time()-t0:.1f}s")
        if self.progress:
            self.progress(100, desc)

    def _pass(self, snap, on_chunk, desc):
        """有快照走本地, 否则走网络扫描"""
        if snap is not None:
            self._scan_pass_local(snap, on_chunk, desc)
        else:
            self._scan_pass(on_chunk, desc)

    # ---------------- bootstrap 各阶段 ----------------

    def _find_strings_and_hp(self, snap=None):
        """第 1 遍: enemy_ 字符串对象集合 S + HP 签名位置 P
        (同时把全部扫描块写入快照 snap, 供后续各遍本地复用)"""
        S, P = set(), []
        hp_min, hp_max = HP_MIN, HP_MAX

        def on_chunk(base, d):
            pos = 0
            while True:
                i = d.find(NEEDLE_ENEMY, pos)
                if i < 0:
                    break
                pos = i + 2
                obj = base + i - gs.Il2CppString.CHARS
                if i < gs.Il2CppString.CHARS:
                    continue
                ln = _i32(d, i - gs.Il2CppString.CHARS + gs.Il2CppString.LENGTH)
                if 8 <= ln <= 80:
                    S.add(obj)
            if np is not None:
                q = np.frombuffer(d, dtype='<u8')
                mask = ((q & 0xFFFFFFFF) == 0) & (q >> 32 >= hp_min) & (q >> 32 <= hp_max)
                idx = np.nonzero(mask)[0]
                P.extend((base + int(i) * 8 for i in idx))
            else:
                for off in range(0, len(d) - 8, 8):
                    v = _u64(d, off)
                    if (v & 0xFFFFFFFF) == 0 and hp_min <= v >> 32 <= hp_max:
                        P.append(base + off)

        self._scan_pass(on_chunk, "enemy字符串+HP签名", sink=snap)
        self.log(f"[扫描] 字符串 {len(S)} 个, HP签名 {len(P)} 处")
        return S, P

    def _find_refs(self, S, snap=None):
        """第 2 遍: 指向 S 的指针位置集合 R"""
        R = set()
        if np is not None:
            s_arr = np.array(sorted(S), dtype='<u8')

            def on_chunk(base, d):
                q = np.frombuffer(d, dtype='<u8')
                idx = np.nonzero(np.isin(q, s_arr))[0]
                R.update(base + int(i) * 8 for i in idx)
        else:
            def on_chunk(base, d):
                for off in range(0, len(d) - 8, 8):
                    if _u64(d, off) in S:
                        R.add(base + off)

        self._pass(snap, on_chunk, "字符串引用")
        self.log(f"[扫描] 引用 {len(R)} 处")
        return R

    def _filter_enemies(self, P, R):
        """候选实体 -> klass 名过滤 -> 场上敌人"""
        survivors = []
        for p in P:
            B = p - gs.EntityFields.M_HP
            for x in range(0x100, 0x1A9, 8):
                if B + x in R:
                    survivors.append(B)
                    break
        self.log(f"[扫描] 候选实体 {len(survivors)} 个, 验证 klass ...")
        out = []
        for B in survivors:
            if self.mc.read_klass_name(B) == 'Enemy':
                out.append(B)
                self.log(f"  敌人 @ {hex(B)}")
        return out

    def _find_items_array(self, enemies, snap=None):
        """第 3 遍: 指向敌人的指针 -> items 数组候选 (块内局部解析, 无额外 adb)。
        返回按匹配分降序的候选地址列表 (可能有重复引用的干扰数组, 由第 4 遍验证)。"""
        eset = set(enemies)
        s_arr = np.array(sorted(eset), dtype='<u8') if np is not None else None
        cand = {}  # 数组基址 -> 匹配数

        def on_chunk(base, d):
            if np is not None:
                q = np.frombuffer(d, dtype='<u8')
                hit_idx = np.nonzero(np.isin(q, s_arr))[0]
            else:
                hit_idx = [o // 8 for o in range(0, len(d) - 8, 8) if _u64(d, o) in eset]
            n = len(d) // 8
            for j in hit_idx:
                j = int(j)
                for slot in range(16):
                    a0 = j - slot - gs.Il2CppArray.ITEMS // 8   # 数组基址(qword索引)
                    if a0 < 0:
                        continue
                    cap = _i32(d, a0 * 8 + gs.Il2CppArray.MAX_LENGTH)
                    # cap 只作粗过滤: 扫描发现的敌人数常偏离真实列表长度
                    # (退场对象未回收/非整数血量漏检/扫描期间刷怪),
                    # 精确性交给匹配分排序与第 5 遍 Scheduler 反查
                    if not (1 <= cap <= 300):
                        continue
                    klass = _u64(d, a0 * 8)
                    # klass 指针合理性: 48 位用户态高地址段 (1TB-256TB)。
                    # 不能按具体设备 ASLR 写死范围 (曾写死 0x70-0x72,
                    # 换机后堆映射到 0x74 段导致全部误杀)
                    if not (0x10000000000 <= klass < 0x1000000000000):
                        continue
                    body0 = a0 + gs.Il2CppArray.ITEMS // 8
                    if body0 + cap > n:
                        continue
                    score = 0
                    for k in range(cap):
                        if _u64(d, body0 * 8 + k * 8) in eset:
                            score += 1
                    A = base + a0 * 8
                    with self._merge_lock:
                        if score > cand.get(A, 0):
                            cand[A] = score

        self._pass(snap, on_chunk, "敌人指针")
        if not cand:
            return []
        cands = sorted(((s, a) for a, s in cand.items() if s >= 1), reverse=True)
        self.log(f"[扫描] items 候选 {len(cands)} 个, 最高匹配 {cands[0][0]}/{len(enemies)}")
        return [a for s, a in cands[:32]]

    def _find_list(self, items_cands, expect_cnt, snap=None):
        """第 4 遍: 单遍扫描同时找多个 items 候选的引用 -> List<Enemy> 候选。
        返回 (exact, near): exact=[(L, items), ...] 为 count==expect_cnt 的
        候选 (按 items 匹配分降序), near=[(L, items), ...] 为 count 合理但
        不等于 expect_cnt 的近似候选 (扫描发现的敌人数常因退场未回收/
        漏检/刷怪偏离真实列表长度)。哪个是真 m_managedWaveEnemies
        由第 5 遍 Scheduler 反查判定。"""
        narr = np.array(sorted(items_cands), dtype='<u8') if np is not None else None
        needle_map = {a: struct.pack('<Q', a) for a in items_cands}
        hits = []  # (items_addr, hit_pos)

        def on_chunk(base, d):
            if np is not None:
                q = np.frombuffer(d, dtype='<u8')
                for i in np.nonzero(np.isin(q, narr))[0]:
                    hits.append((int(q[int(i)]), base + int(i) * 8))
            else:
                for a, nd in needle_map.items():
                    pos = 0
                    while True:
                        i = d.find(nd, pos)
                        if i < 0:
                            break
                        hits.append((a, base + i))
                        pos = i + 8

        self._pass(snap, on_chunk, "List指针")
        self.log(f"[扫描] List 引用命中 {len(hits)} 处")
        exact, near = [], []
        seen = set()
        for items in items_cands:   # 已按匹配分降序
            for v, h in hits:
                if v != items:
                    continue
                L = h - gs.ListInternal.ITEMS
                if L in seen:
                    continue
                d = self.mc.read(L, 0x20)
                if not d or _u64(d, gs.ListInternal.ITEMS) != items:
                    continue
                cnt = _i32(d, gs.ListInternal.SIZE)
                if not (0 < cnt <= 300):
                    continue
                seen.add(L)
                if cnt == expect_cnt:
                    exact.append((L, items))
                else:
                    near.append((L, items))
        self.log(f"[扫描] List 候选 {len(exact)} 个 (+近似 {len(near)} 个)")
        return exact, near

    def _find_scheduler_bc(self, list_addrs, snap=None):
        """第 5 遍: 单遍扫描指向任一 List 候选的指针 -> Scheduler -> SchedulerDriver
        -> BattleController。返回 (list_addr, sched_addr, bc_addr);
        哪个候选被真 Scheduler 持有, 哪个才是真 m_managedWaveEnemies。
        全部未命中返回 (0, 0, 0)。"""
        narr = np.array(sorted(list_addrs), dtype='<u8') if np is not None else None
        needle_map = {a: struct.pack('<Q', a) for a in list_addrs}
        hits = []  # (list_addr, hit_pos)

        def on_chunk(base, d):
            if np is not None:
                q = np.frombuffer(d, dtype='<u8')
                for i in np.nonzero(np.isin(q, narr))[0]:
                    hits.append((int(q[int(i)]), base + int(i) * 8))
            else:
                for a, nd in needle_map.items():
                    pos = 0
                    while True:
                        i = d.find(nd, pos)
                        if i < 0:
                            break
                        hits.append((a, base + i))
                        pos = i + 8

        self._pass(snap, on_chunk, "Scheduler指针")
        self.log(f"[扫描] 命中 {len(hits)} 处")
        for L, h in hits:
            X = h - gs.SchedulerFields.M_MANAGED_WAVE_ENEMIES
            d = self.mc.read(X, 0x200)
            if not d:
                continue
            for off in range(0x10, 0x1F8, 8):
                v = _u64(d, off)
                if not self.mc.is_ptr(v):
                    continue
                if self.mc.read_klass_name(v) == 'SchedulerDriver':
                    bc = self.mc.read_ptr(v + gs.SchedulerDriverFields.BATTLE_CONTROLLER)
                    if bc and self.mc.read_klass_name(bc) == 'BattleController':
                        self.log(f"[扫描] List<Enemy> @ {hex(L)} (Scheduler 确认), "
                                 f"BattleController @ {hex(bc)}")
                        return L, X, bc
        return 0, 0, 0

    # ================= bootstrap =================

    def _read_live_enemy_list(self, list_addr):
        data = self._detail_batch_read([(list_addr, 0x20)])[0]
        if not data:
            return None
        items = _u64(data, gs.ListInternal.ITEMS)
        count = _i32(data, gs.ListInternal.SIZE)
        if not (0 <= count <= 300) or (count > 0 and not self.mc.is_ptr(items)):
            return None
        if count == 0:
            self.items_addr = items
            return []
        body = self._detail_batch_read(
            [(items + gs.Il2CppArray.ITEMS, count * 8)])[0]
        if not body:
            return None
        ptrs = [ptr for ptr in (_u64(body, idx * 8) for idx in range(count))
                if self.mc.is_ptr(ptr)]
        self.items_addr = items
        return ptrs

    def _read_live_enemy_unordered(self, unordered_addr):
        """读取 UnitManager.enemies。

        Scheduler 只管理关卡波次敌人；装置、敌人技能和脚本直接召唤且
        managedByScheduler=false 的实例只会注册到 UnitManager。UnorderedArray
        的数组容量远大于 count，尾部还会残留已移除指针，因此只能取前 count 项。
        """
        if not self.mc.is_ptr(unordered_addr):
            return None
        data = self._detail_batch_read([(unordered_addr, 0x28)])[0]
        if not data:
            return None
        items = _u64(data, gs.UnorderedArrayFields.ITEMS)
        count = _i32(data, gs.UnorderedArrayFields.COUNT)
        if not (0 <= count <= 1000) or (count and not self.mc.is_ptr(items)):
            return None
        if not count:
            self._uf_items, self._uf_cnt, self._uf_ptrs = items, 0, []
            return []
        body = self._detail_batch_read([(
            items + gs.Il2CppArray.ITEMS, count * 8)])[0]
        if not body:
            return None
        ptrs = [ptr for ptr in (_u64(body, idx * 8) for idx in range(count))
                if self.mc.is_ptr(ptr)]
        self._uf_items, self._uf_cnt, self._uf_ptrs = items, count, ptrs
        return ptrs

    @staticmethod
    def _union_enemy_ptrs(primary, fallback):
        """稳定去重：UnitManager 顺序优先，Scheduler 作为版本漂移兜底。"""
        out, seen = [], set()
        for ptr in list(primary or ()) + list(fallback or ()):
            if ptr and ptr not in seen:
                seen.add(ptr)
                out.append(ptr)
        return out

    def _resolve_unit_manager(self, bc_addr=None):
        bc_addr = int(bc_addr or self.bc_addr or 0)
        if not self.mc.is_ptr(bc_addr):
            return False
        unit_manager = self._read_ptr(
            bc_addr + gs.BattleControllerFields.UNIT_MANAGER)
        if (not self.mc.is_ptr(unit_manager)
                or self.mc.read_klass_name(unit_manager) != 'UnitManager'):
            return False
        unordered = self._read_ptr(
            unit_manager + gs.UnitManagerFields.ENEMIES)
        if not self.mc.is_ptr(unordered):
            return False
        enemies = self._read_live_enemy_unordered(unordered)
        if enemies is None:
            return False
        self.unit_manager_addr = unit_manager
        self.unit_enemies_addr = unordered
        return True

    def _bootstrap_via_battle_controller(self):
        """设备侧 klass 扫描直达 BC→Scheduler→List；零敌人开局同样可用。"""
        try:
            if self.progress:
                self.progress(5, '定位当前 BattleController')
            # 复用 deploy_tracker 已验证的通用 Il2CppClass/对象扫描器；通道归
            # EnemyReader 所有，定位完成后继续用于高频敌人轮询。
            from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader

            if self._chan is None:
                self._chan = TcpChannel(self.mc)
                self._chan.open()
            locator = DeployTrackerReader(self.mc)
            locator._channel = self._chan
            locator.set_status_callback(self.log)
            objects = locator._scan_class_objects(('BattleController',))
            if not objects:
                return False
            candidates = locator._battle_controller_candidates(
                objects.get('BattleController', ()))
            ranked = locator._rank_live_battle_controllers(candidates)
            for bc_addr in ranked:
                scheduler = self._read_ptr(
                    bc_addr + gs.BattleControllerFields.SCHEDULER)
                if (not self.mc.is_ptr(scheduler)
                        or self.mc.read_klass_name(scheduler) != 'Scheduler'):
                    continue
                list_addr = self._read_ptr(
                    scheduler + gs.SchedulerFields.M_MANAGED_WAVE_ENEMIES)
                if not self.mc.is_ptr(list_addr):
                    continue
                enemies = self._read_live_enemy_list(list_addr)
                if enemies is None:
                    continue
                self.bc_addr = bc_addr
                self.sched_addr = scheduler
                self.list_addr = list_addr
                unit_enemies = []
                if self._resolve_unit_manager(bc_addr):
                    unit_enemies = list(self._uf_ptrs)
                self.enemy_addrs = self._union_enemy_ptrs(unit_enemies, enemies)
                if self.progress:
                    self.progress(75, '读取关卡出怪序列')
                self.log(f"[扫描] BattleController @ {hex(bc_addr)}, "
                         f"Scheduler @ {hex(scheduler)}, 当前注册实例 "
                         f"{len(self.enemy_addrs)} 个"
                         + (f"（UnitManager {len(unit_enemies)}）"
                            if self.unit_enemies_addr else ''))
                return True
        except Exception as exc:
            self.log(f"[扫描] BattleController 快速链失败: {exc}")
        return False

    def _validate_chain(self):
        """验证缓存的地址链是否仍然有效。
        注意: 只锚定 List 地址; items 数组会随列表扩容重新分配, 不作相等校验。"""
        try:
            d = self.mc.read(self.list_addr, 0x20)
            if not d:
                return False
            items, cnt = _u64(d, gs.ListInternal.ITEMS), _i32(d, gs.ListInternal.SIZE)
            if not (0 <= cnt <= 300) or (cnt > 0 and not self.mc.is_ptr(items)):
                return False
            if cnt > 0:
                arr = self.mc.read(items + gs.Il2CppArray.ITEMS, 8)
                if not arr:
                    return False
                e0 = _u64(arr, 0)
                if e0 and self.mc.read_klass_name(e0) != 'Enemy':
                    return False
            self.items_addr = items  # 刷新为当前 items 数组
            if self.with_bc and self.bc_addr:
                if self.mc.read_klass_name(self.bc_addr) != 'BattleController':
                    return False
                # 同一游戏 PID 内换关卡后旧托管对象可能仍滞留在 GC 堆；
                # Unity 原生对象销毁会清空 m_CachedPtr，以此拒绝复用上一局缓存。
                if not self.mc.is_ptr(self.mc.read_ptr(
                        self.bc_addr + gs.BattleControllerFields.UNITY_CACHED_PTR)):
                    return False
                scheduler = self.mc.read_ptr(
                    self.bc_addr + gs.BattleControllerFields.SCHEDULER)
                if (not self.mc.is_ptr(scheduler)
                        or self.mc.read_klass_name(scheduler) != 'Scheduler'):
                    return False
                if self.mc.read_ptr(
                        scheduler + gs.SchedulerFields.M_MANAGED_WAVE_ENEMIES) != self.list_addr:
                    return False
                self.sched_addr = scheduler
                # UnitManager 是实时敌人的权威容器；缓存可来自旧版（尚未保存该
                # 地址），所以每次都从当前 BattleController 重新解析一次。
                if not self._resolve_unit_manager(self.bc_addr):
                    self.unit_manager_addr = 0
                    self.unit_enemies_addr = 0
            return True
        except Exception:
            return False

    def bootstrap(self, force=False):
        """发现地址链 (优先用缓存)"""
        if not force and os.path.isfile(self.cache_file):
            try:
                c = pickle.load(open(self.cache_file, 'rb'))
                if c.get('ver') in (3, 4) and c.get('pid') == self.mc.pid:
                    self.enemy_addrs = c['enemies']
                    self.items_addr = c['items']
                    self.list_addr = c['list']
                    self.sched_addr = c.get('sched', 0)
                    self.bc_addr = c.get('bc', 0)
                    self.unit_manager_addr = c.get('unit_manager', 0)
                    self.unit_enemies_addr = c.get('unit_enemies', 0)
                    if self._validate_chain():
                        scheduler_enemies = self._read_live_enemy_list(self.list_addr) or []
                        self.enemy_addrs = self._union_enemy_ptrs(
                            self._uf_ptrs if self.unit_enemies_addr else [],
                            scheduler_enemies)
                        self.log(f"[缓存] 地址链有效 (敌人 {len(self.enemy_addrs)} 个, "
                                 f"List @ {hex(self.list_addr)})")
                        self._last_bootstrap = time.time()
                        self._load_spawn_plan()
                        self._prefill()
                        return True
            except Exception as e:
                self.log(f"[缓存] 无效: {e}")
            self.log("[缓存] 已失效, 重新扫描 ...")

        # 主路径不依赖场上已有 Enemy：开局即可从关卡 LevelData 取得完整顺序。
        if self.with_bc and self._bootstrap_via_battle_controller():
            pickle.dump({'ver': 4, 'pid': self.mc.pid, 'enemies': self.enemy_addrs,
                         'items': self.items_addr, 'list': self.list_addr,
                         'sched': self.sched_addr, 'bc': self.bc_addr,
                         'unit_manager': self.unit_manager_addr,
                         'unit_enemies': self.unit_enemies_addr},
                        open(self.cache_file, 'wb'))
            self._last_bootstrap = time.time()
            self._load_spawn_plan()
            self._prefill()
            self.log(f"[完成] 开局地址链与预定出怪序列定位完成")
            return True

        t0 = time.time()
        snap = None
        try:
            snap = _HeapSnapshot()   # 1 遍传输 + 4 遍本地复用; 失败回退 5 遍网络扫
        except OSError as e:
            self.log(f"[扫描] 快照不可用 ({e}), 回退多遍网络扫描")
        try:
            S, P = self._find_strings_and_hp(snap=snap)
            R = self._find_refs(S, snap=snap)
            self.enemy_addrs = self._filter_enemies(P, R)
            if not self.enemy_addrs:
                self.log("[扫描] 未发现敌人 (关卡未开始或已全部退场?)")
                return False
            items_cands = self._find_items_array(self.enemy_addrs, snap=snap)
            if not items_cands:
                self.log("[扫描] 未找到 items 数组")
                return False
            exact, near = self._find_list(items_cands, len(self.enemy_addrs), snap=snap)
            if not exact and not near:
                self.log("[扫描] 未找到 List<Enemy> (可在敌人刚出场满血时重扫)")
                return False
            self.sched_addr = self.bc_addr = 0
            self.list_addr = 0
            if self.with_bc:
                cands = [L for L, _ in exact] + [L for L, _ in near]
                L, self.sched_addr, self.bc_addr = self._find_scheduler_bc(cands, snap=snap)
                if L:
                    self.list_addr = L   # 被真 Scheduler 持有的才是活列表
                else:
                    self.log("[扫描] 未找到 BattleController (继续, 仅无战斗状态信息)")
            if not self.list_addr:
                self.list_addr = exact[0][0] if exact else near[0][0]
                self.log(f"[扫描] List<Enemy> @ {hex(self.list_addr)} (取首候选)")
            d = self.mc.read(self.list_addr, 0x20)
            self.items_addr = _u64(d, gs.ListInternal.ITEMS) if d else 0
            if self.bc_addr:
                self._resolve_unit_manager(self.bc_addr)
                self.enemy_addrs = self._union_enemy_ptrs(
                    self._uf_ptrs if self.unit_enemies_addr else [],
                    self.enemy_addrs)
        finally:
            if snap is not None:
                snap.discard()

        pickle.dump({'ver': 4, 'pid': self.mc.pid, 'enemies': self.enemy_addrs,
                     'items': self.items_addr, 'list': self.list_addr,
                     'sched': self.sched_addr, 'bc': self.bc_addr,
                     'unit_manager': self.unit_manager_addr,
                     'unit_enemies': self.unit_enemies_addr},
                    open(self.cache_file, 'wb'))
        self._last_bootstrap = time.time()
        self._load_spawn_plan()
        self._prefill()
        self.log(f"[完成] 扫描耗时 {time.time()-t0:.0f} 秒, 已缓存")
        return True

    def _prefill(self):
        """预热名称/属性缓存, 让 poll_fast 首帧即全速"""
        for ep in self.enemy_addrs:
            full = self._read_enemy(ep, with_runtime=False)
            self._attr_snapshot[ep] = dict(full.attributes)

    # ================= 轮询 =================

    def _fill_attrs(self, ep, blk, info):
        """填充属性 (cachedData 数组地址有缓存, 失效时走完整链重解析)"""
        cd = None
        cdp = self._attr_cache.get(ep, 0)
        if cdp:
            cd = self.mc.read(cdp, 0x20 + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE)
            if not cd or not (0 < _i32(cd, gs.Il2CppArray.MAX_LENGTH) <= 64):
                self._attr_cache.pop(ep, None)
                cd = None
        if cd is None:
            attrp = _u64(blk, gs.EntityFields.M_ATTRIBUTES)
            ab = self.mc.read(attrp, 0x60) if self.mc.is_ptr(attrp) else None
            cdp2 = _u64(ab, gs.AttributesFields.M_CACHED_DATA) if ab else 0
            if cdp2 and self.mc.is_ptr(cdp2):
                cd2 = self.mc.read(
                    cdp2, 0x20 + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE)
                if cd2 and 0 < _i32(cd2, gs.Il2CppArray.MAX_LENGTH) <= 64:
                    self._attr_cache[ep] = cdp2
                    cd = cd2
        if cd:
            self._apply_cached_data(cd, info)
        return info

    @staticmethod
    def _apply_cached_data(cd, info):
        base = gs.Il2CppArray.ITEMS
        count = min(_i32(cd, gs.Il2CppArray.MAX_LENGTH), gs.AttributeType.E_NUM)
        attrs = {}
        for idx in range(max(0, count)):
            o = base + idx * gs.OBSCURED_FP_SIZE
            if o + 16 > len(cd):
                break
            attrs[idx] = gs.obscured_fp_to_float(_u64(cd, o), _u64(cd, o + 8))
        info.attributes = attrs
        info.max_hp = attrs.get(gs.AttributeType.MAX_HP, 0.0)
        info.atk = attrs.get(gs.AttributeType.ATK, 0.0)
        info.def_ = attrs.get(gs.AttributeType.DEF, 0.0)
        info.res = attrs.get(gs.AttributeType.MAGIC_RESISTANCE, 0.0)
        info.mspd = attrs.get(gs.AttributeType.MOVE_SPEED, 0.0)
        info.aspd = attrs.get(gs.AttributeType.ATTACK_SPEED, 0.0)

    @staticmethod
    def _apply_raw_data(raw, info):
        base = gs.Il2CppArray.ITEMS
        count = min(_i32(raw, gs.Il2CppArray.MAX_LENGTH), gs.AttributeType.E_NUM)
        values = {}
        for idx in range(max(0, count)):
            o = base + idx * gs.OBSCURED_FP_SIZE
            if o + 16 > len(raw):
                break
            values[idx] = gs.obscured_fp_to_float(_u64(raw, o), _u64(raw, o + 8))
        info.raw_attributes = values

    def _fill_skills(self, ep, blk, info):
        """慢速路径技能 CD 解析: m_skills List -> EnemySkill -> PeriodicTimer
        (period=总CD, remaining=剩余CD) + ESkillData.prefabKey (技能名缓存)"""
        out = []
        lp = _u64(blk, gs.EnemyFields.M_SKILLS) if len(blk) >= gs.EnemyFields.READ_SIZE else 0
        if self.mc.is_ptr(lp):
            self._skill_lp[ep] = lp
            hd = self.mc.read(lp, 0x20)
            items = _u64(hd, gs.ListInternal.ITEMS) if hd else 0
            n = _i32(hd, gs.ListInternal.SIZE) if hd else 0
            if 0 < n <= 8 and self.mc.is_ptr(items):
                arr = self.mc.read(items + gs.Il2CppArray.ITEMS, n * 8)
                for j in range(n if arr else 0):
                    s = _u64(arr, j * 8)
                    if not self.mc.is_ptr(s):
                        continue
                    sb = self.mc.read(s, 0x90)
                    if not sb:
                        continue
                    t = _u64(sb, gs.EnemySkillFields.M_COOLDOWN_TIMER)
                    td = self.mc.read(t, 0x20) if self.mc.is_ptr(t) else None
                    if not td:
                        continue
                    period = gs.fp_to_float(_u64(td, gs.PeriodicTimerFields.M_PERIOD_TIME))
                    remain = gs.fp_to_float(_u64(td, gs.PeriodicTimerFields.M_REMAINING_TIME))
                    if not (0 <= period <= 3600):
                        continue
                    key = self._skill_names.get(s)
                    if key is None:
                        dp = _u64(sb, gs.EnemySkillFields.DATA)
                        dd = self.mc.read(dp, 0x28) if self.mc.is_ptr(dp) else None
                        pk = _u64(dd, gs.ESkillDataFields.PREFAB_KEY) if dd else 0
                        key = (self.mc.read_ustring(pk) if self.mc.is_ptr(pk) else None) or '?'
                        self._skill_names[s] = key
                    out.append((key, remain, period))
        info.skills = out
        self._skill_cd[ep] = out
        return info

    def _fill_name(self, ep, blk, info):
        """填充名称 (只读一次, 之后走缓存)"""
        if ep not in self._names:
            eid = self.mc.read_ustring(_u64(blk, gs.EntityFields.ID)) or ''
            if self._db is None:
                self._db = load_enemy_db()
            ent = self._db.get(eid, {})
            self._names[ep] = (eid, ent.get('name') or eid, ent.get('code') or '')
        info.eid, info.name, info.code = self._names[ep]
        return info

    @staticmethod
    def _parse_enemy_block(ep, blk):
        """解析 Enemy 主对象块；不跟随指针，供慢速与聚簇快读共用。"""
        info = EnemyInfo(ep)
        if not blk or len(blk) < 0x148:
            info.alive = False
            return info
        info.hp = gs.fp_to_float(_u64(blk, gs.EntityFields.M_HP))
        info.es = gs.fp_to_float(_u64(blk, gs.EntityFields.M_ES))
        info.direction = _i32(blk, gs.EntityFields.M_DIRECTION)
        info.finish = _i32(blk, gs.EntityFields.FINISH_REASON)
        info.id_ptr = _u64(blk, gs.EntityFields.ID)
        info.attr_ptr = _u64(blk, gs.EntityFields.M_ATTRIBUTES)
        info.state_ptr = _u64(blk, gs.EntityFields.M_STATE_MACHINE)
        info.ep_ptr = _u64(blk, gs.EntityFields.M_EP_ARRAY)
        info.ep_controller_ptr = _u64(blk, gs.EntityFields.M_EP_CONTROLLER)
        info.shield_controller_ptr = _u64(blk, gs.EntityFields.M_SHIELD_CONTROLLER)
        info.buff_container_ptr = _u64(blk, gs.EntityFields.BUFF_CONTAINER)
        if len(blk) >= gs.EnemyFields.READ_SIZE:
            info.pos_x, info.pos_y = _f32x2(blk, gs.EnemyFields.M_POS_IN_LAST_FRAME)
            info.blk_x, info.blk_y = _f32x2(blk, gs.EnemyFields.M_BLOCK_POSITION)
            info.spawn_row = _i32(blk, gs.EnemyFields.ROUTE_SPAWN_POS)
            info.spawn_col = _i32(blk, gs.EnemyFields.ROUTE_SPAWN_POS + 4)
            options = gs.EnemyFields.OPTIONS
            info.is_summon = bool(
                blk[options + gs.EnemyOptionsFields.IS_SUMMON])
            info.action_ptr = _u64(
                blk, options + gs.EnemyOptionsFields.ACTION_DATA)
        info.alive = info.hp > 0 and info.finish == 0
        return info

    @staticmethod
    def _decode_short_array(data, limit):
        if not data or len(data) < gs.Il2CppArray.ITEMS:
            return [0] * limit
        count = min(max(0, _i32(data, gs.Il2CppArray.MAX_LENGTH)), limit)
        out = [0] * limit
        for idx in range(count):
            off = gs.Il2CppArray.ITEMS + idx * 2
            if off + 2 > len(data):
                break
            out[idx] = struct.unpack_from('<h', data, off)[0]
        return out

    @staticmethod
    def _decode_fp_array(data, limit):
        if not data or len(data) < gs.Il2CppArray.ITEMS:
            return {}
        count = min(max(0, _i32(data, gs.Il2CppArray.MAX_LENGTH)), limit)
        out = {}
        for idx in range(count):
            off = gs.Il2CppArray.ITEMS + idx * 8
            if off + 8 > len(data):
                break
            out[idx] = gs.fp_to_float(_u64(data, off))
        return out

    @staticmethod
    def _copy_runtime(info, runtime):
        if not runtime:
            return
        info.state_id = runtime.get('state_id', info.state_id)
        info.shield = runtime.get('shield', info.shield)
        info.ep_remaining = dict(runtime.get('ep_remaining', {}))
        info.ep_break_recovery = bool(runtime.get('ep_break_recovery', False))
        info.abnormal_flags = list(runtime.get('abnormal_flags', info.abnormal_flags))
        info.abnormal_immunes = list(runtime.get('abnormal_immunes', info.abnormal_immunes))
        info.abnormal_antis = list(runtime.get('abnormal_antis', info.abnormal_antis))
        info.abnormal_combos = list(runtime.get('abnormal_combos', info.abnormal_combos))
        info.abnormal_combo_immunes = list(
            runtime.get('abnormal_combo_immunes', info.abnormal_combo_immunes))

    def _fill_runtime_slow(self, info):
        """无 TCP 通道时的完整状态读取兜底。"""
        state = self.mc.read(info.state_ptr + gs.StateMachineFields.CURRENT_STATE_ID, 4) \
            if self.mc.is_ptr(info.state_ptr) else None
        ep = self.mc.read(
            info.ep_ptr, gs.Il2CppArray.ITEMS + gs.ElementType.E_NUM * 8) \
            if self.mc.is_ptr(info.ep_ptr) else None
        shield_ptr = info.shield_controller_ptr
        shield = self.mc.read(shield_ptr + gs.ShieldUIControllerFields.M_SHIELD_TO_SHOW, 8) \
            if self.mc.is_ptr(shield_ptr) else None
        epc = self.mc.read(info.ep_controller_ptr + gs.EPControllerFields.M_IS_IN_BREAK_RECOVERY, 1) \
            if self.mc.is_ptr(info.ep_controller_ptr) else None
        attr = self.mc.read(info.attr_ptr, 0x40) if self.mc.is_ptr(info.attr_ptr) else None
        ptrs = {}
        if attr:
            ptrs = {
                'flags': _u64(attr, gs.AttributesFields.M_ABNORMAL_FLAGS_COUNTER),
                'immunes': _u64(attr, gs.AttributesFields.M_ABNORMAL_IMMUNE_COUNTER),
                'antis': _u64(attr, gs.AttributesFields.M_ABNORMAL_ANTI_COUNTER),
            }
            combo_mgr = _u64(attr, gs.AttributesFields.M_ABNORMAL_COMBO_MGR)
            combo = self.mc.read(combo_mgr, 0x20) if self.mc.is_ptr(combo_mgr) else None
            if combo:
                ptrs['combos'] = _u64(combo, gs.AbnormalComboManagerFields.M_ABNORMAL_COMBO_COUNTER)
                ptrs['combo_immunes'] = _u64(
                    combo, gs.AbnormalComboManagerFields.M_ABNORMAL_COMBO_IMMUNE_COUNTER)
        arrays = {}
        sizes = {
            'flags': gs.AbnormalFlag.E_NUM, 'immunes': gs.AbnormalFlag.E_NUM,
            'antis': gs.AbnormalFlag.E_NUM, 'combos': gs.AbnormalCombo.E_NUM,
            'combo_immunes': gs.AbnormalCombo.E_NUM,
        }
        for key, count in sizes.items():
            p = ptrs.get(key, 0)
            arrays[key] = self._decode_short_array(
                self.mc.read(p, gs.Il2CppArray.ITEMS + count * 2)
                if self.mc.is_ptr(p) else None, count)
        runtime = {
            'state_id': _i32(state, 0) if state else gs.EnemyState.DEFAULT,
            'shield': gs.fp_to_float(_u64(shield, 0)) if shield else 0.0,
            'ep_remaining': self._decode_fp_array(ep, gs.ElementType.E_NUM),
            'ep_break_recovery': bool(epc and epc[0]),
            'abnormal_flags': arrays['flags'],
            'abnormal_immunes': arrays['immunes'],
            'abnormal_antis': arrays['antis'],
            'abnormal_combos': arrays['combos'],
            'abnormal_combo_immunes': arrays['combo_immunes'],
        }
        self._runtime_snapshot[info.addr] = runtime
        self._runtime_ptrs[info.addr] = dict(ptrs, state=info.state_ptr, ep=info.ep_ptr,
                                             epc=info.ep_controller_ptr, shield=shield_ptr)
        self._copy_runtime(info, runtime)

    def _read_enemy(self, ep, with_runtime=True):
        blk = self.mc.read(ep, gs.EnemyFields.READ_SIZE)
        info = self._parse_enemy_block(ep, blk)
        if not blk or len(blk) < 0x148:
            return info
        self._fill_name(ep, blk, info)
        self._fill_attrs(ep, blk, info)
        self._fill_skills(ep, blk, info)
        if with_runtime:
            self._fill_runtime_slow(info)
        return info

    def poll(self):
        """读取一帧快照; 返回 dict"""
        snap = {'ok': False, 'state': -1, 'speed_level': -1, 'time_scale': 0.0,
                'play_time': 0.0, 'scheduler_time': None, 'enemies': [], 'msg': '',
                'on_field_count': 0, 'planned_count': self.planned_count}
        d = self.mc.read(self.list_addr, 0x20)
        if not d:
            snap['msg'] = 'List 读取失败'
            return self._on_stale(snap)
        items, cnt = _u64(d, gs.ListInternal.ITEMS), _i32(d, gs.ListInternal.SIZE)
        if not (0 <= cnt <= 300) or (cnt > 0 and not self.mc.is_ptr(items)):
            snap['msg'] = f'List 数据异常 (cnt={cnt})'
            return self._on_stale(snap)

        scheduler_ptrs = []
        if cnt > 0:
            arr = self.mc.read(items + gs.Il2CppArray.ITEMS, cnt * 8)
            if not arr:
                snap['msg'] = 'items 读取失败'
                return self._on_stale(snap)
            scheduler_ptrs = [
                _u64(arr, i * 8) for i in range(cnt)
                if self.mc.is_ptr(_u64(arr, i * 8))]

        unit_ptrs = self._read_live_enemy_unordered(self.unit_enemies_addr) \
            if self.unit_enemies_addr else None
        ptrs = self._union_enemy_ptrs(unit_ptrs, scheduler_ptrs)
        self.enemy_addrs = ptrs
        observed_enemies = []
        for ep in ptrs:
            if not ep or not self.mc.is_ptr(ep):
                continue
            # 回退路径避免为每个敌人逐指针启动十余次 adb 子进程；沿用最近一次
            # 快速通道的状态快照。详情按钮仍会按需做完整读取。
            info = self._read_enemy(ep, with_runtime=False)
            self._copy_runtime(info, self._runtime_snapshot.get(ep))
            observed_enemies.append(info)

        snap['enemies'] = self._merge_enemy_roster(
            observed_enemies, self._spawned_count())
        snap['on_field_count'] = sum(enemy.alive for enemy in observed_enemies)
        snap['planned_count'] = self.planned_count

        if self.bc_addr:
            b = self.mc.read(self.bc_addr + 0x200, 0xC0)
            if b:
                snap['state'] = _i32(b, gs.BattleControllerFields.M_STATE - 0x200)
                snap['speed_level'] = _i32(b, gs.BattleControllerFields.M_SPEED_LEVEL - 0x200)
                snap['time_scale'] = struct.unpack_from(
                    '<f', b, gs.BattleControllerFields.M_TIME_SCALE - 0x200)[0]
                snap['play_time'] = struct.unpack_from(
                    '<f', b, gs.BattleControllerFields.M_REAL_PLAY_TIME - 0x200)[0]

        if self._bc_static_fields:
            raw_clock = self.mc.read(
                self._bc_static_fields
                + gs.BattleControllerStaticFields.FIXED_PLAY_TIME, 8)
            snap['scheduler_time'] = self._decode_battle_clock(raw_clock)

        snap['enemies'] = self._apply_spawn_timing(
            snap['enemies'], snap['scheduler_time'])

        snap['ok'] = True
        self._stale_cnt = 0
        return snap

    def close(self):
        """关闭常驻 TCP 通道"""
        if self._chan is not None:
            try:
                self._chan.close()
            except Exception:
                pass
            self._chan = None
        if self._detail_chan is not None:
            try:
                self._detail_chan.close()
            except Exception:
                pass
            self._detail_chan = None

    CHAN_RETRY_SEC = 5.0   # 通道失败后的重建冷却 (open 含 adb 部署, 每帧重试太贵)

    def poll_fast(self):
        """准实时轮询 (稳态 ~15-25ms/帧): 常驻 TCP 通道 (设备侧 nc -L sh +
        adb forward, raw 二进制)。稳态每帧仅 1 次敌人簇 dd; List 头每 4
        帧/属性轮换每 3 帧/BC 每 10 帧搭车同批。通道异常 -> 回退慢速 poll()。"""
        if self._chan is None:
            if time.time() - self._chan_dead_ts < self.CHAN_RETRY_SEC:
                return self.poll()   # 冷却期内直接慢速, 避免每帧昂贵重连
            self._chan = TcpChannel(self.mc)
        try:
            snap = self._poll_fast_impl()
            self._chan_fail = 0
            return snap
        except Exception as e:
            self._chan_fail += 1
            if self._chan_fail <= 3 or self._chan_fail % 50 == 0:
                self.log(f'[轮询] 通道异常 ({type(e).__name__}: {e}), 本帧回退慢速读')
            self.close()
            self._chan_dead_ts = time.time()
            return self.poll()

    @staticmethod
    def _cluster_ptrs(ptrs, gap=0x10000):
        """敌人指针按地址聚簇 (每簇一次 dd)"""
        if not ptrs:
            return []
        sp = sorted(ptrs)
        clusters = [[sp[0]]]
        for p in sp[1:]:
            if p - clusters[-1][-1] <= gap:
                clusters[-1].append(p)
            else:
                clusters.append([p])
        return clusters

    def _refresh_runtime_chan(self, eps, infos):
        """批量刷新状态机、损伤条、异常状态/免疫计数和护盾。

        Attributes 里的五个计数数组需要一次跟随指针。指针只在对象换代时重建，
        稳态刷新全部敌人仍然只有一次 batch_read 往返。
        """
        if not eps:
            return

        # 主对象中可直接得到的指针每轮同步；Attributes 换对象时丢弃旧计数数组。
        missing = []
        for ep in eps:
            info = infos.get(ep)
            if info is None:
                continue
            rp = self._runtime_ptrs.setdefault(ep, {})
            if rp.get('attr_obj') != info.attr_ptr:
                for key in ('flags', 'immunes', 'antis', 'combos', 'combo_immunes'):
                    rp.pop(key, None)
                rp['attr_obj'] = info.attr_ptr
            rp.update(state=info.state_ptr, ep=info.ep_ptr, epc=info.ep_controller_ptr,
                      shield=info.shield_controller_ptr)
            if not all(rp.get(k) for k in ('flags', 'immunes', 'antis',
                                            'combos', 'combo_immunes')):
                missing.append(ep)

        # 第一次：Attributes -> 三个 flag 数组 + combo manager。
        attr_eps = [ep for ep in missing
                    if self.mc.is_ptr(self._runtime_ptrs[ep].get('attr_obj', 0))]
        if attr_eps:
            reqs = [(self._runtime_ptrs[ep]['attr_obj'], 0x40) for ep in attr_eps]
            combo_mgrs = {}
            for ep, data in zip(attr_eps, self._chan.batch_read(reqs)):
                if not data:
                    continue
                rp = self._runtime_ptrs[ep]
                rp['flags'] = _u64(data, gs.AttributesFields.M_ABNORMAL_FLAGS_COUNTER)
                rp['immunes'] = _u64(data, gs.AttributesFields.M_ABNORMAL_IMMUNE_COUNTER)
                rp['antis'] = _u64(data, gs.AttributesFields.M_ABNORMAL_ANTI_COUNTER)
                combo = _u64(data, gs.AttributesFields.M_ABNORMAL_COMBO_MGR)
                if self.mc.is_ptr(combo):
                    combo_mgrs[ep] = combo
            if combo_mgrs:
                ceps = list(combo_mgrs)
                for ep, data in zip(
                        ceps, self._chan.batch_read([(combo_mgrs[x], 0x20) for x in ceps])):
                    if data:
                        self._runtime_ptrs[ep]['combos'] = _u64(
                            data, gs.AbnormalComboManagerFields.M_ABNORMAL_COMBO_COUNTER)
                        self._runtime_ptrs[ep]['combo_immunes'] = _u64(
                            data, gs.AbnormalComboManagerFields.M_ABNORMAL_COMBO_IMMUNE_COUNTER)

        reqs, keys = [], []
        for ep in eps:
            rp = self._runtime_ptrs.get(ep, {})
            specs = (
                ('state', rp.get('state', 0) + gs.StateMachineFields.CURRENT_STATE_ID, 4),
                ('ep', rp.get('ep', 0), gs.Il2CppArray.ITEMS + gs.ElementType.E_NUM * 8),
                ('shield', rp.get('shield', 0) + gs.ShieldUIControllerFields.M_SHIELD_TO_SHOW, 8),
                ('epc', rp.get('epc', 0) + gs.EPControllerFields.M_IS_IN_BREAK_RECOVERY, 1),
                ('flags', rp.get('flags', 0),
                 gs.Il2CppArray.ITEMS + gs.AbnormalFlag.E_NUM * 2),
                ('immunes', rp.get('immunes', 0),
                 gs.Il2CppArray.ITEMS + gs.AbnormalFlag.E_NUM * 2),
                ('antis', rp.get('antis', 0),
                 gs.Il2CppArray.ITEMS + gs.AbnormalFlag.E_NUM * 2),
                ('combos', rp.get('combos', 0),
                 gs.Il2CppArray.ITEMS + gs.AbnormalCombo.E_NUM * 2),
                ('combo_immunes', rp.get('combo_immunes', 0),
                 gs.Il2CppArray.ITEMS + gs.AbnormalCombo.E_NUM * 2),
            )
            for kind, addr, size in specs:
                if self.mc.is_ptr(addr):
                    reqs.append((addr, size))
                    keys.append((ep, kind))

        runtime = {ep: dict(self._runtime_snapshot.get(ep, {})) for ep in eps}
        for (ep, kind), data in zip(keys, self._chan.batch_read(reqs) if reqs else []):
            if not data:
                continue
            cur = runtime[ep]
            if kind == 'state':
                cur['state_id'] = _i32(data, 0)
            elif kind == 'ep':
                cur['ep_remaining'] = self._decode_fp_array(data, gs.ElementType.E_NUM)
            elif kind == 'shield':
                cur['shield'] = gs.fp_to_float(_u64(data, 0))
            elif kind == 'epc':
                cur['ep_break_recovery'] = bool(data[0])
            elif kind in ('flags', 'immunes', 'antis'):
                cur['abnormal_' + kind] = self._decode_short_array(data, gs.AbnormalFlag.E_NUM)
            elif kind == 'combos':
                cur['abnormal_combos'] = self._decode_short_array(data, gs.AbnormalCombo.E_NUM)
            elif kind == 'combo_immunes':
                cur['abnormal_combo_immunes'] = self._decode_short_array(
                    data, gs.AbnormalCombo.E_NUM)

        for ep in eps:
            self._runtime_snapshot[ep] = runtime[ep]
            info = infos.get(ep)
            if info is not None:
                self._copy_runtime(info, runtime[ep])

    LIST_EVERY = 4    # List 头每 4 tick 读一次 (检测刷怪/退场; 其余帧沿用上一帧指针)
    ATTR_EVERY = 3    # 每 3 tick 轮换刷新 1 个敌人的属性 (摊平尖峰)
    BC_EVERY = 2      # BC 块 (状态/倍速/时间) 每 2 tick 读一次，供出场倒计时
    SKILL_EVERY = 5   # 每 5 tick 通道内批量刷新全部敌人技能 CD
    STATUS_EVERY = 2  # 状态/损伤条每 2 tick 批量刷新 (约 20-32ms)
    SPAWN_QUEUE_EVERY = 4  # 当前 ActionItem 队列约每 4 tick 校验一次

    def _poll_fast_impl(self):
        t0 = time.time()
        snap = {'ok': False, 'state': -1, 'speed_level': -1, 'time_scale': 0.0,
                'play_time': 0.0, 'scheduler_time': None,
                'enemies': [], 'msg': '', 'frame_ms': 0.0,
                'on_field_count': 0, 'planned_count': self.planned_count}
        self._fast_tick += 1
        tick = self._fast_tick
        prev_ptrs = self._f_ptrs
        read_list = (tick % self.LIST_EVERY == 1) or not prev_ptrs

        # ---- 组装本帧唯一一批请求 (稳态 = 1 簇 dd; 辅助读取降频搭车) ----
        reqs, slot = [], {}
        if read_list:
            slot['list'] = len(reqs)
            reqs.append((self.list_addr, 0x20))
            if self.unit_enemies_addr:
                slot['unit_enemies'] = len(reqs)
                reqs.append((self.unit_enemies_addr, 0x28))
        clusters = self._cluster_ptrs(prev_ptrs)
        slot['c0'] = len(reqs)
        reqs += [(c[0], c[-1] + gs.EnemyFields.READ_SIZE - c[0]) for c in clusters]
        if prev_ptrs and tick % self.ATTR_EVERY == 0:
            aep = prev_ptrs[(tick // self.ATTR_EVERY) % len(prev_ptrs)]
            cdp = self._attr_cache.get(aep, 0)
            if cdp:
                slot['attr'] = (len(reqs), aep)
                reqs.append((cdp, 0x20 + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE))
            else:
                ap = self._attr_ptrs.get(aep, 0)
                if ap:
                    slot['attrp'] = (len(reqs), aep)
                    reqs.append((ap, 0x60))
        if self.bc_addr and tick % self.BC_EVERY == 0:
            slot['bc'] = len(reqs)
            reqs.append((self.bc_addr + 0x200, 0xC0))
            if self._bc_static_fields:
                slot['scheduler_clock'] = len(reqs)
                reqs.append((
                    self._bc_static_fields
                    + gs.BattleControllerStaticFields.FIXED_PLAY_TIME, 8))
        if self.sched_addr:
            slot['scheduler'] = len(reqs)
            reqs.append((self.sched_addr, 0xC8))
        res = self._chan.batch_read(reqs) if reqs else []

        # ---- 实时敌人容器（降频读取）----
        # Scheduler List 用 _version；UnitManager.enemies 是 UnorderedArray，没有
        # version，敌人一进一出时 count 甚至可能不变，所以每次都重读前 count 个槽。
        ptrs = prev_ptrs
        if read_list:
            d = res[slot['list']]
            if not d:
                snap['msg'] = 'List 读取失败'
                return self._on_stale(snap)
            items = _u64(d, gs.ListInternal.ITEMS)
            cnt = _i32(d, gs.ListInternal.SIZE)
            version = _i32(d, gs.ListInternal.VERSION)
            if not (0 <= cnt <= 300) or (cnt > 0 and not self.mc.is_ptr(items)):
                snap['msg'] = f'List 数据异常 (cnt={cnt})'
                return self._on_stale(snap)

            unit_items = unit_cnt = 0
            unit_valid = False
            if 'unit_enemies' in slot:
                ud = res[slot['unit_enemies']]
                if ud:
                    unit_items = _u64(ud, gs.UnorderedArrayFields.ITEMS)
                    unit_cnt = _i32(ud, gs.UnorderedArrayFields.COUNT)
                    unit_valid = (0 <= unit_cnt <= 1000
                                  and (not unit_cnt or self.mc.is_ptr(unit_items)))

            array_reqs, array_kinds = [], []
            if cnt:
                array_reqs.append((items + gs.Il2CppArray.ITEMS, cnt * 8))
                array_kinds.append(('scheduler', cnt))
            if unit_valid and unit_cnt:
                array_reqs.append((unit_items + gs.Il2CppArray.ITEMS, unit_cnt * 8))
                array_kinds.append(('unit', unit_cnt))
            scheduler_ptrs = []
            unit_ptrs = [] if unit_valid else list(self._uf_ptrs)
            array_data = self._chan.batch_read(array_reqs) if array_reqs else []
            for (kind, count), arr in zip(array_kinds, array_data):
                if not arr:
                    if kind == 'scheduler':
                        snap['msg'] = 'Scheduler items 读取失败'
                        return self._on_stale(snap)
                    unit_ptrs = list(self._uf_ptrs)
                    continue
                values = [p for p in (_u64(arr, i * 8) for i in range(count))
                          if self.mc.is_ptr(p)]
                if kind == 'scheduler':
                    scheduler_ptrs = values
                else:
                    unit_ptrs = values
            if unit_valid and not unit_cnt:
                unit_ptrs = []
            ptrs = self._union_enemy_ptrs(unit_ptrs, scheduler_ptrs)
            self._uf_items, self._uf_cnt, self._uf_ptrs = \
                unit_items, unit_cnt, unit_ptrs
            if ptrs != prev_ptrs:
                clusters = self._cluster_ptrs(ptrs)
                cluster_res = self._chan.batch_read(
                    [(c[0], c[-1] + gs.EnemyFields.READ_SIZE - c[0])
                     for c in clusters]) if clusters else []
            else:
                cluster_res = None
            self._f_items, self._f_cnt, self._f_ptrs, self._f_version = \
                items, cnt, ptrs, version
            self.enemy_addrs = ptrs
        else:
            cluster_res = None
        if cluster_res is None:
            cluster_res = res[slot['c0']:slot['c0'] + len(clusters)]

        # ---- 解析敌人块 (hp/direction/finish + id/attr 指针 + 坐标) ----
        infos = {}
        for c, data in zip(clusters, cluster_res):
            if not data:
                continue
            for ep in c:
                off = ep - c[0]
                if off + gs.EnemyFields.READ_SIZE > len(data):
                    continue
                blk = data[off:off + gs.EnemyFields.READ_SIZE]
                info = self._parse_enemy_block(ep, blk)
                infos[ep] = info
                self._attr_ptrs[ep] = info.attr_ptr
                skl = _u64(data, off + gs.EnemyFields.M_SKILLS)
                if self.mc.is_ptr(skl):
                    self._skill_lp[ep] = skl

        # ---- 新敌人: 通道内解析名称+属性 (仅列表变化帧触发) ----
        new_eps = [ep for ep in ptrs if ep not in self._names or ep not in self._attr_snapshot]
        if new_eps:
            self._fill_new_enemies_chan(new_eps, infos)

        # ---- 状态机 / 异常状态 / 免疫 / 五种损伤条 ----
        runtime_missing = any(ep not in self._runtime_snapshot for ep in ptrs)
        if ptrs and (runtime_missing or tick % self.STATUS_EVERY == 0):
            self._refresh_runtime_chan(ptrs, infos)

        # ---- 属性轮换刷新 (每 ATTR_EVERY 帧 1 个敌人) ----
        if 'attr' in slot:
            i, aep = slot['attr']
            cd = res[i]
            if cd and 0 < _i32(cd, gs.Il2CppArray.MAX_LENGTH) <= 64:
                tmp = EnemyInfo(aep)
                self._apply_cached_data(cd, tmp)
                self._attr_snapshot[aep] = dict(tmp.attributes)
            else:
                self._attr_cache.pop(aep, None)   # 数组已失效, 下轮重建
        elif 'attrp' in slot:
            i, aep = slot['attrp']
            d = res[i]
            cdp = _u64(d, gs.AttributesFields.M_CACHED_DATA) if d else 0
            if cdp and self.mc.is_ptr(cdp):
                self._attr_cache[aep] = cdp

        # ---- 技能 CD 批量刷新 (每 SKILL_EVERY 帧一轮) ----
        if ptrs and tick % self.SKILL_EVERY == 0:
            self._refresh_skills_chan(ptrs)

        live = set(ptrs)
        enemies = []
        for ep in ptrs:
            info = infos.get(ep)
            if info is None:
                continue
            nm = self._names.get(ep)
            if nm:
                info.eid, info.name, info.code = nm
            s = self._attr_snapshot.get(ep)
            if s:
                info.attributes = dict(s)
                info.max_hp = s.get(gs.AttributeType.MAX_HP, 0.0)
                info.atk = s.get(gs.AttributeType.ATK, 0.0)
                info.def_ = s.get(gs.AttributeType.DEF, 0.0)
                info.res = s.get(gs.AttributeType.MAGIC_RESISTANCE, 0.0)
                info.mspd = s.get(gs.AttributeType.MOVE_SPEED, 0.0)
                info.aspd = s.get(gs.AttributeType.ATTACK_SPEED, 0.0)
            self._copy_runtime(info, self._runtime_snapshot.get(ep))
            info.skills = self._skill_cd.get(ep, [])
            enemies.append(info)
        # 清理已退场敌人的缓存 (地址可能被 GC 复用)
        for cache in (self._names, self._attr_cache, self._attr_snapshot, self._attr_ptrs,
                      self._runtime_snapshot, self._runtime_ptrs,
                      self._skill_lp, self._skill_cd):
            for ep in list(cache):
                if ep not in live:
                    cache.pop(ep, None)
        # ---- BC 块 ----
        if 'bc' in slot:
            b = res[slot['bc']]
            if b:
                self._bc_snap = (
                    _i32(b, gs.BattleControllerFields.M_STATE - 0x200),
                    _i32(b, gs.BattleControllerFields.M_SPEED_LEVEL - 0x200),
                    struct.unpack_from('<f', b, gs.BattleControllerFields.M_TIME_SCALE - 0x200)[0],
                    struct.unpack_from('<f', b, gs.BattleControllerFields.M_REAL_PLAY_TIME - 0x200)[0])
        if self._bc_snap:
            (snap['state'], snap['speed_level'],
             snap['time_scale'], snap['play_time']) = self._bc_snap
        if 'scheduler_clock' in slot:
            value = self._decode_battle_clock(res[slot['scheduler_clock']])
            if value is not None:
                self._scheduler_time_snap = value
        snap['scheduler_time'] = self._scheduler_time_snap

        # ---- Scheduler 当前 ActionItem 队列 / 未出场 ETA ----
        scheduler_data = res[slot['scheduler']] if 'scheduler' in slot else None
        spawned_count = (_i32(scheduler_data, gs.SchedulerFields.M_SPAWNED_ENEMIES_CNT)
                         if scheduler_data else 0)
        if (scheduler_data and (tick % self.SPAWN_QUEUE_EVERY == 1
                                or not self._action_queue_entries)):
            self._refresh_action_queue_chan(scheduler_data)
        rows = self._merge_enemy_roster(enemies, spawned_count)
        snap['enemies'] = self._apply_spawn_timing(
            rows, snap['scheduler_time'])
        snap['on_field_count'] = sum(enemy.alive for enemy in enemies)
        snap['planned_count'] = self.planned_count

        snap['ok'] = True
        snap['frame_ms'] = round((time.time() - t0) * 1000, 1)
        self._stale_cnt = 0
        return snap

    def _refresh_skills_chan(self, ptrs):
        """通道内批量刷新全部敌人技能 CD: 列表头 -> items -> EnemySkill 块 ->
        PeriodicTimer 共 4 轮 batch; 技能静态名 (ESkillData.prefabKey) 仅首见时
        再读 2 轮, 之后走 _skill_names 缓存"""
        eps = [ep for ep in ptrs if self.mc.is_ptr(self._skill_lp.get(ep, 0))]
        if not eps:
            return
        heads = self._chan.batch_read([(self._skill_lp[ep], 0x20) for ep in eps])
        n_of, reqs, keys = {}, [], []
        for ep, d in zip(eps, heads):
            if not d:
                continue                          # 读失败保留旧快照
            items, n = _u64(d, gs.ListInternal.ITEMS), _i32(d, gs.ListInternal.SIZE)
            if n == 0:
                self._skill_cd[ep] = []
            elif 0 < n <= 8 and self.mc.is_ptr(items):
                n_of[ep] = n
                reqs.append((items + gs.Il2CppArray.ITEMS, n * 8))
                keys.append(ep)
        sks_of, reqs2, keys2 = {}, [], []
        if reqs:
            for ep, d in zip(keys, self._chan.batch_read(reqs)):
                if not d:
                    continue
                sks = [s for s in (_u64(d, j * 8) for j in range(n_of[ep]))
                       if self.mc.is_ptr(s)]
                sks_of[ep] = sks
                for s in sks:
                    reqs2.append((s, 0x90))
                    keys2.append((ep, s))
        timers, datas = {}, {}
        if reqs2:
            for (ep, s), d in zip(keys2, self._chan.batch_read(reqs2)):
                if not d:
                    continue
                t = _u64(d, gs.EnemySkillFields.M_COOLDOWN_TIMER)
                dp = _u64(d, gs.EnemySkillFields.DATA)
                if self.mc.is_ptr(t):
                    timers[s] = t
                if s not in self._skill_names and self.mc.is_ptr(dp):
                    datas[s] = dp
        remain_of = {}
        if timers:
            sks = list(timers)
            for s, d in zip(sks, self._chan.batch_read([(timers[s], 0x20) for s in sks])):
                if not d:
                    continue
                period = gs.fp_to_float(_u64(d, gs.PeriodicTimerFields.M_PERIOD_TIME))
                remain = gs.fp_to_float(_u64(d, gs.PeriodicTimerFields.M_REMAINING_TIME))
                if 0 <= period <= 3600 and -1 <= remain <= 3600:
                    remain_of[s] = (remain, period)
        if datas:   # 首见技能: data 块 -> prefabKey 字符串
            pks = {}
            sks = list(datas)
            for s, d in zip(sks, self._chan.batch_read([(datas[s], 0x28) for s in sks])):
                if d:
                    pk = _u64(d, gs.ESkillDataFields.PREFAB_KEY)
                    if self.mc.is_ptr(pk):
                        pks[s] = pk
            if pks:
                sks = list(pks)
                for s, d in zip(sks, self._chan.batch_read([(pks[s], 0x80) for s in sks])):
                    if d and 0 < _i32(d, gs.Il2CppString.LENGTH) <= 64:
                        ln = _i32(d, gs.Il2CppString.LENGTH)
                        try:
                            self._skill_names[s] = d[gs.Il2CppString.CHARS:
                                                     gs.Il2CppString.CHARS + ln * 2
                                                     ].decode('utf-16-le') or '?'
                        except Exception:
                            pass
        for ep, sks in sks_of.items():
            self._skill_cd[ep] = [(self._skill_names.get(s, '?'), r, p)
                                  for s in sks if s in remain_of
                                  for r, p in (remain_of[s],)]
        # 技能对象随敌人退场释放, 修剪名称缓存防地址复用串名
        live_sks = {s for sks in sks_of.values() for s in sks}
        for s in list(self._skill_names):
            if s not in live_sks:
                self._skill_names.pop(s, None)

    def _fill_new_enemies_chan(self, new_eps, infos):
        """新敌人通道内解析: 第 1 批 id 字符串+Attributes 块, 第 2 批 cachedData"""
        if self._db is None:
            self._db = load_enemy_db()
        reqs, keys = [], []
        for ep in new_eps:
            info = infos.get(ep)
            if info is None:
                continue
            if info.id_ptr and self.mc.is_ptr(info.id_ptr):
                reqs.append((info.id_ptr, 0x80))
                keys.append(('id', ep))
            if info.attr_ptr and self.mc.is_ptr(info.attr_ptr):
                reqs.append((info.attr_ptr, 0x60))
                keys.append(('attr', ep))
        cdps = {}
        if reqs:
            for (kind, ep), d in zip(keys, self._chan.batch_read(reqs)):
                if kind == 'id':
                    eid = ''
                    if d and 0 < _i32(d, gs.Il2CppString.LENGTH) <= 128:
                        ln = _i32(d, gs.Il2CppString.LENGTH)
                        try:
                            eid = d[gs.Il2CppString.CHARS:
                                    gs.Il2CppString.CHARS + ln * 2].decode('utf-16-le')
                        except Exception:
                            eid = ''
                    ent = self._db.get(eid, {})
                    self._names[ep] = (eid, ent.get('name') or eid, ent.get('code') or '')
                else:
                    cdp = _u64(d, gs.AttributesFields.M_CACHED_DATA) if d else 0
                    if cdp and self.mc.is_ptr(cdp):
                        cdps[ep] = cdp
        if cdps:
            eps = list(cdps)
            reqs = [(cdps[ep], 0x20 + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE)
                    for ep in eps]
            for ep, cd in zip(eps, self._chan.batch_read(reqs)):
                if cd and 0 < _i32(cd, gs.Il2CppArray.MAX_LENGTH) <= 64:
                    self._attr_cache[ep] = cdps[ep]
                    tmp = EnemyInfo(ep)
                    self._apply_cached_data(cd, tmp)
                    self._attr_snapshot[ep] = dict(tmp.attributes)
        # 通道内未解决的走一次完整慢读兜底
        for ep in new_eps:
            if ep not in self._names or ep not in self._attr_snapshot:
                full = self._read_enemy(ep, with_runtime=False)
                if ep not in self._names:
                    self._names[ep] = (full.eid, full.name, full.code)
                if ep not in self._attr_snapshot:
                    self._attr_snapshot[ep] = dict(full.attributes)
                if ep not in infos:
                    infos[ep] = full

    def _detail_batch_read(self, reqs):
        """批量读取；详情线程走独立端口，绝不占住高频轮询通道。"""
        if not reqs:
            return []
        if getattr(self._detail_context, 'active', False):
            if self._detail_chan is None:
                self._detail_chan = TcpChannel(self.mc, port=DETAIL_TCP_PORT)
            return self._detail_chan.batch_read(reqs)
        if self._chan is not None:
            return self._chan.batch_read(reqs)
        return [self.mc.read(addr, size) for addr, size in reqs]

    def _read_strings(self, ptrs, max_chars=256):
        unique = [p for p in dict.fromkeys(ptrs) if self.mc.is_ptr(p)]
        if not unique:
            return {}
        size = gs.Il2CppString.CHARS + max_chars * 2
        out = {}
        for ptr, data in zip(unique, self._detail_batch_read([(p, size) for p in unique])):
            if not data or len(data) < gs.Il2CppString.CHARS:
                continue
            count = _i32(data, gs.Il2CppString.LENGTH)
            if not (0 <= count <= max_chars):
                continue
            try:
                out[ptr] = data[gs.Il2CppString.CHARS:
                                gs.Il2CppString.CHARS + count * 2].decode('utf-16-le')
            except UnicodeDecodeError:
                continue
        return out

    def _read_blackboards(self, bb_ptrs):
        """读取 Blackboard(List<DataPair>)；DataPair 步长为 0x18。"""
        unique = [p for p in dict.fromkeys(bb_ptrs) if self.mc.is_ptr(p)]
        result = {p: [] for p in unique}
        if not unique:
            return result
        heads = self._detail_batch_read([(p, 0x20) for p in unique])
        arrays = {}
        reqs, owners = [], []
        for ptr, head in zip(unique, heads):
            if not head:
                continue
            items, count = _u64(head, gs.ListInternal.ITEMS), _i32(head, gs.ListInternal.SIZE)
            if 0 < count <= 256 and self.mc.is_ptr(items):
                reqs.append((items + gs.Il2CppArray.ITEMS, count * 0x18))
                owners.append((ptr, count))
        for (ptr, count), data in zip(owners, self._detail_batch_read(reqs)):
            if data:
                arrays[ptr] = (count, data)
        string_ptrs = []
        parsed = {}
        for ptr, (count, data) in arrays.items():
            rows = []
            for idx in range(count):
                off = idx * 0x18
                if off + 0x18 > len(data):
                    break
                key_ptr = _u64(data, off)
                value = struct.unpack_from('<f', data, off + 8)[0]
                value_str_ptr = _u64(data, off + 0x10)
                string_ptrs.extend((key_ptr, value_str_ptr))
                rows.append((key_ptr, value, value_str_ptr))
            parsed[ptr] = rows
        strings = self._read_strings(string_ptrs)
        for ptr, rows in parsed.items():
            result[ptr] = [
                {'key': strings.get(kp, ''), 'value': value,
                 'value_str': strings.get(sp, '') if sp else ''}
                for kp, value, sp in rows
            ]
        return result

    @staticmethod
    def _mask_names(mask, names):
        return [names.get(idx, str(idx)) for idx in range(64) if mask & (1 << idx)]

    def _read_plain_fp_arrays(self, ptrs):
        unique = [p for p in dict.fromkeys(ptrs) if self.mc.is_ptr(p)]
        if not unique:
            return {}
        size = gs.Il2CppArray.ITEMS + gs.AttributeType.E_NUM * 8
        return {ptr: self._decode_fp_array(data, gs.AttributeType.E_NUM)
                for ptr, data in zip(unique, self._detail_batch_read([(p, size) for p in unique]))
                if data}

    def _read_active_buffs(self, container_ptr):
        """读取敌人 BuffContainer 中当前有效的 Buff。"""
        if not self.mc.is_ptr(container_ptr):
            return []
        (container,) = self._detail_batch_read([(container_ptr, 0x30)])
        dbl_ptr = _u64(container, gs.BuffContainerFields.M_BUFFS) if container else 0
        if not self.mc.is_ptr(dbl_ptr):
            return []
        (dbl,) = self._detail_batch_read([(dbl_ptr, 0x28)])
        list_ptr = _u64(dbl, gs.DoubleBufferedListFields.M_INTERNAL_LIST) if dbl else 0
        if not self.mc.is_ptr(list_ptr):
            return []
        (head,) = self._detail_batch_read([(list_ptr, 0x20)])
        if not head:
            return []
        items, count = _u64(head, gs.ListInternal.ITEMS), _i32(head, gs.ListInternal.SIZE)
        if not (0 < count <= 512 and self.mc.is_ptr(items)):
            return []
        (array,) = self._detail_batch_read(
            [(items + gs.Il2CppArray.ITEMS, count * 0x10)])
        if not array:
            return []
        ptrs = [_u64(array, idx * 0x10) for idx in range(count)
                if idx * 0x10 + 8 <= len(array)]
        ptrs = [p for p in ptrs if self.mc.is_ptr(p)]
        blocks = self._detail_batch_read([(p, gs.BuffFields.READ_SIZE) for p in ptrs])
        records = [(p, data) for p, data in zip(ptrs, blocks) if data]
        if not records:
            return []

        string_ptrs, bb_ptrs, fp_ptrs = [], [], []
        for _, data in records:
            string_ptrs.extend((_u64(data, gs.BuffFields.KEY),
                                _u64(data, gs.BuffFields.OVERRIDE_KEY),
                                _u64(data, gs.BuffFields.EFFECT_KEY)))
            bb_ptrs.append(_u64(data, gs.BuffFields.M_BLACKBOARD))
            fp_ptrs.extend(_u64(data, off) for off in (
                gs.BuffFields.M_ATTRIBUTE_MULTIPLIERS,
                gs.BuffFields.M_ATTRIBUTE_ADDITIONS,
                gs.BuffFields.M_ATTRIBUTE_FINAL_ADDITIONS,
                gs.BuffFields.M_ATTRIBUTE_FINAL_SCALERS))
        strings = self._read_strings(string_ptrs)
        blackboards = self._read_blackboards(bb_ptrs)
        fp_arrays = self._read_plain_fp_arrays(fp_ptrs)

        out = []
        for ptr, data in records:
            mask = _u64(data, gs.BuffFields.ATTRIBUTE_MASK)
            mul_ptr = _u64(data, gs.BuffFields.M_ATTRIBUTE_MULTIPLIERS)
            add_ptr = _u64(data, gs.BuffFields.M_ATTRIBUTE_ADDITIONS)
            fadd_ptr = _u64(data, gs.BuffFields.M_ATTRIBUTE_FINAL_ADDITIONS)
            scale_ptr = _u64(data, gs.BuffFields.M_ATTRIBUTE_FINAL_SCALERS)
            mul = fp_arrays.get(mul_ptr, {})
            add = fp_arrays.get(add_ptr, {})
            fadd = fp_arrays.get(fadd_ptr, {})
            scale = fp_arrays.get(scale_ptr, {})
            modifiers = []
            for idx in range(gs.AttributeType.E_NUM):
                if not (mask & (1 << idx)):
                    continue
                modifiers.append({
                    'index': idx,
                    'key': gs.ATTRIBUTE_INTERNAL_NAMES.get(idx, str(idx)),
                    'name': gs.ATTRIBUTE_CN_NAMES.get(idx, str(idx)),
                    'addition': add.get(idx, 0.0),
                    'multiplier': mul.get(idx, 0.0),
                    'final_addition': fadd.get(idx, 0.0),
                    'final_scaler': scale.get(idx, 1.0),
                })
            source = _u64(data, gs.BuffFields.M_SOURCE)
            source_name = ''
            if source in self._names:
                source_name = self._names[source][1]
            key_ptr = _u64(data, gs.BuffFields.KEY)
            override_ptr = _u64(data, gs.BuffFields.OVERRIDE_KEY)
            effect_ptr = _u64(data, gs.BuffFields.EFFECT_KEY)
            bb_ptr = _u64(data, gs.BuffFields.M_BLACKBOARD)
            out.append({
                'addr': ptr,
                'key': strings.get(key_ptr, '') or '?',
                'override_key': strings.get(override_ptr, ''),
                'effect_key': strings.get(effect_ptr, ''),
                'instance_uid': struct.unpack_from('<I', data, gs.BuffFields.INSTANCE_UID)[0],
                'priority': _i32(data, gs.BuffFields.PRIORITY),
                'life_time': gs.fp_to_float(_u64(data, gs.BuffFields.M_LIFE_TIME)),
                'remaining_time': gs.fp_to_float(_u64(data, gs.BuffFields.M_REMAINING_TIME)),
                'existing_time': gs.fp_to_float(_u64(data, gs.BuffFields.M_EXISTING_TIME)),
                'trigger_count': _i32(data, gs.BuffFields.M_TRIGGER_CNT),
                'stack_count': _i32(data, gs.BuffFields.M_STACK_CNT),
                'max_valid_stack_count': _i32(data, gs.BuffFields.M_MAX_VALID_STACK_CNT),
                'enabled': bool(data[gs.BuffFields.IS_ACTUALLY_ENABLED]),
                'valid': bool(data[gs.BuffFields.IS_VALID]),
                'finished': bool(data[gs.BuffFields.IS_FINISHED]),
                'ep_break_buff': bool(data[gs.BuffFields.IS_EP_BREAK_BUFF]),
                'source_addr': source,
                'source': source_name or (hex(source) if source else '关卡/无实体来源'),
                'ability_addr': _u64(data, gs.BuffFields.M_ABILITY),
                'attribute_modifiers': modifiers,
                'abnormal_flags': self._mask_names(
                    _u64(data, gs.BuffFields.ABNORMAL_FLAG_MASK),
                    gs.ABNORMAL_FLAG_CN_NAMES),
                'abnormal_immunes': self._mask_names(
                    _u64(data, gs.BuffFields.ABNORMAL_IMMUNE_MASK),
                    gs.ABNORMAL_FLAG_CN_NAMES),
                'abnormal_antis': self._mask_names(
                    _u64(data, gs.BuffFields.ABNORMAL_ANTI_MASK),
                    gs.ABNORMAL_FLAG_CN_NAMES),
                'abnormal_combos': self._mask_names(
                    _u64(data, gs.BuffFields.ABNORMAL_COMBO_MASK),
                    gs.ABNORMAL_COMBO_CN_NAMES),
                'abnormal_combo_immunes': self._mask_names(
                    _u64(data, gs.BuffFields.ABNORMAL_COMBO_IMMUNE_MASK),
                    gs.ABNORMAL_COMBO_CN_NAMES),
                'has_shield': bool(data[gs.BuffFields.HAS_SHIELD]),
                'shield_mask': _i32(data, gs.BuffFields.SHIELD_MASK),
                'blackboard': blackboards.get(bb_ptr, []),
            })
        return out

    def _read_global_buffs(self, selected_addr=0):
        """读取 BattleController.m_globalBuffs，并解析精确目标映射。"""
        if not self.bc_addr:
            return []
        (slot,) = self._detail_batch_read(
            [(self.bc_addr + gs.BattleControllerFields.M_GLOBAL_BUFFS, 8)])
        list_ptr = _u64(slot, 0) if slot else 0
        if not self.mc.is_ptr(list_ptr):
            return []
        (head,) = self._detail_batch_read([(list_ptr, 0x20)])
        if not head:
            return []
        items, count = _u64(head, gs.ListInternal.ITEMS), _i32(head, gs.ListInternal.SIZE)
        if not (0 < count <= 256 and self.mc.is_ptr(items)):
            return []
        (array,) = self._detail_batch_read([(items + gs.Il2CppArray.ITEMS, count * 8)])
        if not array:
            return []
        ptrs = [_u64(array, idx * 8) for idx in range(count)]
        ptrs = [p for p in ptrs if self.mc.is_ptr(p)]
        records = [(p, data) for p, data in zip(
            ptrs, self._detail_batch_read([(p, gs.GlobalBuffFields.READ_SIZE) for p in ptrs]))
                   if data]
        if not records:
            return []

        string_ptrs = [_u64(data, gs.GlobalBuffFields.KEY) for _, data in records]
        bb_ptrs = [_u64(data, gs.GlobalBuffFields.BLACKBOARD) for _, data in records]
        strings = self._read_strings(string_ptrs)
        blackboards = self._read_blackboards(bb_ptrs)

        # Dictionary<ObjectPtr<Entity>, List<uint>>：Entry 步长 0x20，key 在 +8。
        map_ptrs = [_u64(data, gs.GlobalBuffFields.TARGET_MAP) for _, data in records]
        valid_maps = [p for p in map_ptrs if self.mc.is_ptr(p)]
        map_targets = {p: [] for p in valid_maps}
        map_heads = self._detail_batch_read([(p, 0x30) for p in valid_maps])
        entry_reqs, entry_owners = [], []
        for mp, mh in zip(valid_maps, map_heads):
            if not mh:
                continue
            entries, used = _u64(mh, 0x18), _i32(mh, 0x20)
            if 0 < used <= 2048 and self.mc.is_ptr(entries):
                entry_reqs.append((entries + gs.Il2CppArray.ITEMS, used * 0x20))
                entry_owners.append((mp, used))
        for (mp, used), data in zip(entry_owners, self._detail_batch_read(entry_reqs)):
            if not data:
                continue
            for idx in range(used):
                off = idx * 0x20
                if off + 0x20 > len(data) or _i32(data, off) < 0:
                    continue
                target = _u64(data, off + 8)
                if self.mc.is_ptr(target):
                    map_targets[mp].append(target)

        # GlobalBuff._buffs 中的静态 BuffData 概览。
        buff_arrays = [_u64(data, gs.GlobalBuffFields.BUFFS) for _, data in records]
        valid_arrays = [p for p in buff_arrays if self.mc.is_ptr(p)]
        array_heads = self._detail_batch_read([(p, 0x20) for p in valid_arrays])
        data_ptrs_by_array = {p: [] for p in valid_arrays}
        data_reqs, data_owners = [], []
        for ap, ah in zip(valid_arrays, array_heads):
            if not ah:
                continue
            n = _i32(ah, gs.Il2CppArray.MAX_LENGTH)
            if 0 < n <= 128:
                data_reqs.append((ap + gs.Il2CppArray.ITEMS, n * 8))
                data_owners.append((ap, n))
        all_data_ptrs = []
        for (ap, n), data in zip(data_owners, self._detail_batch_read(data_reqs)):
            if not data:
                continue
            vals = [_u64(data, idx * 8) for idx in range(n)]
            vals = [p for p in vals if self.mc.is_ptr(p)]
            data_ptrs_by_array[ap] = vals
            all_data_ptrs.extend(vals)
        data_blocks = {p: data for p, data in zip(
            all_data_ptrs,
            self._detail_batch_read([(p, gs.BuffDataFields.READ_SIZE) for p in all_data_ptrs]))
                       if data}
        data_string_ptrs = []
        for data in data_blocks.values():
            data_string_ptrs.extend((_u64(data, gs.BuffDataFields.BUFF_KEY),
                                     _u64(data, gs.BuffDataFields.TEMPLATE_KEY),
                                     _u64(data, gs.BuffDataFields.DURATION_KEY)))
        data_strings = self._read_strings(data_string_ptrs)

        side_names = {0: '友方', 1: '敌方', 2: '中立', 3: '全部'}
        out = []
        for ptr, data in records:
            key_ptr = _u64(data, gs.GlobalBuffFields.KEY)
            bb_ptr = _u64(data, gs.GlobalBuffFields.BLACKBOARD)
            map_ptr = _u64(data, gs.GlobalBuffFields.TARGET_MAP)
            buff_array = _u64(data, gs.GlobalBuffFields.BUFFS)
            targets = map_targets.get(map_ptr, [])
            buff_defs = []
            for dp in data_ptrs_by_array.get(buff_array, []):
                dd = data_blocks.get(dp)
                if not dd:
                    continue
                buff_defs.append({
                    'buff_key': data_strings.get(_u64(dd, gs.BuffDataFields.BUFF_KEY), ''),
                    'template_key': data_strings.get(
                        _u64(dd, gs.BuffDataFields.TEMPLATE_KEY), ''),
                    'duration_key': data_strings.get(
                        _u64(dd, gs.BuffDataFields.DURATION_KEY), ''),
                    'life_time_type': dd[gs.BuffDataFields.LIFE_TIME_TYPE],
                    'life_time': struct.unpack_from('<f', dd, gs.BuffDataFields.LIFE_TIME)[0],
                    'priority': _i32(dd, gs.BuffDataFields.PRIORITY),
                })
            source_type = _i32(data, gs.GlobalBuffFields.SOURCE_TYPE)
            out.append({
                'addr': ptr,
                'key': strings.get(key_ptr, '') or '?',
                'instance_uid': struct.unpack_from(
                    '<I', data, gs.GlobalBuffFields.INSTANCE_UID)[0],
                'source_type': source_type,
                'source_name': side_names.get(source_type, str(source_type)),
                'target_count': len(targets),
                'target_addrs': targets,
                'applies_to_selected': bool(selected_addr and selected_addr in targets),
                'blackboard': blackboards.get(bb_ptr, []),
                'buff_defs': buff_defs,
            })
        return out

    def read_enemy_detail(self, addr, heavy_only=False):
        """按需读取一个敌人的详情。

        heavy_only 用于实时详情线程：只取原始属性、Buff 与关卡效果，HP/状态/
        损伤条/技能由同一帧主轮询对象提供。读取期间使用 27274 独立通道。
        """
        if not self.mc.is_ptr(addr):
            return None
        self._detail_context.active = True
        try:
            return self._read_enemy_detail_impl(addr, heavy_only)
        finally:
            self._detail_context.active = False

    def _read_enemy_detail_impl(self, addr, heavy_only=False):
        (blk,) = self._detail_batch_read([(addr, gs.EnemyFields.READ_SIZE)])
        if not blk or len(blk) < 0x148:
            return None
        info = self._parse_enemy_block(addr, blk)
        if not heavy_only:
            self._fill_name(addr, blk, info)

        # 同时读取原始和最终属性，详情页可直接比较 Buff 前后变化。
        (attr_head,) = self._detail_batch_read([(info.attr_ptr, 0x60)]) \
            if self.mc.is_ptr(info.attr_ptr) else (None,)
        if attr_head:
            raw_ptr = _u64(attr_head, gs.AttributesFields.M_RAW_DATA)
            cached_ptr = _u64(attr_head, gs.AttributesFields.M_CACHED_DATA)
            reqs, kinds = [], []
            size = gs.Il2CppArray.ITEMS + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE
            if self.mc.is_ptr(raw_ptr):
                reqs.append((raw_ptr, size)); kinds.append('raw')
            if self.mc.is_ptr(cached_ptr):
                reqs.append((cached_ptr, size)); kinds.append('cached')
            for kind, data in zip(kinds, self._detail_batch_read(reqs)):
                if not data:
                    continue
                if kind == 'raw':
                    self._apply_raw_data(data, info)
                else:
                    self._apply_cached_data(data, info)
                    self._attr_cache[addr] = cached_ptr
                    self._attr_snapshot[addr] = dict(info.attributes)
        elif addr in self._attr_snapshot:
            info.attributes = dict(self._attr_snapshot[addr])

        if not heavy_only:
            if self._chan is not None:
                self._refresh_runtime_chan([addr], {addr: info})
            else:
                self._fill_runtime_slow(info)
            info.skills = list(self._skill_cd.get(addr, []))
        info.buffs = self._read_active_buffs(info.buff_container_ptr)
        info.global_buffs = self._read_global_buffs(addr)
        return info

    def _on_stale(self, snap):
        self._stale_cnt += 1
        if self._stale_cnt >= 3 and time.time() - self._last_bootstrap > 300:
            self.log("[轮询] 数据链失效, 重新扫描 ...")
            if self.bootstrap(force=True):
                self._stale_cnt = 0
                snap['msg'] += ' (已重建)'
            else:
                self._last_bootstrap = time.time()  # 5 分钟内不再重试
                snap['msg'] += ' (重建失败, 可能已退出关卡)'
        return snap
