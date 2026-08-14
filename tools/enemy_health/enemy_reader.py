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

import copy
import math
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
from .precise_position import PrecisePositionReader

NEEDLE_ENEMY = 'enemy_'.encode('utf-16-le')   # UTF-16LE "enemy_"
HP_MIN, HP_MAX = 50, 1_000_000                # HP 签名高32位范围
SCAN_CAP = 32 * 1024 * 1024                   # 每块 32MB
DETAIL_TCP_PORT = 27274                        # 与敌人主轮询/RNG/部署通道隔离

# 早期敌人有少量护盾并未接入后来统一的 IShieldSource / ShieldUIController。
# 这些护盾把实时剩余值放在 Buff Blackboard 中；规则集中放在这里，避免把
# 敌人地址或关卡地址写死在扫描流程中。鼠王的屏障由 a/b/c 三段组成，三段
# dynamic 相加才是完整的、仅吸收法术伤害的剩余屏障值。
CUSTOM_SHIELD_RULES = (
    {
        'enemy_ids': frozenset({'enemy_1509_mousek'}),
        'buff_prefix': 'mousek_shield[',
        'value_keys': frozenset({'dynamic'}),
        'mask': 4,  # DamageTypeMask.MAGICAL
        'label': '法术屏障',
    },
)

# 这些类型都继承 SelectorTrigger，运行时共享 m_lastTarget@0x38 布局。
# 具体派生类覆写 Search 时仍可能附带额外条件，因此只有“已有有效目标”可以
# 直接判定通过；空目标不能反向断言下一次 Search 一定失败。
SELECTOR_TRIGGER_TYPES = frozenset({
    'SelectorTrigger', 'BoomberangAttackTrigger', 'EntityOnRouteTrigger',
    'HalfIdleLhdoorSkillTrigger', 'HalfIdleLhportSkillTrigger',
    'HunterBulletTrigger', 'RangedSelectorTrigger', 'SelectorOrAlwaysTrigger',
    'SelectorTriggerWithCertainCondition',
})


def _custom_shield_rule(enemy_id='', buff_key=''):
    key = (buff_key or '').lower()
    for rule in CUSTOM_SHIELD_RULES:
        enemy_ids = rule.get('enemy_ids', ())
        if enemy_ids and enemy_id and enemy_id not in enemy_ids:
            continue
        if key.startswith(rule['buff_prefix']):
            return rule
    return None


def summarize_custom_shields(buffs, enemy_id=''):
    """汇总未接入 ShieldUIController 的旧式 Buff 护盾。

    返回 ``(剩余值, 伤害类型掩码, 来源列表)``。来源列表同时保留 Blackboard
    数值地址，供主轮询在发现一次后直接刷新，不必持续重扫完整 Buff 链。
    """
    total = 0.0
    mask = 0
    sources = []
    for buff in buffs or ():
        rule = _custom_shield_rule(enemy_id, buff.get('key', ''))
        if not rule:
            continue
        active = (buff.get('enabled', True) and buff.get('valid', True)
                  and not buff.get('finished', False))
        for row in buff.get('blackboard') or ():
            if row.get('key') not in rule['value_keys']:
                continue
            value = row.get('value', 0.0)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                continue
            value = max(0.0, float(value))
            if active:
                total += value
                mask |= rule['mask']
            sources.append({
                'buff_addr': buff.get('addr', 0),
                'buff_key': buff.get('key', ''),
                'value_addr': row.get('value_addr', 0),
                'value': value,
                'mask': rule['mask'],
                'label': rule['label'],
                'active': active,
            })
    return total, mask, sources

if getattr(sys, 'frozen', False):
    # 打包模式: _MEIPASS 是每次启动重建的临时目录, 缓存放 exe 旁以便跨启动复用
    CACHE_FILE = os.path.join(os.path.dirname(sys.executable), 'enemy_cache.pkl')
else:
    CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'enemy_cache.pkl')


def _u64(b, o):
    return struct.unpack_from('<Q', b, o)[0]


def _i32(b, o):
    return struct.unpack_from('<i', b, o)[0]


def _u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def _f32x2(b, o):
    return struct.unpack_from('<2f', b, o)


def seconds_to_frames(seconds, frame_duration=1.0 / 30.0):
    """把可靠的游戏时间倒计时换算为逻辑帧；无倒计时返回 ``None``。"""
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
        return None
    if seconds < 0:
        return None
    if not isinstance(frame_duration, (int, float)) or not math.isfinite(frame_duration):
        frame_duration = 1.0 / 30.0
    frame_duration = max(1.0 / 240.0, min(1.0, float(frame_duration)))
    return max(0, int(math.ceil(max(0.0, float(seconds)) / frame_duration - 1e-7)))


def spine_track_remaining(animation_start, animation_end, track_time,
                          entry_scale=1.0, state_scale=1.0,
                          skeleton_scale=1.0, loop=False):
    """计算 Spine 非循环 TrackEntry 距动画内容终点的游戏时间。

    ``AnimationState.Update`` 的现网汇编顺序为 SkeletonAnimation.timeScale ×
    AnimationState.timeScale × TrackEntry.timeScale；TrackEntry.trackTime 已包含
    已播放进度。循环轨道没有“当前动作结束”语义，因此明确返回 ``None``。
    """
    values = (animation_start, animation_end, track_time, entry_scale,
              state_scale, skeleton_scale)
    if loop or not all(isinstance(value, (int, float)) and math.isfinite(value)
                       for value in values):
        return None
    duration = float(animation_end) - float(animation_start)
    speed = float(entry_scale) * float(state_scale) * float(skeleton_scale)
    if duration < 0 or duration > 3600 or speed <= 0 or speed > 10000:
        return None
    if track_time < -3600 or track_time > 1_000_000_000:
        return None
    return max(0.0, duration - float(track_time)) / speed


def countdown_text(action):
    """动作倒计时的统一短文本，供敌我两个表格复用。"""
    action = action or {}
    frames = action.get('remaining_frames')
    seconds = action.get('remaining')
    kind = action.get('remaining_kind') or ''
    parts = []
    if isinstance(frames, int) and frames >= 0:
        parts.append(f'{frames} 帧')
    if isinstance(seconds, (int, float)) and math.isfinite(seconds) and seconds >= 0:
        parts.append(f'{seconds:.2f} 秒')
    if parts:
        text = ' / '.join(parts)
        return f'{text}（{kind}）' if kind else text
    return kind or '条件驱动'


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
                 'data_ptr',
                 'pos_x', 'pos_y', 'precise_pos_x', 'precise_pos_y',
                 'precise_pos_valid', 'blk_x', 'blk_y', 'spawn_row', 'spawn_col', 'skills',
                 'state_ptr', 'state_id', 'ep_ptr', 'ep_controller_ptr',
                 'shield_controller_ptr', 'es', 'shield',
                 'special_shield', 'special_shield_mask', 'special_shield_sources',
                 'ep_remaining', 'ep_break_recovery', 'buff_container_ptr',
                 'attributes', 'raw_attributes', 'abnormal_flags', 'abnormal_immunes',
                 'abnormal_antis', 'abnormal_combos', 'abnormal_combo_immunes',
                 'status_timers',
                 'buffs', 'global_buffs', 'roster_id', 'spawn_order', 'wave_index',
                 'fragment_index', 'action_index', 'spawn_index', 'route_index',
                 'lifecycle', 'planned', 'spawn_eta', 'spawn_condition',
                 'spawn_kind', 'spawn_source', 'is_summon', 'action_ptr', 'action',
                 'skills_detail', 'current_tile_ptr', 'spawn_frame', 'end_frame',
                 'end_reason')

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
        self.data_ptr = 0
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.precise_pos_x = 0.0
        self.precise_pos_y = 0.0
        self.precise_pos_valid = False
        self.blk_x = 0.0
        self.blk_y = 0.0
        self.spawn_row = 0
        self.spawn_col = 0
        self.skills = []          # [(prefabKey, remaining, period), ...]
        # 技能判定元数据 [{name, remaining, period, priority, sp_cost,
        # max_triggers, trigger_count, has_trigger, cast_like_attack}, ...]
        self.skills_detail = []
        self.state_ptr = 0
        self.state_id = gs.EnemyState.DEFAULT
        self.ep_ptr = 0
        self.ep_controller_ptr = 0
        self.shield_controller_ptr = 0
        self.es = 0.0
        self.shield = 0.0
        self.special_shield = 0.0
        self.special_shield_mask = 0
        self.special_shield_sources = []
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
        # "flag:<index>" / "combo:<index>" ->
        # {remaining: float|None, infinite: bool, source_count: int}
        self.status_timers = {}
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
        self.spawn_frame = None
        self.end_frame = None
        self.end_reason = ''
        # m_currentTile 原始指针 (未校验): 非空且是合法指针 = 实体正站在地图
        # 格子上, 是「已出场」的硬性信号, 优先级高于路线投影估算。
        self.current_tile_ptr = 0
        # 当前动作链的结构化快照。phase/name 用于主表；其余字段在详情页展示。
        # 地址和时间均来自运行时对象，不根据技能 CD 猜测“正在施放”。
        self.action = {}

    def attribute(self, index, default=0.0):
        return self.attributes.get(index, default)

    @property
    def total_shield(self):
        return max(0.0, self.shield) + max(0.0, self.special_shield)

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
        def decorate(name, timer):
            if timer.get('infinite'):
                return name + '（无限）'
            if isinstance(timer.get('remaining'), (int, float)):
                return name + f"（{max(0.0, timer['remaining']):.2f}s）"
            return name

        entries = []
        for kind, values, names in (
                ('flag', self.abnormal_flags, gs.ABNORMAL_FLAG_CN_NAMES),
                ('combo', self.abnormal_combos, gs.ABNORMAL_COMBO_CN_NAMES)):
            for index, count in enumerate(values):
                if count <= 0:
                    continue
                entries.append(decorate(
                    names.get(index, str(index)),
                    self.status_timers.get(f'{kind}:{index}') or {}))
        state_status = {
            gs.EnemyState.STUN: ('眩晕', 'flag:0'),
            gs.EnemyState.FROZEN: ('冻结', 'flag:16'),
            gs.EnemyState.LEVITATE: ('浮空', 'flag:25'),
            gs.EnemyState.PALSY: ('麻痹', 'flag:39'),
            gs.EnemyState.UNBALANCE: ('失衡', ''),
        }.get(self.state_id)
        if state_status and not any(text.startswith(state_status[0]) for text in entries):
            entries.append(decorate(
                state_status[0], self.status_timers.get(state_status[1]) or {}))
        return '、'.join(entries) if entries else '正常'

    @property
    def action_text(self):
        action = self.action or {}
        return action.get('name') or gs.ENEMY_STATE_NAMES.get(
            self.state_id, f'未知({self.state_id})')

    @property
    def effective_max_ep(self):
        """实体当前真正使用的损伤条上限，而不是只返回基础属性。"""
        base_maximum = max(0.0, self.attribute(gs.AttributeType.MAX_EP, 0.0))
        runtime_maximum = max(
            0.0, self.ep_remaining.get(gs.ElementType.NONE, 0.0))
        return max(base_maximum, runtime_maximum)

    def element_damage(self, element_type):
        # MAX_EP is the base attribute, but some runtime entity subclasses
        # override Entity.maxEp (giant bosses are one example).  The game
        # initializes the unused NONE slot in m_epArray with that effective
        # maxEp, so it is the authoritative live capacity for every concrete
        # elemental-damage bar.  Keep the attribute as a fallback for pending
        # enemies and older layouts where the runtime array is unavailable.
        maximum = self.effective_max_ep
        remaining = max(0.0, self.ep_remaining.get(element_type, maximum))
        damage = max(0.0, maximum - remaining)
        return damage, remaining, maximum


class EnemyReader:
    def __init__(self, adb_path=None, package='com.hypergryph.arknights',
                 cache_file=CACHE_FILE, with_bc=True, log=print, workers=8, mc=None,
                 adb_serial=None, diagnostics=False):
        self.mc = mc if mc is not None else MemCore(
            adb_path, package, adb_serial=adb_serial)
        self.cache_file = cache_file
        self.with_bc = with_bc
        self.log = log
        self.workers = workers          # 完整快照解析并发数（读取统一走 memsrv v4）
        self.diagnostics = bool(diagnostics)
        self._identity_diag_signature = None
        self._identity_diag_ts = 0.0
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
        self._buff_source_names = {}  # buff 来源实体 addr -> 名称 (干员/召唤物等)
        self._char_names = None   # charId -> 中文名 (惰性加载)
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
        self._custom_shield_ptrs = {} # enemy addr -> 旧式 Buff 护盾的值/状态地址
        self._custom_shield_probe_tick = {} # enemy addr -> 最近一次 Buff 链探测 tick
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
        self._poll_stop = threading.Event()  # GUI 停止时中断 memsrv v4 读取
        self._skill_lp = {}           # enemy addr -> m_skills List* (主块内提取)
        self._skill_ap = {}           # enemy addr -> m_allSkills EnemySkill[]*
        self._skill_source_layout = {} # (enemy, active/all) -> ptr/items/count
        self._skill_ptrs = {}         # enemy addr -> 最近一次成功解析的 EnemySkill 地址
        self._active_skill_ptrs = {}  # enemy addr -> m_skills 中当前启用且已排序的技能
        self._skill_names = {}        # skill addr -> prefabKey (技能静态名缓存)
        self._skill_cd = {}           # enemy addr -> [(key, remaining, period), ...]
        self._skill_runtime_meta = {} # skill addr -> family/触发/运行时 Ability
        self._skill_static_meta = {}  # skill addr -> {priority, sp_cost} (ESkillData)
        self._skill_enriched = {}     # enemy addr -> [技能判定元数据 dict, ...]
        self._trigger_type_cache = {} # TargetTrigger addr -> 运行时 klass 名
        self._status_timer_cache = {} # entity addr -> 当前异常态对应的 Buff 地址
        self._animation_name_cache = {} # il2cpp string addr -> animKey/空值
        self._animator_layout_cache = {} # animator -> {klass, skeleton/...}
        self._spine_face_skeleton_cache = {} # FaceConfiguration -> SkeletonAnimation
        self._spine_skeleton_layout_cache = {} # skeleton -> state/tracks/items
        self._spine_animation_cache = {} # Spine.Animation -> {name, duration}
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
        self._fixed_frame_snap = None
        self._frame_duration_snap = 1.0 / 30.0
        self.precise_position_enabled = False
        self._precise_position_reader = None
        self._route_meta = {}           # routeIndex -> 起点/首个进场路线点
        self._routes_export = []        # 完整路线（供排轴前端绘图）
        self._main_route_count = 0      # 主路线数组原始长度（extra 路线顺延编号）
        self._level_map_data = {}       # 当前关卡地图（纯 JSON 数据）
        self._level_enemy_meta = {}     # enemy key -> 静态移速/delayToBorn

    @property
    def planned_count(self):
        return len(self._spawn_plan) + len(self._runtime_spawn_plan)

    @property
    def plan_level_id(self):
        return self._plan_level_id

    def build_stage_export(self, stage_info=None):
        """返回可直接写入 JSON、并由排轴前端导入的当前关卡快照。"""
        from .stage_export import build_stage_export
        return build_stage_export(self, stage_info)

    def set_precise_position_enabled(self, enabled):
        """Enable the independent Unity Transform coordinate chain."""
        self.precise_position_enabled = bool(enabled)
        if not self.precise_position_enabled and self._precise_position_reader:
            self._precise_position_reader.clear()

    def _refresh_precise_positions(self, ptrs, infos):
        if not self.precise_position_enabled or not ptrs:
            return
        if self._precise_position_reader is None \
                or self._precise_position_reader.channel is not self._chan:
            self._precise_position_reader = PrecisePositionReader(self.mc, self._chan)
        values = self._precise_position_reader.read(ptrs)
        for enemy_addr, info in infos.items():
            position = values.get(enemy_addr)
            if position is None:
                info.precise_pos_valid = False
                continue
            info.precise_pos_x, info.precise_pos_y = position
            info.precise_pos_valid = True

    # ================= 连接 =================

    def connect(self):
        self._poll_stop.clear()
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

    def _read_object_array_slots(self, array_ptr, max_count=4096):
        """同 _read_object_array，但返回 (slot, ptr) 列表与数组原始长度。

        空槽被过滤时不压实下标——调用方若要用下标对齐游戏内数组
        （如 spawn 的 route_index），必须用原始槽位号。
        """
        if not self.mc.is_ptr(array_ptr):
            return [], 0
        head = self._detail_batch_read([(array_ptr, gs.Il2CppArray.ITEMS)])[0]
        if not head:
            return [], 0
        count = _i32(head, gs.Il2CppArray.MAX_LENGTH)
        if not (0 <= count <= max_count):
            return [], 0
        if count == 0:
            return [], 0
        body = self._detail_batch_read(
            [(array_ptr + gs.Il2CppArray.ITEMS, count * 8)])[0]
        if not body:
            return [], 0
        slots = [(idx, ptr) for idx, ptr in
                 enumerate(_u64(body, i * 8) for i in range(count))
                 if self.mc.is_ptr(ptr)]
        return slots, count

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
            route_index = self._global_route_index(
                _i32(action, gs.SpawnActionFields.ROUTE_INDEX),
                bool(action[gs.SpawnActionFields.USE_EXTRA_ROUTE]))
            for spawn_index in range(count):
                record = dict(base_meta)
                record.update({
                    'key': key,
                    'action_ptr': action_ptr,
                    'action_index': action_index,
                    'spawn_index': spawn_index,
                    'route_index': route_index,
                    'time_offset': (float(base_delay) + pre_delay
                                    + max(0.0, interval) * spawn_index),
                    'managed': bool(action[gs.SpawnActionFields.MANAGED_BY_SCHEDULER]),
                    'hidden_group': self._read_ustring_fast(
                        _u64(action, gs.SpawnActionFields.HIDDEN_GROUP)),
                    'random_spawn_group': self._read_ustring_fast(
                        _u64(action, gs.SpawnActionFields.RANDOM_SPAWN_GROUP)),
                    'random_spawn_pack': self._read_ustring_fast(
                        _u64(action, gs.SpawnActionFields.RANDOM_SPAWN_PACK)),
                    'random_type': _i32(action, gs.SpawnActionFields.RANDOM_TYPE),
                    'refresh_type': _i32(action, gs.SpawnActionFields.REFRESH_TYPE),
                    'weight': _i32(action, gs.SpawnActionFields.WEIGHT),
                    'dont_block_wave': bool(
                        action[gs.SpawnActionFields.DONT_BLOCK_WAVE]),
                    'not_count_in_total': bool(
                        action[gs.SpawnActionFields.NOT_COUNT_IN_TOTAL]),
                })
                if record['random_spawn_group'] or record['random_spawn_pack']:
                    record['spawn_kind'] = 'conditional'
                    record['spawn_source'] = (
                        record['random_spawn_group'] or record['random_spawn_pack'])
                    record['spawn_condition'] = (
                        f"等待随机出怪组「{record['spawn_source']}」确定")
                elif record['hidden_group']:
                    record['spawn_kind'] = 'conditional'
                    record['spawn_source'] = record['hidden_group']
                    record['spawn_condition'] = (
                        f"等待隐藏组「{record['hidden_group']}」启用")
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
            static_fields + gs.BattleControllerStaticFields.FIXED_FRAME_COUNT,
            gs.BattleControllerStaticFields.DELTA_PLAY_TIME_FP
            - gs.BattleControllerStaticFields.FIXED_FRAME_COUNT + 8)])[0]
        if not raw:
            return False
        frame, now, frame_duration = self._decode_battle_clock_snapshot(raw)
        if not (-1.0 <= now <= 864000.0):
            return False
        self._bc_static_fields = static_fields
        self._fixed_frame_snap = frame
        self._scheduler_time_snap = now
        if frame_duration:
            self._frame_duration_snap = frame_duration
        return True

    @staticmethod
    def _decode_battle_clock(raw):
        if not raw or len(raw) < 8:
            return None
        value = gs.fp_to_float(_u64(raw, 0))
        return value if -1.0 <= value <= 864000.0 else None

    @staticmethod
    def _decode_battle_clock_snapshot(raw):
        """解析 static_fields+0x14 起的 frame/time/delta 原子快照。"""
        delta_off = (gs.BattleControllerStaticFields.DELTA_PLAY_TIME_FP
                     - gs.BattleControllerStaticFields.FIXED_FRAME_COUNT)
        if not raw or len(raw) < delta_off + 8:
            return None, None, None
        frame = _u32(raw, 0)
        play_time = gs.fp_to_float(_u64(raw, 4))
        delta = gs.fp_to_float(_u64(raw, delta_off))
        if not (-1.0 <= play_time <= 864000.0):
            play_time = None
        if not (0.000001 <= delta <= 1.0):
            delta = None
        return frame, play_time, delta

    def _make_plan_record(self, source, order, roster_id):
        record = dict(source)
        self._decorate_spawn_record(record)
        record['roster_id'] = roster_id
        record['spawn_order'] = order
        record['seen'] = False
        record['addr'] = 0
        record.setdefault('spawn_eta', None)
        record.setdefault('spawn_condition', '等待关卡调度')
        record.setdefault('spawn_kind', 'scheduled')
        record.setdefault('spawn_source', '')
        record.setdefault('spawn_frame', None)
        record.setdefault('end_frame', None)
        record.setdefault('end_reason', '')
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

    def _remember_enemy_name(self, eid, name='', code='', desc=''):
        """合并静态表和关卡运行时名称，并同步所有尚未出场的同类计划项。"""
        if not eid:
            return '', ''
        if self._db is None:
            self._db = load_enemy_db()
        old = self._db.get(eid, {})
        clean_name = name.strip() if isinstance(name, str) else ''
        if clean_name and len(clean_name) <= 128 and not any(
                ord(ch) < 0x20 for ch in clean_name):
            merged = dict(old)
            merged['name'] = clean_name
            if code:
                merged['code'] = code
            if desc:
                merged['desc'] = desc
            self._db[eid] = merged
            old = merged
        resolved_name = old.get('name') or eid
        resolved_code = old.get('code') or code or ''
        for record in self._all_plan_records():
            if record.get('key') != eid:
                continue
            planned = record.get('info')
            if planned is not None and planned.lifecycle != 'active':
                planned.name = resolved_name
                planned.code = resolved_code
        return resolved_name, resolved_code

    def _load_level_enemy_names(self, level_data):
        """从当前 LevelData.EnemyData[] 读取新版敌人名，不依赖旧图鉴表。"""
        enemies_ptr = self._read_ptr(level_data + gs.LevelDataFields.ENEMIES)
        data_ptrs = self._read_object_array(enemies_ptr, 4096)
        if not data_ptrs:
            return 0
        blocks = self._detail_batch_read([
            (ptr, gs.LevelEnemyDataFields.ATTRIBUTES + 8) for ptr in data_ptrs])
        rows = []
        string_ptrs = []
        for block in blocks:
            if not block:
                continue
            name_ptr = _u64(block, gs.LevelEnemyDataFields.NAME)
            desc_ptr = _u64(block, gs.LevelEnemyDataFields.DESCRIPTION)
            key_ptr = _u64(block, gs.LevelEnemyDataFields.KEY)
            rows.append((key_ptr, name_ptr, desc_ptr,
                         _u64(block, gs.LevelEnemyDataFields.ATTRIBUTES)))
            string_ptrs.extend((key_ptr, name_ptr, desc_ptr))
        strings = self._read_strings(string_ptrs, max_chars=512)
        attr_rows = [(key_ptr, attr_ptr) for key_ptr, _name, _desc, attr_ptr in rows
                     if self.mc.is_ptr(attr_ptr)]
        attr_data = self._detail_batch_read([
            (attr_ptr + gs.StaticAttributesDataFields.MOVE_SPEED, 0x18)
            for _key_ptr, attr_ptr in attr_rows]) if attr_rows else []
        self._level_enemy_meta = {}
        for (key_ptr, _attr_ptr), data in zip(attr_rows, attr_data):
            if not data or len(data) < 0x18 or not data[0x0C]:
                continue
            speed = gs.decrypt_obscured_float(_u32(data, 0), _u32(data, 4))
            if math.isfinite(speed) and 0.01 <= speed <= 100.0:
                key = strings.get(key_ptr, '')
                if key:
                    self._level_enemy_meta.setdefault(key, {})['move_speed'] = speed
        loaded = 0
        for key_ptr, name_ptr, desc_ptr, _attr_ptr in rows:
            eid = strings.get(key_ptr, '')
            name = strings.get(name_ptr, '')
            if eid and name:
                self._remember_enemy_name(
                    eid, name, desc=strings.get(desc_ptr, ''))
                loaded += 1
        return loaded

    @staticmethod
    def _finite_float(data, offset, default=0.0):
        value = struct.unpack_from('<f', data, offset)[0]
        return float(value) if math.isfinite(value) else default

    def _load_predefined_devices(self, level_data):
        """读取预置角色/装置位置；tokenInsts 在关卡数据中通常就是预置装置。"""
        devices = []
        definitions = (
            ('normal', gs.LevelDataFields.PREDEFINES),
            ('hard', gs.LevelDataFields.HARD_PREDEFINES),
        )
        arrays = (
            ('character', gs.PredefinedDataFields.CHARACTER_INSTS),
            ('token', gs.PredefinedDataFields.TOKEN_INSTS),
        )
        for difficulty, level_offset in definitions:
            predefined = self._read_ptr(level_data + level_offset)
            if not self.mc.is_ptr(predefined):
                continue
            for kind, array_offset in arrays:
                items = self._read_object_array(
                    self._read_ptr(predefined + array_offset), 4096)
                blocks = self._detail_batch_read([
                    (item, gs.PredefinedCharacterFields.READ_SIZE) for item in items])
                string_ptrs = []
                for block in blocks:
                    if block:
                        string_ptrs.extend((
                            _u64(block, gs.PredefinedCharacterFields.CHARACTER_KEY),
                            _u64(block, gs.PredefinedCharacterFields.ALIAS),
                        ))
                strings = self._read_strings(
                    [ptr for ptr in string_ptrs if self.mc.is_ptr(ptr)], max_chars=256)
                for block in blocks:
                    if not block:
                        continue
                    row = _i32(block, gs.PredefinedCharacterFields.POSITION)
                    col = _i32(block, gs.PredefinedCharacterFields.POSITION + 4)
                    key_ptr = _u64(block, gs.PredefinedCharacterFields.CHARACTER_KEY)
                    alias_ptr = _u64(block, gs.PredefinedCharacterFields.ALIAS)
                    devices.append({
                        'kind': kind,
                        'difficulty': difficulty,
                        'key': strings.get(key_ptr, ''),
                        'alias': strings.get(alias_ptr, ''),
                        'row': row,
                        'col': col,
                        'direction': _i32(
                            block, gs.PredefinedCharacterFields.DIRECTION),
                        'hidden': bool(block[gs.PredefinedCharacterFields.HIDDEN]),
                    })
        return devices

    def _load_level_map(self, level_data):
        """读取 MapData.short[,] 与 TileData[]，只保留稳定的可视化字段。"""
        map_id = self._read_ustring_fast(
            self._read_ptr(level_data + gs.LevelDataFields.MAP_ID))
        map_data = self._read_ptr(level_data + gs.LevelDataFields.MAP_DATA)
        self._level_map_data = {'mapId': map_id or '', 'rows': 0, 'cols': 0,
                                'tiles': [], 'blockEdges': [], 'devices': [],
                                'tags': []}
        if not self.mc.is_ptr(map_data):
            return False

        map_array = self._read_ptr(map_data + gs.MapDataFields.MAP)
        tile_array = self._read_ptr(map_data + gs.MapDataFields.TILES)
        header = self._detail_batch_read([(map_array, gs.Il2CppArray.ITEMS)])[0] \
            if self.mc.is_ptr(map_array) else None
        total = int(_u64(header, gs.Il2CppArray.MAX_LENGTH)) if header else 0
        bounds = _u64(header, gs.Il2CppArray.BOUNDS) if header else 0
        rows = cols = 0
        if self.mc.is_ptr(bounds):
            bound_data = self._detail_batch_read([(bounds, 0x20)])[0]
            if bound_data:
                rows = int(_u64(bound_data, 0x00))
                cols = int(_u64(bound_data, 0x10))
        if not (0 < rows <= 128 and 0 < cols <= 128 and rows * cols == total):
            rows = cols = 0

        tile_ptrs = self._read_object_array(tile_array, 16384)
        tile_blocks = self._detail_batch_read([
            (ptr, gs.TileDataFields.READ_SIZE) for ptr in tile_ptrs])
        key_ptrs = [_u64(block, gs.TileDataFields.TILE_KEY)
                    for block in tile_blocks if block]
        strings = self._read_strings(
            [ptr for ptr in key_ptrs if self.mc.is_ptr(ptr)], max_chars=256)
        definitions = []
        for block in tile_blocks:
            if not block:
                definitions.append({})
                continue
            definitions.append({
                'tileKey': strings.get(_u64(block, gs.TileDataFields.TILE_KEY), ''),
                'heightType': _i32(block, gs.TileDataFields.HEIGHT_TYPE),
                'buildableType': _i32(block, gs.TileDataFields.BUILDABLE_TYPE),
                'passableMask': _i32(block, gs.TileDataFields.PASSABLE_MASK),
                'playerSideMask': _i32(block, gs.TileDataFields.PLAYER_SIDE_MASK),
                'advancedBuildableMask': _i32(
                    block, gs.TileDataFields.ADVANCED_BUILDABLE_MASK),
            })

        if total and total <= 16384:
            cell_data = self._detail_batch_read([(
                map_array + gs.Il2CppArray.ITEMS, total * 2)])[0]
        else:
            cell_data = None
        indices = [struct.unpack_from('<h', cell_data, index * 2)[0]
                   for index in range(total)] if cell_data else []
        if not rows or not cols:
            # 旧运行时若 bounds 不可读，TileData 通常仍是一格一项；保留一行
            # 数据而不是导出损坏尺寸，前端会明确显示“地图尺寸不可用”。
            rows, cols = (1, len(indices)) if indices else (0, 0)
        tiles = []
        for index, tile_index in enumerate(indices):
            tile = dict(definitions[tile_index]) \
                if 0 <= tile_index < len(definitions) else {}
            # 内存 short[,] 首行 = 画面顶部（与官方 JSON map 一致，实机显示验证）。
            # 注意 GridPosition/路线坐标相反（row 0 = 画面底部），由前端导入时翻转。
            tile.update(row=index // max(1, cols), col=index % max(1, cols),
                        tileIndex=tile_index)
            tiles.append(tile)

        edge_ptrs = self._read_object_array(
            self._read_ptr(map_data + gs.MapDataFields.BLOCK_EDGES), 16384)
        edge_blocks = self._detail_batch_read([
            (ptr, gs.MapEdgeFields.READ_SIZE) for ptr in edge_ptrs])
        edges = [{
            'row': _i32(block, gs.MapEdgeFields.POSITION),
            'col': _i32(block, gs.MapEdgeFields.POSITION + 4),
            'direction': _i32(block, gs.MapEdgeFields.DIRECTION),
            'blockMask': _i32(block, gs.MapEdgeFields.BLOCK_MASK),
        } for block in edge_blocks if block]

        tag_ptrs = self._read_object_array(
            self._read_ptr(map_data + gs.MapDataFields.TAGS), 4096)
        tag_strings = self._read_strings(tag_ptrs, max_chars=256)
        self._level_map_data.update({
            'rows': rows, 'cols': cols, 'tiles': tiles,
            'blockEdges': edges,
            'devices': self._load_predefined_devices(level_data),
            'tags': [tag_strings.get(ptr, '') for ptr in tag_ptrs
                     if tag_strings.get(ptr, '')],
        })
        return bool(tiles)

    def _global_route_index(self, route_index, use_extra):
        """把 (useExtraRoute, routeIndex) 换算成导出用的全局路线编号。

        游戏内 spawn 的 routeIndex 在主路线数组与 extraRoutes 数组内各自从 0
        计数（ActionData.useExtraRoute 区分）；导出时 extra 路线统一接在主路线
        数组长度之后，保证全局唯一、与 _routes_export 的 index 一一对应。
        """
        if route_index < 0:
            return route_index
        if use_extra:
            return self._main_route_count + route_index
        return route_index

    def _load_route_meta(self, level_data):
        """读取完整路线，并保留用于估算可见进场时间的首段摘要。"""
        self._route_meta = {}
        self._routes_export = []
        self._main_route_count = 0
        checkpoint_names = {
            value: name for name, value in vars(gs.RouteCheckpointType).items()
            if name.isupper() and isinstance(value, int)
        }
        main_route_count = 0
        for is_extra, level_offset in (
                (False, gs.LevelDataFields.ROUTES),
                (True, gs.LevelDataFields.EXTRA_ROUTES)):
            slots, array_count = self._read_object_array_slots(
                self._read_ptr(level_data + level_offset), 4096)
            if not is_extra:
                main_route_count = array_count
                self._main_route_count = array_count
            blocks = self._detail_batch_read([
                (ptr, gs.RouteDataFields.READ_SIZE) for _, ptr in slots])
            for (slot, _route_ptr), block in zip(slots, blocks):
                if not block:
                    continue
                # index 必须与游戏内数组槽位一致（spawn 的 route_index 直接引用
                # 槽位；空槽被过滤后 enumerate 位置会错位，17-17 实测 route 29
                # 为空导致后续路线全部错一位）。extra 路线接在主路线数组之后编号。
                route_index = slot if not is_extra else main_route_count + slot
                start = (_i32(block, gs.RouteDataFields.START_POSITION),
                         _i32(block, gs.RouteDataFields.START_POSITION + 4))
                end = (_i32(block, gs.RouteDataFields.END_POSITION),
                       _i32(block, gs.RouteDataFields.END_POSITION + 4))
                checkpoints = self._read_object_array(
                    _u64(block, gs.RouteDataFields.CHECKPOINTS), 4096)
                cp_blocks = self._detail_batch_read([
                    (cp, gs.RouteCheckpointFields.READ_SIZE) for cp in checkpoints])
                entry = None
                fixed_wait = 0.0
                exported_checkpoints = []
                for cp in cp_blocks:
                    if not cp:
                        continue
                    cp_type = _i32(cp, gs.RouteCheckpointFields.TYPE)
                    position = (
                        _i32(cp, gs.RouteCheckpointFields.POSITION),
                        _i32(cp, gs.RouteCheckpointFields.POSITION + 4))
                    wait = self._finite_float(cp, gs.RouteCheckpointFields.TIME)
                    exported_checkpoints.append({
                        'type': cp_type,
                        'typeName': checkpoint_names.get(cp_type, f'UNKNOWN_{cp_type}'),
                        'time': wait,
                        'position': {'row': position[0], 'col': position[1]},
                        'reachOffset': {
                            'x': self._finite_float(cp, gs.RouteCheckpointFields.REACH_OFFSET),
                            'y': self._finite_float(cp, gs.RouteCheckpointFields.REACH_OFFSET + 4),
                        },
                        'randomizeReachOffset': bool(
                            cp[gs.RouteCheckpointFields.RANDOMIZE_REACH_OFFSET]),
                        'reachDistance': self._finite_float(
                            cp, gs.RouteCheckpointFields.REACH_DISTANCE),
                    })
                    if entry is None and cp_type == gs.RouteCheckpointType.MOVE:
                        entry = position
                    elif entry is None and cp_type == gs.RouteCheckpointType.WAIT_FOR_SECONDS:
                        if 0 < wait <= 3600:
                            fixed_wait += wait
                motion_mode = _i32(block, gs.RouteDataFields.MOTION_MODE)
                diagonal = bool(block[gs.RouteDataFields.ALLOW_DIAGONAL_MOVE])
                self._routes_export.append({
                    'index': route_index,
                    'isExtra': is_extra,
                    'motionMode': motion_mode,
                    'motionModeName': {0: 'WALK', 1: 'FLY'}.get(
                        motion_mode, f'UNKNOWN_{motion_mode}'),
                    'start': {'row': start[0], 'col': start[1]},
                    'end': {'row': end[0], 'col': end[1]},
                    'spawnRandomRange': {
                        'x': self._finite_float(block, gs.RouteDataFields.SPAWN_RANDOM_RANGE),
                        'y': self._finite_float(block, gs.RouteDataFields.SPAWN_RANDOM_RANGE + 4),
                    },
                    'spawnOffset': {
                        'x': self._finite_float(block, gs.RouteDataFields.SPAWN_OFFSET),
                        'y': self._finite_float(block, gs.RouteDataFields.SPAWN_OFFSET + 4),
                    },
                    'allowDiagonalMove': diagonal,
                    'checkpoints': exported_checkpoints,
                })
                if entry is None:
                    continue
                row_delta = entry[0] - start[0]
                col_delta = entry[1] - start[1]
                distance = (math.hypot(row_delta, col_delta) if diagonal
                            else abs(row_delta) + abs(col_delta))
                if distance > 0.01:
                    self._route_meta[route_index] = {
                        'start': start, 'entry': entry, 'distance': distance,
                        'fixed_wait': fixed_wait, 'diagonal': diagonal,
                    }

    def _load_scheduler_enemy_meta(self):
        """补读 prefab 的 delayToBorn；该值不在 LevelData.EnemyData 中。"""
        if not self.sched_addr:
            return
        map_ptr = self._read_ptr(self.sched_addr + gs.SchedulerFields.M_ENEMY_MAP)
        head = self._detail_batch_read([(map_ptr, 0x30)])[0] \
            if self.mc.is_ptr(map_ptr) else None
        entries = _u64(head, 0x18) if head else 0
        count = _i32(head, 0x20) if head else 0
        if not self.mc.is_ptr(entries) or not (0 <= count <= 4096):
            return
        raw = self._detail_batch_read([(
            entries + gs.Il2CppArray.ITEMS, count * 0x28)])[0] if count else b''
        if raw is None:
            return
        items = []
        key_ptrs = []
        for index in range(count):
            off = index * 0x28
            if _i32(raw, off) < 0:
                continue
            key_ptr = _u64(raw, off + 8)
            data_ptr = _u64(raw, off + 0x10)
            delay = struct.unpack_from('<f', raw, off + 0x20)[0]
            if self.mc.is_ptr(key_ptr) and math.isfinite(delay) and 0 <= delay <= 3600:
                items.append((key_ptr, delay, data_ptr))
                key_ptrs.append(key_ptr)
        strings = self._read_strings(key_ptrs, max_chars=128)
        data_items = [(key_ptr, data_ptr) for key_ptr, _delay, data_ptr in items
                      if self.mc.is_ptr(data_ptr)]
        attr_ptrs = self._detail_batch_read([
            (data_ptr + gs.LevelEnemyDataFields.ATTRIBUTES, 8)
            for _key_ptr, data_ptr in data_items]) if data_items else []
        speed_items = []
        for (key_ptr, _data_ptr), attr_raw in zip(data_items, attr_ptrs):
            attr_ptr = _u64(attr_raw, 0) if attr_raw else 0
            if self.mc.is_ptr(attr_ptr):
                speed_items.append((key_ptr, attr_ptr))
        speed_raw = self._detail_batch_read([
            (attr_ptr + gs.StaticAttributesDataFields.MOVE_SPEED, 0x18)
            for _key_ptr, attr_ptr in speed_items]) if speed_items else []
        speeds = {}
        for (key_ptr, _attr_ptr), data in zip(speed_items, speed_raw):
            if not data or len(data) < 0x18 or not data[0x0C]:
                continue
            speed = gs.decrypt_obscured_float(_u32(data, 0), _u32(data, 4))
            if math.isfinite(speed) and 0.01 <= speed <= 100:
                speeds[key_ptr] = speed
        for key_ptr, delay, _data_ptr in items:
            key = strings.get(key_ptr, '')
            if key:
                meta = self._level_enemy_meta.setdefault(key, {})
                meta['delay_to_born'] = delay
                if key_ptr in speeds:
                    meta['move_speed'] = speeds[key_ptr]

    def _decorate_spawn_record(self, record):
        """把调度生成时间换算所需的路线/敌人静态参数附到计划项。"""
        key = record.get('key', '')
        route = self._route_meta.get(record.get('route_index', -1), {})
        enemy = self._level_enemy_meta.get(key, {})
        speed = enemy.get('move_speed', 0.0)
        delay = enemy.get('delay_to_born', 0.0)
        distance = route.get('distance', 0.0)
        walk = distance / speed if distance > 0 and speed > 0 else 0.0
        fixed_wait = route.get('fixed_wait', 0.0)
        record.update(
            route_start=route.get('start'), route_entry=route.get('entry'),
            route_entry_distance=distance, move_speed_static=speed,
            delay_to_born=delay,
            visible_entry_delay=max(0.0, delay + fixed_wait + walk))

    @staticmethod
    def _remaining_route_entry(enemy, record):
        """实体已经生成后，估算其到达首个进场路线点的剩余秒数。"""
        start = record.get('route_start')
        entry = record.get('route_entry')
        distance = record.get('route_entry_distance', 0.0)
        speed = enemy.mspd or record.get('move_speed_static', 0.0)
        if (not start or not entry or distance <= 0.01 or speed <= 0.01):
            return None
        # GridPosition 是 (row, col)，场上 Vector2 是 (col, row)。用投影判断
        # 是否已经越过第一个路线点，避免出生点存在小幅随机偏移时误判。
        sx, sy = float(start[1]), float(start[0])
        ex, ey = float(entry[1]), float(entry[0])
        vx, vy = ex - sx, ey - sy
        denom = vx * vx + vy * vy
        if denom <= 1e-6:
            return None
        progress = ((enemy.pos_x - sx) * vx + (enemy.pos_y - sy) * vy) / denom
        if progress >= 0.98:
            return 0.0
        progress = max(0.0, progress)
        return max(0.0, distance * (1.0 - progress) / speed)

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
        self._buff_source_names = {}   # 新一局实体地址重新分配, 来源缓存作废
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
        self._fixed_frame_snap = None
        self._frame_duration_snap = 1.0 / 30.0
        self._status_timer_cache.clear()
        self._skill_source_layout.clear()
        self._animation_name_cache.clear()
        for order, source in enumerate(records, 1):
            record = self._make_plan_record(source, order, -order)
            self._spawn_plan.append(record)

    def _load_spawn_plan(self):
        """解析固定 waves、条件 branches 和仅由事件/召唤使用的敌人类型。"""
        if not self.bc_addr:
            self._level_map_data = {}
            self._routes_export = []
            self._set_spawn_plan([])
            return False
        level_data = self._read_ptr(self.bc_addr + gs.BattleControllerFields.LEVEL_DATA)
        if (not self.mc.is_ptr(level_data)
                or self.mc.read_klass_name(level_data) != 'LevelData'):
            self._level_map_data = {}
            self._routes_export = []
            self._set_spawn_plan([])
            return False
        level_id = self._read_ustring_fast(
            self._read_ptr(level_data + gs.LevelDataFields.LEVEL_ID))
        runtime_name_count = self._load_level_enemy_names(level_data)
        self._load_level_map(level_data)
        self._load_route_meta(level_data)
        self._load_scheduler_enemy_meta()
        waves_ptr = self._read_ptr(level_data + gs.LevelDataFields.WAVES)
        wave_ptrs = self._read_object_array(waves_ptr, 1024)
        records = []
        nominal_wave_time = 0.0
        for wave_index, wave_ptr in enumerate(wave_ptrs):
            wave = self._detail_batch_read([(wave_ptr, 0x30)])[0]
            if not wave:
                continue
            wave_pre_delay = struct.unpack_from(
                '<f', wave, gs.WaveDataFields.PRE_DELAY)[0]
            wave_post_delay = struct.unpack_from(
                '<f', wave, gs.WaveDataFields.POST_DELAY)[0]
            if not math.isfinite(wave_pre_delay):
                wave_pre_delay = 0.0
            if not math.isfinite(wave_post_delay):
                wave_post_delay = 0.0
            wave_start = nominal_wave_time + max(0.0, wave_pre_delay)
            wave_end = wave_start
            fragments_ptr = _u64(wave, gs.WaveDataFields.FRAGMENTS)
            fragment_ptrs = self._read_object_array(fragments_ptr, 4096)
            for fragment_index, fragment_ptr in enumerate(fragment_ptrs):
                fragment = self._detail_batch_read([(fragment_ptr, 0x20)])[0]
                if not fragment:
                    continue
                fragment_delay = struct.unpack_from(
                    '<f', fragment, gs.FragmentDataFields.PRE_DELAY)[0]
                if not math.isfinite(fragment_delay):
                    fragment_delay = 0.0
                actions_ptr = _u64(fragment, gs.FragmentDataFields.ACTIONS)
                action_ptrs = self._read_object_array(actions_ptr, 8192)
                fragment_records = self._expand_spawn_actions(action_ptrs, {
                    'wave_index': wave_index,
                    'fragment_index': fragment_index,
                    'spawn_kind': 'scheduled',
                    'spawn_condition': (
                        f'等待第 {wave_index + 1} 波第 {fragment_index + 1} 段进入调度'),
                    'wave_pre_delay': wave_pre_delay,
                    'wave_max_wait': struct.unpack_from(
                        '<f', wave, gs.WaveDataFields.MAX_WAIT_NEXT)[0],
                }, max(0.0, fragment_delay))
                for record in fragment_records:
                    record['nominal_spawn_time'] = wave_start + record['time_offset']
                    wave_end = max(wave_end, record['nominal_spawn_time'])
                records.extend(fragment_records)
            nominal_wave_time = wave_end + max(0.0, wave_post_delay)
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
                     f"潜在召唤类型 {ref_count}，名称 {runtime_name_count}）")
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
        enemy.spawn_frame = record.get('spawn_frame')
        enemy.end_frame = record.get('end_frame')
        enemy.end_reason = record.get('end_reason', '')
        return enemy

    def _bind_plan_enemy(self, enemy, record):
        entry_eta = self._remaining_route_entry(enemy, record)
        # 实体已站在地图格子上 = 已出场。路线投影在路线元数据不匹配时会
        # 误判「仍在地图外」, 格子指针优先级更高。
        on_tile = bool(enemy.current_tile_ptr) and self.mc.is_ptr(
            enemy.current_tile_ptr)
        before_entry = (isinstance(entry_eta, (int, float))
                        and entry_eta > 0.05 and not on_tile)
        self._copy_plan_metadata(enemy, record, 'pending' if before_entry else 'active')
        enemy.spawn_eta = entry_eta if before_entry else 0.0
        enemy.spawn_condition = ('实体已生成，正在地图外进入战场'
                                 if before_entry else '已出场')
        record['spawn_eta'] = enemy.spawn_eta
        record['spawn_condition'] = enemy.spawn_condition
        if (not before_entry and record.get('spawn_frame') is None
                and self._fixed_frame_snap is not None):
            record['spawn_frame'] = int(self._fixed_frame_snap)
            enemy.spawn_frame = record['spawn_frame']
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
        enemy.spawn_frame = (int(self._fixed_frame_snap)
                             if self._fixed_frame_snap is not None else None)
        self._addr_to_roster[enemy.addr] = roster_id
        self._roster_last[roster_id] = enemy

    def _find_claimable_record(self, enemy):
        """为场上实体认领一个尚未出场的计划项 (首见绑定与动态行重试共用)。

        ActionData 指针能精确区分同种敌人的固定波次与运行时召唤；
        isSummon 则避免召唤物误认领尚未出场的同名固定波次项。"""
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
        return record

    def _merge_enemy_roster(self, live_enemies, spawned_count=0):
        """把当前实例合并进开局计划，返回含未出场/场上/已离场的稳定顺序。"""
        # UnitManager 在死亡动画/回收前仍短暂保留对象；HP 归零或 finishReason
        # 非零即应进入“已离场”，不能继续算作场上敌人。
        departing = {enemy.addr: enemy for enemy in live_enemies if not enemy.alive}
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
            departure = departing.get(addr)
            # DEAD/REACH_EXIT 状态中实体通常还会在 UnitManager 保留
            # 一小段时间，但其 Transform、Buff、护盾和技能字段可能已在
            # 回收流程中被清零。不能用这个“死亡清理帧”覆盖上一帧
            # 完整存活快照。deepcopy 同时避免修改仍可能由 UI 消费的
            # 上一个双缓冲快照对象。
            previous = self._roster_last.get(roster_id)
            source = previous or departure
            old = copy.deepcopy(source) if source is not None else None
            if old is not None:
                old.lifecycle = 'departed'
                old.alive = False
                old.end_frame = (int(self._fixed_frame_snap)
                                 if self._fixed_frame_snap is not None else None)
                reason_source = departure or old
                old.end_reason = (
                    'death' if (reason_source.hp <= 0
                                or reason_source.state_id == gs.EnemyState.DEAD) else
                    f'finish_{reason_source.finish}' if reason_source.finish else
                    'departed')
                self._roster_last[roster_id] = old
            record = self._plan_by_id.get(roster_id)
            if record is not None:
                record['addr'] = 0
                if old is not None:
                    record['end_frame'] = old.end_frame
                    record['end_reason'] = old.end_reason
                    record['info'] = old

        for enemy in live_enemies:
            roster_id = self._addr_to_roster.get(enemy.addr)
            if roster_id is not None:
                record = self._plan_by_id.get(roster_id)
                if record is not None:
                    self._bind_plan_enemy(enemy, record)
                    continue
                # 动态行：首帧 ID/isSummon 瞬读失败会把计划内敌人误落成动态行，
                # 计划项则永远停在「未出场」。每轮重试认领，保证场上实体
                # 优先对回计划表。
                claim = self._find_claimable_record(enemy)
                if claim is not None:
                    self._roster_last.pop(roster_id, None)
                    self._bind_plan_enemy(enemy, claim)
                    continue
                enemy.roster_id = roster_id
                enemy.spawn_order = self._roster_last[roster_id].spawn_order
                enemy.lifecycle = 'active'
                enemy.planned = False
                self._roster_last[roster_id] = enemy
                continue

            record = self._find_claimable_record(enemy)
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
                'route_index': self._global_route_index(
                    _i32(data, gs.SpawnActionFields.ROUTE_INDEX),
                    bool(data[gs.SpawnActionFields.USE_EXTRA_ROUTE])),
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
            if record.get('addr') and info.alive:
                on_tile = bool(getattr(info, 'current_tile_ptr', 0)) \
                    and self.mc.is_ptr(info.current_tile_ptr)
                if on_tile:
                    # 实体已在地图格子上: 无论调度计时是否对得上, 直接纠为已出场。
                    record['spawn_eta'] = 0.0
                    record['spawn_condition'] = '已出场'
                    if (record.get('spawn_frame') is None
                            and self._fixed_frame_snap is not None):
                        record['spawn_frame'] = int(self._fixed_frame_snap)
                    self._copy_plan_metadata(info, record, 'active')
                    continue
                entry_eta = self._remaining_route_entry(info, record)
                if isinstance(entry_eta, (int, float)) and entry_eta > 0.05:
                    record['spawn_eta'] = entry_eta
                    record['spawn_condition'] = '实体已生成，正在地图外进入战场'
                    self._copy_plan_metadata(info, record, 'pending')
                    continue
            token = record.get('runtime_token') or (
                record.get('action_ptr'), record.get('spawn_index', 0))
            entry = entry_map.get(token)
            if (entry is not None and self._fragment_start_time >= 0
                    and scheduler_time is not None):
                entity_eta = max(0.0, self._fragment_start_time
                                 + entry['time_offset'] - float(scheduler_time))
                entry_delay = record.get('visible_entry_delay', 0.0)
                eta = entity_eta + max(0.0, entry_delay)
                record['spawn_eta'] = eta
                if entry_delay > 0.05:
                    record['spawn_condition'] = (
                        f'按实际进场计时（实体生成后约 {entry_delay:.1f} 秒进入地图）')
                else:
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
                    d = None   # 该内存块读取失败：跳过该块，不让整遍定位崩溃
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
                self._chan = self.mc.channel()
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

    def _track_attr_object(self, ep, attr_ptr):
        """记录实体当前 Attributes；对象换代时立即丢弃上一阶段的派生缓存。"""
        previous = self._attr_ptrs.get(ep, 0)
        if previous != attr_ptr:
            self._attr_cache.pop(ep, None)
            self._attr_snapshot.pop(ep, None)
        self._attr_ptrs[ep] = attr_ptr
        return previous != attr_ptr

    def _fill_attrs(self, ep, blk, info):
        """填充属性 (cachedData 数组地址有缓存, 失效时走完整链重解析)"""
        attrp = _u64(blk, gs.EntityFields.M_ATTRIBUTES)
        self._track_attr_object(ep, attrp)
        cd = None
        cdp = self._attr_cache.get(ep, 0)
        if cdp:
            cd = self.mc.read(cdp, 0x20 + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE)
            if not cd or not (0 < _i32(cd, gs.Il2CppArray.MAX_LENGTH) <= 64):
                self._attr_cache.pop(ep, None)
                cd = None
        if cd is None:
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
        """慢速路径技能 CD 解析。

        ``m_skills`` 是会在初始化、切阶段或技能启停时短暂清空的动态列表；
        ``m_allSkills`` 是敌人创建后稳定存在的完整数组。两者合并读取，避免一次
        临时空列表把已经显示的技能永久清掉，直到用户手动重新扫描。
        """
        out = []
        timed = []
        lp = _u64(blk, gs.EnemyFields.M_SKILLS) if len(blk) >= gs.EnemyFields.READ_SIZE else 0
        ap = _u64(blk, gs.EnemyFields.M_ALL_SKILLS) \
            if len(blk) >= gs.EnemyFields.READ_SIZE else 0
        if self.mc.is_ptr(lp):
            self._skill_lp[ep] = lp
        if self.mc.is_ptr(ap):
            self._skill_ap[ep] = ap

        skill_ptrs = []
        active_ptrs = []

        def append_container(ptr, is_array, active=False):
            if not self.mc.is_ptr(ptr):
                return False
            hd = self.mc.read(ptr, 0x20)
            if not hd:
                return False
            if is_array:
                items = ptr
                n = _i32(hd, gs.Il2CppArray.MAX_LENGTH)
            else:
                items = _u64(hd, gs.ListInternal.ITEMS)
                n = _i32(hd, gs.ListInternal.SIZE)
            if not (0 <= n <= 32):
                return False
            if n and not self.mc.is_ptr(items):
                return False
            arr = self.mc.read(items + gs.Il2CppArray.ITEMS, n * 8) if n else b''
            if n and not arr:
                return False
            for j in range(n):
                skill = _u64(arr, j * 8)
                if self.mc.is_ptr(skill):
                    if active and skill not in active_ptrs:
                        active_ptrs.append(skill)
                    if skill not in skill_ptrs:
                        skill_ptrs.append(skill)
            return True

        active_ok = append_container(lp, False, active=True)
        all_ok = append_container(ap, True)
        if active_ok:
            self._active_skill_ptrs[ep] = active_ptrs
        # 动态列表临时读取失败时沿用上次成功解析的对象地址；完整数组成功读取
        # （包括合法空数组）时才有权覆盖旧缓存。
        if skill_ptrs:
            self._skill_ptrs[ep] = skill_ptrs
        elif all_ok or (active_ok and ep not in self._skill_ptrs):
            self._skill_ptrs[ep] = []
        else:
            skill_ptrs = list(self._skill_ptrs.get(ep, ()))

        for s in skill_ptrs:
            sb = self.mc.read(s, gs.EnemySkillFields.READ_SIZE)
            if not sb:
                continue
            trigger_addr = _u64(sb, gs.EnemySkillFields.TRIGGER)
            self._skill_runtime_meta[s] = {
                'family_mask': _i32(sb, gs.EnemySkillFields.FAMILY_MASK),
                'cast_like_attack': bool(sb[gs.EnemySkillFields.CAST_LIKE_ATTACK]),
                'check_parent_active': bool(
                    sb[gs.EnemySkillFields.CHECK_PARENT_ACTIVE]),
                'ignore_silence': bool(sb[gs.EnemySkillFields.IGNORE_SILENCE]),
                'max_triggers': _i32(sb, gs.EnemySkillFields.MAX_TRIGGER_TIME),
                'trigger_count': _i32(sb, gs.EnemySkillFields.M_TRIGGER_CNT),
                'trigger_addr': trigger_addr,
                'has_trigger': self.mc.is_ptr(trigger_addr),
                'sp_cost_runtime': _i32(sb, gs.EnemySkillFields.M_SP_COST),
                'ability_addr': (_u64(sb, gs.EnemySkillFields.ABILITY)
                                 or _u64(sb, gs.EnemySkillFields.M_MAIN_ABILITY)),
                'parent_mode_addr': _u64(sb, gs.EnemySkillFields.PARENT_MODE),
                'is_enabled': s in self._active_skill_ptrs.get(ep, ()),
            }
            t = _u64(sb, gs.EnemySkillFields.M_COOLDOWN_TIMER)
            td = self.mc.read(t, 0x20) if self.mc.is_ptr(t) else None
            if not td:
                continue
            period = gs.fp_to_float(_u64(td, gs.PeriodicTimerFields.M_PERIOD_TIME))
            remain = gs.fp_to_float(_u64(td, gs.PeriodicTimerFields.M_REMAINING_TIME))
            if not (0 <= period <= 3600 and -1 <= remain <= 3600):
                continue
            key = self._skill_names.get(s)
            if key is None or s not in self._skill_static_meta:
                dp = _u64(sb, gs.EnemySkillFields.DATA)
                dd = self.mc.read(dp, 0x28) if self.mc.is_ptr(dp) else None
                if dd:
                    prio = _i32(dd, gs.ESkillDataFields.PRIORITY)
                    sp_cost = _i32(dd, gs.ESkillDataFields.SP_COST)
                    if -10000 <= prio <= 10000 and 0 <= sp_cost <= 100000:
                        self._skill_static_meta[s] = {
                            'priority': prio, 'sp_cost': sp_cost}
                if key is None:
                    pk = _u64(dd, gs.ESkillDataFields.PREFAB_KEY) if dd else 0
                    key = (self.mc.read_ustring(pk) if self.mc.is_ptr(pk) else None) or '?'
                    self._skill_names[s] = key
            out.append((key, remain, period))
            timed.append((s, remain, period))
        trigger_states = self._read_trigger_states_chan([
            self._skill_runtime_meta.get(s, {}).get('trigger_addr', 0)
            for s in skill_ptrs])
        for s in skill_ptrs:
            meta = self._skill_runtime_meta.get(s, {})
            meta.update(trigger_states.get(meta.get('trigger_addr', 0), {}))
        rows = [self._build_skill_row(s, remain, period)
                for s, remain, period in timed]
        if out or not self._skill_cd.get(ep) or (all_ok and not skill_ptrs):
            self._skill_cd[ep] = out
            self._skill_enriched[ep] = rows
        info.skills = list(self._skill_cd.get(ep, ()))
        info.skills_detail = list(self._skill_enriched.get(ep, ()))
        return info

    def _fill_name(self, ep, blk, info):
        """填充名称 (只读一次, 之后走缓存; 空 ID 是瞬读失败, 不缓存,
        留待下帧重试, 否则实体永远无法按 ID 认领计划项)"""
        if ep not in self._names:
            eid = self.mc.read_ustring(_u64(blk, gs.EntityFields.ID)) or ''
            if eid:
                runtime_name = ''
                data_ptr = info.data_ptr or _u64(blk, gs.EnemyFields.DATA)
                if self.mc.is_ptr(data_ptr):
                    name_ptr = self._read_ptr(data_ptr + gs.LevelEnemyDataFields.NAME)
                    if self.mc.is_ptr(name_ptr):
                        runtime_name = self.mc.read_ustring(name_ptr) or ''
                name, code = self._remember_enemy_name(eid, runtime_name)
                self._names[ep] = (eid, name, code)
        info.eid, info.name, info.code = self._names.get(ep, ('', '', ''))
        return info

    @staticmethod
    def _parse_enemy_block(ep, blk):
        """解析 Enemy 主对象块；不跟随指针，供慢速与聚簇快读共用。"""
        info = EnemyInfo(ep)
        min_size = max(gs.EntityFields.BUFF_CONTAINER + 8,
                       gs.EnemyFields.DATA + 8)
        if not blk or len(blk) < min_size:
            info.alive = False
            return info
        info.hp = gs.fp_to_float(_u64(blk, gs.EntityFields.M_HP))
        info.es = gs.fp_to_float(_u64(blk, gs.EntityFields.M_ES))
        info.direction = _i32(blk, gs.EntityFields.M_DIRECTION)
        info.finish = _i32(blk, gs.EntityFields.FINISH_REASON)
        info.id_ptr = _u64(blk, gs.EntityFields.ID)
        info.attr_ptr = _u64(blk, gs.EntityFields.M_ATTRIBUTES)
        info.data_ptr = _u64(blk, gs.EnemyFields.DATA)
        info.current_tile_ptr = _u64(blk, gs.EnemyFields.M_CURRENT_TILE)
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
            info.action = {
                'animator_addr': _u64(blk, gs.UnitFields.ANIMATOR),
                'current_mode_addr': _u64(blk, gs.UnitFields.CURRENT_MODE),
                'sp': gs.obscured_fp_to_float(
                    _u64(blk, gs.EntityFields.M_SP),
                    _u64(blk, gs.EntityFields.M_SP + 8)),
                'max_sp': _i32(blk, gs.EntityFields.MAX_SP),
                'override_attack_addr': _u64(blk, gs.UnitFields.OVERRIDE_ATTACK),
                'override_combat_addr': _u64(blk, gs.UnitFields.OVERRIDE_COMBAT),
                'attack_ability_addr': _u64(
                    blk, gs.EnemyFields.ATTACK_ABILITY_CASTED),
                'combat_ability_addr': _u64(
                    blk, gs.EnemyFields.COMBAT_ABILITY_CASTED),
                'combat_escape_time': gs.fp_to_float(_u64(
                    blk, gs.EnemyFields.COMBAT_NEXT_ESCAPE_TIME)),
                'attack_wrapper_addr': _u64(
                    blk, gs.EnemyFields.ATTACK_WRAPPER),
                'combat_wrapper_addr': _u64(
                    blk, gs.EnemyFields.COMBAT_WRAPPER),
                'blocker_addr': _u64(blk, gs.EnemyFields.M_BLOCKER),
            }
        # HP=0 本身不能证明实体已经离场：多阶段 Boss 会先清空 HP，再进入
        # REBORN。状态机批次稍后给出权威终止态；读不到状态时宁可保留一帧。
        info.alive = info.finish == 0
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
        # 多阶段 Boss 在 REBORN/BORN 中会把 HP 暂时清零，但实例仍由
        # UnitManager 持有且尚未 finish。不能把这一小段误记为已离场。
        info.alive = (info.finish == 0 and info.state_id not in (
            gs.EnemyState.TERMINAL, gs.EnemyState.DEAD,
            gs.EnemyState.REACH_EXIT))
        info.action = dict(runtime.get('action', info.action))
        info.shield = runtime.get('shield', info.shield)
        info.special_shield = runtime.get('special_shield', info.special_shield)
        info.special_shield_mask = runtime.get(
            'special_shield_mask', info.special_shield_mask)
        info.special_shield_sources = list(runtime.get(
            'special_shield_sources', info.special_shield_sources))
        info.ep_remaining = dict(runtime.get('ep_remaining', {}))
        info.ep_break_recovery = bool(runtime.get('ep_break_recovery', False))
        info.abnormal_flags = list(runtime.get('abnormal_flags', info.abnormal_flags))
        info.abnormal_immunes = list(runtime.get('abnormal_immunes', info.abnormal_immunes))
        info.abnormal_antis = list(runtime.get('abnormal_antis', info.abnormal_antis))
        info.abnormal_combos = list(runtime.get('abnormal_combos', info.abnormal_combos))
        info.abnormal_combo_immunes = list(
            runtime.get('abnormal_combo_immunes', info.abnormal_combo_immunes))
        info.status_timers = {
            str(key): dict(value) for key, value in
            (runtime.get('status_timers') or {}).items()
        }

    def _resolve_animation_states_chan(self, actions):
        """从 Spine/Mesh 两种 CurrentAniState 候选中解析当前动画键。"""
        ptrs = []
        for action in actions.values():
            for candidate in action.get('animation_candidates', ()):
                ptr = candidate.get('key_ptr', 0)
                speed = candidate.get('speed')
                if (self.mc.is_ptr(ptr) and isinstance(speed, (int, float))
                        and math.isfinite(speed) and abs(speed) <= 100
                        and ptr not in self._animation_name_cache):
                    ptrs.append(ptr)
        ptrs = list(dict.fromkeys(ptrs))
        if ptrs:
            for ptr, data in zip(ptrs, self._detail_batch_read([(ptr, 0x100)
                                                                 for ptr in ptrs])):
                value = ''
                if data and len(data) >= gs.Il2CppString.CHARS:
                    count = _i32(data, gs.Il2CppString.LENGTH)
                    if 0 < count <= 96 and gs.Il2CppString.CHARS + count * 2 <= len(data):
                        try:
                            value = data[gs.Il2CppString.CHARS:
                                         gs.Il2CppString.CHARS + count * 2
                                         ].decode('utf-16-le')
                        except UnicodeDecodeError:
                            value = ''
                self._animation_name_cache[ptr] = value
        for action in actions.values():
            chosen = None
            for candidate in action.get('animation_candidates', ()):
                name = self._animation_name_cache.get(candidate.get('key_ptr', 0), '')
                if name:
                    chosen = (name, candidate.get('speed'), candidate.get('backend'))
                    break
            if chosen:
                action['animation_key'], action['animation_speed'], \
                    action['animation_backend'] = chosen
            else:
                action.pop('animation_key', None)
                action.pop('animation_speed', None)
                action.pop('animation_backend', None)
            action.pop('animation_candidates', None)

    def _read_object_class_names_chan(self, ptrs):
        """批量读取托管对象 klass 名；只用于首次校准动画器具体类型。"""
        ptrs = [ptr for ptr in dict.fromkeys(ptrs) if self.mc.is_ptr(ptr)]
        if not ptrs:
            return {}
        klasses = {}
        for ptr, data in zip(ptrs, self._detail_batch_read([(ptr, 8) for ptr in ptrs])):
            klass = _u64(data, 0) if data else 0
            if self.mc.is_ptr(klass):
                klasses[ptr] = klass
        name_ptrs = {}
        owners = list(klasses)
        for ptr, data in zip(
                owners, self._detail_batch_read([
                    (klasses[ptr] + 0x10, 8) for ptr in owners])):
            name_ptr = _u64(data, 0) if data else 0
            if self.mc.is_ptr(name_ptr):
                name_ptrs[ptr] = name_ptr
        out = {}
        owners = list(name_ptrs)
        for ptr, data in zip(
                owners, self._detail_batch_read([
                    (name_ptrs[ptr], 96) for ptr in owners])):
            if not data:
                continue
            raw = data.split(b'\0', 1)[0]
            try:
                out[ptr] = raw.decode('utf-8')
            except UnicodeDecodeError:
                continue
        return out

    def _read_trigger_states_chan(self, ptrs, prefetched=None):
        """读取 TargetTrigger 的原始运行时判定状态。

        这里只复现能从对象字段无副作用读取的部分。不能调用游戏的 ``Search``，
        因为它会刷新选择器、消费随机数或触发关卡分支；这类条件返回 ``None``，
        由上层明确显示为“规则条件待判”，而不是擅自猜测。
        """
        ptrs = [ptr for ptr in dict.fromkeys(ptrs) if self.mc.is_ptr(ptr)]
        if not ptrs:
            return {}
        missing = [ptr for ptr in ptrs if ptr not in self._trigger_type_cache]
        if missing:
            self._trigger_type_cache.update(self._read_object_class_names_chan(missing))
        prefetched = prefetched or {}
        blocks = [prefetched.get(ptr) for ptr in ptrs]
        missing = [(idx, ptr) for idx, (ptr, data) in enumerate(
            zip(ptrs, blocks)) if not data]
        if missing:
            fetched = self._detail_batch_read([
                (ptr, gs.TargetTriggerFields.READ_SIZE)
                for _idx, ptr in missing])
            for (idx, _ptr), data in zip(missing, fetched):
                blocks[idx] = data
        out = {}
        for ptr, data in zip(ptrs, blocks):
            trigger_type = self._trigger_type_cache.get(ptr, '')
            item = {
                'trigger_addr': ptr,
                'trigger_type': trigger_type or 'TargetTrigger',
                'trigger_ready': None,
                'trigger_reason': '该 TargetTrigger 的 Search 条件尚未解析',
            }
            if not data:
                item['trigger_reason'] = 'TargetTrigger 本轮读取失败'
            elif trigger_type == 'AlwaysTrigger':
                item.update(trigger_ready=True,
                            trigger_reason='AlwaysTrigger 原始规则恒为通过')
            elif trigger_type == 'NeverTrigger':
                item.update(trigger_ready=False,
                            trigger_reason='NeverTrigger 原始规则恒为不通过')
            elif trigger_type in SELECTOR_TRIGGER_TYPES:
                target = _u64(data, gs.SelectorTriggerFields.LAST_TARGET)
                minimum = _i32(data, gs.SelectorTriggerFields.MIN_TARGET_NUM)
                item.update(trigger_target_addr=target,
                            trigger_min_targets=minimum)
                if self.mc.is_ptr(target) and minimum <= 1:
                    item.update(
                        trigger_ready=True,
                        trigger_reason=(
                            f'{trigger_type}.m_lastTarget 已有有效目标，满足最少 '
                            f'{max(1, minimum)} 个目标'))
                elif self.mc.is_ptr(target):
                    item['trigger_reason'] = (
                        f'{trigger_type} 已缓存目标，但最少目标数为 {minimum}；'
                        '必须执行选择器才能确认总数')
                else:
                    item['trigger_reason'] = (
                        f'{trigger_type}.m_lastTarget 当前为空；下一次 Search 可能刷新，'
                        '不能据此判定失败')
            elif trigger_type == 'LevelBranchTrigger':
                branch_ptr = _u64(data, 0x30)
                item.update(
                    trigger_branch_ptr=branch_ptr,
                    trigger_reason=(
                        'LevelBranchTrigger 依赖关卡 Scheduler 的分支完成/循环状态；'
                        '客户端在 Search 时查询，当前对象没有缓存布尔结果'))
            elif trigger_type == 'SpTrigger':
                item.update(
                    trigger_value_type=_i32(data, gs.SpTriggerFields.VALUE_TYPE),
                    trigger_value=struct.unpack_from(
                        '<f', data, gs.SpTriggerFields.VALUE_TO_COMPARE)[0],
                    trigger_compare_type=_i32(data, gs.SpTriggerFields.COMPARE_TYPE),
                    trigger_reason=(
                        'SpTrigger 还需按 CompareType 对 owner 当前技力/充能层数求值'))
            out[ptr] = item
        return out

    def _resolve_spine_animation_meta_chan(self, animation_ptrs):
        missing = [ptr for ptr in dict.fromkeys(animation_ptrs)
                   if self.mc.is_ptr(ptr) and ptr not in self._spine_animation_cache]
        if not missing:
            return
        name_ptrs = {}
        for ptr, data in zip(
                missing, self._detail_batch_read([
                    (ptr, gs.SpineAnimationFields.READ_SIZE) for ptr in missing])):
            if not data:
                continue
            name_ptr = _u64(data, gs.SpineAnimationFields.NAME)
            duration = struct.unpack_from(
                '<f', data, gs.SpineAnimationFields.DURATION)[0]
            self._spine_animation_cache[ptr] = {
                'name': '',
                'duration': duration if math.isfinite(duration) else None,
            }
            if self.mc.is_ptr(name_ptr):
                name_ptrs[ptr] = name_ptr
        strings = self._read_strings(name_ptrs.values(), 96)
        for ptr, name_ptr in name_ptrs.items():
            self._spine_animation_cache[ptr]['name'] = strings.get(name_ptr, '')

    def _discover_spine_skeleton_layouts_chan(self, skeletons):
        """把 SkeletonAnimation 固定链解析到 track 0 的 items 数组。"""
        missing = [ptr for ptr in dict.fromkeys(skeletons)
                   if self.mc.is_ptr(ptr)
                   and ptr not in self._spine_skeleton_layout_cache]
        states = {}
        for skeleton, data in zip(
                missing, self._detail_batch_read([
                    (ptr + gs.SkeletonAnimationFields.STATE, 8)
                    for ptr in missing])):
            state = _u64(data, 0) if data else 0
            if self.mc.is_ptr(state):
                states[skeleton] = state
        tracks = {}
        for skeleton, data in zip(
                states, self._detail_batch_read([
                    (state + gs.SpineAnimationStateFields.TRACKS, 8)
                    for state in states.values()])):
            track_list = _u64(data, 0) if data else 0
            if self.mc.is_ptr(track_list):
                tracks[skeleton] = track_list
        for skeleton, data in zip(
                tracks, self._detail_batch_read([
                    (track_list, 0x20) for track_list in tracks.values()])):
            if not data:
                continue
            items = _u64(data, gs.SpineExposedListFields.ITEMS)
            count = _i32(data, gs.SpineExposedListFields.COUNT)
            if self.mc.is_ptr(items) and 0 < count <= 16:
                self._spine_skeleton_layout_cache[skeleton] = {
                    'state': states[skeleton],
                    'tracks': tracks[skeleton],
                    'items': items,
                }

    def _refresh_animation_tracks_chan(self, actions):
        """读取 Spine track 0，给当前动作提供精确动画剩余量和排队动画。

        动画器 concrete type 与 Skeleton/AnimationState 链只在首次出现时解析；
        稳态每轮批量核对三个固定指针，再读取 track 0 小块，避免逐对象 TCP 往返。
        MeshAnimator 没有 Spine TrackEntry，继续保留状态机/Ability 兜底。
        """
        track_keys = (
            'animation_track_addr', 'animation_track_name', 'animation_loop',
            'animation_start', 'animation_end', 'animation_track_time',
            'animation_track_speed', 'animation_remaining',
            'animation_exact', 'animation_next_track_name',
        )
        for action in actions.values():
            for key in track_keys:
                action.pop(key, None)

        animator_of = {
            owner: action.get('animator_addr', 0)
            for owner, action in actions.items()
            if self.mc.is_ptr(action.get('animator_addr', 0))
        }
        unknown = [animator for animator in dict.fromkeys(animator_of.values())
                   if animator not in self._animator_layout_cache]
        for animator, klass in self._read_object_class_names_chan(unknown).items():
            self._animator_layout_cache[animator] = {'klass': klass}

        skeleton_of = {}
        direct_reqs, direct_keys = [], []
        for owner, animator in animator_of.items():
            layout = self._animator_layout_cache.get(animator, {})
            klass = layout.get('klass', '')
            if klass == 'SingleSpineAnimator':
                skeleton = layout.get('skeleton', 0)
                if self.mc.is_ptr(skeleton):
                    skeleton_of[owner] = skeleton
                else:
                    direct_reqs.append((
                        animator + gs.SingleSpineAnimatorFields.SKELETON, 8))
                    direct_keys.append((owner, animator, 'single'))
            elif klass == 'CharacterAnimator':
                direct_reqs.append((
                    animator + gs.CharacterAnimatorFields.ACTIVE_FACE, 8))
                direct_keys.append((owner, animator, 'character'))
            elif klass == 'MultiSpineAnimator':
                direct_reqs.append((
                    animator + gs.MultiSpineAnimatorFields.FACES, 0x18))
                direct_keys.append((owner, animator, 'multi'))

        missing_faces = {}
        multi_heads = {}
        for (owner, animator, kind), data in zip(
                direct_keys,
                self._detail_batch_read(direct_reqs) if direct_reqs else []):
            if not data:
                continue
            if kind == 'single':
                skeleton = _u64(data, 0)
                if self.mc.is_ptr(skeleton):
                    self._animator_layout_cache[animator]['skeleton'] = skeleton
                    skeleton_of[owner] = skeleton
            elif kind == 'character':
                face = _u64(data, 0)
                skeleton = self._spine_face_skeleton_cache.get(face, 0)
                if self.mc.is_ptr(skeleton):
                    skeleton_of[owner] = skeleton
                elif self.mc.is_ptr(face):
                    missing_faces[owner] = face
            else:
                faces = _u64(data, 0)
                index = _i32(data, 0x10)
                if self.mc.is_ptr(faces) and 0 <= index <= 32:
                    multi_heads[owner] = (faces, index)

        if missing_faces:
            for owner, data in zip(
                    missing_faces, self._detail_batch_read([
                        (face + gs.SpineFaceFields.SKELETON, 8)
                        for face in missing_faces.values()])):
                skeleton = _u64(data, 0) if data else 0
                if self.mc.is_ptr(skeleton):
                    face = missing_faces[owner]
                    self._spine_face_skeleton_cache[face] = skeleton
                    skeleton_of[owner] = skeleton

        multi_items = {}
        if multi_heads:
            for owner, data in zip(
                    multi_heads, self._detail_batch_read([
                        (faces, 0x20) for faces, _index in multi_heads.values()])):
                if not data:
                    continue
                items = _u64(data, gs.ListInternal.ITEMS)
                count = _i32(data, gs.ListInternal.SIZE)
                index = multi_heads[owner][1]
                if self.mc.is_ptr(items) and 0 <= index < count <= 32:
                    multi_items[owner] = (items, index)
        multi_subs = {}
        if multi_items:
            for owner, data in zip(
                    multi_items, self._detail_batch_read([
                        (items + gs.Il2CppArray.ITEMS + index * 8, 8)
                        for items, index in multi_items.values()])):
                sub = _u64(data, 0) if data else 0
                if self.mc.is_ptr(sub):
                    multi_subs[owner] = sub
        if multi_subs:
            for owner, data in zip(
                    multi_subs, self._detail_batch_read([
                        (sub + gs.SpineFaceFields.SKELETON, 8)
                        for sub in multi_subs.values()])):
                skeleton = _u64(data, 0) if data else 0
                if self.mc.is_ptr(skeleton):
                    skeleton_of[owner] = skeleton

        self._discover_spine_skeleton_layouts_chan(skeleton_of.values())
        valid = {
            owner: (skeleton, self._spine_skeleton_layout_cache[skeleton])
            for owner, skeleton in skeleton_of.items()
            if skeleton in self._spine_skeleton_layout_cache
        }
        if not valid:
            return

        # 同一批核对 Skeleton->state、state->tracks、tracks->items，读取当前
        # track 指针，并投机读取上一帧 track。稳态由原来的三次往返压成一次；
        # 只有动画切换导致 track 指针变化时才补读新对象。
        verify_reqs, verify_keys = [], []
        for owner, (skeleton, layout) in valid.items():
            verify_reqs.extend((
                (skeleton + gs.SkeletonAnimationFields.STATE, 0x40),
                (layout['state'] + gs.SpineAnimationStateFields.TRACKS, 0x58),
                (layout['tracks'], 0x20),
                (layout['items'] + gs.Il2CppArray.ITEMS, 8),
            ))
            verify_keys.extend(((owner, 'skeleton'), (owner, 'state'),
                                (owner, 'tracks'), (owner, 'track_ptr')))
            cached_track = layout.get('track', 0)
            if self.mc.is_ptr(cached_track):
                verify_reqs.append((cached_track, gs.SpineTrackEntryFields.READ_SIZE))
                verify_keys.append((owner, 'cached_track'))
        verified = {owner: {} for owner in valid}
        for (owner, kind), data in zip(
                verify_keys, self._detail_batch_read(verify_reqs)):
            if not data:
                continue
            skeleton, layout = valid[owner]
            if kind == 'skeleton':
                state = _u64(data, 0)
                scale = struct.unpack_from(
                    '<f', data,
                    gs.SkeletonAnimationFields.TIME_SCALE
                    - gs.SkeletonAnimationFields.STATE)[0]
                if state == layout['state'] and math.isfinite(scale):
                    verified[owner]['skeleton_scale'] = scale
            elif kind == 'state':
                tracks = _u64(data, 0)
                scale = struct.unpack_from(
                    '<f', data,
                    gs.SpineAnimationStateFields.TIME_SCALE
                    - gs.SpineAnimationStateFields.TRACKS)[0]
                if tracks == layout['tracks'] and math.isfinite(scale):
                    verified[owner]['state_scale'] = scale
            elif kind == 'tracks':
                items = _u64(data, gs.SpineExposedListFields.ITEMS)
                count = _i32(data, gs.SpineExposedListFields.COUNT)
                if items == layout['items'] and 0 < count <= 16:
                    verified[owner]['items_ok'] = True
            elif kind == 'track_ptr':
                track = _u64(data, 0)
                if self.mc.is_ptr(track):
                    verified[owner]['track'] = track
            else:
                verified[owner]['cached_track_data'] = data

        track_owners = [owner for owner, row in verified.items()
                        if row.get('items_ok')
                        and 'skeleton_scale' in row and 'state_scale' in row
                        and self.mc.is_ptr(row.get('track', 0))]
        track_ptrs = {owner: verified[owner]['track'] for owner in track_owners}
        track_data = {}
        missing_track_owners = []
        for owner, track in track_ptrs.items():
            layout = valid[owner][1]
            cached = layout.get('track', 0)
            data = verified[owner].get('cached_track_data')
            layout['track'] = track
            if track == cached and data:
                track_data[owner] = data
            else:
                missing_track_owners.append(owner)
        for owner, data in zip(
                missing_track_owners, self._detail_batch_read([
                    (track_ptrs[owner], gs.SpineTrackEntryFields.READ_SIZE)
                    for owner in missing_track_owners])):
            if data:
                track_data[owner] = data

        parsed = {}
        next_ptrs = {}
        for owner, data in track_data.items():
            if not data:
                continue
            start = struct.unpack_from(
                '<f', data, gs.SpineTrackEntryFields.ANIMATION_START)[0]
            end = struct.unpack_from(
                '<f', data, gs.SpineTrackEntryFields.ANIMATION_END)[0]
            track_time = struct.unpack_from(
                '<f', data, gs.SpineTrackEntryFields.TRACK_TIME)[0]
            entry_scale = struct.unpack_from(
                '<f', data, gs.SpineTrackEntryFields.TIME_SCALE)[0]
            loop = bool(data[gs.SpineTrackEntryFields.LOOP])
            row = verified[owner]
            remaining = spine_track_remaining(
                start, end, track_time, entry_scale,
                row['state_scale'], row['skeleton_scale'], loop)
            parsed[owner] = {
                'track': track_ptrs[owner],
                'animation': _u64(data, gs.SpineTrackEntryFields.ANIMATION),
                'next': _u64(data, gs.SpineTrackEntryFields.NEXT),
                'loop': loop, 'start': start, 'end': end,
                'track_time': track_time,
                'speed': entry_scale * row['state_scale'] * row['skeleton_scale'],
                'remaining': remaining,
            }
            if self.mc.is_ptr(parsed[owner]['next']):
                next_ptrs[owner] = parsed[owner]['next']

        next_animations = {}
        if next_ptrs:
            for owner, data in zip(
                    next_ptrs, self._detail_batch_read([
                        (ptr + gs.SpineTrackEntryFields.ANIMATION, 8)
                        for ptr in next_ptrs.values()])):
                animation = _u64(data, 0) if data else 0
                if self.mc.is_ptr(animation):
                    next_animations[owner] = animation
        animation_ptrs = [row['animation'] for row in parsed.values()]
        animation_ptrs.extend(next_animations.values())
        self._resolve_spine_animation_meta_chan(animation_ptrs)

        for owner, row in parsed.items():
            action = actions[owner]
            meta = self._spine_animation_cache.get(row['animation'], {})
            action.update({
                'animation_track_addr': row['track'],
                'animation_track_name': meta.get('name') or action.get('animation_key', ''),
                'animation_loop': row['loop'],
                'animation_start': row['start'],
                'animation_end': row['end'],
                'animation_track_time': row['track_time'],
                'animation_track_speed': row['speed'],
            })
            if row['remaining'] is not None:
                action['animation_remaining'] = row['remaining']
                action['animation_exact'] = True
            next_meta = self._spine_animation_cache.get(
                next_animations.get(owner, 0), {})
            if next_meta.get('name'):
                action['animation_next_track_name'] = next_meta['name']

    def _refresh_status_timers_chan(self, targets, snapshots, tick):
        """低开销读取维持异常状态的 Buff 剩余时间。

        只在进入异常态或缓存失效时遍历 BuffContainer；稳定期间直接读取已缓存
        Buff 的计时器和 mask，避免每个高速轮询都重新展开整条容器链。
        ``targets`` 元素为 ``(addr, container, state, flag_bits, combo_bits)``，
        后两项包含实体当前全部生效状态，而非只挑状态机对应的少数异常。
        """
        def bits(value):
            if value is None:
                return ()
            if isinstance(value, int):
                return (value,)
            return tuple(value)

        targets = [(addr, container, state_id, bits(flag_bits), bits(combo_bits))
                   for addr, container, state_id, flag_bits, combo_bits in targets
                   if self.mc.is_ptr(container)]
        if not targets:
            return
        active = {addr for addr, *_rest in targets}
        target_states = {addr: state_id for addr, _container, state_id, *_rest in targets}
        for addr, container, state_id, flag_bits, combo_bits in targets:
            cached = self._status_timer_cache.get(addr)
            signature = (container, state_id, tuple(flag_bits), tuple(combo_bits))
            cached_signature = cached.get('signature') if cached else None
            if cached_signature and len(cached_signature) == 4:
                cached_signature = (
                    cached_signature[0], cached_signature[1],
                    bits(cached_signature[2]), bits(cached_signature[3]))
            if not cached or cached_signature != signature:
                self._status_timer_cache[addr] = {
                    'signature': signature, 'buffs': [], 'last_probe': -10000,
                }
            else:
                cached['signature'] = signature

        # 完整 60Hz 模式下容器结构也逐帧确认。稳定指针链将 container、
        # double buffer、List 头、items 和 Buff 动态块合并进一个 batch；任一
        # 指针变化时当帧补读后续层，不降低采样频率。
        probes = list(targets)
        reqs, tags = [], []
        buff_read_size = (gs.BuffFields.ABNORMAL_COMBO_MASK + 8
                          - gs.BuffFields.M_LIFE_TIME)
        for addr, container, *_rest in probes:
            cache = self._status_timer_cache[addr]
            cache['last_probe'] = tick
            reqs.append((container, 0x30))
            tags.append((addr, 'container'))
            if cache.get('signature', (None,))[0] != container:
                continue
            double = cache.get('double', 0)
            list_ptr = cache.get('list', 0)
            items = cache.get('items', 0)
            count = cache.get('count', 0)
            if self.mc.is_ptr(double):
                reqs.append((double, 0x28))
                tags.append((addr, 'double'))
            if self.mc.is_ptr(list_ptr):
                reqs.append((list_ptr, 0x20))
                tags.append((addr, 'list'))
            if self.mc.is_ptr(items) and 0 < count <= 512:
                reqs.append((items + gs.Il2CppArray.ITEMS, count * 0x10))
                tags.append((addr, 'body'))
            for buff in cache.get('buffs', ()):
                if self.mc.is_ptr(buff):
                    reqs.append((buff + gs.BuffFields.M_LIFE_TIME,
                                 buff_read_size))
                    tags.append((addr, 'buff', buff))
        values = dict(zip(tags, self._detail_batch_read(reqs)))

        doubles, need = {}, []
        for addr, container, *_rest in probes:
            data = values.get((addr, 'container'))
            double = _u64(data, gs.BuffContainerFields.M_BUFFS) if data else 0
            if not self.mc.is_ptr(double):
                if data:
                    self._status_timer_cache[addr].update(
                        double=0, list=0, items=0, count=0, buffs=[])
                continue
            doubles[addr] = double
            cache = self._status_timer_cache[addr]
            if cache.get('double') != double or not values.get((addr, 'double')):
                need.append((addr, double))
        double_data = {addr: values.get((addr, 'double')) for addr in doubles}
        for (addr, _ptr), data in zip(
                need, self._detail_batch_read([(ptr, 0x28) for _addr, ptr in need])):
            double_data[addr] = data

        lists, need = {}, []
        for addr, double in doubles.items():
            data = double_data.get(addr)
            list_ptr = (_u64(data, gs.DoubleBufferedListFields.M_INTERNAL_LIST)
                        if data else 0)
            if not self.mc.is_ptr(list_ptr):
                if data:
                    self._status_timer_cache[addr].update(
                        double=double, list=0, items=0, count=0, buffs=[])
                continue
            lists[addr] = list_ptr
            cache = self._status_timer_cache[addr]
            if cache.get('list') != list_ptr or not values.get((addr, 'list')):
                need.append((addr, list_ptr))
        list_data = {addr: values.get((addr, 'list')) for addr in lists}
        for (addr, _ptr), data in zip(
                need, self._detail_batch_read([(ptr, 0x20) for _addr, ptr in need])):
            list_data[addr] = data

        heads, need = {}, []
        for addr, list_ptr in lists.items():
            data = list_data.get(addr)
            items = _u64(data, gs.ListInternal.ITEMS) if data else 0
            count = _i32(data, gs.ListInternal.SIZE) if data else -1
            if not (0 <= count <= 512 and (not count or self.mc.is_ptr(items))):
                if data:
                    self._status_timer_cache[addr].update(
                        double=doubles[addr], list=list_ptr,
                        items=0, count=0, buffs=[])
                continue
            heads[addr] = (items, count)
            cache = self._status_timer_cache[addr]
            if count and ((cache.get('items'), cache.get('count')) != (items, count)
                          or not values.get((addr, 'body'))):
                need.append((addr, items, count))
        body_data = {addr: values.get((addr, 'body')) for addr in heads}
        for (addr, _items, _count), data in zip(
                need, self._detail_batch_read([
                    (items + gs.Il2CppArray.ITEMS, count * 0x10)
                    for _addr, items, count in need])):
            body_data[addr] = data

        for addr, (items, count) in heads.items():
            data = body_data.get(addr) if count else b''
            buffs = []
            if not count:
                buffs = []
            elif data:
                buffs = [_u64(data, idx * 0x10) for idx in range(count)
                         if idx * 0x10 + 8 <= len(data)]
                buffs = [ptr for ptr in buffs if self.mc.is_ptr(ptr)]
            else:
                buffs = list(self._status_timer_cache[addr].get('buffs', ()))
            cache = self._status_timer_cache[addr]
            cache.update(
                double=doubles[addr], list=lists[addr], items=items,
                count=count, buffs=buffs)

        rows, missing_reqs, block_values = [], [], {}
        for addr, _container, state_id, flag_bits, combo_bits in targets:
            for buff in self._status_timer_cache[addr]['buffs']:
                row = (addr, state_id, flag_bits, combo_bits, buff)
                rows.append(row)
                data = values.get((addr, 'buff', buff))
                if data:
                    block_values[(addr, buff)] = data
                else:
                    missing_reqs.append((addr, buff))
        for (addr, buff), data in zip(
                missing_reqs, self._detail_batch_read([
                    (buff + gs.BuffFields.M_LIFE_TIME, buff_read_size)
                    for _addr, buff in missing_reqs])):
            block_values[(addr, buff)] = data
        matches = {addr: {} for addr in active}
        for addr, _state, flag_bits, combo_bits, buff in rows:
            data = block_values.get((addr, buff))
            if not data:
                continue
            base = gs.BuffFields.M_LIFE_TIME
            finished = bool(data[gs.BuffFields.IS_FINISHED - base])
            enabled = bool(data[gs.BuffFields.IS_ACTUALLY_ENABLED - base])
            valid = bool(data[gs.BuffFields.IS_VALID - base])
            if finished or not enabled or not valid:
                continue
            flag_mask = _u64(data, gs.BuffFields.ABNORMAL_FLAG_MASK - base)
            combo_mask = _u64(data, gs.BuffFields.ABNORMAL_COMBO_MASK - base)
            life = gs.fp_to_float(_u64(data, 0))
            remaining = gs.fp_to_float(_u64(
                data, gs.BuffFields.M_REMAINING_TIME - base))
            for bit in flag_bits:
                if flag_mask & (1 << bit):
                    matches[addr].setdefault(f'flag:{bit}', []).append(
                        (life, remaining))
            for bit in combo_bits:
                if combo_mask & (1 << bit):
                    matches[addr].setdefault(f'combo:{bit}', []).append(
                        (life, remaining))

        state_primary = {
            gs.EnemyState.STUN: 'flag:0',
            gs.EnemyState.FROZEN: 'flag:16',
            gs.EnemyState.LEVITATE: 'flag:25',
            gs.EnemyState.PALSY: 'flag:39',
        }
        for addr, by_status in matches.items():
            action = snapshots.setdefault(addr, {}).setdefault('action', {})
            timers = {}
            for key, values in by_status.items():
                finite = [max(0.0, remaining) for life, remaining in values
                          if life >= 0 and remaining >= 0]
                if len(finite) == len(values):
                    timers[key] = {
                        'remaining': max(finite, default=0.0),
                        'infinite': False,
                        'source_count': len(values),
                    }
                else:
                    timers[key] = {
                        'remaining': None,
                        'infinite': True,
                        'source_count': len(values),
                    }
            snapshots[addr]['status_timers'] = timers
            primary = state_primary.get(
                snapshots[addr].get('state_id', target_states.get(addr)))
            if primary is None and 'combo:0' in timers:
                primary = 'combo:0'
            selected = timers.get(primary) if primary else None
            if selected:
                action['status_source_count'] = selected['source_count']
                action['status_infinite'] = selected['infinite']
                if selected['remaining'] is None:
                    action.pop('status_remaining', None)
                else:
                    action['status_remaining'] = selected['remaining']
            else:
                action.pop('status_remaining', None)
                action.pop('status_source_count', None)
                action.pop('status_infinite', None)
                # 原地址已失效但状态仍在，下轮重新展开容器寻找覆盖后的 Buff。
                if self._status_timer_cache[addr]['buffs']:
                    self._status_timer_cache[addr]['buffs'] = []
                    self._status_timer_cache[addr]['last_probe'] = tick - 10

    def _predict_enemy_next_action(self, info, action):
        """展示游戏已写入的下一动作，或按客户端原始规则计算当前结果。

        AttackWrapper 没有 next 槽；CombatWrapper 的 picked 槽只在切状态前短暂
        存在。未写入时复现 MoveState 分流和 Wrapper._PickAbility：按 priority
        从高到低逐组检查 ``m_skills``，每组逐项执行启用/CD/次数/父模式/SP、
        family 与 TargetTrigger 条件；当前组没有可用项时继续下一组，同优先级
        多个通过项由游戏随机择一。无法无副作用复现的 Lua、关卡分支或目标
        重新搜索会明确标为“条件未完全解析”。
        """
        for key in ('next_action', 'next_action_detail', 'next_action_confidence',
                    'next_action_lane', 'next_action_candidates',
                    'next_action_rule', 'next_action_rule_detail',
                    'next_action_rule_confidence',
                    'next_action_rule_candidates'):
            action.pop(key, None)

        def publish_same(label, detail, confidence):
            """游戏已确定或当前无预测空间时，两行展示同一权威结果。"""
            action.update(
                next_action=label,
                next_action_detail=detail,
                next_action_confidence=confidence,
                next_action_rule=label,
                next_action_rule_detail=detail,
                next_action_rule_confidence=confidence,
            )

        state_id = info.state_id
        if state_id in (gs.EnemyState.TERMINAL, gs.EnemyState.DEAD,
                        gs.EnemyState.REACH_EXIT):
            publish_same('无', '实体已结束', 'confirmed')
            return

        picked_skill = action.get('combat_skill_addr', 0)
        picked_name = self._skill_names.get(picked_skill, '')
        picked_ability = action.get('combat_wrapper_ability_addr', 0)
        picked_is_current_cast = (
            state_id == gs.EnemyState.COMBAT and action.get('casting'))
        if (not picked_is_current_cast
                and action.get('combat_ability_picked')
                and self.mc.is_ptr(picked_ability)):
            if picked_name:
                label = f'技能：{picked_name}'
            elif picked_ability == action.get('combat_base_ability_addr', 0):
                label = '基础战斗能力'
            else:
                label = '已选中的战斗能力'
            publish_same(
                label,
                '游戏 CombatWrapper.m_combatAbilityPicked=1，且 '
                'm_pickedAbility 已写入；切换前仍可能被异常状态中断',
                'confirmed')
            return

        queued_animation = action.get('animation_next_track_name', '')
        if queued_animation:
            publish_same(
                f'已排队动画：{queued_animation}',
                'Spine TrackEntry.next 已存在；这是游戏已排队的下一段动画',
                'confirmed')
            return

        if state_id in (gs.EnemyState.MOVE, gs.EnemyState.ATTACK,
                        gs.EnemyState.COMBAT):
            snapshot_after_current = state_id != gs.EnemyState.MOVE

            def publish_rule(label, detail, confidence):
                if snapshot_after_current:
                    detail = (
                        '当前动作尚未结束；以下是用当前内存快照执行原始规则的结果，'
                        '结束回调时目标/CD/状态若变化，游戏会重新计算。' + detail)
                    if confidence == 'rule_calculated':
                        confidence = 'rule_snapshot'
                action.update(next_action=label,
                              next_action_detail=detail,
                              next_action_confidence=confidence)

            def publish_original_rule(label, detail, confidence):
                """发布不加入实时 CD 的 Boss/敌人自身规则首选。"""
                if snapshot_after_current:
                    detail = (
                        '当前动作尚未结束；以下是用当前内存快照执行原始规则的结果，'
                        '结束回调时目标/状态若变化，游戏会重新计算。' + detail)
                    if confidence == 'rule_calculated':
                        confidence = 'rule_snapshot'
                action.update(next_action_rule=label,
                              next_action_rule_detail=detail,
                              next_action_rule_confidence=confidence)

            blocked = self.mc.is_ptr(action.get('blocker_addr', 0))
            lane = 'combat' if blocked else 'attack'
            family = (gs.AbilityFamilyMask.COMBAT if blocked
                      else gs.AbilityFamilyMask.ATTACK)
            lane_cn = '战斗' if blocked else '普攻'
            fallback = '基础战斗能力' if blocked else '普通攻击'
            base_cd = (action.get(f'{lane}_base') or {}).get('cd_remaining')
            if (base_cd is None
                    and action.get('ability_addr') == action.get(
                        f'{lane}_base_ability_addr')):
                # 当前正在施放的正是基础能力；它的计时器已读到 action 顶层，
                # 不会再重复生成 attack_base/combat_base 子块。
                base_cd = action.get('cd_remaining')
            action['next_action_lane'] = lane
            target_text = ('已被阻挡，MoveState 下一次检查先进入 COMBAT'
                           if blocked else
                           '未被阻挡，MoveState 只会在 SearchTarget 找到目标后进入 ATTACK')

            # 现版 GameAssembly 的 _PickAbility 反汇编显示：选中优先级初始为
            # INT_MIN，技能通过 family/CD/次数/触发条件后才写入；写入后遇到
            # 不同 priority 才结束遍历。因此某个高优先级组全部失败时必须继续
            # 下一组，不能直接回退基础攻击。
            active_rows = [row for row in (info.skills_detail or ())
                           if row.get('is_enabled') is not False]
            priority_groups = {}
            for row in active_rows:
                priority = row.get('priority', 0)
                if not isinstance(priority, (int, float)):
                    priority = 0
                priority_groups.setdefault(priority, []).append(row)

            def sp_trigger_result(row):
                if row.get('trigger_type') != 'SpTrigger':
                    return row.get('trigger_ready'), row.get('trigger_reason', '')
                if row.get('trigger_value_type') != 0:
                    return None, 'SpTrigger 使用充能层数，当前尚未读取该层数'
                current = action.get('sp')
                expected = row.get('trigger_value')
                compare = row.get('trigger_compare_type')
                if not (isinstance(current, (int, float))
                        and math.isfinite(current)
                        and isinstance(expected, (int, float))
                        and math.isfinite(expected)):
                    return None, 'SpTrigger 当前技力或比较值不可用'
                comparisons = {
                    0: current < expected, 1: current <= expected,
                    2: current > expected, 3: current >= expected,
                    4: abs(current - expected) <= 1e-5,
                }
                if compare not in comparisons:
                    return None, f'SpTrigger CompareType={compare} 未知'
                value = comparisons[compare]
                return value, f'SpTrigger 原始比较：SP {current:g} 对 {expected:g} -> {value}'

            def evaluate(row, include_cooldown=True):
                failures, unresolved = [], []
                if not (row.get('family_mask', 0) & family):
                    failures.append(f'family 不属于 {lane_cn}')
                if include_cooldown:
                    remaining = row.get('remaining')
                    if not isinstance(remaining, (int, float)):
                        unresolved.append('CD 未读取')
                    elif remaining > 0.0:
                        failures.append(f'CD {remaining:.2f}秒')
                maximum = row.get('max_triggers', 0)
                count = row.get('trigger_count', 0)
                if maximum > 0 and count >= maximum:
                    failures.append(f'次数已用尽 {count}/{maximum}')
                if row.get('check_parent_active'):
                    parent = row.get('parent_mode_addr', 0)
                    current_mode = action.get('current_mode_addr', 0)
                    if self.mc.is_ptr(parent) and self.mc.is_ptr(current_mode):
                        if parent != current_mode:
                            failures.append('所属 UnitMode 未激活')
                    else:
                        unresolved.append('所属 UnitMode 未读取')
                if (len(info.abnormal_flags) > 12 and info.abnormal_flags[12] > 0
                        and not row.get('ignore_silence')):
                    failures.append('当前被沉默')
                if (len(info.abnormal_flags) > 24
                        and info.abnormal_flags[24] > 0):
                    failures.append('当前技能不可激活')
                cost = row.get('sp_cost', 0)
                current_sp = action.get('sp')
                if isinstance(cost, (int, float)) and cost > 0:
                    if isinstance(current_sp, (int, float)) and math.isfinite(current_sp):
                        if current_sp + 1e-5 < cost:
                            failures.append(f'SP不足 {current_sp:g}/{cost:g}')
                    else:
                        unresolved.append('当前 SP 未读取')
                if row.get('has_trigger'):
                    trigger_ready, trigger_reason = sp_trigger_result(row)
                    if trigger_ready is False:
                        failures.append(trigger_reason or 'TargetTrigger 未通过')
                    elif trigger_ready is None:
                        unresolved.append(trigger_reason or 'TargetTrigger 条件待判')
                if failures:
                    return False, failures + unresolved
                if unresolved:
                    return None, unresolved
                return True, ['全部原始判据通过']

            priorities = sorted(priority_groups, reverse=True)

            def select_candidates(include_cooldown):
                passed, uncertain, rejected = [], [], []
                selected_priority = None
                for priority in priorities:
                    group_passed, group_uncertain, group_rejected = [], [], []
                    for row in priority_groups[priority]:
                        result, reasons = evaluate(row, include_cooldown)
                        entry = (row, reasons)
                        if result is True:
                            group_passed.append(entry)
                        elif result is None:
                            group_uncertain.append(entry)
                        else:
                            group_rejected.append(entry)
                    rejected.extend(group_rejected)
                    if group_passed or group_uncertain:
                        selected_priority = priority
                        passed = group_passed
                        uncertain = group_uncertain
                        break
                return passed, uncertain, rejected, selected_priority

            def describe(entries):
                return '；'.join(
                    f"{row.get('name') or '?'}：{'，'.join(reasons)}"
                    for row, reasons in entries)

            def selection_basis(selected_priority, rejected, title):
                basis = f'{title}：{target_text}'
                if selected_priority is not None:
                    basis += (f'；priority={selected_priority} 是从高到低首个仍有'
                              '可用或待判候选的组')
                elif active_rows:
                    basis += '；所有优先级组均未通过'
                if rejected:
                    basis += '；未通过：' + describe(rejected)
                return basis

            # 第一行：只执行敌人自身配置的优先级、family、次数、SP 和触发规则，
            # 明确不加入当前 CD。它回答“按这个 Boss 的代码，下一发优先想做什么”。
            raw_passed, raw_uncertain, raw_rejected, raw_priority = (
                select_candidates(False))
            raw_possible = raw_passed + raw_uncertain
            action['next_action_rule_candidates'] = [
                row.get('name') or '?' for row, _ in raw_possible]
            raw_basis = selection_basis(
                raw_priority, raw_rejected,
                '按客户端 _PickAbility 原始规则计算（未加入当前 CD）')
            if raw_uncertain:
                raw_names = ' / '.join(
                    row.get('name') or '?' for row, _ in raw_possible)
                if raw_passed:
                    raw_label = f'规则候选：{raw_names}'
                else:
                    has_lower = any(priority < raw_priority
                                    for priority in priorities)
                    otherwise = ('继续检查较低优先级技能'
                                 if has_lower else fallback)
                    raw_label = f'条件待判：{raw_names}；否则{otherwise}'
                publish_original_rule(
                    raw_label,
                    raw_basis + '；尚未无副作用解析：' + describe(raw_uncertain)
                    + '。该行不使用技能 CD，只表达敌人自身规则首选',
                    'rule_partial')
            elif raw_passed:
                raw_names = [row.get('name') or '?' for row, _ in raw_passed]
                if len(raw_names) == 1:
                    raw_label = f'技能：{raw_names[0]}'
                    raw_confidence = 'rule_calculated'
                    raw_suffix = '；原始规则当前只有一个技能候选（未加入 CD）'
                else:
                    raw_label = '随机择一：' + ' / '.join(raw_names)
                    raw_confidence = 'rule_candidates'
                    raw_suffix = '；同优先级多个原始候选，由战斗 RNG 随机择一（未加入 CD）'
                publish_original_rule(
                    raw_label, raw_basis + raw_suffix, raw_confidence)
            else:
                if blocked:
                    raw_target_ready = True
                    raw_target_reason = '当前 blocker 有效'
                else:
                    raw_target_ready = action.get('attack_trigger_ready')
                    raw_target_reason = (action.get('attack_trigger_reason')
                                         or '普攻 TargetTrigger 未读取')
                if raw_target_ready is True:
                    publish_original_rule(
                        fallback, raw_basis + f'；{raw_target_reason}，原始规则回退基础能力',
                        'rule_calculated')
                elif raw_target_ready is False:
                    publish_original_rule(
                        '当前无可执行动作', raw_basis + f'；{raw_target_reason}',
                        'rule_calculated')
                else:
                    publish_original_rule(
                        f'规则候选：{fallback}',
                        raw_basis + f'；{raw_target_reason}', 'rule_partial')

            # 第二行：在完全相同的原始规则上加入实时技能 CD，得到当前实际候选。
            passed, uncertain, rejected, selected_priority = (
                select_candidates(True))

            all_possible = passed + uncertain
            action['next_action_candidates'] = [
                row.get('name') or '?' for row, _ in all_possible]
            basis = selection_basis(
                selected_priority, rejected,
                '按客户端 _PickAbility 原始规则并加入实时 CD 计算')

            if uncertain:
                possible_names = ' / '.join(
                    row.get('name') or '?' for row, _ in all_possible)
                if passed:
                    label = f'规则候选：{possible_names}'
                else:
                    has_lower = any(priority < selected_priority
                                    for priority in priorities)
                    otherwise = ('继续检查较低优先级技能'
                                 if has_lower else fallback)
                    label = f'条件待判：{possible_names}；否则{otherwise}'
                publish_rule(
                    label,
                    basis + '；尚未无副作用解析：' + describe(uncertain)
                    + '。这些条件会在游戏真正调用 Search/CheckTrigger 时确定',
                    'rule_partial')
                return

            if passed:
                names = [row.get('name') or '?' for row, _ in passed]
                if len(names) == 1:
                    label = f'技能：{names[0]}'
                    confidence = 'rule_calculated'
                    suffix = '；当前只有一个技能通过全部已解析原始判据'
                else:
                    label = '随机择一：' + ' / '.join(names)
                    confidence = 'rule_candidates'
                    suffix = '；同优先级多个技能通过，客户端会调用战斗 RNG 随机择一'
                publish_rule(label, basis + suffix, confidence)
                return

            base_ready = (base_cd <= 0.0 if isinstance(base_cd, (int, float))
                          else None)
            if base_ready is False:
                publish_rule(
                    f'等待{fallback}冷却（{base_cd:.2f}秒）',
                    basis + f'；全部技能组均未通过，{fallback}当前也未就绪',
                    'rule_calculated')
                return
            if blocked:
                target_ready = True  # blocker 就是 CombatWrapper 的目标
                target_reason = '当前 blocker 有效'
            else:
                target_ready = action.get('attack_trigger_ready')
                target_reason = action.get('attack_trigger_reason') or '普攻 TargetTrigger 未读取'
            if base_ready is True and target_ready is True:
                publish_rule(fallback,
                             basis + f'；{target_reason}，基础能力已就绪',
                             'rule_calculated')
            elif target_ready is False:
                publish_rule('当前无可执行动作', basis + f'；{target_reason}',
                             'rule_calculated')
            else:
                publish_rule(
                    f'规则候选：{fallback}',
                    basis + f'；全部技能组均未通过；{target_reason}'
                    + ('；基础能力就绪状态未读取' if base_ready is None else ''),
                    'rule_partial')
            return

        detail = '当前没有已写入的 picked Ability 或排队动画，下一动作尚未由游戏决定'
        publish_same('等待游戏判定', detail, 'unselected')

    def _finalize_enemy_action(self, info, now=None, frame=None,
                               frame_duration=None):
        """把状态机、Ability、后摇和 CD 合成为可直接展示的动作阶段。"""
        action = dict(info.action or {})
        for key in (
                'phase', 'name', 'detail', 'remaining', 'remaining_frames',
                'remaining_kind', 'elapsed_frames', 'skill_name',
                'ready_skills', 'clock_source', 'next_action',
                'next_action_detail', 'next_action_confidence',
                'next_action_lane', 'next_action_candidates',
                'next_action_rule', 'next_action_rule_detail',
                'next_action_rule_confidence',
                'next_action_rule_candidates'):
            action.pop(key, None)
        now = now if isinstance(now, (int, float)) and math.isfinite(now) else None
        frame = frame if isinstance(frame, int) and frame >= 0 else None
        frame_duration = frame_duration or self._frame_duration_snap or 1.0 / 30.0
        state_id = info.state_id
        state_name = gs.ENEMY_STATE_NAMES.get(state_id, f'未知({state_id})')
        action['state_name'] = state_name
        action['current_frame'] = frame

        ability = action.get('ability_addr', 0)
        skill_ptr = action.get('skill_addr', 0)
        if not self.mc.is_ptr(skill_ptr) and self.mc.is_ptr(ability):
            for candidate in self._skill_ptrs.get(info.addr, ()):
                if self._skill_runtime_meta.get(candidate, {}).get('ability_addr') == ability:
                    skill_ptr = candidate
                    break
        skill_name = self._skill_names.get(skill_ptr, '') if skill_ptr else ''
        if skill_name:
            action['skill_name'] = skill_name

        ready_skills = [name for name, remaining, _period in info.skills
                        if isinstance(remaining, (int, float)) and remaining <= 0.0]
        action['ready_skills'] = ready_skills

        def set_countdown(seconds, kind, source='runtime'):
            if not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
                return False
            seconds = max(0.0, float(seconds))
            action['remaining'] = seconds
            action['remaining_frames'] = (
                seconds_to_frames(seconds, frame_duration)
                if frame is not None else None)
            action['remaining_kind'] = kind
            action['clock_source'] = source
            return True

        if action.get('casting') and frame is not None:
            start = action.get('cast_start_frame')
            if isinstance(start, int) and 0 <= start <= frame:
                action['elapsed_frames'] = frame - start

        animation_remaining = action.get('animation_remaining')
        animation_remaining = (
            float(animation_remaining)
            if isinstance(animation_remaining, (int, float))
            and math.isfinite(animation_remaining) and animation_remaining >= 0
            else None)

        if state_id in (gs.EnemyState.TERMINAL, gs.EnemyState.DEAD,
                        gs.EnemyState.REACH_EXIT):
            action.update(phase='finished', name=state_name,
                          detail='状态已结束，不再进入下一动作',
                          remaining=0.0, remaining_frames=0,
                          remaining_kind='完成态', clock_source='state')
        elif state_id in (gs.EnemyState.BORN, gs.EnemyState.REBORN):
            action.update(phase='state_countdown', name=state_name,
                          detail='状态节点自身倒计时')
            if not set_countdown(action.get('state_time'), '状态剩余', 'state_node'):
                action['remaining_kind'] = '等待状态节点退出'
        elif state_id == gs.EnemyState.COMBAT:
            if action.get('casting'):
                label = f'技能动作中：{skill_name}' if skill_name else '战斗动作中'
                action.update(phase='combat_casting', name=label,
                              detail='Ability 正在施放；Spine 轨道可给出当前动画终点')
                deadline = action.get('combat_escape_time')
                gate = deadline - now if now is not None and isinstance(
                    deadline, (int, float)) and math.isfinite(deadline) else None
                gates = [value for value in (animation_remaining, gate)
                         if isinstance(value, (int, float)) and value > 0]
                if gates:
                    kind = ('动作可退出剩余（未中断）' if gate and gate > 0
                            else '当前动画剩余（未中断）')
                    set_countdown(max(gates), kind, 'spine/state_gate')
                else:
                    action['remaining_kind'] = '能力回调/状态切换条件'
            else:
                deadline = action.get('combat_escape_time')
                remaining = deadline - now if now is not None and isinstance(
                    deadline, (int, float)) and math.isfinite(deadline) else None
                if remaining is not None and remaining > 0.0001:
                    action.update(phase='combat_recovery', name='战斗动作后摇',
                                  detail='能力已结束，尚未到达可退出战斗状态的时刻')
                    set_countdown(remaining, '后摇剩余', 'enemy.combatNextEscapeTime')
                elif action.get('combat_interrupted'):
                    action.update(phase='combat_interrupted', name='战斗动作被中断',
                                  detail='等待状态机完成中断切换',
                                  remaining_kind='状态切换条件')
                else:
                    action.update(phase='combat_wait', name='战斗动作收尾',
                                  detail='CD 就绪也要等待当前战斗状态和目标条件退出',
                                  remaining_kind='动画/状态切换条件')
        elif state_id == gs.EnemyState.ATTACK:
            if action.get('casting'):
                label = f'攻击型技能：{skill_name}' if skill_name else '普通攻击动作中'
                action.update(phase='attack_casting', name=label,
                              detail='Ability 正在施放；倒计时取当前非循环 Spine 动画终点')
                if not set_countdown(animation_remaining,
                                     '当前动画剩余（未中断）', 'spine_track'):
                    action['remaining_kind'] = '动画/能力回调决定'
            else:
                action.update(phase='attack_recovery', name='普通攻击收尾',
                              detail='攻击 Ability 已结束，等待状态机切回待机/移动',
                              remaining_kind='动画/状态切换条件')
                if animation_remaining is not None:
                    set_countdown(animation_remaining,
                                  '收尾动画剩余（未中断）', 'spine_track')
        elif state_id in (gs.EnemyState.STUN, gs.EnemyState.FROZEN,
                          gs.EnemyState.LEVITATE, gs.EnemyState.PALSY):
            action.update(phase='abnormal', name=state_name,
                          detail='异常状态由一个或多个 Buff 标志维持')
            if not set_countdown(action.get('status_remaining'), '异常持续剩余', 'buff'):
                action['remaining_kind'] = 'Buff/异常条件解除'
        elif (info.abnormal_combos
                and len(info.abnormal_combos) > gs.AbnormalCombo.SLEEPING
                and info.abnormal_combos[gs.AbnormalCombo.SLEEPING] > 0):
            # 睡眠不改状态机状态（敌人停在移动/待机等），单独按 combo 识别；
            # 剩余时间由维持睡眠的 Buff 决定（夜半/提提等技能均为限时 Buff）。
            action.update(phase='abnormal_sleep', name=f'{state_name}·睡眠',
                          detail='睡眠中：无法移动/攻击/施放技能，'
                                 '由维持睡眠的 Buff 时长决定醒来时刻')
            if not set_countdown(action.get('status_remaining'), '睡眠剩余', 'buff'):
                action['remaining_kind'] = 'Buff/异常条件解除'
        elif state_id == gs.EnemyState.MOVE:
            candidates = []
            value = action.get('cd_remaining')
            if isinstance(value, (int, float)) and 0 < value < 3600:
                candidates.append(float(value))
            for role in ('attack_base', 'combat_base'):
                value = (action.get(role) or {}).get('cd_remaining')
                if isinstance(value, (int, float)) and 0 < value < 3600:
                    candidates.append(float(value))
            candidates.extend(float(remain) for _name, remain, _period in info.skills
                              if isinstance(remain, (int, float)) and 0 < remain < 3600)
            if candidates:
                action.update(phase='move_cooldown', name='移动 / 等待下一动作',
                              detail='此倒计时是最早动作可用时间，不等于移动状态必然结束')
                set_countdown(min(candidates), '下一动作可用', 'ability_cooldown')
            elif ready_skills:
                action.update(phase='move_ready', name='移动 / 技能已就绪',
                              detail='等待目标、技能触发器及状态机允许施放',
                              remaining_kind='目标/触发/状态条件')
            else:
                action.update(phase='moving', name='移动',
                              detail='路径与阻挡条件决定何时离开移动状态',
                              remaining_kind='路径/阻挡条件')
        else:
            action.update(phase='state_wait', name=state_name,
                          detail='该状态没有统一的倒计时槽，由状态节点条件退出',
                          remaining_kind='状态节点条件')

        if ready_skills and state_id in (
                gs.EnemyState.ATTACK, gs.EnemyState.COMBAT,
                gs.EnemyState.STUN, gs.EnemyState.FROZEN,
                gs.EnemyState.LEVITATE, gs.EnemyState.PALSY):
            action['detail'] += '；已有技能 CD 就绪，但须先退出当前状态'
        self._predict_enemy_next_action(info, action)
        info.action = action
        runtime = self._runtime_snapshot.get(info.addr)
        if runtime is not None:
            runtime['action'] = dict(action)
        return action

    def _read_enemy(self, ep, with_runtime=True):
        (blk,) = self._detail_batch_read([(ep, gs.EnemyFields.READ_SIZE)])
        if not blk:
            (blk,) = self._detail_batch_read([(ep, gs.EnemyFields.READ_SIZE)])
        info = self._parse_enemy_block(ep, blk)
        if not blk or len(blk) < max(gs.EntityFields.BUFF_CONTAINER + 8,
                                    gs.EnemyFields.DATA + 8):
            return info
        self._fill_name(ep, blk, info)
        self._fill_attrs(ep, blk, info)
        self._fill_skills(ep, blk, info)
        if with_runtime:
            if self._chan is None:
                raise RuntimeError('memsrv v4 主通道尚未建立')
            self._refresh_runtime_chan([ep], {ep: info})
        return info

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

    def request_poll_stop(self):
        """请求实时轮询尽快停止，并打断正在等待的 TCP 读取。"""
        self._poll_stop.set()
        self.close()

    def resume_polling(self):
        self._poll_stop.clear()

    def poll_fast(self):
        """完整 60Hz 轮询：每帧读取容器、属性、状态、技能、动画与 BC。

        memsrv v4 是唯一读取后端；通道异常直接上抛并停止发布快照。
        """
        if self._poll_stop.is_set():
            raise InterruptedError('敌人轮询已请求停止')
        if self._chan is None:
            self._chan = self.mc.channel()
        try:
            snap = self._poll_fast_impl()
            snap['read_mode'] = 'fast'
            snap['read_backend'] = 'srv'
            snap['memsrv_version'] = getattr(self._chan, 'srv_version', 0)
            snap['strict_60hz'] = self._chan.srv_version == 4
            self._chan_fail = 0
            return snap
        except Exception as e:
            if self._poll_stop.is_set():
                raise InterruptedError('敌人轮询已请求停止') from e
            self._chan_fail += 1
            if self._chan_fail <= 3 or self._chan_fail % 50 == 0:
                self.log(f'[轮询] memsrv v4 异常 ({type(e).__name__}: {e})')
            self.close()
            raise RuntimeError(f'memsrv v4 读取失败: {e}') from e

    @staticmethod
    def _cluster_ptrs(ptrs, gap=0x10000):
        """敌人指针按地址聚簇（历史扫描算法辅助函数）。"""
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

    def _poll_clusters(self, ptrs):
        """memsrv v4 精确读取每个对象。"""
        return [[ptr] for ptr in ptrs]

    def _refill_failed_reads(self, reqs, results):
        """同帧重读 results 中失败的项并回填。敌人仍在 List 中, 一次通道
        瞬态抖动不应被当成"敌人消失"; 重读也失败才按本帧缺失 (真实消失)
        处理。通道彻底故障时异常上抛并停止本轮发布。"""
        failed = [i for i, data in enumerate(results) if not data]
        if failed:
            retry = self._chan.batch_read([reqs[i] for i in failed])
            for i, data in zip(failed, retry):
                if data:
                    results[i] = data
        return results

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
        runtime = {ep: dict(self._runtime_snapshot.get(ep, {})) for ep in eps}
        for ep in eps:
            info = infos.get(ep)
            if info is None:
                continue
            merged_action = dict(runtime[ep].get('action', {}))
            merged_action.update(info.action or {})
            runtime[ep]['action'] = merged_action
        for ep in eps:
            rp = self._runtime_ptrs.get(ep, {})
            specs = (
                ('state', rp.get('state', 0) + gs.StateMachineFields.CURRENT_STATE_ID, 0x10),
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
            action = runtime.get(ep, {}).get('action', {})
            attack_wrapper = action.get('attack_wrapper_addr', 0)
            combat_wrapper = action.get('combat_wrapper_addr', 0)
            current_mode = action.get('current_mode_addr', 0)
            animator = action.get('animator_addr', 0)
            if self.mc.is_ptr(current_mode):
                reqs.append((current_mode, gs.UnitModeFields.READ_SIZE))
                keys.append((ep, 'unit_mode'))
            if self.mc.is_ptr(attack_wrapper):
                reqs.append((attack_wrapper, gs.EnemyAttackWrapperFields.READ_SIZE))
                keys.append((ep, 'attack_wrapper'))
            if self.mc.is_ptr(combat_wrapper):
                reqs.append((combat_wrapper, gs.EnemyCombatWrapperFields.READ_SIZE))
                keys.append((ep, 'combat_wrapper'))
            if self.mc.is_ptr(animator):
                for kind, offset in (
                        ('anim_spine', gs.UnitAnimatorFields.SPINE_CURRENT_STATE),
                        ('anim_mesh', gs.UnitAnimatorFields.MESH_CURRENT_STATE)):
                    reqs.append((animator + offset,
                                 gs.UnitAnimatorFields.CURRENT_STATE_SIZE))
                    keys.append((ep, kind))
            for idx, source in enumerate(self._custom_shield_ptrs.get(ep, ())):
                value_addr = source.get('value_addr', 0)
                buff_addr = source.get('buff_addr', 0)
                if self.mc.is_ptr(value_addr):
                    reqs.append((value_addr, 4))
                    keys.append((ep, f'custom_value:{idx}'))
                if self.mc.is_ptr(buff_addr):
                    reqs.append((buff_addr + gs.BuffFields.IS_FINISHED,
                                 gs.BuffFields.IS_VALID - gs.BuffFields.IS_FINISHED + 1))
                    keys.append((ep, f'custom_status:{idx}'))

        for (ep, kind), data in zip(keys, self._chan.batch_read(reqs) if reqs else []):
            if not data:
                continue
            cur = runtime[ep]
            if kind == 'state':
                cur['state_id'] = _i32(data, 0)
                state_node = _u64(data, 8)
                if cur['action'].get('state_node_addr') != state_node:
                    cur['action'].pop('state_time', None)
                    cur['action'].pop('status_remaining', None)
                cur['action']['state_node_addr'] = state_node
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
            elif kind == 'attack_wrapper':
                action = cur['action']
                action['target_addr'] = _u64(
                    data, gs.EnemyAttackWrapperFields.CURRENT_TARGET)
                action['attack_skill_addr'] = _u64(
                    data, gs.EnemyAttackWrapperFields.CURRENT_SKILL)
                action['attack_wrapper_ability_addr'] = _u64(
                    data, gs.EnemyAttackWrapperFields.CURRENT_ABILITY)
                action['last_attack_ability_addr'] = _u64(
                    data, gs.EnemyAttackWrapperFields.LAST_ABILITY)
                action['last_attack_skill_addr'] = _u64(
                    data, gs.EnemyAttackWrapperFields.LAST_SKILL)
            elif kind == 'unit_mode':
                action = cur['action']
                action['mode_combat_addr'] = _u64(
                    data, gs.UnitModeFields.COMBAT)
                action['mode_attack_addr'] = _u64(
                    data, gs.UnitModeFields.ATTACK)
                action['mode_attack_trigger_addr'] = _u64(
                    data, gs.UnitModeFields.ATTACK_TRIGGER)
            elif kind == 'combat_wrapper':
                action = cur['action']
                action['combat_wrapper_ability_addr'] = _u64(
                    data, gs.EnemyCombatWrapperFields.PICKED_ABILITY)
                action['combat_skill_addr'] = _u64(
                    data, gs.EnemyCombatWrapperFields.PICKED_SKILL)
                action['combat_ability_picked'] = bool(
                    data[gs.EnemyCombatWrapperFields.ABILITY_PICKED])
                action['combat_interrupted'] = bool(
                    data[gs.EnemyCombatWrapperFields.INTERRUPTED])
                action['last_combat_ability_addr'] = _u64(
                    data, gs.EnemyCombatWrapperFields.LAST_ABILITY)
                action['last_combat_skill_addr'] = _u64(
                    data, gs.EnemyCombatWrapperFields.LAST_SKILL)
            elif kind in ('anim_spine', 'anim_mesh'):
                speed = struct.unpack_from('<f', data, 8)[0]
                cur['action'].setdefault('animation_candidates', []).append({
                    'key_ptr': _u64(data, 0),
                    'speed': speed,
                    'backend': 'Spine' if kind == 'anim_spine' else 'Mesh',
                })
            elif kind.startswith('custom_value:'):
                idx = int(kind.split(':', 1)[1])
                sources = self._custom_shield_ptrs.get(ep, ())
                if idx < len(sources):
                    value = struct.unpack_from('<f', data, 0)[0]
                    if math.isfinite(value) and 0 <= value <= 1_000_000_000:
                        sources[idx]['value'] = value
            elif kind.startswith('custom_status:'):
                idx = int(kind.split(':', 1)[1])
                sources = self._custom_shield_ptrs.get(ep, ())
                if idx < len(sources):
                    enabled_off = (gs.BuffFields.IS_ACTUALLY_ENABLED
                                   - gs.BuffFields.IS_FINISHED)
                    valid_off = gs.BuffFields.IS_VALID - gs.BuffFields.IS_FINISHED
                    sources[idx]['active'] = (
                        not bool(data[0]) and bool(data[enabled_off])
                        and bool(data[valid_off]))

        attack_trigger_owners = {}
        for ep in eps:
            trigger = runtime[ep]['action'].get('mode_attack_trigger_addr', 0)
            if self.mc.is_ptr(trigger):
                attack_trigger_owners[trigger] = ep
        for trigger, state in self._read_trigger_states_chan(
                attack_trigger_owners).items():
            action = runtime[attack_trigger_owners[trigger]]['action']
            action['attack_trigger_type'] = state.get('trigger_type', '')
            action['attack_trigger_ready'] = state.get('trigger_ready')
            action['attack_trigger_reason'] = state.get('trigger_reason', '')
            action['attack_trigger_target_addr'] = state.get(
                'trigger_target_addr', 0)

        self._resolve_animation_states_chan({
            ep: runtime[ep]['action'] for ep in eps})
        self._refresh_animation_tracks_chan({
            ep: runtime[ep]['action'] for ep in eps})

        # Wrapper/主对象给出“这一次到底选中了哪个 Ability”。第二批只读取
        # 当前动作能力本身，m_isCasting 与 castStartFrameCnt 不再由 CD 推断。
        ability_reqs, ability_keys = [], []
        for ep in eps:
            cur = runtime.get(ep, {})
            action = cur.get('action', {})
            state_id = cur.get('state_id', infos.get(ep).state_id if infos.get(ep) else 0)
            if state_id == gs.EnemyState.ATTACK:
                ability = (action.get('attack_ability_addr', 0)
                           or action.get('attack_wrapper_ability_addr', 0))
                skill = action.get('attack_skill_addr', 0)
            elif state_id == gs.EnemyState.COMBAT:
                ability = (action.get('combat_ability_addr', 0)
                           or action.get('combat_wrapper_ability_addr', 0))
                skill = action.get('combat_skill_addr', 0)
            else:
                ability = (action.get('combat_ability_addr', 0)
                           or action.get('attack_ability_addr', 0))
                skill = 0
            action['ability_addr'] = ability
            action['skill_addr'] = skill
            for key in ('casting', 'cast_start_frame', 'attached',
                        'finish_reason', 'timer_addr', 'cd_period', 'cd_remaining'):
                action.pop(key, None)
            if self.mc.is_ptr(ability):
                ability_reqs.append((ability, gs.AbilityFields.READ_SIZE))
                ability_keys.append((ep, 'ability'))
            for role in ('attack', 'combat'):
                base_ability = (action.get(f'override_{role}_addr', 0)
                                or action.get(f'mode_{role}_addr', 0))
                action[f'{role}_base_ability_addr'] = base_ability
                action.pop(f'{role}_base', None)
                if self.mc.is_ptr(base_ability) and base_ability != ability:
                    ability_reqs.append((base_ability, gs.AbilityFields.READ_SIZE))
                    ability_keys.append((ep, f'{role}_base'))
            state_node = action.get('state_node_addr', 0)
            if self.mc.is_ptr(state_node):
                ability_reqs.append((
                    state_node + gs.StateNodeFields.ACTION_TIME, 8))
                ability_keys.append((ep, 'state_time'))
        for (ep, kind), data in zip(
                ability_keys,
                self._chan.batch_read(ability_reqs) if ability_reqs else []):
            if not data:
                continue
            action = runtime[ep]['action']
            if kind == 'state_time':
                action['state_time'] = gs.fp_to_float(_u64(data, 0))
                continue
            target = action if kind == 'ability' else action.setdefault(kind, {})
            target['casting'] = bool(data[gs.AbilityFields.IS_CASTING])
            target['cast_start_frame'] = _u32(
                data, gs.AbilityFields.CAST_START_FRAME)
            target['attached'] = bool(data[gs.AbilityFields.IS_ATTACHED])
            target['finish_reason'] = _i32(data, gs.AbilityFields.FINISH_REASON)
            timer = _u64(data, gs.AbilityFields.COOLDOWN_TIMER)
            target['timer_addr'] = timer

        timer_keys = []
        for ep, kind in ability_keys:
            if kind == 'state_time':
                continue
            action = runtime[ep]['action']
            target = action if kind == 'ability' else action.get(kind, {})
            timer = target.get('timer_addr', 0)
            if self.mc.is_ptr(timer):
                timer_keys.append((ep, kind, timer))
        if timer_keys:
            timer_reqs = [(timer, 0x20) for _ep, _kind, timer in timer_keys]
            for (ep, kind, _timer), data in zip(
                    timer_keys, self._chan.batch_read(timer_reqs)):
                if not data:
                    continue
                action = runtime[ep]['action']
                target = action if kind == 'ability' else action.get(kind, {})
                target['cd_period'] = gs.fp_to_float(_u64(
                    data, gs.PeriodicTimerFields.M_PERIOD_TIME))
                target['cd_remaining'] = gs.fp_to_float(_u64(
                    data, gs.PeriodicTimerFields.M_REMAINING_TIME))

        state_bits = {
            gs.EnemyState.STUN: 0,
            gs.EnemyState.FROZEN: 16,
            gs.EnemyState.LEVITATE: 25,
            gs.EnemyState.PALSY: 39,
        }
        # 对全部当前生效 flag/combo 展开 Buff mask；这样寒冷、沉默、恐惧、
        # 禁锢、束缚等不切换状态机的异常也能取得各自剩余时间。
        status_targets = []
        for ep in eps:
            state_id = runtime[ep].get('state_id', gs.EnemyState.DEFAULT)
            info = infos.get(ep)
            if info is None:
                continue
            flags = runtime[ep].get('abnormal_flags') or ()
            combos = runtime[ep].get('abnormal_combos') or ()
            runtime[ep]['status_timers'] = {}
            flag_bits = {idx for idx, count in enumerate(flags) if count > 0}
            combo_bits = {idx for idx, count in enumerate(combos) if count > 0}
            state_bit = state_bits.get(state_id)
            if state_bit is not None:
                flag_bits.add(state_bit)
            if not flag_bits and not combo_bits:
                runtime[ep]['status_timers'] = {}
                action = runtime[ep].setdefault('action', {})
                action.pop('status_remaining', None)
                action.pop('status_source_count', None)
                action.pop('status_infinite', None)
                self._status_timer_cache.pop(ep, None)
                continue
            status_targets.append((
                ep, info.buff_container_ptr, state_id,
                tuple(sorted(flag_bits)), tuple(sorted(combo_bits))))
        self._refresh_status_timers_chan(status_targets, runtime, self._fast_tick)

        for ep in eps:
            sources = self._custom_shield_ptrs.get(ep, ())
            if sources:
                active = [source for source in sources if source.get('active')]
                runtime[ep]['special_shield'] = sum(
                    max(0.0, source.get('value', 0.0)) for source in active)
                runtime[ep]['special_shield_mask'] = 0
                for source in active:
                    runtime[ep]['special_shield_mask'] |= source.get('mask', 0)
                runtime[ep]['special_shield_sources'] = [
                    dict(source) for source in sources]
            self._runtime_snapshot[ep] = runtime[ep]
            info = infos.get(ep)
            if info is not None:
                self._copy_runtime(info, runtime[ep])

    # 完整实时模式：所有敌方运行时数据每个采样帧都读取。常量保留给诊断
    # 输出和测试识别，但不再以取模方式跳帧。
    LIST_EVERY = 1
    ATTR_EVERY = 1
    BC_EVERY = 1
    SKILL_EVERY = 1
    STATUS_EVERY = 1
    SPAWN_QUEUE_EVERY = 1

    def _poll_fast_impl(self):
        t0 = time.time()
        snap = {'ok': False, 'state': -1, 'speed_level': -1, 'time_scale': 0.0,
                'play_time': 0.0, 'scheduler_time': None,
                'fixed_frame': self._fixed_frame_snap,
                'frame_duration': self._frame_duration_snap,
                'enemies': [], 'msg': '', 'frame_ms': 0.0,
                'on_field_count': 0, 'planned_count': self.planned_count,
                'read_mode': 'fast', 'read_backend': 'tcp'}
        self._fast_tick += 1
        tick = self._fast_tick
        prev_ptrs = self._f_ptrs
        read_list = True

        # ---- 组装本帧唯一一批请求（辅助读取降频搭车）----
        reqs, slot = [], {}
        if read_list:
            slot['list'] = len(reqs)
            reqs.append((self.list_addr, 0x20))
            if self.unit_enemies_addr:
                slot['unit_enemies'] = len(reqs)
                reqs.append((self.unit_enemies_addr, 0x28))
        clusters = self._poll_clusters(prev_ptrs)
        slot['c0'] = len(reqs)
        reqs += [(c[0], c[-1] + gs.EnemyFields.READ_SIZE - c[0]) for c in clusters]
        slot['attrs'] = []
        slot['attr_heads'] = []
        for aep in prev_ptrs:
            cdp = self._attr_cache.get(aep, 0)
            if cdp:
                slot['attrs'].append((len(reqs), aep, cdp))
                reqs.append((cdp, 0x20 + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE))
            else:
                ap = self._attr_ptrs.get(aep, 0)
                if ap:
                    slot['attr_heads'].append((len(reqs), aep, ap))
                    reqs.append((ap, 0x60))
        if self.bc_addr:
            slot['bc'] = len(reqs)
            reqs.append((self.bc_addr + 0x200, 0xC0))
            if self._bc_static_fields:
                slot['battle_clock'] = len(reqs)
                reqs.append((
                    self._bc_static_fields
                    + gs.BattleControllerStaticFields.FIXED_FRAME_COUNT,
                    gs.BattleControllerStaticFields.DELTA_PLAY_TIME_FP
                    - gs.BattleControllerStaticFields.FIXED_FRAME_COUNT + 8))
        if self.sched_addr:
            slot['scheduler'] = len(reqs)
            reqs.append((self.sched_addr, 0xC8))
        res = self._chan.batch_read(reqs) if reqs else []
        if 'battle_clock' in slot:
            frame, value, frame_duration = self._decode_battle_clock_snapshot(
                res[slot['battle_clock']])
            if frame is not None:
                self._fixed_frame_snap = frame
            if value is not None:
                self._scheduler_time_snap = value
            if frame_duration is not None:
                self._frame_duration_snap = frame_duration

        # ---- 实时敌人容器（降频读取）----
        # Scheduler List 用 _version；UnitManager.enemies 是 UnorderedArray，没有
        # version，敌人一进一出时 count 甚至可能不变，所以每次都重读前 count 个槽。
        ptrs = prev_ptrs
        if read_list:
            d = res[slot['list']]
            if not d:
                # 通道瞬态失败: 同帧补读一次再判 stale, 避免整帧数据链假失效
                d = self._chan.batch_read([(self.list_addr, 0x20)])[0]
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
            array_data = self._refill_failed_reads(array_reqs, array_data)
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
                clusters = self._poll_clusters(ptrs)
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
        # 敌人仍在 List 中但块读取瞬态失败时, 同帧补读一次; 仍读不到才按
        # 本帧缺失处理, 不把一次通道抖动渲染成"敌人离场又回来"。
        cluster_res = self._refill_failed_reads(
            [(c[0], c[-1] + gs.EnemyFields.READ_SIZE - c[0]) for c in clusters],
            list(cluster_res))

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
                self._track_attr_object(ep, info.attr_ptr)
                skl = _u64(data, off + gs.EnemyFields.M_SKILLS)
                if self.mc.is_ptr(skl):
                    self._skill_lp[ep] = skl
                all_skl = _u64(data, off + gs.EnemyFields.M_ALL_SKILLS)
                if self.mc.is_ptr(all_skl):
                    self._skill_ap[ep] = all_skl

        # ---- 新敌人: 通道内解析名称+属性 (仅列表变化帧触发) ----
        new_eps = [ep for ep in ptrs if ep not in self._names or ep not in self._attr_snapshot]
        if new_eps:
            self._fill_new_enemies_chan(new_eps, infos)
        self._log_identity_diagnostics(ptrs, infos)
        # bootstrap 可能已经预填名称/属性缓存，因此不能只依赖 new_eps。对规则中声明的
        # 敌人至少探测一次；若 Buff 比实体稍晚挂载，则约每 50 tick 低频重试。
        custom_probe_eps = []
        for ep in ptrs:
            enemy_id = self._names.get(ep, ('', '', ''))[0]
            if not any(enemy_id in rule.get('enemy_ids', ())
                       for rule in CUSTOM_SHIELD_RULES):
                continue
            last_probe = self._custom_shield_probe_tick.get(ep, -10_000)
            if (ep not in self._custom_shield_ptrs
                    and tick - last_probe >= 50):
                custom_probe_eps.append(ep)
        if custom_probe_eps:
            self._discover_custom_shields(custom_probe_eps, infos)

        # ---- 状态机 / 异常状态 / 免疫 / 五种损伤条 ----
        readable_ptrs = [ep for ep in ptrs if ep in infos]
        if readable_ptrs:
            self._refresh_runtime_chan(readable_ptrs, infos)
            self._refresh_precise_positions(readable_ptrs, infos)

        # ---- 全部敌人属性每个采样帧刷新 ----
        for i, aep, expected_cdp in slot.get('attrs', ()):
            if self._attr_cache.get(aep) != expected_cdp:
                continue  # 本帧主对象已切换 Attributes，丢弃旧阶段的在途结果
            cd = res[i]
            if cd and 0 < _i32(cd, gs.Il2CppArray.MAX_LENGTH) <= 64:
                tmp = EnemyInfo(aep)
                self._apply_cached_data(cd, tmp)
                self._attr_snapshot[aep] = dict(tmp.attributes)
            else:
                self._attr_cache.pop(aep, None)   # 数组已失效, 下轮重建
        for i, aep, expected_attr in slot.get('attr_heads', ()):
            if self._attr_ptrs.get(aep) != expected_attr:
                continue
            d = res[i]
            cdp = _u64(d, gs.AttributesFields.M_CACHED_DATA) if d else 0
            if cdp and self.mc.is_ptr(cdp):
                self._attr_cache[aep] = cdp

        # ---- 技能、触发器和 CD 每个采样帧刷新 ----
        if ptrs:
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
            info.skills_detail = list(self._skill_enriched.get(ep, ()))
            self._finalize_enemy_action(
                info, self._scheduler_time_snap, self._fixed_frame_snap,
                self._frame_duration_snap)
            enemies.append(info)
        # 清理已退场敌人的缓存 (地址可能被 GC 复用)
        for cache in (self._names, self._attr_cache, self._attr_snapshot, self._attr_ptrs,
                      self._runtime_snapshot, self._runtime_ptrs,
                      self._custom_shield_ptrs, self._custom_shield_probe_tick,
                      self._skill_lp, self._skill_ap, self._skill_ptrs,
                      self._active_skill_ptrs,
                      self._skill_cd, self._skill_enriched):
            for ep in list(cache):
                if ep not in live:
                    cache.pop(ep, None)
        if self._precise_position_reader is not None:
            for ep in set(self._precise_position_reader._value_addrs) - live:
                self._precise_position_reader.discard(ep)
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
        snap['scheduler_time'] = self._scheduler_time_snap
        snap['fixed_frame'] = self._fixed_frame_snap
        snap['frame_duration'] = self._frame_duration_snap

        # ---- Scheduler 当前 ActionItem 队列 / 未出场 ETA ----
        scheduler_data = res[slot['scheduler']] if 'scheduler' in slot else None
        spawned_count = (_i32(scheduler_data, gs.SchedulerFields.M_SPAWNED_ENEMIES_CNT)
                         if scheduler_data else 0)
        if scheduler_data:
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

    def read_frame_guard_fast(self) -> dict:
        """在敌我完整读取结束后复核战斗帧与暂停状态。

        返回值用于检测一份快照是否跨越了暂停边界。该读取走同一个 memsrv
        批次，不启动新的 ADB 子进程。
        """
        if self._chan is None:
            return {
                'frame': self._fixed_frame_snap,
                'time_scale': self._bc_snap[2] if self._bc_snap else None,
                'play_time': self._bc_snap[3] if self._bc_snap else None,
            }
        reqs, keys = [], []
        if self._bc_static_fields:
            reqs.append((
                self._bc_static_fields
                + gs.BattleControllerStaticFields.FIXED_FRAME_COUNT,
                gs.BattleControllerStaticFields.DELTA_PLAY_TIME_FP
                - gs.BattleControllerStaticFields.FIXED_FRAME_COUNT + 8))
            keys.append('clock')
        if self.bc_addr:
            reqs.append((self.bc_addr + 0x200, 0xC0))
            keys.append('bc')
        if not reqs:
            return {'frame': self._fixed_frame_snap, 'time_scale': None,
                    'play_time': None}
        # 帧尾守卫必须独立实读，不能命中本帧预取值；用它证明整份敌我
        # 快照没有跨越逻辑帧/暂停边界。
        values = dict(zip(keys, self._chan.batch_read(
            reqs, force_live=True, remember=False)))
        frame = self._fixed_frame_snap
        if values.get('clock'):
            new_frame, now, frame_duration = self._decode_battle_clock_snapshot(
                values['clock'])
            if new_frame is not None:
                frame = self._fixed_frame_snap = new_frame
            if now is not None:
                self._scheduler_time_snap = now
            if frame_duration is not None:
                self._frame_duration_snap = frame_duration
        time_scale = play_time = None
        bc_data = values.get('bc')
        if bc_data:
            state = _i32(
                bc_data, gs.BattleControllerFields.M_STATE - 0x200)
            speed = _i32(
                bc_data, gs.BattleControllerFields.M_SPEED_LEVEL - 0x200)
            time_scale = struct.unpack_from(
                '<f', bc_data,
                gs.BattleControllerFields.M_TIME_SCALE - 0x200)[0]
            play_time = struct.unpack_from(
                '<f', bc_data,
                gs.BattleControllerFields.M_REAL_PLAY_TIME - 0x200)[0]
            self._bc_snap = (state, speed, time_scale, play_time)
        return {'frame': frame, 'time_scale': time_scale,
                'play_time': play_time}

    def _refresh_skills_chan(self, ptrs):
        """通道内批量刷新全部敌人技能 CD。

        动态 ``m_skills`` 与稳定 ``m_allSkills`` 同时读取并去重。完整数组或
        items 的单次读取失败时沿用最近一次成功解析的技能对象地址，不再把一次
        瞬态空值直接发布到 UI；下一轮会自动恢复，无需重新扫描地址链。
        """
        eps = [ep for ep in ptrs
               if (self.mc.is_ptr(self._skill_lp.get(ep, 0))
                   or self.mc.is_ptr(self._skill_ap.get(ep, 0))
                   or self._skill_ptrs.get(ep))]
        if not eps:
            return

        sources = []
        frame_reqs, frame_tags = [], []
        for ep in eps:
            lp = self._skill_lp.get(ep, 0)
            ap = self._skill_ap.get(ep, 0)
            if self.mc.is_ptr(lp):
                sources.append((ep, 'active', lp))
            if self.mc.is_ptr(ap):
                sources.append((ep, 'all', ap))
        for ep, kind, ptr in sources:
            frame_reqs.append((ptr, 0x20))
            frame_tags.append(('head', ep, kind))
            layout = self._skill_source_layout.get((ep, kind), {})
            if layout.get('ptr') == ptr and layout.get('count', 0):
                frame_reqs.append((
                    layout['items'] + gs.Il2CppArray.ITEMS,
                    layout['count'] * 8))
                frame_tags.append(('body', ep, kind))
        # 上帧已验证的技能、Trigger 和计时器地址也并入同一批。当前技能块
        # 仍会重新给出真实指针；不一致时下面立即补读新地址。
        cached_skills = list(dict.fromkeys(
            skill for ep in eps for skill in self._skill_ptrs.get(ep, ())
            if self.mc.is_ptr(skill)))
        for skill in cached_skills:
            frame_reqs.append((skill, gs.EnemySkillFields.READ_SIZE))
            frame_tags.append(('skill', skill))
            meta = self._skill_runtime_meta.get(skill, {})
            trigger = meta.get('trigger_addr', 0)
            timer = meta.get('timer_addr', 0)
            if self.mc.is_ptr(trigger):
                frame_reqs.append((trigger, gs.TargetTriggerFields.READ_SIZE))
                frame_tags.append(('trigger', trigger))
            if self.mc.is_ptr(timer):
                frame_reqs.append((timer, 0x20))
                frame_tags.append(('timer', skill, timer))
        frame_values = dict(zip(
            frame_tags, self._chan.batch_read(frame_reqs) if frame_reqs else []))

        decoded_sources = {ep: set() for ep in eps}
        body_reqs, body_keys, source_layouts = [], [], {}
        for ep, kind, ptr in sources:
            d = frame_values.get(('head', ep, kind))
            if not d:
                continue
            if kind == 'all':
                items = ptr
                n = _i32(d, gs.Il2CppArray.MAX_LENGTH)
            else:
                items = _u64(d, gs.ListInternal.ITEMS)
                n = _i32(d, gs.ListInternal.SIZE)
            if not (0 <= n <= 32) or (n and not self.mc.is_ptr(items)):
                continue
            source_layouts[(ep, kind)] = {
                'ptr': ptr, 'items': items, 'count': n}
            if n == 0:
                decoded_sources[ep].add(kind)
            else:
                cached = self._skill_source_layout.get((ep, kind), {})
                data = frame_values.get(('body', ep, kind))
                if (cached.get('ptr') == ptr
                        and (cached.get('items'), cached.get('count')) == (items, n)
                        and data):
                    frame_values[('current_body', ep, kind)] = data
                else:
                    body_reqs.append((items + gs.Il2CppArray.ITEMS, n * 8))
                    body_keys.append((ep, kind, n))
        for (ep, kind, _n), data in zip(
                body_keys, self._chan.batch_read(body_reqs) if body_reqs else []):
            frame_values[('current_body', ep, kind)] = data
        self._skill_source_layout.update(source_layouts)

        sks_of = {ep: [] for ep in eps}
        active_of = {ep: [] for ep in eps}
        for (ep, kind), layout in source_layouts.items():
            n = layout['count']
            if not n:
                continue
            d = frame_values.get(('current_body', ep, kind))
            if not d:
                continue
            decoded_sources[ep].add(kind)
            for j in range(n):
                skill = _u64(d, j * 8)
                if self.mc.is_ptr(skill):
                    if kind == 'active' and skill not in active_of[ep]:
                        active_of[ep].append(skill)
                    if skill not in sks_of[ep]:
                        sks_of[ep].append(skill)

        # active 优先、all 补全；若容器读取不完整则继续用上次成功的对象地址。
        for ep in eps:
            current = sks_of[ep]
            all_available = self.mc.is_ptr(self._skill_ap.get(ep, 0))
            if 'active' in decoded_sources[ep]:
                self._active_skill_ptrs[ep] = active_of[ep]
            if current:
                self._skill_ptrs[ep] = current
            elif all_available and 'all' in decoded_sources[ep]:
                self._skill_ptrs[ep] = []
            elif ('active' in decoded_sources[ep]
                  and ep not in self._skill_ptrs):
                self._skill_ptrs[ep] = []
            else:
                sks_of[ep] = list(self._skill_ptrs.get(ep, ()))

        skill_reqs, skill_keys = [], []
        for ep in eps:
            for skill in sks_of[ep]:
                skill_reqs.append((skill, gs.EnemySkillFields.READ_SIZE))
                skill_keys.append((ep, skill))
        timers, datas = {}, {}
        if skill_reqs:
            skill_data = [frame_values.get(('skill', skill))
                          for _ep, skill in skill_keys]
            missing = [(idx, req) for idx, (req, data) in enumerate(
                zip(skill_reqs, skill_data)) if not data]
            if missing:
                fetched = self._chan.batch_read([req for _idx, req in missing])
                for (idx, _req), data in zip(missing, fetched):
                    skill_data[idx] = data
            for (ep, s), d in zip(skill_keys, skill_data):
                if not d:
                    continue
                trigger_addr = _u64(d, gs.EnemySkillFields.TRIGGER)
                timer_addr = _u64(d, gs.EnemySkillFields.M_COOLDOWN_TIMER)
                self._skill_runtime_meta[s] = {
                    'family_mask': _i32(d, gs.EnemySkillFields.FAMILY_MASK),
                    'cast_like_attack': bool(d[gs.EnemySkillFields.CAST_LIKE_ATTACK]),
                    'check_parent_active': bool(
                        d[gs.EnemySkillFields.CHECK_PARENT_ACTIVE]),
                    'ignore_silence': bool(d[gs.EnemySkillFields.IGNORE_SILENCE]),
                    'max_triggers': _i32(d, gs.EnemySkillFields.MAX_TRIGGER_TIME),
                    'trigger_count': _i32(d, gs.EnemySkillFields.M_TRIGGER_CNT),
                    'trigger_addr': trigger_addr,
                    'timer_addr': timer_addr,
                    'has_trigger': self.mc.is_ptr(trigger_addr),
                    'sp_cost_runtime': _i32(d, gs.EnemySkillFields.M_SP_COST),
                    'ability_addr': (_u64(d, gs.EnemySkillFields.ABILITY)
                                     or _u64(d, gs.EnemySkillFields.M_MAIN_ABILITY)),
                    'parent_mode_addr': _u64(d, gs.EnemySkillFields.PARENT_MODE),
                    'is_enabled': s in self._active_skill_ptrs.get(ep, ()),
                }
                dp = _u64(d, gs.EnemySkillFields.DATA)
                if self.mc.is_ptr(timer_addr):
                    timers[s] = timer_addr
                if (self.mc.is_ptr(dp) and (s not in self._skill_names
                                            or s not in self._skill_static_meta)):
                    datas[s] = dp
        trigger_states = self._read_trigger_states_chan(
            [meta.get('trigger_addr', 0)
             for meta in self._skill_runtime_meta.values()],
            prefetched={
                trigger: frame_values.get(('trigger', trigger))
                for trigger in {
                    meta.get('trigger_addr', 0)
                    for meta in self._skill_runtime_meta.values()}
                if self.mc.is_ptr(trigger)})
        for meta in self._skill_runtime_meta.values():
            meta.update(trigger_states.get(meta.get('trigger_addr', 0), {}))
        remain_of = {}
        if timers:
            sks = list(timers)
            timer_data = [frame_values.get(('timer', s, timers[s])) for s in sks]
            missing = [(idx, s) for idx, (s, data) in enumerate(
                zip(sks, timer_data)) if not data]
            if missing:
                fetched = self._chan.batch_read([
                    (timers[s], 0x20) for _idx, s in missing])
                for (idx, _s), data in zip(missing, fetched):
                    timer_data[idx] = data
            for s, d in zip(sks, timer_data):
                if not d:
                    continue
                period = gs.fp_to_float(_u64(d, gs.PeriodicTimerFields.M_PERIOD_TIME))
                remain = gs.fp_to_float(_u64(d, gs.PeriodicTimerFields.M_REMAINING_TIME))
                if 0 <= period <= 3600 and -1 <= remain <= 3600:
                    remain_of[s] = (remain, period)
        if datas:   # 首见技能: data 块 -> prefabKey 字符串 + 静态判定参数
            pks = {}
            sks = list(datas)
            for s, d in zip(sks, self._chan.batch_read([(datas[s], 0x28) for s in sks])):
                if not d:
                    continue
                prio = _i32(d, gs.ESkillDataFields.PRIORITY)
                sp_cost = _i32(d, gs.ESkillDataFields.SP_COST)
                if -10000 <= prio <= 10000 and 0 <= sp_cost <= 100000:
                    self._skill_static_meta[s] = {
                        'priority': prio, 'sp_cost': sp_cost}
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
            out = [(self._skill_names.get(s, '?'), r, p)
                   for s in sks if s in remain_of
                   for r, p in (remain_of[s],)]
            enriched = [self._build_skill_row(s, *remain_of[s])
                        for s in sks if s in remain_of]
            # 计时器也可能在切阶段的一帧内为 NULL；有旧值时继续保留，下一轮
            # 自动重试。只有完整数组明确为空时才立即发布空技能列表。
            if out or not self._skill_cd.get(ep):
                self._skill_cd[ep] = out
                self._skill_enriched[ep] = enriched
            elif ('all' in decoded_sources[ep] and not sks
                  and self.mc.is_ptr(self._skill_ap.get(ep, 0))):
                self._skill_cd[ep] = []
                self._skill_enriched[ep] = []
        # 技能对象随敌人退场释放, 修剪名称缓存防地址复用串名
        live_sks = {s for ep in ptrs for s in self._skill_ptrs.get(ep, ())}
        for s in list(self._skill_names):
            if s not in live_sks:
                self._skill_names.pop(s, None)
        for s in list(self._skill_runtime_meta):
            if s not in live_sks:
                self._skill_runtime_meta.pop(s, None)
        for s in list(self._skill_static_meta):
            if s not in live_sks:
                self._skill_static_meta.pop(s, None)
        live_sources = {
            (ep, kind) for ep in eps for kind, ptr in (
                ('active', self._skill_lp.get(ep, 0)),
                ('all', self._skill_ap.get(ep, 0)))
            if self.mc.is_ptr(ptr)}
        for key in list(self._skill_source_layout):
            if key not in live_sources:
                self._skill_source_layout.pop(key, None)
        live_triggers = {
            meta.get('trigger_addr') for meta in self._skill_runtime_meta.values()
            if self.mc.is_ptr(meta.get('trigger_addr', 0))}
        live_triggers.update(
            runtime.get('action', {}).get('mode_attack_trigger_addr', 0)
            for runtime in self._runtime_snapshot.values()
            if self.mc.is_ptr(runtime.get('action', {}).get(
                'mode_attack_trigger_addr', 0)))
        for trigger in list(self._trigger_type_cache):
            if trigger not in live_triggers:
                self._trigger_type_cache.pop(trigger, None)

    def _build_skill_row(self, skill, remain, period):
        """汇总单个技能的运行时与静态判定参数，供下一动作推断与详情页使用。"""
        meta = self._skill_runtime_meta.get(skill, {})
        static = self._skill_static_meta.get(skill, {})
        return {
            'addr': skill,
            'name': self._skill_names.get(skill, '?'),
            'remaining': remain, 'period': period,
            'priority': static.get('priority', 0),
            'sp_cost': meta.get('sp_cost_runtime', static.get('sp_cost', 0)),
            'max_triggers': meta.get('max_triggers', 0),
            'trigger_count': meta.get('trigger_count', 0),
            'has_trigger': bool(meta.get('has_trigger')),
            'trigger_addr': meta.get('trigger_addr', 0),
            'trigger_type': meta.get('trigger_type', ''),
            'trigger_ready': meta.get('trigger_ready'),
            'trigger_reason': meta.get('trigger_reason', ''),
            'trigger_target_addr': meta.get('trigger_target_addr', 0),
            'trigger_value_type': meta.get('trigger_value_type'),
            'trigger_value': meta.get('trigger_value'),
            'trigger_compare_type': meta.get('trigger_compare_type'),
            'family_mask': meta.get('family_mask', 0),
            'cast_like_attack': bool(meta.get('cast_like_attack')),
            'check_parent_active': bool(meta.get('check_parent_active')),
            'parent_mode_addr': meta.get('parent_mode_addr', 0),
            'ignore_silence': bool(meta.get('ignore_silence')),
            'is_enabled': meta.get('is_enabled'),
        }

    def _fill_new_enemies_chan(self, new_eps, infos):
        """新敌人通道内解析：批量读取 ID、关卡名称、Attributes 与 cachedData。"""
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
            if info.data_ptr and self.mc.is_ptr(info.data_ptr):
                reqs.append((info.data_ptr, gs.LevelEnemyDataFields.ATTRIBUTES))
                keys.append(('data', ep))
        cdps, eids, name_ptrs = {}, {}, {}
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
                    eids[ep] = eid
                elif kind == 'attr':
                    cdp = _u64(d, gs.AttributesFields.M_CACHED_DATA) if d else 0
                    if cdp and self.mc.is_ptr(cdp):
                        cdps[ep] = cdp
                elif d:
                    name_ptr = _u64(d, gs.LevelEnemyDataFields.NAME)
                    if self.mc.is_ptr(name_ptr):
                        name_ptrs[ep] = name_ptr

        reqs, keys = [], []
        for ep, cdp in cdps.items():
            reqs.append((cdp, 0x20 + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE))
            keys.append(('cached', ep))
        for ep, name_ptr in name_ptrs.items():
            reqs.append((name_ptr, gs.Il2CppString.CHARS + 128 * 2))
            keys.append(('name', ep))
        runtime_names = {}
        if reqs:
            for (kind, ep), data in zip(keys, self._chan.batch_read(reqs)):
                if kind == 'cached':
                    if data and 0 < _i32(data, gs.Il2CppArray.MAX_LENGTH) <= 64:
                        self._attr_cache[ep] = cdps[ep]
                        tmp = EnemyInfo(ep)
                        self._apply_cached_data(data, tmp)
                        self._attr_snapshot[ep] = dict(tmp.attributes)
                    continue
                if not data:
                    continue
                count = _i32(data, gs.Il2CppString.LENGTH)
                if not (0 < count <= 128):
                    continue
                try:
                    runtime_names[ep] = data[
                        gs.Il2CppString.CHARS:
                        gs.Il2CppString.CHARS + count * 2].decode('utf-16-le')
                except UnicodeDecodeError:
                    continue

        for ep, eid in eids.items():
            if not eid:
                # 瞬读失败不缓存空 ID: 一旦缓存, new_eps 不再重试, 实体永远
                # 无法按 ID 认领计划项 (计划行卡「未出场」, 实体落动态行)。
                continue
            name, code = self._remember_enemy_name(eid, runtime_names.get(ep, ''))
            self._names[ep] = (eid, name, code)
        # 通道内未解决的走一次完整慢读兜底 (空结果不缓存, 下帧重试)
        for ep in new_eps:
            if ep not in self._names or ep not in self._attr_snapshot:
                full = self._read_enemy(ep, with_runtime=False)
                if ep not in self._names and full.eid:
                    self._names[ep] = (full.eid, full.name, full.code)
                if ep not in self._attr_snapshot and full.attributes:
                    self._attr_snapshot[ep] = dict(full.attributes)
                if ep not in infos:
                    infos[ep] = full

    def _log_identity_diagnostics(self, ptrs, infos):
        """测试版低频输出实体身份解析健康度；失败时附三条原始指针摘要。"""
        if not self.diagnostics:
            return
        missing_ids = [ep for ep in ptrs
                       if not self._names.get(ep, ('', '', ''))[0]]
        missing_attrs = [ep for ep in ptrs if not self._attr_snapshot.get(ep)]
        signature = (len(ptrs), len(missing_ids), len(missing_attrs))
        now = time.time()
        if (signature == self._identity_diag_signature
                and now - self._identity_diag_ts < 5.0):
            return
        self._identity_diag_signature = signature
        self._identity_diag_ts = now
        channel = self._chan
        backend = (f"{getattr(channel, 'mode', None) or '未连接'}"
                   f"/v{getattr(channel, 'srv_version', 0)}")
        if not missing_ids and not missing_attrs:
            self.log(
                f"[诊断] 实体解析健康：总数 {len(ptrs)}，ID {len(ptrs)}，"
                f"属性 {len(ptrs)}，通道 {backend}")
            return
        self.log(
            f"[诊断] 实体解析不完整：总数 {len(ptrs)}，"
            f"缺 ID {len(missing_ids)}，缺属性 {len(missing_attrs)}，通道 {backend}")
        samples = list(dict.fromkeys(missing_ids + missing_attrs))[:3]
        for ep in samples:
            info = infos.get(ep)
            try:
                klass = self.mc.read_klass_name(ep) or '?'
            except Exception as exc:
                klass = f"读取失败:{type(exc).__name__}"
            if info is None:
                self.log(f"[诊断]   {hex(ep)} class={klass} 主对象块未读取")
                continue
            self.log(
                f"[诊断]   {hex(ep)} class={klass} hp={info.hp:.3f} "
                f"id_ptr={hex(info.id_ptr) if info.id_ptr else '0'}"
                f"({'ok' if self.mc.is_ptr(info.id_ptr) else 'invalid'}) "
                f"attr_ptr={hex(info.attr_ptr) if info.attr_ptr else '0'}"
                f"({'ok' if self.mc.is_ptr(info.attr_ptr) else 'invalid'}) "
                f"data_ptr={hex(info.data_ptr) if info.data_ptr else '0'}"
                f"({'ok' if self.mc.is_ptr(info.data_ptr) else 'invalid'})")

    def _detail_batch_read(self, reqs):
        """批量读取；详情线程走独立端口，绝不占住高频轮询通道。"""
        if not reqs:
            return []
        if getattr(self._detail_context, 'active', False):
            if self._poll_stop.is_set():
                raise InterruptedError('敌人详情读取已请求停止')
            if self._detail_chan is None:
                self._detail_chan = TcpChannel(self.mc, port=DETAIL_TCP_PORT)
            return self._detail_chan.batch_read(reqs)
        if self._chan is not None:
            return self._chan.batch_read(reqs)
        raise RuntimeError('memsrv v4 主通道尚未建立')

    def _read_strings(self, ptrs, max_chars=256):
        unique = [p for p in dict.fromkeys(ptrs) if self.mc.is_ptr(p)]
        if not unique:
            return {}
        size = gs.Il2CppString.CHARS + max_chars * 2
        results = list(self._detail_batch_read([(p, size) for p in unique]))
        # 通道瞬态失败同批补读一次: buff 每秒重建时字符串读失败会把键名渲染成 '?'
        failed = [i for i, data in enumerate(results)
                  if not data or len(data) < gs.Il2CppString.CHARS]
        if failed:
            for i, data in zip(failed,
                               self._detail_batch_read([(unique[i], size)
                                                        for i in failed])):
                if data:
                    results[i] = data
        out = {}
        for ptr, data in zip(unique, results):
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
                owners.append((ptr, items, count))
        for (ptr, items, count), data in zip(owners, self._detail_batch_read(reqs)):
            if data:
                arrays[ptr] = (items, count, data)
        string_ptrs = []
        parsed = {}
        for ptr, (items, count, data) in arrays.items():
            rows = []
            for idx in range(count):
                off = idx * 0x18
                if off + 0x18 > len(data):
                    break
                key_ptr = _u64(data, off)
                value = struct.unpack_from('<f', data, off + 8)[0]
                value_str_ptr = _u64(data, off + 0x10)
                string_ptrs.extend((key_ptr, value_str_ptr))
                value_addr = items + gs.Il2CppArray.ITEMS + off + 8
                rows.append((key_ptr, value, value_str_ptr, value_addr))
            parsed[ptr] = rows
        strings = self._read_strings(string_ptrs)
        for ptr, rows in parsed.items():
            result[ptr] = [
                {'key': strings.get(kp, ''), 'value': value,
                 'value_str': strings.get(sp, '') if sp else '',
                 'value_addr': value_addr}
                for kp, value, sp, value_addr in rows
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

    def _get_char_names(self):
        """惰性加载 charId -> 中文名 (与 deploy_tracker 共用同一份静态表)。"""
        if self._char_names is None:
            self._char_names = {}
            try:
                from tools.deploy_tracker.char_names import load_char_names
                root = os.path.abspath(os.path.join(
                    os.path.dirname(__file__), '..', '..'))
                self._char_names = load_char_names(root)
            except Exception:
                pass
        return self._char_names

    def _resolve_buff_source_names(self, addrs):
        """批量解析 buff 来源实体名称。

        敌人命中 ``_names``；干员/召唤物等其他实体读 Entity.id 字符串后按
        静态表 (char_*/token_* -> 中文名, enemy_* -> 敌人数据库) 映射，
        再退化为 id 原文。成功的结果按地址缓存；读不到的不缓存，下一轮重试。
        """
        out = {}
        pending = []
        for addr in dict.fromkeys(addrs):
            if not self.mc.is_ptr(addr):
                continue
            if addr in self._names:
                out[addr] = self._names[addr][1]
            elif self._buff_source_names.get(addr):
                out[addr] = self._buff_source_names[addr]
            else:
                pending.append(addr)
        if not pending:
            return out
        blocks = self._detail_batch_read(
            [(addr, gs.EntityFields.ID + 8) for addr in pending])
        id_ptrs = [_u64(blk, gs.EntityFields.ID) if blk else 0
                   for blk in blocks]
        strings = self._read_strings(id_ptrs)
        if self._db is None:
            self._db = load_enemy_db()
        char_names = self._get_char_names()
        for addr, id_ptr in zip(pending, id_ptrs):
            eid = strings.get(id_ptr, '') if id_ptr else ''
            if not eid:
                continue
            name = char_names.get(eid.split('@', 1)[0]) \
                or (self._db.get(eid) or {}).get('name') or eid
            self._buff_source_names[addr] = name
            out[addr] = name
        return out

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

        string_ptrs, bb_ptrs, fp_ptrs, data_ptrs = [], [], [], []
        for _, data in records:
            string_ptrs.extend((_u64(data, gs.BuffFields.KEY),
                                _u64(data, gs.BuffFields.OVERRIDE_KEY),
                                _u64(data, gs.BuffFields.EFFECT_KEY)))
            bb_ptrs.append(_u64(data, gs.BuffFields.M_BLACKBOARD))
            data_ptrs.append(_u64(data, gs.BuffFields.M_DATA))
            fp_ptrs.extend(_u64(data, off) for off in (
                gs.BuffFields.M_ATTRIBUTE_MULTIPLIERS,
                gs.BuffFields.M_ATTRIBUTE_ADDITIONS,
                gs.BuffFields.M_ATTRIBUTE_FINAL_ADDITIONS,
                gs.BuffFields.M_ATTRIBUTE_FINAL_SCALERS))
        unique_data_ptrs = [p for p in dict.fromkeys(data_ptrs) if self.mc.is_ptr(p)]
        data_blocks = {
            ptr: data for ptr, data in zip(
                unique_data_ptrs,
                self._detail_batch_read([
                    (ptr, gs.BuffDataFields.READ_SIZE) for ptr in unique_data_ptrs]))
            if data
        }
        for data in data_blocks.values():
            string_ptrs.extend((
                _u64(data, gs.BuffDataFields.BUFF_KEY),
                _u64(data, gs.BuffDataFields.TEMPLATE_KEY),
                _u64(data, gs.BuffDataFields.OVERRIDE_KEY),
                _u64(data, gs.BuffDataFields.OVERRIDE_EFFECT_KEY),
                _u64(data, gs.BuffDataFields.AUDIO_SIGNAL),
                _u64(data, gs.BuffDataFields.DURATION_KEY),
            ))
            bb_ptrs.append(_u64(data, gs.BuffDataFields.BLACKBOARD))
        strings = self._read_strings(string_ptrs)
        blackboards = self._read_blackboards(bb_ptrs)
        fp_arrays = self._read_plain_fp_arrays(fp_ptrs)

        src_names = self._resolve_buff_source_names(
            [_u64(data, gs.BuffFields.M_SOURCE) for _, data in records])

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
            source_name = src_names.get(source, '')
            key_ptr = _u64(data, gs.BuffFields.KEY)
            override_ptr = _u64(data, gs.BuffFields.OVERRIDE_KEY)
            effect_ptr = _u64(data, gs.BuffFields.EFFECT_KEY)
            bb_ptr = _u64(data, gs.BuffFields.M_BLACKBOARD)
            data_ptr = _u64(data, gs.BuffFields.M_DATA)
            definition_data = data_blocks.get(data_ptr)
            definition = {}
            if definition_data:
                definition = {
                    'addr': data_ptr,
                    'buff_key': strings.get(_u64(
                        definition_data, gs.BuffDataFields.BUFF_KEY), ''),
                    'template_key': strings.get(_u64(
                        definition_data, gs.BuffDataFields.TEMPLATE_KEY), ''),
                    'override_key': strings.get(_u64(
                        definition_data, gs.BuffDataFields.OVERRIDE_KEY), ''),
                    'override_effect_key': strings.get(_u64(
                        definition_data, gs.BuffDataFields.OVERRIDE_EFFECT_KEY), ''),
                    'audio_signal': strings.get(_u64(
                        definition_data, gs.BuffDataFields.AUDIO_SIGNAL), ''),
                    'duration_key': strings.get(_u64(
                        definition_data, gs.BuffDataFields.DURATION_KEY), ''),
                    'life_time_type': definition_data[
                        gs.BuffDataFields.LIFE_TIME_TYPE],
                    'life_time': struct.unpack_from(
                        '<f', definition_data, gs.BuffDataFields.LIFE_TIME)[0],
                    'trigger_life_type': definition_data[
                        gs.BuffDataFields.TRIGGER_LIFE_TYPE],
                    'trigger_count': _i32(
                        definition_data, gs.BuffDataFields.TRIGGER_COUNT),
                    'trigger_interval': struct.unpack_from(
                        '<f', definition_data,
                        gs.BuffDataFields.TRIGGER_INTERVAL)[0],
                    'max_stack_count': _i32(
                        definition_data, gs.BuffDataFields.MAX_STACK_COUNT),
                    'max_valid_stack_count': _i32(
                        definition_data,
                        gs.BuffDataFields.MAX_VALID_STACK_COUNT),
                    'override_type': _i32(
                        definition_data, gs.BuffDataFields.OVERRIDE_TYPE),
                    'priority': _i32(
                        definition_data, gs.BuffDataFields.PRIORITY),
                    'disable_override': bool(definition_data[
                        gs.BuffDataFields.DISABLE_OVERRIDE]),
                    'load_from_db': bool(definition_data[
                        gs.BuffDataFields.LOAD_FROM_DB]),
                    'durable': bool(definition_data[
                        gs.BuffDataFields.IS_DURABLE]),
                    'damage_missable': bool(definition_data[
                        gs.BuffDataFields.IS_DAMAGE_MISSABLE]),
                    'silenceable': bool(definition_data[
                        gs.BuffDataFields.IS_SILENCEABLE]),
                    'stunnable': bool(definition_data[
                        gs.BuffDataFields.IS_STUNNABLE]),
                    'freezable': bool(definition_data[
                        gs.BuffDataFields.IS_FREEZABLE]),
                    'levitatable': bool(definition_data[
                        gs.BuffDataFields.IS_LEVITATABLE]),
                    'ground_boundable': bool(definition_data[
                        gs.BuffDataFields.IS_GROUND_BOUNDABLE]),
                    'status_resistable': definition_data[
                        gs.BuffDataFields.STATUS_RESISTABLE],
                    'independent_character_source': bool(definition_data[
                        gs.BuffDataFields.INDEPENDENT_CHARACTER_SOURCE]),
                    'blackboard': blackboards.get(_u64(
                        definition_data, gs.BuffDataFields.BLACKBOARD), []),
                }
            record = {
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
                'data_addr': data_ptr,
                'definition': definition,
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
            }
            custom_value, custom_mask, custom_sources = summarize_custom_shields(
                [record])
            record['custom_shield_value'] = custom_value
            record['custom_shield_mask'] = custom_mask
            record['custom_shield_sources'] = custom_sources
            out.append(record)
        return out

    def _discover_custom_shields(self, eps, infos):
        """首次见到旧式特殊护盾敌人时解析一次 Buff 链并缓存直读地址。"""
        for ep in eps:
            self._custom_shield_probe_tick[ep] = self._fast_tick
            info = infos.get(ep)
            if info is None or not self.mc.is_ptr(info.buff_container_ptr):
                continue
            enemy_id = self._names.get(ep, ('', '', ''))[0]
            if not any(enemy_id in rule.get('enemy_ids', ())
                       for rule in CUSTOM_SHIELD_RULES):
                continue
            buffs = self._read_active_buffs(info.buff_container_ptr)
            total, mask, sources = summarize_custom_shields(buffs, enemy_id)
            sources = [source for source in sources
                       if self.mc.is_ptr(source.get('buff_addr', 0))
                       and self.mc.is_ptr(source.get('value_addr', 0))]
            if not sources:
                continue
            self._custom_shield_ptrs[ep] = sources
            runtime = self._runtime_snapshot.setdefault(ep, {})
            runtime['special_shield'] = total
            runtime['special_shield_mask'] = mask
            runtime['special_shield_sources'] = [dict(source) for source in sources]
            self._copy_runtime(info, runtime)

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
        if not blk or len(blk) < max(gs.EntityFields.BUFF_CONTAINER + 8,
                                    gs.EnemyFields.DATA + 8):
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
            if self._chan is None:
                raise RuntimeError('memsrv v4 主通道尚未建立')
            self._refresh_runtime_chan([addr], {addr: info})
            info.skills = list(self._skill_cd.get(addr, []))
            info.skills_detail = list(self._skill_enriched.get(addr, ()))
        info.buffs = self._read_active_buffs(info.buff_container_ptr)
        special, special_mask, special_sources = summarize_custom_shields(
            info.buffs, info.eid)
        info.special_shield = special
        info.special_shield_mask = special_mask
        info.special_shield_sources = special_sources
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
