"""
明日方舟 IL2CPP 运行时结构偏移定义

基于 Ark_data/dump.cs (2.7.x 版本) 分析, 并已对 2026-07 在线版本
(Android arm64, versionName=2.7.51) 逐项实测验证:

  [实测验证 2026-07-21]
  - 5 个场上敌人 (enemy_1007_slime_2) 通过 klass 名 'Enemy' 确认
  - m_hp=0x40, <id>=0x130, m_attributes=0x98, m_cachedData=0x50
  - ObscuredFP 步长 0x28, XOR 解密后 Q32.32 定点数
  - List<Enemy>: _items=0x10 _size=0x18, 数组数据 +0x20, 长度 +0x18
  - Scheduler.m_managedWaveEnemies=0xC0（此前从引用点反推时误写为 0xB8）
  - BattleController.unitManager=0x2B8；UnitManager.enemies=0x20
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

import json
import os
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


def decrypt_obscured_float(key: int, hidden: int) -> float:
    """解密 ACTk v2 ``ObscuredFloat``。

    新版 ACTk 在异或前会交换密文的第 1、2 字节。客户端
    ``ObscuredFloat.Decrypt`` (RVA 0x6135D50) 会先执行同一交换再 XOR；
    不能直接把 ``hidden ^ key`` 当作 IEEE754。
    """
    packed = bytearray(struct.pack('<I', hidden & 0xFFFFFFFF))
    packed[1], packed[2] = packed[2], packed[1]
    bits = struct.unpack('<I', packed)[0] ^ (key & 0xFFFFFFFF)
    return struct.unpack('<f', struct.pack('<I', bits & 0xFFFFFFFF))[0]


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
    M_EP_CONTROLLER = 0x100   # Entity.EPController*
    M_SHIELD_CONTROLLER = 0x108  # Entity.ShieldUIController*
    M_DIRECTION = 0xEC        # int32
    M_ATTRIBUTES = 0xB0       # Attributes* [2026-08 新版实测]
    ID = 0x148                # string <id> [2026-08 新版实测]
    TMPL_ID = 0x150           # string <tmplId>
    FINISH_REASON = 0x158     # int32
    BUFF_CONTAINER = 0x168    # Buff.BuffContainer*
    MAX_SP = 0x178            # int32
    MINUS_HP = 0x180          # FP


# ============================================================
# Unit / Character（友方干员与召唤物）[2026-08-03 现网实测]
# ============================================================
class UnitFields:
    ANIMATOR = 0x198              # UnitAnimator*
    CURRENT_MODE = 0x200          # UnitMode*
    OVERRIDE_ATTACK = 0x208       # Ability*
    OVERRIDE_COMBAT = 0x218       # Ability*
    TALENTS = 0x270               # BasicTalent[]
    DYNAMIC_ABILITIES = 0x278     # List<Ability>
    SP_SHOWN_BUFF = 0x280         # Buff*
    ATTACK_RANGE_TILES = 0x2A0    # List<Tile>


class UnitModeFields:
    """UnitMode 中决定普通攻击/战斗动作的能力指针。"""
    COMBAT = 0x38                 # Ability*
    ATTACK = 0x40                 # Ability*
    ATTACK_TRIGGER = 0x48         # TargetTrigger*，普通攻击 SearchTarget 使用
    READ_SIZE = 0x50


class UnitAnimatorFields:
    """两类常用 UnitAnimator 的 CurrentAniState 内联字段。"""
    SPINE_CURRENT_STATE = 0xD8   # SpineAnimator.CurrentAniState
    MESH_CURRENT_STATE = 0x180   # MeshAnimator.CurrentAniState
    CURRENT_STATE_SIZE = 0x10    # string* animKey + float playSpeed


class CharacterAnimatorFields:
    ACTIVE_FACE = 0x148          # CharacterAnimator.FaceConfiguration*


class SingleSpineAnimatorFields:
    SKELETON = 0xF0             # Spine.Unity.SkeletonAnimation*


class MultiSpineAnimatorFields:
    FACES = 0xF0                # List<SubSpineConfig>*
    ACTIVE_SPINE_INDEX = 0x100  # int32


class SpineFaceFields:
    SKELETON = 0x10             # FaceConfiguration/SubSpineConfig.skeleton


class SkeletonAnimationFields:
    STATE = 0x100               # Spine.AnimationState*
    LOOP = 0x138                # bool
    TIME_SCALE = 0x13C          # float


class SpineAnimationStateFields:
    TRACKS = 0x18               # Spine.ExposedList<TrackEntry>*
    TIME_SCALE = 0x6C           # float


class SpineExposedListFields:
    ITEMS = 0x10                # T[]
    COUNT = 0x18                # int32


class SpineTrackEntryFields:
    ANIMATION = 0x10            # Spine.Animation*
    NEXT = 0x18                 # 已排队的下一轨道项
    LOOP = 0x64                 # bool
    ANIMATION_START = 0x74      # float
    ANIMATION_END = 0x78        # float
    TRACK_TIME = 0x88           # float
    TRACK_END = 0x94            # float；通常为 float.MaxValue，不能当动画终点
    TIME_SCALE = 0x98           # float
    READ_SIZE = 0xB0


class SpineAnimationFields:
    NAME = 0x10                 # string*
    DURATION = 0x28             # float
    READ_SIZE = 0x30


class CharacterFields:
    CREATED_TIME = 0x390          # FP
    DEAD_TIME = 0x398             # FP
    ROOT_TILE = 0x3A8             # Tile*
    BLOCKED_ENEMY_MANAGER = 0x3B0 # Character.BlockedEnemyManager*
    BLOCK_RADIUS_MANAGER = 0x3B8  # Character.BlockRadiusManager*
    SKILL = 0x3D8                 # BasicSkill*
    SKILL_DATA = 0x3E0            # SkillData*
    MAX_ES_RATIO = 0x440          # FP
    # 旧 dump.cs 中此槽是 currentSkin；2026-08-04 现网为 CharacterAnimator*。
    # Unit.ANIMATOR 对我方实例为 NULL，因此动作轨道必须从此槽兜底。
    RUNTIME_ANIMATOR = 0x458      # CharacterAnimator* [现网实测]
    CURRENT_SKIN = 0x458          # 兼容旧名称，勿用于当前现网类型判断
    DECK_BUFF_DATA = 0x460        # object*
    DECK_BUFF_BLACKBOARD = 0x468  # Blackboard*
    DEPLOY_COST_THIS_TIME = 0x504 # int32
    CARD_UID = 0x520              # uint32
    DATA = 0x530                  # BattleCharacterData*
    READ_SIZE = 0x548


class BlockedEnemyManagerFields:
    TOTAL_VOLUME = 0x10           # int32
    BLOCKED_ENEMIES = 0x18        # List<Enemy>*


class TileFields:
    GRAPHIC = 0x30                # TileGraphic*
    DATA = 0x70                   # TileData*


class TileGraphicFields:
    GRID_ROW = 0x20               # GridPosition.row
    GRID_COL = 0x24               # GridPosition.col


class BattleCharacterDataFields:
    ID = 0x10
    ALIAS = 0x18
    TMPL_ID = 0x20
    NAME_CN = 0x28
    NAME_EN = 0x30
    ATTRIBUTES = 0x38
    LEVEL = 0x40
    EVOLVE_PHASE = 0x44
    POTENTIAL_RANK = 0x48
    FAVOR_BATTLE_PHASE = 0x4C
    PREFAB_KEY = 0x50
    RANGE_ID = 0x58
    UNIQUE_ID = 0x6C
    PROFESSION = 0x70
    SUB_PROFESSION_DATA = 0x78
    RARITY = 0x80
    DEPLOY_POSITION = 0x84
    TEAM_KEY = 0x88
    IS_TOKEN = 0x90
    IS_PREDEFINED = 0x91
    IS_HIDDEN = 0x92
    IS_ASSIST = 0x93
    TOKEN_OR_HOST_KEY = 0x98
    TOKEN_OR_HOST_UID = 0xA0
    TOKEN_INITIAL_COUNT = 0xA4
    MAIN_SKILL_INDEX = 0x100
    MAIN_SKILL = 0x108
    TALENTS = 0x110
    TRAIT = 0x118
    UNI_EQUIP_QUERIES = 0x120
    UNI_EQUIPS = 0x128
    UNI_EQUIP_SETTINGS = 0x130
    NATION_ID = 0x138
    GROUP_ID = 0x140
    TEAM_ID = 0x148
    SUB_POWER = 0x150
    SHARED = 0x158
    RUNTIME_DATA = 0x178
    READ_SIZE = 0x180


class BattleLoggerFields:
    LOGS = 0x20
    SQUAD = 0x28
    STATS = 0x30
    READ_SIZE = 0x40


class BattleStatsFields:
    CHAR_ADVANCED_STATS = 0x30
    TOTAL_HEAL = 0xB8
    TOTAL_DAMAGE = 0xBC
    READ_SIZE = 0xC0


class CharAdvancedStatsFields:
    OUTPUT_DAMAGE_RANGE = 0x10       # Vector2，伤害以负 HP 变化记录
    INPUT_DAMAGE_RANGE = 0x18
    OUTPUT_DAMAGE_TOTAL = 0x20       # float，伤害通常为负数
    OUTPUT_ELEMENT_DAMAGE_TOTAL = 0x28  # List<float>，不含 NONE，共 5 项
    OUTPUT_EP_BREAK_COUNT = 0x30        # List<int>，不含 NONE，共 5 项
    OUTPUT_DAMAGE_BY_TYPE_TOTAL = 0x38  # List<float>，DamageType 0..5
    SNAPSHOTS = 0x40
    READ_SIZE = 0x48


class DamageType:
    NONE = 0
    PHYSICAL = 1
    MAGICAL = 2
    PURE = 3
    HEAL = 4
    ELEMENT = 5
    E_NUM = 6


DAMAGE_TYPE_NAMES = {
    DamageType.NONE: '无', DamageType.PHYSICAL: '物理伤害',
    DamageType.MAGICAL: '法术伤害', DamageType.PURE: '真实伤害',
    DamageType.HEAL: '治疗量', DamageType.ELEMENT: '元素伤害',
}


class BasicSkillFields:
    TRIGGER_COUNT = 0x90
    RANGE_ID_MODE_INDEX = 0x94
    WAIT_FOR_SKILL_END = 0x98
    IS_EARLY_FINISHED = 0x99
    IS_OVERLOADED = 0x9A
    COST_MIN_SP = 0x9C
    OWNER = 0xA8
    DATA = 0xB0
    ATTACK_BLACKBOARD = 0xB8
    ABILITY = 0xC0
    MAX_TRIGGER_TIME = 0xCC
    BEHAVIOURS = 0xD8
    CHANT_BEHAVIOUR = 0xE0
    CACHED_OPERATION_SIDE = 0x110
    BLACKBOARD = 0x118
    READ_SIZE = 0x120


class SkillDataFields:
    NAME = 0x10
    SKILL_ID = 0x18
    RANGE_ID = 0x20
    ICON_ID = 0x28
    LEVEL = 0x30
    DESCRIPTION = 0x38
    SKILL_TYPE = 0x40
    DURATION_TYPE = 0x44
    SP_DATA = 0x48
    PREFAB_KEY = 0x50
    DURATION = 0x58
    BLACKBOARD = 0x60
    READ_SIZE = 0x70


class SpDataFields:
    SP_TYPE = 0x10
    MAX_CHARGE_TIME = 0x20       # ObscuredInt
    SP_COST = 0x34               # ObscuredInt
    INIT_SP = 0x48               # ObscuredInt
    INCREMENT = 0x5C             # ObscuredFloat
    INCREMENTS = 0x78
    READ_SIZE = 0x80


class AbilityFields:
    OWNER = 0x48
    IS_CASTING = 0x58
    CAST_START_FRAME = 0x5C
    COOLDOWN_TIMER = 0x68
    PASSIVE_BUFF_UIDS = 0x70
    UNIQUE_ID = 0x78
    BLACKBOARD = 0x80
    IS_ATTACHED = 0x88
    DAMAGE_MISS_FLAG = 0xB0
    FINISH_REASON = 0xB4
    READ_SIZE = 0xC0


class StateNodeFields:
    """Character 的 Attack/Combat/Skill 状态节点公共计时槽。"""
    ACTION_TIME = 0x18            # Attack/Combat=绝对截止时间；Skill=剩余后摇
    READ_SIZE = 0x20


class BasicTalentFields:
    OVERWRITE_TALENT_KEY = 0x18
    OWNER = 0x30
    ABILITY = 0x38
    PARENT_MODE = 0x40
    DATA = 0x48
    READ_SIZE = 0x50


class TalentDataFields:
    REQUIRED_POTENTIAL_RANK = 0x18
    PREFAB_KEY = 0x20
    NAME = 0x28
    DESCRIPTION = 0x30
    RANGE_ID = 0x38
    BLACKBOARD = 0x40
    TOKEN_KEY = 0x48
    IS_HIDDEN = 0x50
    READ_SIZE = 0x58


class CharacterState:
    TERMINAL = -1
    DEFAULT = 0
    IDLE = 1
    ATTACK = 2
    COMBAT = 3
    SKILL = 4
    STUN = 5
    DEAD = 6
    BORN = 7
    DISAPPEAR = 8
    FROZEN = 9
    REBORN = 10
    DYING = 11
    DIALOG = 12
    DOZE = 13
    NAMES = {
        -1: '结束', 0: '默认', 1: '待机', 2: '攻击', 3: '战斗', 4: '技能中',
        5: '眩晕', 6: '阵亡', 7: '入场', 8: '消失', 9: '冻结',
        10: '重生', 11: '濒死', 12: '对话', 13: '昏睡',
    }


PROFESSION_CATEGORY_NAMES = {
    1: '近卫', 2: '狙击', 4: '重装', 8: '医疗', 16: '辅助',
    32: '术师', 64: '特种', 128: '召唤物', 256: '装置', 512: '先锋',
}
BUILDABLE_TYPE_NAMES = {0: '不可部署', 1: '近战位', 2: '远程位', 3: '任意位置'}
SKILL_TYPE_NAMES = {0: '被动', 1: '手动触发', 2: '自动触发'}
SKILL_DURATION_TYPE_NAMES = {0: '普通', 1: '弹药'}
SP_TYPE_NAMES = {
    0: '无', 1: '自动回复', 2: '攻击回复', 4: '受击回复',
    6: '攻击或受击回复', 7: '全部方式',
}


# ============================================================
# Enemy (敌方单位)
# ============================================================
class EnemyFields:
    M_CURRENT_TILE = 0x350      # Tile*
    M_CURSOR = 0x360            # DirectionCursor*
    M_BLOCKER = 0x390           # ObjectPtr<Character>（首槽为对象指针）
    M_BLOCK_POSITION = 0x3F8    # Vector2 (float x,y) 阻挡位置
    M_POS_IN_LAST_FRAME = 0x408 # Vector2 (float x,y) 上一帧地图坐标
    M_ALL_SKILLS = 0x448        # EnemySkill[] 全部技能组件
    ROUTE_SPAWN_POS = 0x4B0     # GridPosition (int32 row,col) 出生格
    ATTACK_ABILITY_CASTED = 0x4E8  # Ability* 当前普通攻击能力
    COMBAT_ABILITY_CASTED = 0x4F0  # Ability* 当前战斗/技能能力
    COMBAT_NEXT_ESCAPE_TIME = 0x4F8 # FP 战斗动作可退出的绝对时间
    M_SKILLS = 0x4D0            # List<EnemySkill> 激活技能列表
    DATA = 0x510                # LevelData.EnemyData*
    OPTIONS = 0x518             # inline Enemy.Options
    ATTACK_WRAPPER = 0x550      # Enemy.AttackWrapper*
    COMBAT_WRAPPER = 0x558      # Enemy.CombatWrapper*
    READ_SIZE = 0x568           # 含两个动作 Wrapper 与动作计时字段


class EnemyOptionsFields:
    IS_SUMMON = 0x08            # bool（相对 Enemy.Options）
    HIDDEN_GROUP_KEY = 0x10     # string
    ACTION_DATA = 0x20          # LevelData.ActionData*


# ============================================================
# EnemySkill (敌方技能)  [已实测验证 2026-07-23]
# 注意: EnemySkill 是 MonoBehaviour, 字段含 0x10 对象头 + 0x8 m_CachedPtr
# ============================================================
class EnemySkillFields:
    FAMILY_MASK = 0x18          # Ability.FamilyGroupMask
    TRIGGER = 0x20              # TargetTrigger* (NULL=无目标触发器, 就绪即放)
    CHECK_PARENT_ACTIVE = 0x28  # bool，要求所属 UnitMode 当前激活
    CAST_LIKE_ATTACK = 0x3B     # bool，以普通攻击流程施放
    MAX_TRIGGER_TIME = 0x2C     # int32 最多触发次数
    OVERWRITE_INIT_CD = 0x34    # int32 初始冷却覆盖
    IGNORE_SILENCE = 0x38       # bool，沉默时仍可使用
    M_SP_COST = 0x3C            # int32
    M_TRIGGER_CNT = 0x40        # int32 已触发次数
    M_COOLDOWN_TIMER = 0x48     # PeriodicTimer* 冷却计时器
    M_MAIN_ABILITY = 0x58       # Ability*
    ABILITY = 0x70              # Ability* 当前运行时能力
    PARENT_MODE = 0x78          # UnitMode*
    DATA = 0x80                 # ESkillData* 静态配置
    OWNER = 0x88                # Enemy*
    READ_SIZE = 0x90


class TargetTriggerFields:
    """TargetTrigger 及常见派生类的运行时判定字段。"""
    ABILITY = 0x18              # Ability* backing field
    READ_SIZE = 0x78


class SelectorTriggerFields:
    KEEP_TARGET = 0x20          # bool
    MIN_TARGET_NUM = 0x24       # int32
    OVERRIDE_SEARCH_TICK = 0x28 # int32
    SELECTOR = 0x30             # TargetSelector*
    LAST_TARGET = 0x38          # ObjectPtr<Entity> 首槽


class SpTriggerFields:
    VALUE_TYPE = 0x20           # 0=Value, 1=ChargeLayer
    VALUE_TO_COMPARE = 0x24     # float
    COMPARE_TYPE = 0x28         # CompareType
    OWNER = 0x30                # Entity*


class AbilityFamilyMask:
    """Ability.FamilyGroupMask；EnemySkill 只能参加对应动作流程。"""
    NONE = 0
    ATTACK = 1
    COMBAT = 2
    SKILL = 4
    TALENT = 8
    GENERAL = 16
    ATTACK_OR_COMBAT = ATTACK | COMBAT


class EnemyAttackWrapperFields:
    CURRENT_TARGET = 0x18       # Entity*
    CURRENT_SKILL = 0x20        # EnemySkill*
    CURRENT_ABILITY = 0x28      # Ability*
    LAST_ABILITY = 0x30         # Ability*
    LAST_SKILL = 0x38           # EnemySkill*
    READ_SIZE = 0x40


class EnemyCombatWrapperFields:
    PICKED_ABILITY = 0x18       # Ability*
    PICKED_SKILL = 0x20         # EnemySkill*
    ABILITY_PICKED = 0x28       # bool
    INTERRUPTED = 0x29          # bool
    LAST_ABILITY = 0x30         # Ability*
    LAST_SKILL = 0x38           # EnemySkill*
    READ_SIZE = 0x40


class PeriodicTimerFields:
    M_PERIOD_TIME = 0x10        # FP 周期 (技能总 CD, 秒)
    M_REMAINING_TIME = 0x18     # FP 剩余 (当前 CD 剩余, 秒)


class ESkillDataFields:
    PREFAB_KEY = 0x10           # string 技能 ID
    PRIORITY = 0x18             # int32
    COOLDOWN = 0x1C             # float 配置 CD
    INIT_COOLDOWN = 0x20        # float 初始 CD (出场后首次)
    SP_COST = 0x24              # int32


class LevelEnemyDataFields:
    """LevelData.EnemyData；运行时可提供新敌人的本地化名称。"""
    NAME = 0x10                 # string
    DESCRIPTION = 0x18          # string
    KEY = 0x20                  # string enemy_xxx
    ATTRIBUTES = 0x28           # AttributesData


class StaticAttributesDataFields:
    """关卡 ``AttributesData`` 中用于未出场估时的静态字段。"""
    MOVE_SPEED = 0x8C           # ObscuredFloat (0x18 bytes)


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
    CURRENT_STATE = 0x50        # 当前 StateNode*
    READ_SIZE = 0x58


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
    E_NUM = 46


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
    (45, 'GROUND_BOUND', '地面束缚'),
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
    IS_FINISHED = 0x1EA
    IS_ACTUALLY_ENABLED = 0x1ED
    IS_VALID = 0x1F0
    IS_EP_BREAK_BUFF = 0x1F1
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
    ATTRIBUTES = 0x10
    BUFF_KEY = 0x18
    LOAD_FROM_DB = 0x20
    IS_DURABLE = 0x21
    IS_DAMAGE_MISSABLE = 0x22
    IS_SILENCEABLE = 0x23
    IS_STUNNABLE = 0x24
    IS_FREEZABLE = 0x25
    IS_LEVITATABLE = 0x26
    IS_GROUND_BOUNDABLE = 0x27
    STATUS_RESISTABLE = 0x28
    TEMPLATE_KEY = 0x30
    DISABLE_OVERRIDE = 0x38
    OVERRIDE_KEY = 0x40
    OVERRIDE_TYPE = 0x48
    MAX_STACK_COUNT = 0x4C
    MAX_VALID_STACK_COUNT = 0x54
    INDEPENDENT_CHARACTER_SOURCE = 0x58
    OVERRIDE_EFFECT_KEY = 0x60
    AUDIO_SIGNAL = 0x70
    LIFE_TIME_TYPE = 0x78
    DURATION_KEY = 0x80
    LIFE_TIME = 0x88
    TRIGGER_LIFE_TYPE = 0x8C
    TRIGGER_COUNT = 0x90
    TRIGGER_INTERVAL = 0x94
    PRIORITY = 0xA0
    BLACKBOARD = 0xB8
    READ_SIZE = 0xC8


# ============================================================
# BattleController  [运行时实测验证 2026-07-22]
# 注意: dump.cs 的标量偏移与现网版本有 ~0x10 漂移, 以下为实测值
# ============================================================
class BattleControllerFields:
    UNITY_CACHED_PTR = 0x10   # UnityEngine.Object.m_CachedPtr；销毁后清零
    MAP = 0x28                # Map* [实测 klass=Map]
    SCHEDULER = 0x30          # Scheduler* [2026-07-30 现网实测 klass=Scheduler]
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
    UNIT_MANAGER = 0x2B8      # UnitManager*；其 enemies 含非 Scheduler 管理的召唤敌人
    # 注意: 标量字段相对 dump.cs 有漂移；Scheduler/LevelData 等引用字段现网仍匹配。


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
# Scheduler / LevelData 出怪序列 [2026-07-30 现网实测]
# BattleController+0x30 直接持有真实 Scheduler 对象；此前从
# m_managedWaveEnemies 反推时误减了 0xB8（实际字段为 0xC0），得到的是
# Scheduler+8 的伪基址，后续所有偏移才被迫整体少写 8。这里统一恢复真实基址。
# ============================================================
class SchedulerFields:
    M_SPAWNED_ENEMIES_CNT = 0x24       # uint32
    M_WAVE_START_TIME = 0x90            # FP，当前波次绝对开始时间
    M_FRAGMENT_START_TIME = 0x98        # FP，当前片段绝对开始时间
    M_WAVES = 0xA0                     # WaveData[]（与 LevelData.waves 同一数组）
    M_ENEMY_MAP = 0xA8                 # Dictionary<string, Scheduler.EnemyItem>
    M_ACTION_QUEUE = 0xB8              # List<Scheduler.ActionItem> 当前待执行行动
    M_MANAGED_WAVE_ENEMIES = 0xC0      # List<Enemy> [实测]
    M_MANAGED_FINAL_ENEMIES = 0xC8     # List<Enemy>
    M_CACHED_ENEMIES = 0xE0            # ListSet<Enemy>
    SCHEDULER_DRIVER = 0x138           # SchedulerDriver* [实测 klass=SchedulerDriver]
    TOTAL_ENEMIES_CNT = 0x128          # int32


class BattleControllerStaticFields:
    """BattleController Il2CppClass.static_fields 内的战斗逻辑时钟。"""
    FIXED_FRAME_COUNT = 0x14            # uint32
    FIXED_PLAY_TIME = 0x18              # FP；Scheduler 各 startTime 使用同一时基
    FIXED_PLAY_TIME_FLOAT = 0x28        # float，与 FIXED_PLAY_TIME 同步
    DELTA_PLAY_TIME_FP = 0x48           # FP；当前每逻辑帧推进的战斗时间


class Il2CppClassFields:
    STATIC_FIELDS = 0xB8


class UnitManagerFields:
    ALL_UNITS = 0x10
    CHARACTERS = 0x18
    ENEMIES = 0x20                    # UnorderedArray<Unit>*
    NEUTRAL_UNITS = 0x28


class UnorderedArrayFields:
    """Torappu.UnorderedArray<T>（现网 UnitManager.enemies 实测）。"""
    ITEMS = 0x10                      # T[]
    ITEM_MAP = 0x18                   # Dictionary<T, int>
    COUNT = 0x20                      # int32；仅前 count 个数组槽有效


class SchedulerDriverFields:
    """SchedulerDriver (Lua 驱动桥) [实测]"""
    BATTLE_CONTROLLER = 0x10           # BattleController* [实测 klass=BattleController]
    SCHEDULER_WRAPPER = 0x18           # SchedulerWrapper*


class LevelDataFields:
    MAP_ID = 0x20                      # string
    MAP_DATA = 0x38                    # MapData*
    LEVEL_ID = 0x18                    # string
    ROUTES = 0x60                      # RouteData[]
    EXTRA_ROUTES = 0x68                # RouteData[]
    ENEMIES = 0x70                     # EnemyData[]（含本关本地化名称与属性）
    ENEMY_DB_REFS = 0x78               # EnemyDataDbReference[]
    WAVES = 0x80                       # WaveData[]
    BRANCHES = 0x88                    # ListDict<string, BranchData>
    PREDEFINES = 0x90                  # PredefinedData*
    HARD_PREDEFINES = 0x98             # PredefinedData*


class MapDataFields:
    MAP = 0x10                         # short[,]，值为 tiles 下标
    TILES = 0x18                       # TileData[]
    BLOCK_EDGES = 0x20                 # MapData.Edge[]
    TAGS = 0x28                        # string[]
    EFFECTS = 0x30                     # MapEffectData[]
    LAYER_RECTS = 0x38                 # string[]


class TileDataFields:
    TILE_KEY = 0x10                    # string
    HEIGHT_TYPE = 0x18                 # 0=低台, 1=高台
    BUILDABLE_TYPE = 0x1C
    PASSABLE_MASK = 0x20
    PLAYER_SIDE_MASK = 0x24
    ADVANCED_BUILDABLE_MASK = 0x28
    BLACKBOARD = 0x30
    EFFECTS = 0x38
    READ_SIZE = 0x40


class MapEdgeFields:
    POSITION = 0x10                   # GridPosition(row, col)
    DIRECTION = 0x18
    BLOCK_MASK = 0x1C
    READ_SIZE = 0x20


class PredefinedDataFields:
    CHARACTER_INSTS = 0x10
    TOKEN_INSTS = 0x18
    CHARACTER_CARDS = 0x20
    TOKEN_CARDS = 0x28


class PredefinedCharacterFields:
    CHARACTER_KEY = 0x10              # CharacterInst.Metadata.characterKey
    HIDDEN = 0x70
    ALIAS = 0x78
    POSITION = 0x80                   # GridPosition(row, col)
    DIRECTION = 0x88
    READ_SIZE = 0x90


class RouteDataFields:
    MOTION_MODE = 0x10
    START_POSITION = 0x14              # GridPosition(row, col)
    END_POSITION = 0x1C
    SPAWN_RANDOM_RANGE = 0x24          # Vector2
    SPAWN_OFFSET = 0x2C                # Vector2
    CHECKPOINTS = 0x38                 # CheckpointData[]
    ALLOW_DIAGONAL_MOVE = 0x40
    READ_SIZE = 0x48


class RouteCheckpointFields:
    TYPE = 0x10
    TIME = 0x14
    POSITION = 0x18                    # GridPosition(row, col)
    REACH_OFFSET = 0x20                # Vector2
    RANDOMIZE_REACH_OFFSET = 0x28
    REACH_DISTANCE = 0x2C
    READ_SIZE = 0x30


class RouteCheckpointType:
    MOVE = 0
    WAIT_FOR_SECONDS = 1
    WAIT_FOR_PLAY_TIME = 2
    WAIT_CURRENT_FRAGMENT_TIME = 3
    WAIT_CURRENT_WAVE_TIME = 4
    DISAPPEAR = 5
    APPEAR_AT_POS = 6
    ALERT = 7
    PATROL_MOVE = 8
    WAIT_BOSSRUSH_WAVE = 9
    MAP_OFFSET_MOVE = 10
    INVALID = 11


class WaveDataFields:
    PRE_DELAY = 0x10                   # float
    POST_DELAY = 0x14                  # float
    MAX_WAIT_NEXT = 0x18               # float
    FRAGMENTS = 0x20                   # FragmentData[]


class FragmentDataFields:
    PRE_DELAY = 0x10                   # float
    ACTIONS = 0x18                     # ActionData[]


class BranchDataFields:
    PHASES = 0x10                      # PhaseData[]


class BranchPhaseDataFields:
    PRE_DELAY = 0x10                   # float
    ACTIONS = 0x18                     # ActionData[]


class SpawnActionFields:
    ACTION_TYPE = 0x10                 # int32; SPAWN=0
    MANAGED_BY_SCHEDULER = 0x14        # bool
    KEY = 0x18                         # string enemy key
    COUNT = 0x20                       # int32
    PRE_DELAY = 0x24                   # float
    INTERVAL = 0x28                    # float
    ROUTE_INDEX = 0x30                 # int32
    HIDDEN_GROUP = 0x38                # string
    RANDOM_SPAWN_GROUP = 0x40          # string
    RANDOM_SPAWN_PACK = 0x48           # string
    RANDOM_TYPE = 0x50                 # int32
    REFRESH_TYPE = 0x54                # int32
    WEIGHT = 0x58                      # int32
    DONT_BLOCK_WAVE = 0x5C             # bool
    FORCE_BLOCK_WAVE_IN_BRANCH = 0x5D  # bool
    IS_VALID = 0x5E                    # bool（预处理/随机选择后的结果）
    NOT_COUNT_IN_TOTAL = 0x5F          # bool
    EXTRA_META = 0x60                  # object
    ACTION_ID = 0x68                   # LevelData.ActionID（4×int32）
    READ_SIZE = 0x78


class SchedulerActionItemFields:
    """Scheduler.ActionItem 是内联值类型，存放在 List<ActionItem> 数组中。"""
    DATA = 0x00                         # ActionData*
    TIME_OFFSET = 0x08                  # float，距当前片段起点的执行偏移
    SIZE = 0x10


class SpawnActionType:
    SPAWN = 0


# ============================================================
# 自动生成偏移覆盖
# ============================================================
GENERATED_OFFSET_INFO = {}


def apply_generated_offsets(path=None):
    """加载 update_from_unpack.py 从新版 dump.cs 生成的偏移。

    源码中的数值是最近一次验证通过的安全默认值；生成文件只允许覆盖本模块中
    已声明的字段，避免损坏文件或新字段名称误改任意模块状态。
    """
    global GENERATED_OFFSET_INFO
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'generated_offsets.json')
    if not os.path.isfile(path):
        return False
    try:
        with open(path, 'r', encoding='utf-8') as stream:
            payload = json.load(stream)
        classes = payload.get('classes', {})
        for class_name, values in classes.items():
            target = globals().get(class_name)
            if not isinstance(target, type) or not isinstance(values, dict):
                continue
            for field_name, value in values.items():
                if not hasattr(target, field_name):
                    continue
                if isinstance(value, str):
                    value = int(value, 0)
                if isinstance(value, int) and 0 <= value <= 0x10000:
                    if field_name == 'READ_SIZE':
                        # 自动脚本只认识它提取到的最后一个字段；手工验证过的扩展字段
                        # 可能位于其后。读取块可以更大但绝不能被生成值截短。
                        value = max(int(getattr(target, field_name)), value)
                    setattr(target, field_name, value)
        enums = payload.get('enums', {})
        for enum_name, values in enums.items():
            target = globals().get(enum_name)
            if not isinstance(target, type) or not isinstance(values, dict):
                continue
            count = values.get('E_NUM')
            if isinstance(count, int) and 0 < count <= 256 and hasattr(target, 'E_NUM'):
                target.E_NUM = count
        GENERATED_OFFSET_INFO = {
            'source': payload.get('source', ''),
            'source_sha256': payload.get('source_sha256', ''),
            'generated_at': payload.get('generated_at', ''),
        }
        return True
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


apply_generated_offsets()


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
