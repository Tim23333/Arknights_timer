"""Projectile system (enemy/operator ranged attacks).

Game model (dump.cs Projectile + BasicMovement):
  - Ability with ``_projectileKey`` spawns a Projectile at the OnAttack event
    frame of its animation;
  - the projectile flies at ``projectile_speed`` (grids/second) toward the
    target (trace target or fixed destination);
  - on arrival (reached) the hit effects/damage are applied.

Speeds are extracted from the game's ``[uc]projectiles.ab`` (10832
components); the default table covers the common speeds (10/15/8/5 ...).
Verified: Faust (projectile_faust_s1) = 10.0 grids/s.
"""

from .consts import DamageType
from .damage import calculate_damage

# projectileKey -> speed (grids/s). Extracted from game assets; common speeds
# observed: 10 (most common), 15, 8, 5, 30, 20, 12, 6, 7, 9, 3, 4, 18.
DEFAULT_SPEED = 10.0

import io as _io
import json as _json
import os as _os

_SPEED_TABLE = None


def _load_speed_table():
    global _SPEED_TABLE
    if _SPEED_TABLE is None:
        _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                           "data_projectile_speeds.json")
        try:
            with _io.open(_p, encoding="utf-8") as f:
                _SPEED_TABLE = _json.load(f)
        except Exception:
            _SPEED_TABLE = {}
    return _SPEED_TABLE


class Projectile:
    """In-flight ranged attack. Damage lands when it reaches the target."""

    def __init__(self, source, target, speed, damage_type=DamageType.PHYSICAL,
                 atk_scale=1.0, start_x=None, start_y=None, key=None,
                 hit_callback=None, delay_ticks=0,
                 penetrate_ratio=0.0, penetrate_fixed=0.0):
        self.source = source
        self.target = target
        self.speed = speed if speed and speed > 0 else DEFAULT_SPEED
        self.damage_type = damage_type
        self.atk_scale = atk_scale
        self.penetrate_ratio = float(penetrate_ratio or 0.0)
        self.penetrate_fixed = float(penetrate_fixed or 0.0)
        self.key = key
        self.hit_callback = hit_callback
        self.start_x = start_x if start_x is not None else source.pos_x
        self.start_y = start_y if start_y is not None else source.pos_y
        self.pos_x = self.start_x
        self.pos_y = self.start_y
        self.travel_t = 0.0
        # cast-animation windup before the projectile actually launches
        # (Ability._preDelay seconds at 30 ticks/s, e.g. Texas S2 0.5s)
        self.delay_ticks = int(delay_ticks or 0)
        self.dead = False
        self.hit = False

    @property
    def distance(self):
        dx = self.target.pos_x - self.start_x
        dy = self.target.pos_y - self.start_y
        return (dx * dx + dy * dy) ** 0.5

    @property
    def flight_frames(self):
        """Logic frames to reach target (30 ticks/s)."""
        return int(round(self.distance / self.speed * 30.0))

    def update(self, dt):
        """Advance one tick; returns True when the projectile hits."""
        if self.dead:
            return False
        # still in cast windup: hold at the source, no movement
        if self.delay_ticks > 0:
            self.delay_ticks -= 1
            return False
        self.travel_t += dt
        if self.target is None or getattr(self.target, "dead", False):
            self.dead = True
            return False
        dx = self.target.pos_x - self.pos_x
        dy = self.target.pos_y - self.pos_y
        dist = (dx * dx + dy * dy) ** 0.5
        step = self.speed * dt
        if dist <= step:
            self.pos_x = self.target.pos_x
            self.pos_y = self.target.pos_y
            self.hit = True
            self.dead = True
            return True
        self.pos_x += dx / dist * step
        self.pos_y += dy / dist * step
        return False

    def on_hit(self, battle):
        """Apply the attack's damage/effects on arrival."""
        if self.hit_callback is not None:
            self.hit_callback(battle, self)
            return
        # pass the RAW atk*scale; battle.apply_damage applies the source
        # penetration + target mitigation exactly once (calling
        # calculate_damage here and then apply_damage double-applied it)
        atk = self.source.attributes.get("atk")
        amount = float(atk or 0.0) * float(self.atk_scale or 1.0)
        battle.apply_damage(self.target, amount, self.damage_type,
                            source=self.source)
        battle.emit(battle.tick, "attack",
                    {"unit": self.source.inst_id,
                     "target": self.target.inst_id,
                     "projectile": self.key,
                     "type": "projectile_hit"})

    def to_dict(self):
        return {
            "key": self.key,
            "source": self.source.inst_id,
            "target": self.target.inst_id if self.target else None,
            "speed": self.speed,
            "pos": {"x": round(self.pos_x, 3), "y": round(self.pos_y, 3)},
            "distance": round(self.distance, 3),
            "flightFrames": self.flight_frames,
            "travelT": round(self.travel_t, 3),
        }


def projectile_speed(projectile_key):
    """Speed lookup: exact table first (extracted [uc]projectiles speeds),
    then heuristic, then default 10 grids/s."""
    if not projectile_key:
        return DEFAULT_SPEED
    table = _load_speed_table()
    if projectile_key in table:
        try:
            return float(table[projectile_key])
        except (TypeError, ValueError):
            pass
    low = projectile_key.lower()
    for k, v in table.items():
        if k.lower() == low:
            try:
                return float(v)
            except (TypeError, ValueError):
                break
    key = low
    # heuristic from observed speeds in game assets
    if "arrow" in key or "bow" in key or "shot" in key:
        return 10.0
    if "magic" in key or "ball" in key:
        return 8.0
    if "rocket" in key or "bomb" in key or "mortar" in key:
        return 5.0
    if "laser" in key or "beam" in key:
        return 30.0
    return DEFAULT_SPEED
