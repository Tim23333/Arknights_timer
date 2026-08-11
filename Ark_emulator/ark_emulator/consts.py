"""Global constants and enums (sourced from Ark_data/dump.cs + enemy docs)."""

# ---- timing ----
TIME_ROUGH_LOGIC_RATE = 30          # 1 second = 30 logic ticks (dump.cs:441464)
DT = 1.0 / TIME_ROUGH_LOGIC_RATE
UPDATE_POS_TICK = 5                 # enemy tile refresh every 5 ticks
SEARCH_TARGET_TICK = 3              # SelectorTrigger.SEARCH_TARGET_TICK
                                    # (dump.cs:437169): attack/skill target
                                    # selectors re-run at most once every 3
                                    # logic ticks (0.1s at 30Hz); prefab
                                    # _overrideSearchTargetTick / force bypass.
TILE_SEARCH_TARGET_TICK = 5         # TileTrigger.SEARCH_TARGET_TICK
                                    # (dump.cs:437439): tile selectors.
ROUTE_REACH_DISTANCE = 0.05         # dump.cs:366628

# ---- damage types ----
class DamageType:
    PHYSICAL = 0
    MAGICAL = 1
    TRUE = 2
    ELEMENT = 3

# minimum physical damage ratio (game-standard, verify vs BattleFormula)
PHYS_MIN_DAMAGE_RATIO = 0.05


def resolve_attack_range(radius):
    """Enemy attack range in grid units.

    Positive ``rangeRadius`` values >= 1.0 are used as-is; ``None`` /
    ``0`` / negative placeholders (-1.0 melee, -99 unset) and sub-1.0
    melee radii (0.3/0.4/0.5/0.6/0.8 are all melee entries, which must
    still reach an adjacent tile at distance 1.0) fall back to the
    standard melee reach of 1.5 tiles (adjacent, including diagonal).
    """
    try:
        r = float(radius)
    except (TypeError, ValueError):
        return 1.5
    return r if r >= 1.0 else 1.5


def translate_game_damage_type(v):
    """Game prefab DamageType (NONE=0 PHYSICAL=1 MAGICAL=2 PURE=3 HEAL=4
    ELEMENT=5, dump.cs:366766) -> emulator DamageType (PHYSICAL=0 MAGICAL=1
    TRUE=2 ELEMENT=3). Returns None when unmapped."""
    _m = {1: DamageType.PHYSICAL, 2: DamageType.MAGICAL,
          3: DamageType.TRUE, 5: DamageType.ELEMENT}
    try:
        return _m.get(int(v))
    except (TypeError, ValueError):
        return None


def translate_game_element_type(v):
    """Game ElementType (NONE=0 SANITY=1 WATER=2 FIRE=3 DARK=4 ANGER=5,
    dump.cs:366797) -> emulator EP type (0=neural 1=water 2=fire 3=dark)."""
    try:
        g = int(v)
    except (TypeError, ValueError):
        return 0
    return g - 1 if g > 0 else 0




# ---- force / mass (PRTS push/pull tables + BattleFormula.CalculatePush/PullForce) ----
# effective level = forceLevel - massLevel, clamped to [-3, 3]
# push row: (force N, initial speed m/s, projectile dist, effect dist)
#   - projectile: displacement = initial speed x 1s decelerating
#   - projectile vs effect rows differ by about one force level
PUSH_FORCE_TABLE = {
    -3: (0, 0.0, 0.0, 0.0),
    -2: (100, 1.0, 0.11825, 0.08492),
    -1: (200, 2.0, 0.4403, 0.37363),
    0: (400, 4.0, 1.6958, 1.56247),
    1: (450, 4.5, 2.13705, 1.98705),
    2: (530, 5.3, 2.95013, 2.77347),
    3: (580, 5.8, 3.52392, 3.33058),
}
# pull row: (force N, attract N, duration s, pull at d=2, pull at d=3)
#   - effective level >= 0 pulls all the way home (see below)
#   - decelerating pull: F_t = F0 * (x_t/x0)^4 with stop radius 0.6708
#   - duration: 0.5s when level < -1, otherwise 1s
PULL_FORCE_TABLE = {
    -3: (0, 0.0, 0.5, 0.0, 0.0),
    -2: (2, 2.0, 0.5, 0.0320, 0.0325),
    -1: (10, 10.0, 1.0, 0.5699, 0.9240),
    0: (40, 40.0, 1.0, None, None),
    1: (42, 42.0, 1.0, None, None),
    2: (44, 44.0, 1.0, None, None),
    3: (46, 46.0, 1.0, None, None),
}
PULL_STOP_RADIUS = 0.6708        # stop radius when pulled home
PULL_FRONT_OFFSET = 0.5          # pull target: 0.5 tiles in front
PUSH_ANGLE_CORRECTION = 45.0     # oblique angle -> radial correction
PUSH_DIST_CORRECTION = 0.25      # too close -> radial correction
PUSH_CORRECTED_LEVEL_DELTA = -2  # radial-correction effective-level delta


def force_level_from(force, mass_level):
    """effective level = force - massLevel (enemy mass, default 0)."""
    try:
        fl = int(round(float(force)))
    except (TypeError, ValueError):
        fl = 0
    try:
        m = int(mass_level)
    except (TypeError, ValueError):
        m = 0
    return fl - m


def clamp_force_level(level):
    return max(-3, min(3, int(level)))


def push_displacement(force, mass_level, kind="effect"):
    """Push distance by kind: 'projectile' (bullet) or 'effect'."""
    lvl = clamp_force_level(force_level_from(force, mass_level))
    row = PUSH_FORCE_TABLE[lvl]
    return row[2] if kind == "projectile" else row[3]


def push_initial_speed(force, mass_level):
    """Push initial speed in tiles/s for the effective level."""
    lvl = clamp_force_level(force_level_from(force, mass_level))
    return PUSH_FORCE_TABLE[lvl][1]


def push_duration(force, mass_level, kind="effect"):
    """Push duration: 2 * distance / initial speed (decelerating model).

    PRTS states push is a decelerating motion with initial speed v0;
    duration is derived as 2d/v0 for that model.
    """
    d = push_displacement(force, mass_level, kind)
    v0 = push_initial_speed(force, mass_level)
    if d <= 0 or v0 <= 0:
        return 0.0
    return 2.0 * d / v0


def pull_duration(force, mass_level):
    """Pull duration in seconds for the effective level."""
    lvl = clamp_force_level(force_level_from(force, mass_level))
    return PULL_FORCE_TABLE[lvl][2]


def pull_pulled_home(force, mass_level):
    """True when the effective level >= 0 (pull all the way home)."""
    return force_level_from(force, mass_level) >= 0


def pull_displacement(force, mass_level, dist_to_puller):
    """Pull displacement for negative effective levels.

    PRTS publishes pull amounts at d=2 and d=3; distances in between are
    linearly interpolated on [2, 3].
    """
    lvl = clamp_force_level(force_level_from(force, mass_level))
    row = PULL_FORCE_TABLE[lvl]
    d2, d3 = row[3], row[4]
    if d2 is None:
        return max(0.0, float(dist_to_puller))
    x = max(0.0, float(dist_to_puller))
    if x <= 2.0:
        return d2
    if x >= 3.0:
        return d3
    return d2 + (d3 - d2) * (x - 2.0)

# ---- ability finish reasons (dump.cs:367458) ----
class FinishReason:
    NORMAL_EXIT = 0
    INTERRUPTED = 1
    OWNER_DEAD = 2
    TARGET_DEAD = 3
    PALSY = 4

# ---- Enemy.States.State (dump.cs:441897) ----
class EnemyState:
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
    TERMINAL = -1

STATE_NAMES = {
    EnemyState.DEFAULT: "DEFAULT", EnemyState.MOVE: "MOVE",
    EnemyState.ATTACK: "ATTACK", EnemyState.COMBAT: "COMBAT",
    EnemyState.STUN: "STUN", EnemyState.DEAD: "DEAD", EnemyState.BORN: "BORN",
    EnemyState.REACH_EXIT: "REACH_EXIT", EnemyState.REBORN: "REBORN",
    EnemyState.UNBALANCE: "UNBALANCE", EnemyState.FALLDOWN: "FALLDOWN",
    EnemyState.DISAPPEAR: "DISAPPEAR", EnemyState.BLINK: "BLINK",
    EnemyState.FROZEN: "FROZEN", EnemyState.LEVITATE: "LEVITATE",
    EnemyState.DIALOG: "DIALOG", EnemyState.PALSY: "PALSY",
    EnemyState.TERMINAL: "TERMINAL",
}

# ---- AbnormalFlag (dump.cs:1442098) ----
class AbnormalFlag:
    STUNNED = 0
    SP_RECOVER_STOPPED = 1
    TARGET_FREE = 2
    BLOCK_FREE = 3
    HIDDEN = 4
    INVINCIBLE = 5
    UNDEADABLE = 6
    HEAL_FREE = 7
    UNBALANCE_IMMUNE = 8
    INVISIBLE = 9
    DISARMED = 11
    SILENCED = 12
    UNMOVABLE = 13
    FROZEN = 16
    CAMOUFLAGE = 17
    STUNNED_NO_AMPLIFY_DAMAGE = 19
    DISABLE_COMBAT = 20
    COLD = 23
    SKILL_NOT_ACTIVATABLE = 24
    LEVITATE = 25
    DURANCE = 26
    OUT_OF_GROUND = 28
    DISARMED_COMBAT = 31
    FEARED = 33
    SKILL_ACTIVABLE_IN_ABNORMAL = 34
    MOTION_TARGET_FREE = 35
    FORCE_LEVITATE = 36
    PALSY = 39
    PALSYING = 40
    ATTRACTED = 41
    DOZE = 43
    TELEPORTED = 44
    GROUND_BOUND = 45

# abnormal -> enemy state override (06 doc table)
ABNORMAL_STATE = {
    AbnormalFlag.STUNNED: EnemyState.STUN,
    AbnormalFlag.FROZEN: EnemyState.FROZEN,
    AbnormalFlag.LEVITATE: EnemyState.LEVITATE,
    AbnormalFlag.PALSY: EnemyState.PALSY,
}

# ---- MotionMode / MotionMask ----
class MotionMode:
    WALK = 0
    FLY = 1

class MotionMask:
    NONE = 0
    WALK_ONLY = 1
    FLY_ONLY = 2
    ALL = 3

# ---- BuildableType (dump.cs:1442162) ----
class BuildableType:
    MELEE = 1
    RANGED = 2

# ---- damage/element blackboard keys ----
BB = {
    "ATK": "atk", "DEF": "def", "ATK_SCALE": "atk_scale",
    "BLOCK_CNT": "block_cnt", "INTERVAL": "interval",
    "CONVEYOR_SPEED": "conveyor_speed", "MASS_LEVEL": "mass_level",
    "STUN": "stun", "DURATION": "duration", "MOVE_SPEED": "move_speed",
    "EP_DAMAGE_RATIO": "ep_damage_ratio", "EP_DAMAGE_RATIO_TRIGGER": "ep_damage_ratio[trigger]",
    "EP_DAMAGE_RATIO_DAMAGE": "ep_damage_ratio[damage]",
    "RANGE_RADIUS": "range_radius", "VIEW_RADIUS": "viewRadius",
    "MAX_CNT": "max_cnt", "SLUGGISH": "sluggish",
}
