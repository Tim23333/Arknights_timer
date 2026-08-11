"""Attack timing from Spine skeletons (precise hit frames).

Two data sources, both extracted from Spine 3.8.99 skeletons with
big-endian floats:
  - data_enemy_spine_events.json     : 1006 enemy skeletons
  - data_character_spine_events.json : 449 operator skeletons

Each unit maps its ability ``_animKey`` (e.g. "Attack", "Skill", "Skill_1")
to an animation in its skeleton; the OnAttack event time is the exact frame
where damage/effect lands within the attack animation.

The game plays the ability animation scaled so the full animation spans the
attack interval; the hit frame = onAttack_time / duration * scaled_duration
(proportional, computed via hit_frame_ratio()).
"""

import io
import json
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
_ENEMY_DATA = os.path.join(_DIR, "data_enemy_spine_events.json")
_CHAR_DATA = os.path.join(_DIR, "data_character_spine_events.json")
_TIMING_DATA = os.path.join(_DIR, "data_enemy_attack_timing.json")
_cache = {}


def _load(path):
    if path not in _cache:
        with io.open(path, encoding="utf-8") as f:
            _cache[path] = json.load(f)
    return _cache[path]


def _animations(unit_key):
    """Skeleton animations for an enemy or operator key ({} if unknown)."""
    for path in (_ENEMY_DATA, _CHAR_DATA):
        entry = _load(path).get(unit_key)
        if entry and "animations" in entry:
            return entry["animations"]
    return {}


def find_animation(unit_key, anim_key):
    """Resolve an ability animKey to an actual skeleton animation name.
    Prefers exact name, then name that starts with or contains the animKey
    (e.g. "Attack" -> "Attack_A"/"Attack_B"/"Attack1"), then any attack anim,
    then any skill anim."""
    anims = _animations(unit_key)
    if not anims:
        return None
    if anim_key in anims:
        return anim_key
    if anim_key:
        for name in anims:
            if name.startswith(anim_key) or anim_key in name:
                return name
    for name in anims:
        low = name.lower()
        if "attack" in low:
            return name
    for name in anims:
        low = name.lower()
        if "skill" in low:
            return name
    return None


def skill_hit_times(unit_key, prefab_key):
    """Calibrated OnAttack times for a skill prefab.

    data_enemy_attack_timing.json maps each enemy's skills (prefabKey) to
    its animation (animKey) and the exact OnAttack times inside it - the
    authoritative hit frames for ability effects. Returns [] when absent.
    """
    try:
        entry = _load(_TIMING_DATA).get(unit_key) or {}
        for s in entry.get("skills") or []:
            if s.get("prefabKey") == prefab_key:
                return sorted(float(t) for t in (s.get("onAttack") or [])
                              if t is not None)
    except Exception:
        pass
    return []


def on_attack_times(unit_key, anim_key=None):
    """Hit-frame times (seconds within the animation) for an ability."""
    anims = _animations(unit_key)
    name = find_animation(unit_key, anim_key) if anim_key else None
    if name is None and anims:
        name = find_animation(unit_key, "Attack")
    if name is None:
        return []
    return [e["t"] for e in anims[name].get("events", [])
            if e.get("event") == "OnAttack"]


def animation_duration(unit_key, anim_key=None):
    anims = _animations(unit_key)
    name = find_animation(unit_key, anim_key) if anim_key else None
    if name is None and anims:
        name = find_animation(unit_key, "Attack")
    if name is None:
        return None
    return anims[name].get("duration")


def hit_frame_ratio(unit_key, anim_key=None):
    """Proportion of the animation elapsed when damage lands (0..1)."""
    anims = _animations(unit_key)
    name = find_animation(unit_key, anim_key) if anim_key else None
    if name is None and anims:
        name = find_animation(unit_key, "Attack")
    if name is None:
        return 0.5
    dur = anims[name].get("duration") or 0.0
    times = [e["t"] for e in anims[name].get("events", [])
             if e.get("event") == "OnAttack"]
    if not times or dur <= 0:
        return 0.5
    return max(0.0, min(1.0, times[0] / dur))


def attack_frame_seconds(unit_key, anim_key=None, interval=None):
    """Absolute seconds from attack start to damage landing.
    If interval is given, uses proportional scaling (OnAttack / duration *
    interval); otherwise returns the raw OnAttack time in the animation."""
    if interval:
        return hit_frame_ratio(unit_key, anim_key) * interval
    times = on_attack_times(unit_key, anim_key)
    return times[0] if times else 0.0


def animation_names(unit_key):
    """All skeleton animation names for a unit."""
    return list(_animations(unit_key).keys())
