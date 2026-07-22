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
    M_DIRECTION = 0xD4        # int32
    M_ATTRIBUTES = 0x98       # Attributes* [实测]
    ID = 0x130                # string <id> [实测]
    TMPL_ID = 0x138           # string <tmplId>
    FINISH_REASON = 0x140     # int32
    MAX_SP = 0x160            # int32
    MINUS_HP = 0x168          # FP


# ============================================================
# Enemy (敌方单位)  [dump.cs 偏移, 需 e2e 验证]
# ============================================================
class EnemyFields:
    M_CURRENT_TILE = 0x320      # Tile*
    M_BLOCK_POSITION = 0x3C0    # Vector2 (float x,y) 阻挡位置
    M_POS_IN_LAST_FRAME = 0x3D0 # Vector2 (float x,y) 上一帧地图坐标
    ROUTE_SPAWN_POS = 0x478     # GridPosition (int32 row,col) 出生格
    READ_SIZE = 0x480           # 稳态每敌读取跨度


# ============================================================
# Attributes (属性系统)  [已实测验证]
# ============================================================
class AttributesFields:
    M_RAW_DATA = 0x40         # ObscuredFP[] 原始属性
    M_CACHED_DATA = 0x50      # ObscuredFP[] 计算后属性 [实测]


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
    E_NUM = 36


# ============================================================
# BattleController  [运行时实测验证 2026-07-22]
# 注意: dump.cs 的标量偏移与现网版本有 ~0x10 漂移, 以下为实测值
# ============================================================
class BattleControllerFields:
    MAP = 0x28                # Map* [实测 klass=Map]
    FACTORY = 0x38            # BattleFactory* [实测 klass=BattleFactory]
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
