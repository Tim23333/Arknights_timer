"""Enemy Spine skeleton animation-event extraction (attack timing source).

Arknights enemy animations are Spine 3.8.99 binary skeletons. The game fires
battle-relevant events (e.g. ``OnAttack``) on the animation timeline; the
ability system's ``_animKey`` (e.g. "Attack", "Attack_A") selects which
animation to play and the event time is where the damage/effect lands.

This module wraps spine_asset (optional dependency) and additionally exposes
raw event-frame bytes for further calibration. Skeleton structure (bones /
slots / skins / events / animation names) parses reliably; exact event frame
times are extracted when the binary layout is unambiguous.
"""

import io
import os

from .project_paths import SPINE_ASSET_LIB


def _load_spine_lib():
    """Locate the spine_asset library (wheel extracted in unpack_work)."""
    candidates = [
        str(SPINE_ASSET_LIB),
    ]
    for c in candidates:
        if os.path.isdir(c) and os.path.exists(os.path.join(c, "spine_asset")):
            return c
    return None


def parse_skeleton(skel_path):
    """Parse a Spine binary skeleton; returns skeleton_data or None."""
    lib = _load_spine_lib()
    if lib is None:
        return None
    import sys
    if lib not in sys.path:
        sys.path.insert(0, lib)
    from spine_asset.v38.SkeletonBinary import SkeletonBinary
    with io.open(skel_path, "rb") as f:
        data = f.read()
    return SkeletonBinary().read_skeleton_data(data)


def attack_events(skel_path):
    """Return {anim_name: {"duration": float, "events": [(name, time)]}}.
    Time is the library-reported value; may need calibration for this build.
    """
    sd = parse_skeleton(skel_path)
    if sd is None:
        return {}
    out = {}
    for a in sd.animations:
        evs = []
        for tl in a.timelines:
            if type(tl).__name__ == "EventTimeline":
                for fr, ev in zip(tl.frames, tl.events):
                    name = getattr(getattr(ev, "data", None), "name", None)
                    evs.append((name, fr, getattr(ev, "float_value", None)))
        out[a.name] = {"duration": a.duration, "events": evs}
    return out


def summarize(skel_path):
    """Human-readable summary for a skeleton file."""
    sd = parse_skeleton(skel_path)
    if sd is None:
        return {"error": "spine_asset not available"}
    return {
        "version": sd.version,
        "bones": [b.name for b in sd.bones],
        "slots": [s.name for s in sd.slots],
        "events": [e.name for e in sd.events],
        "animations": [a.name for a in sd.animations],
        "attack_animations": [a.name for a in sd.animations
                              if "Attack" in a.name or "attack" in a.name],
    }


if __name__ == "__main__":
    import sys as _sys
    for p in _sys.argv[1:]:
        print(p)
        print(summarize(p))
        print(attack_events(p))
