"""
明日方舟 IL2CPP 运行时结构偏移定义

基于 Ark_data/dump.cs (2.7.x 版本) 分析, 并已对 2026-07 在线版本
(Android arm64, versionName=2.7.51) 逐项实测验证:

  [实测验证 2026-07-21]
  - 5 个场上敌人 (enemy_1007_slime_2) 通过 klass 名 'Enemy' 确认
  - m_hp=0x40, <id>=0x130, m_attributes=0x98, m_cachedData=0x50
  - ObscuredFP 步长 0x28, XOR 解密后 Q32.32 定点数
  - List<Enemy>: _items=0x10 _size=0x18, 数组数据 +0x20, 长度 +0x18
  - Scheduler.m_managedWaveEnemies=0xB8 (全堆唯一引用点定位)
  - SchedulerDriver: +0x10=BattleController; BC: state=0x220 speed=0x228
    timeScale=0x280 playTime=0x284 (dump.cs 旧偏移 0x30/0x22C/0x234/0x294 已失效)

  [实测验证 2026-07-23] (5-10 浮士德 + 4 小怪)
  - m_skills=0x498 (List<EnemySkill>) / m_allSkills=0x410 (数组) 均有效
  - EnemySkill: cooldownTimer=0x48 data=0x80; PeriodicTimer: period=0x10
    remaining=0x18 (普通 FP); ESkillData: prefabKey=0x10 cooldown=0x1C
    initCooldown=0x20。浮士德 SummonBallis/CriticalHit 两计时器出场
    经过时间互相吻合 (3.63s), 链路确认

所有偏移均为相对对象起始地址的绝对偏移 (含 0x10 对象头)。
"""

import struct

# ============================================================
# IL2CPP 基础布局 (64 位)
# ============================================================
IL2CPP_OBJECT_HEADER_SIZE = 0x10  # klass(8) + monitor(8)


class Il2CppString:
    """Il2CppString 布局"""
    LENGTH = 0x10      # int32 字符数
    CHARS = 0x14       # UTF-16LE 数据


class Il2CppArray:
    """Il2CppArray 布局 (64 位)"""
    BOUNDS = 0x10      # Il2CppArrayBounds* (可为 NULL)
    MAX_LENGTH = 0x18  # int32 数组容量
    ITEMS = 0x20       # 数据起始


class ListInternal:
    """System.Collections.Generic.List<T> (64 位)"""
    ITEMS = 0x10       # T[] 数组指针
    SIZE = 0x18        # int32 元素数量
    VERSION = 0x1C     # int32


# ============================================================
# 定点数 FP (Q32.32)
# ============================================================
FP_FRACTIONAL_BITS = 32
FP_ONE = 1 << FP_FRACTIONAL_BITS


def fp_to_float(raw_value: int) -> float:
    """FP (Q32.32 定点数, int64 存储) 转 float"""
    if raw_value & 0x8000000000000000:
        raw_value -= 1 << 64
    return raw_value / FP_ONE


# ============================================================
# Anti-Cheat 混淆数值 (CodeStage Anti-Cheat Toolkit)
# ============================================================
class ObscuredLong:
    """ObscuredLong: sizeof=0x28 (对齐后)"""
    CRYPTO_KEY = 0x00       # int64 currentCryptoKey
    HIDDEN_VALUE = 0x08     # int64 hiddenValue
    INITED = 0x10           # bool
    FAKE_VALUE = 0x18       # int64
    FAKE_VALUE_ACTIVE = 0x20  # bool
    SIZE = 0x28


# ObscuredFP 内嵌一个 ObscuredLong (_serializedValue @ 0x0)
OBSCURED_FP_SIZE = ObscuredLong.SIZE  # 0x28


def decrypt_obscured_long(key: int, hidden: int) -> int:
    """real = hidden XOR key"""
    return (hidden ^ key) & 0xFFFFFFFFFFFFFFFF


def obscured_fp_to_float(key: int, hidden: int) -> float:
    """ObscuredFP 解密并转 float"""
    return fp_to_float(decrypt_obscured_long(key, hidden))


class ObscuredInt:
    """ObscuredInt: sizeof=0x14"""
    CURRENT_CRYPTO_KEY = 0x00   # int32
    HIDDEN_VALUE = 0x04         # int32
    INITED = 0x08               # bool
    FAKE_VALUE = 0x0C           # int32
    FAKE_VALUE_ACTIVE = 0x10    # bool
    SIZE = 0x14


def decrypt_obscured_int(key: int, hidden: int) -> int:
    return (hidden ^ key) & 0xFFFFFFFF


# ============================================================
# Entity (战场实体基类)  [已实测验证]
# ============================================================
class EntityFields:
    M_STATE_MACHINE = 0x38    # StateMachine*
    M_HP = 0x40               # FP 当前血量 [实测]
    M_ES = 0x48               # FP 元素护盾
    M_SP = 0x50               # ObscuredFP 技力
    M_RESPAWN_CNT = 0x78      # int32
    M_EP_ARRAY = 0x80         # FP[]
    M_EP_CONTROLLER = 0xE8    # Entity.EPController*
    M_SHIELD_CONTROLLER = 0xF0  # Entity.ShieldUIController*
    M_DIRECTION = 0xD4        # int32
    M_ATTRIBUTES = 0x98       # Attributes* [实测]
    ID = 0x130                # string <id> [实测]
    TMPL_ID = 0x138           # string <tmplId>
    FINISH_REASON = 0x140     # int32
    BUFF_CONTAINER = 0x150    # Buff.BuffContainer*
    MAX_SP = 0x160            # int32
    MINUS_HP = 0x168          # FP


# ============================================================
# Enemy (敌方单位)
# ============================================================
class EnemyFields:
    M_CURRENT_TILE = 0x320      # Tile*
    M_BLOCK_POSITION = 0x3C0    # Vector2 (float x,y) 阻挡位置
    M_POS_IN_LAST_FRAME = 0x3D0 # Vector2 (float x,y) 上一帧地图坐标
    M_ALL_SKILLS = 0x410        # EnemySkill[] 全部技能组件 [实测]
    ROUTE_SPAWN_POS = 0x478     # GridPosition (int32 row,col) 出生格
    READ_SIZE = 0x4A0           # 稳态每敌读取跨度 (含 m_skills 指针 0x498+8)
    M_SKILLS = 0x498            # List<EnemySkill> 激活技能列表 [实测]


# ============================================================
# EnemySkill (敌方技能)  [已实测验证 2026-07-23]
# 注意: EnemySkill 是 MonoBehaviour, 字段含 0x10 对象头 + 0x8 m_CachedPtr
# ============================================================
class EnemySkillFields:
    MAX_TRIGGER_TIME = 0x2C     # int32 最多触发次数
    OVERWRITE_INIT_CD = 0x34    # int32 初始冷却覆盖
    M_SP_COST = 0x3C            # int32
    M_TRIGGER_CNT = 0x40        # int32 已触发次数
    M_COOLDOWN_TIMER = 0x48     # PeriodicTimer* 冷却计时器
    M_MAIN_ABILITY = 0x58       # Ability*
    DATA = 0x80                 # ESkillData* 静态配置
    OWNER = 0x88                # Enemy*


class PeriodicTimerFields:
    M_PERIOD_TIME = 0x10        # FP 周期 (技能总 CD, 秒)
    M_REMAINING_TIME = 0x18     # FP 剩余 (当前 CD 剩余, 秒)


class ESkillDataFields:
    PREFAB_KEY = 0x10           # string 技能 ID
    PRIORITY = 0x18             # int32
    COOLDOWN = 0x1C             # float 配置 CD
    INIT_COOLDOWN = 0x20        # float 初始 CD (出场后首次)
    SP_COST = 0x24              # int32


# ============================================================
# Attributes (属性系统)  [已实测验证]
# ============================================================
class AttributesFields:
    M_ABNORMAL_FLAGS_COUNTER = 0x20    # short[AbnormalFlag.E_NUM]
    M_ABNORMAL_IMMUNE_COUNTER = 0x28   # short[AbnormalFlag.E_NUM]
    M_ABNORMAL_ANTI_COUNTER = 0x30     # short[AbnormalFlag.E_NUM]
    M_ABNORMAL_COMBO_MGR = 0x38        # Attributes.AbnormalComboManager*
    M_RAW_DATA = 0x40                  # ObscuredFP[] 原始属性
    M_CACHED_DATA = 0x50               # ObscuredFP[] 计算后属性 [实测]


class AbnormalComboManagerFields:
    M_ABNORMAL_COMBO_COUNTER = 0x10
    M_ABNORMAL_COMBO_IMMUNE_COUNTER = 0x18


class StateMachineFields:
    CURRENT_STATE_ID = 0x48


class EPControllerFields:
    M_IS_IN_BREAK_RECOVERY = 0x20


class ShieldUIControllerFields:
    M_SHIELD_TO_SHOW = 0x18


class AttributeType:
    MAX_HP = 0
    ATK = 1
    DEF = 2
    MAGIC_RESISTANCE = 3
    COST = 4
    BLOCK_CNT = 5
    MOVE_SPEED = 6
    ATTACK_SPEED = 7
    BASE_ATTACK_TIME = 8
    HP_RECOVERY_PER_SEC = 13
    SP_RECOVERY_PER_SEC = 14
    ABILITY_RANGE_FORWARD_EXTEND = 15
    MAX_DEPLOY_COUNT = 16
    DEF_PENETRATE = 17
    MAGIC_RESIST_PENETRATE = 18
    HP_RECOVERY_PER_SEC_BY_MAX_HP_RATIO = 19
    TAUNT_LEVEL = 20
    RESPAWN_TIME = 21
    MASS_LEVEL = 23
    BASE_FORCE_LEVEL = 24
    DEF_PENETRATE_FIXED = 25
    ONE_MINUS_STATUS_RESISTANCE = 26
    MAGIC_RESIST_PENETRATE_FIXED = 27
    MAX_EP = 28
    EP_RECOVERY_PER_SEC = 29
    SP_RECOVER_RATIO = 30
    EP_DAMAGE_RESISTANCE = 31
    EP_RESISTANCE = 32
    DAMAGE_HITRATE_PHYSICAL = 33
    DAMAGE_HITRATE_MAGICAL = 34
    EP_BREAK_RECOVER_SPEED = 35
    SLOW_DOWN = 36
    BLOCK_RADIUS_SCALE = 37
    E_NUM = 38


# (枚举值, 内部名, 中文名)。9-12 是游戏保留槽，不在界面中展示。
ATTRIBUTE_DEFS = (
    (0, 'MAX_HP', '最大生命'),
    (1, 'ATK', '攻击'),
    (2, 'DEF', '防御'),
    (3, 'MAGIC_RESISTANCE', '法术抗性'),
    (4, 'COST', '部署费用'),
    (5, 'BLOCK_CNT', '阻挡数'),
    (6, 'MOVE_SPEED', '移动速度'),
    (7, 'ATTACK_SPEED', '攻击速度'),
    (8, 'BASE_ATTACK_TIME', '基础攻击间隔'),
    (13, 'HP_RECOVERY_PER_SEC', '每秒生命恢复'),
    (14, 'SP_RECOVERY_PER_SEC', '每秒技力恢复'),
    (15, 'ABILITY_RANGE_FORWARD_EXTEND', '技能范围前向延伸'),
    (16, 'MAX_DEPLOY_COUNT', '最大部署数'),
    (17, 'DEF_PENETRATE', '物理穿透比例'),
    (18, 'MAGIC_RESIST_PENETRATE', '法抗穿透比例'),
    (19, 'HP_RECOVERY_PER_SEC_BY_MAX_HP_RATIO', '按最大生命每秒恢复'),
    (20, 'TAUNT_LEVEL', '嘲讽等级'),
    (21, 'RESPAWN_TIME', '再部署时间'),
    (22, 'MAX_DECK_STACK_CNT', '最大卡组堆叠数'),
    (23, 'MASS_LEVEL', '重量等级'),
    (24, 'BASE_FORCE_LEVEL', '基础力度等级'),
    (25, 'DEF_PENETRATE_FIXED', '固定物理穿透'),
    (26, 'ONE_MINUS_STATUS_RESISTANCE', '一减状态抗性'),
    (27, 'MAGIC_RESIST_PENETRATE_FIXED', '固定法抗穿透'),
    (28, 'MAX_EP', '损伤条上限'),
    (29, 'EP_RECOVERY_PER_SEC', '每秒损伤恢复'),
    (30, 'SP_RECOVER_RATIO', '技力恢复倍率'),
    (31, 'EP_DAMAGE_RESISTANCE', '元素损伤减免'),
    (32, 'EP_RESISTANCE', '元素抗性'),
    (33, 'DAMAGE_HITRATE_PHYSICAL', '物理伤害命中倍率'),
    (34, 'DAMAGE_HITRATE_MAGICAL', '法术伤害命中倍率'),
    (35, 'EP_BREAK_RECOVER_SPEED', '元素爆发恢复速度'),
    (36, 'SLOW_DOWN', '减速倍率'),
    (37, 'BLOCK_RADIUS_SCALE', '阻挡半径倍率'),
)
ATTRIBUTE_INTERNAL_NAMES = {idx: key for idx, key, _ in ATTRIBUTE_DEFS}
ATTRIBUTE_CN_NAMES = {idx: name for idx, _, name in ATTRIBUTE_DEFS}


class AbnormalFlag:
    E_NUM = 45


ABNORMAL_FLAG_DEFS = (
    (0, 'STUNNED', '眩晕'),
    (1, 'SP_RECOVER_STOPPED', '停止技力回复'),
    (2, 'TARGET_FREE', '不可选中'),
    (3, 'BLOCK_FREE', '不可阻挡'),
    (4, 'HIDDEN', '隐藏'),
    (5, 'INVINCIBLE', '无敌'),
    (6, 'UNDEADABLE', '不会死亡'),
    (7, 'HEAL_FREE', '禁止治疗'),
    (8, 'UNBALANCE_IMMUNE', '失衡免疫'),
    (9, 'INVISIBLE', '隐形'),
    (10, 'UNUSED_PLACEHOLDER_1', '保留状态1'),
    (11, 'DISARMED', '缴械'),
    (12, 'SILENCED', '沉默'),
    (13, 'UNMOVABLE', '不可移动'),
    (14, 'UNUSED_PLACEHOLDER_2', '保留状态2'),
    (15, 'ALLY_TARGET_FREE', '友方不可选中'),
    (16, 'FROZEN', '冻结'),
    (17, 'CAMOUFLAGE', '迷彩'),
    (18, 'FORCE_DISARMED', '强制缴械'),
    (19, 'STUNNED_NO_AMPLIFY_DAMAGE', '眩晕（不增伤）'),
    (20, 'DISABLE_COMBAT', '禁止战斗'),
    (21, 'ELEMENT_FREE_ALL', '免疫全部元素损伤'),
    (22, 'UNMOVABLE_PRIVATE', '不可移动（私有）'),
    (23, 'COLD', '寒冷'),
    (24, 'SKILL_NOT_ACTIVATABLE', '技能不可激活'),
    (25, 'LEVITATE', '浮空'),
    (26, 'DURANCE', '禁锢'),
    (27, 'NOT_WITHDRAWABLE', '不可撤退'),
    (28, 'OUT_OF_GROUND', '离地'),
    (29, 'SP_MODIFY_STOPPED', '停止技力修改'),
    (30, 'ANTI_STATUS_RESISTABLE', '抵抗可抵抗状态'),
    (31, 'DISARMED_COMBAT', '战斗缴械'),
    (32, 'TOWER_TARGET_FREE', '塔不可选中'),
    (33, 'FEARED', '恐惧'),
    (34, 'SKILL_ACTIVABLE_IN_ABNORMAL', '异常中可激活技能'),
    (35, 'MOTION_TARGET_FREE', '移动目标不可选中'),
    (36, 'FORCE_LEVITATE', '强制浮空'),
    (37, 'BUFF_ADD_CAN_BE_CANCELED_IF_DEFENSE', '可被防御取消的Buff'),
    (38, 'DEFENSE_BUFF_ADD_IF_CANCELABLE_BUFF', '防御可取消Buff'),
    (39, 'PALSY', '麻痹'),
    (40, 'PALSYING', '麻痹中'),
    (41, 'ATTRACTED', '吸引'),
    (42, 'FEARED_PRIVATE', '恐惧（私有）'),
    (43, 'DOZE', '昏睡'),
    (44, 'TELEPORTED', '传送'),
)
ABNORMAL_FLAG_INTERNAL_NAMES = {idx: key for idx, key, _ in ABNORMAL_FLAG_DEFS}
ABNORMAL_FLAG_CN_NAMES = {idx: name for idx, _, name in ABNORMAL_FLAG_DEFS}


class AbnormalCombo:
    SLEEPING = 0
    SHELTERING = 1
    E_NUM = 2


ABNORMAL_COMBO_DEFS = (
    (0, 'SLEEPING', '睡眠'),
    (1, 'SHELTERING', '庇护'),
)
ABNORMAL_COMBO_INTERNAL_NAMES = {idx: key for idx, key, _ in ABNORMAL_COMBO_DEFS}
ABNORMAL_COMBO_CN_NAMES = {idx: name for idx, _, name in ABNORMAL_COMBO_DEFS}


class ElementType:
    NONE = 0
    SANITY = 1
    WATER = 2
    FIRE = 3
    DARK = 4
    ANGER = 5
    E_NUM = 6


ELEMENT_DEFS = (
    (1, 'SANITY', '神经损伤'),
    (2, 'WATER', '侵蚀损伤'),
    (3, 'FIRE', '灼燃损伤'),
    (4, 'DARK', '凋亡损伤'),
    (5, 'ANGER', '狂躁损伤'),
)
ELEMENT_INTERNAL_NAMES = {idx: key for idx, key, _ in ELEMENT_DEFS}
ELEMENT_CN_NAMES = {idx: name for idx, _, name in ELEMENT_DEFS}

DAMAGE_TYPE_MASK_CN_NAMES = {2: '物理', 4: '法术', 8: '真实', 16: '治疗', 32: '元素'}


class EnemyState:
    TERMINAL = -1
    DEFAULT = 0
    MOVE = 1
    ATTACK = 2
    COMBAT = 3
    STUN = 4
    DEAD = 5
    BORN = 6
    REACH_EXIT = 7
    REBORN = 8
    UNBALANCE = 9
    FALLDOWN = 10
    DISAPPEAR = 11
    BLINK = 12
    FROZEN = 13
    LEVITATE = 14
    DIALOG = 15
    PALSY = 16


ENEMY_STATE_NAMES = {
    -1: '终止', 0: '默认', 1: '移动', 2: '攻击', 3: '战斗', 4: '眩晕',
    5: '死亡', 6: '出生', 7: '到达终点', 8: '重生', 9: '失衡',
    10: '坠落', 11: '消失', 12: '闪现', 13: '冻结', 14: '浮空',
    15: '剧情', 16: '麻痹',
}


class BuffContainerFields:
    M_BUFFS = 0x18


class DoubleBufferedListFields:
    M_INTERNAL_LIST = 0x10
    M_CACHED_BUFFER = 0x18


class BuffFields:
    M_SOURCE = 0x18
    M_ABILITY = 0x28
    M_ATTRIBUTE_MULTIPLIERS = 0x48
    M_ATTRIBUTE_ADDITIONS = 0x50
    M_ATTRIBUTE_FINAL_ADDITIONS = 0x58
    M_ATTRIBUTE_FINAL_SCALERS = 0x60
    M_DATA = 0x68
    M_LIFE_TIME = 0x70
    M_REMAINING_TIME = 0x78
    M_EXISTING_TIME = 0x80
    M_TRIGGER_CNT = 0x88
    M_STACK_CNT = 0x8C
    M_MAX_VALID_STACK_CNT = 0x90
    M_BLACKBOARD = 0xA8
    IS_FINISHED = 0x1E9
    IS_ACTUALLY_ENABLED = 0x1EC
    IS_VALID = 0x1EF
    IS_EP_BREAK_BUFF = 0x1F0
    KEY = 0x1F8
    OVERRIDE_KEY = 0x200
    INSTANCE_UID = 0x208
    PRIORITY = 0x20C
    ATTRIBUTE_MASK = 0x210
    ABNORMAL_FLAG_MASK = 0x218
    ABNORMAL_IMMUNE_MASK = 0x220
    ABNORMAL_ANTI_MASK = 0x228
    ABNORMAL_COMBO_MASK = 0x230
    ABNORMAL_COMBO_IMMUNE_MASK = 0x238
    EFFECT_KEY = 0x240
    SHIELD_MASK = 0x268
    HAS_SHIELD = 0x26C
    READ_SIZE = 0x270


class GlobalBuffFields:
    KEY = 0x18
    BUFFS = 0x80
    SOURCE_TYPE = 0xCC
    TARGET_MAP = 0x138
    BLACKBOARD = 0x140
    INSTANCE_UID = 0x148
    READ_SIZE = 0x150


class BuffDataFields:
    BUFF_KEY = 0x18
    TEMPLATE_KEY = 0x28
    LIFE_TIME_TYPE = 0x70
    DURATION_KEY = 0x78
    LIFE_TIME = 0x80
    PRIORITY = 0x98
    READ_SIZE = 0xA0


# ============================================================
# BattleController  [运行时实测验证 2026-07-22]
# 注意: dump.cs 的标量偏移与现网版本有 ~0x10 漂移, 以下为实测值
# ============================================================
class BattleControllerFields:
    MAP = 0x28                # Map* [实测 klass=Map]
    FACTORY = 0x38            # BattleFactory* [实测 klass=BattleFactory]
    M_GLOBAL_BUFFS = 0x68     # List<GlobalBuff> [2026-07 现网实测]
    M_LOGGER = 0xD8           # BattleLogger* [实测 klass=BattleLogger]
    LEVEL_DATA = 0x158        # LevelData* [实测 klass=LevelData]
    GAME_MODE = 0x170         # DefaultGameMode* [实测 klass=DefaultGameMode]
    DIALOG_CONTROLLER = 0x1B8 # DialogController* [实测]
    M_STATE = 0x220           # int32 State (0=NONE 1=INITED 2=PLAYING 3=FINISHED) [实测=2]
    M_SPEED_LEVEL = 0x228     # int32 SpeedLevel (0-3) [实测=1]
    M_TIME_SCALE = 0x280      # float 时间倍率 [实测=1.0]
    M_REAL_PLAY_TIME = 0x284  # float 战斗时间(秒) [实测]
    # 注意: dump.cs 中 _scheduler=0x30 / m_state=0x22C / m_speedLevel=0x234 /
    # m_realPlayTime=0x294 在现网版本均不成立 (实测+0x30非指针, +0x294为指针区内)


class BattleState:
    NONE = 0
    INITED = 1
    PLAYING = 2
    FINISHED = 3


class SpeedLevel:
    SLOW_MOTION = 0
    STANDARD = 1
    FAST = 2
    SUPER_FAST = 3
    NAMES = {0: "慢动作", 1: "1x", 2: "2x", 3: "4x"}


# ============================================================
# Scheduler  [已实测验证]
# 运行时定位方式: 全堆扫指向 m_managedWaveEnemies List 的指针,
# 全堆唯一命中即 Scheduler+0xB8 (实测唯一)。该对象的 klass 指针
# 异常(读不出类名), 但字段内容与 dump.cs Scheduler 类吻合。
# 注意: dump.cs 的 <battleController>k__BackingField=0x128 在现网
# 版本是 DialogController; BattleController 需经 SchedulerDriver 到达。
# ============================================================
class SchedulerFields:
    M_SPAWNED_ENEMIES_CNT = 0x1C       # uint32
    M_WAVES = 0x98                     # WaveData[]
    M_MANAGED_WAVE_ENEMIES = 0xB8      # List<Enemy> [实测: 全堆唯一引用点]
    M_MANAGED_FINAL_ENEMIES = 0xC0     # List<Enemy>
    M_CACHED_ENEMIES = 0xD8            # ListSet<Enemy>
    SCHEDULER_DRIVER = 0xF0            # SchedulerDriver* [实测 klass=SchedulerDriver]
    TOTAL_ENEMIES_CNT = 0x120          # int32


class SchedulerDriverFields:
    """SchedulerDriver (Lua 驱动桥) [实测]"""
    BATTLE_CONTROLLER = 0x10           # BattleController* [实测 klass=BattleController]
    SCHEDULER_WRAPPER = 0x18           # SchedulerWrapper*


# ============================================================
# 辅助函数
# ============================================================
def read_int32(mem: bytes, offset: int) -> int:
    return struct.unpack_from('<i', mem, offset)[0]


def read_uint32(mem: bytes, offset: int) -> int:
    return struct.unpack_from('<I', mem, offset)[0]


def read_int64(mem: bytes, offset: int) -> int:
    return struct.unpack_from('<q', mem, offset)[0]


def read_uint64(mem: bytes, offset: int) -> int:
    return struct.unpack_from('<Q', mem, offset)[0]


def read_float(mem: bytes, offset: int) -> float:
    return struct.unpack_from('<f', mem, offset)[0]


def read_ptr(mem: bytes, offset: int) -> int:
    return struct.unpack_from('<Q', mem, offset)[0]
