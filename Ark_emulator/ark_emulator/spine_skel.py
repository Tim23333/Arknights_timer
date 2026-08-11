"""Minimal Spine 3.8.x binary (.skel) parser.

Parses just enough of the format to extract:
  - animation names and durations
  - event timelines (name -> time list), e.g. OnAttack / Skill_Begin
  - animation names referenced by enemy abilities (_animKey)

Format reference: Spine runtime binary parsing (SkeletonBinary.cs v3.8).
Only read; works for both essentials/non-essentials variants.
"""

import io
import struct


class _R:
    def __init__(self, data):
        self.f = io.BytesIO(data)
        self.data = data

    def read_byte(self):
        b = self.f.read(1)
        return b[0] if b else 0

    def read_bool(self):
        return self.read_byte() != 0

    def read_int(self):
        b = self.f.read(4)
        return struct.unpack("<i", b)[0]

    def read_float(self):
        b = self.f.read(4)
        return struct.unpack("<f", b)[0]

    def read_short(self):
        b = self.f.read(2)
        return struct.unpack("<h", b)[0]

    def read_unsigned_short(self):
        b = self.f.read(2)
        return struct.unpack("<H", b)[0]

    def read_string(self):
        """Spine binary string: single null byte = null, else len-prefixed."""
        b = self.read_byte()
        if b == 0:
            return None
        n = b
        if n == 255:
            n = self.read_unsigned_short()
        raw = self.f.read(n)
        return raw.decode("utf-8", "replace")

    def read_float_array(self, n, scale=1.0):
        if n == 0:
            return []
        out = []
        for _ in range(n):
            out.append(self.read_float() * scale)
        return out

    def read_short_array(self, n):
        if n == 0:
            return []
        return [self.read_short() for _ in range(n)]

    def read_skin(self):
        name = self.read_string()
        bones = []
        nb = self.read_byte()
        for _ in range(nb):
            bones.append(self.read_int())
        # slots: name, x, y, scale, rotation, width, height
        ns = self.read_byte()
        slots = []
        for _ in range(ns):
            slot_name = self.read_string()
            x = self.read_float()
            y = self.read_float()
            scale = self.read_float()
            rotation = self.read_float()
            width = self.read_float()
            height = self.read_float()
            slots.append((slot_name, x, y, scale, rotation, width, height))
        return name, bones, slots


def _parse_events(r, events_out):
    """Parse the single global events block (events dict)."""
    ne = r.read_byte()
    for _ in range(ne):
        name = r.read_string()
        int_v = r.read_int()
        float_v = r.read_float()
        string_v = r.read_string()
        events_out[name] = {"int": int_v, "float": float_v, "string": string_v}


def _skip_curves(r, frame_count):
    """Spine curves: each frame may have 0/1/2/3 curve control bytes."""
    for _ in range(frame_count - 1):
        c = r.read_byte()
        if c == 0:
            pass
        elif c == 1:
            r.read_float()
            r.read_float()
        elif c == 2:
            r.read_float()
        elif c == 3:
            r.read_float()
            r.read_float()
            r.read_float()
            r.read_float()


def _read_timeline(r, anim_name, events):
    """Read one timeline; returns dict with kind + data."""
    kind = r.read_byte()
    if kind == 1:                     # rotate
        n = r.read_unsigned_short()
        frames = []
        for _ in range(n):
            t = r.read_float()
            angle = r.read_float()
            frames.append((t, angle))
        _skip_curves(r, n)
        return {"kind": "rotate", "frames": frames}
    if kind in (2, 3, 4):             # translate / scale / shear
        n = r.read_unsigned_short()
        frames = []
        for _ in range(n):
            t = r.read_float()
            x = r.read_float()
            y = r.read_float()
            frames.append((t, x, y))
        _skip_curves(r, n)
        return {"kind": "translate" if kind == 2 else "scale" if kind == 3
                else "shear", "frames": frames}
    if kind == 5:                     # attachment
        n = r.read_unsigned_short()
        frames = []
        for _ in range(n):
            t = r.read_float()
            name = r.read_string()
            frames.append((t, name))
        return {"kind": "attachment", "frames": frames}
    if kind == 6:                     # color
        n = r.read_unsigned_short()
        frames = []
        for _ in range(n):
            t = r.read_float()
            r_ = r.read_float(); g = r.read_float(); b = r.read_float(); a = r.read_float()
            frames.append((t, (r_, g, b, a)))
        _skip_curves(r, n)
        return {"kind": "color", "frames": frames}
    if kind == 7:                     # deform
        n = r.read_unsigned_short()
        frames = []
        for _ in range(n):
            t = r.read_float()
            vn = r.read_int()
            vs = r.read_float_array(vn, 1.0)
            frames.append((t, vs))
        _skip_curves(r, n)
        return {"kind": "deform", "frames": frames}
    if kind == 8:                     # event (attack check points!)
        n = r.read_unsigned_short()
        frames = []
        for _ in range(n):
            t = r.read_float()
            ev_name = r.read_string()
            frames.append((t, ev_name))
        return {"kind": "event", "frames": frames}
    if kind == 9:                     # draw order
        n = r.read_unsigned_short()
        frames = []
        for _ in range(n):
            t = r.read_float()
            off = r.read_int()
            inds = r.read_short_array(off)
            frames.append((t, inds))
        return {"kind": "drawOrder", "frames": frames}
    if kind == 10:                    # ik
        n = r.read_unsigned_short()
        frames = []
        for _ in range(n):
            t = r.read_float()
            r_ = r.read_float()
            b = r.read_byte()
            frames.append((t, r_, b))
        _skip_curves(r, n)
        return {"kind": "ik", "frames": frames}
    raise ValueError(f"unknown timeline kind {kind} in {anim_name}")


def parse_skel(data):
    """Parse a Spine 3.8 binary skeleton; returns dict with animations."""
    r = _R(data)
    # --- header ---
    # Observed layout in this game build: hash fixed 28 bytes (no length
    # prefix; first byte 0x1c is part of the hash), then len-prefixed
    # version string "3.8.99".
    hash_s = r.f.read(28).decode("ascii", "replace")
    ver_len = r.read_byte()
    version = r.f.read(ver_len).decode("ascii", "replace")
    if not version.startswith("3.8"):
        raise ValueError(f"unsupported spine version {version}")
    r.read_bool()   # x flag
    r.read_bool()   # y flag
    r.read_bool()   # width flag
    r.read_bool()   # height flag
    nonessential = r.read_bool()
    fps_flag = r.read_byte()
    if fps_flag:
        r.read_float()
    if nonessential:
        r.read_string()  # audio path
    # --- skeleton ---
    skeleton_name = r.read_string()
    x = r.read_float(); y = r.read_float()
    w = r.read_float(); h = r.read_float()
    r.read_float()            # fps
    r.read_string()           # images path
    if nonessential:
        r.read_string()       # audio path
    # --- bones ---
    nb = r.read_int()
    for _ in range(nb):
        name = r.read_string()
        parent = r.read_int()
        _len = r.read_float()
        _x = r.read_float(); _y = r.read_float()
        rot = r.read_float()
        sx = r.read_float(); sy = r.read_float()
        shx = r.read_float(); shy = r.read_float()
        _inherit = r.read_byte()
    # --- slots ---
    ns = r.read_int()
    for _ in range(ns):
        name = r.read_string()
        bone = r.read_int()
        r_ = r.read_byte(); g = r.read_byte(); b = r.read_byte(); a = r.read_byte()
        _add = r.read_byte()
        _att = r.read_string()
        _blend = r.read_byte()
    # --- ik constraints ---
    nik = r.read_int()
    for _ in range(nik):
        r.read_string()
        r.read_byte()          # order
        n = r.read_byte()
        for _2 in range(n):
            r.read_int()
        r.read_int()           # target
        r.read_byte()          # bend direction
        r.read_float()         # mix
        r.read_float()         # compress (3.8)
    # --- transform constraints ---
    ntc = r.read_int()
    for _ in range(ntc):
        r.read_string()
        r.read_byte()          # order
        n = r.read_byte()
        for _2 in range(n):
            r.read_int()
        r.read_int()           # target
        r.read_float(); r.read_float(); r.read_float(); r.read_float()  # translate/scale/shear/rotate mix
        r.read_float(); r.read_float(); r.read_float()  # offsets
        r.read_byte()          # local
        r.read_byte()          # relative
    # --- path constraints ---
    npc = r.read_int()
    for _ in range(npc):
        r.read_string()
        r.read_byte()          # order
        n = r.read_byte()
        for _2 in range(n):
            r.read_int()
        r.read_int()           # target
        r.read_float(); r.read_float()      # position mix/translate mix
        r.read_float(); r.read_float(); r.read_float()  # rotate/scale/shear mix
        r.read_byte()          # position mode
        r.read_byte()          # spacing mode
        r.read_byte()          # rotate mode
        r.read_string()        # spacing key (3.8)
        r.read_float()         # spacing (3.8)
        r.read_float(); r.read_float()      # position (3.8)
        r.read_float()         # rotate (3.8)
        r.read_byte()          # tangents flag (3.8)
        r.read_string()        # color key (3.8)
        r.read_float(); r.read_float(); r.read_float(); r.read_float()  # color (3.8)
    # --- skins ---
    nsk = r.read_byte()
    skins = []
    for _ in range(nsk):
        skins.append(r.read_skin())
    default_skin = r.read_string()
    # --- events ---
    events = {}
    _parse_events(r, events)
    # --- animations ---
    nan = r.read_byte()
    animations = {}
    for _ in range(nan):
        name = r.read_string()
        ntl = r.read_byte()
        anim = {"timelines": [], "events": [], "duration": 0.0}
        for _2 in range(ntl):
            tl = _read_timeline(r, name, events)
            anim["timelines"].append(tl)
            if tl["kind"] == "event":
                for t, ev in tl["frames"]:
                    anim["events"].append((t, ev))
            if tl["frames"]:
                anim["duration"] = max(anim["duration"], tl["frames"][-1][0])
        animations[name] = anim
    return {
        "version": version,
        "skeleton": skeleton_name,
        "events": events,
        "animations": animations,
        "skins": [s[0] for s in skins],
    }




def extract_attack_events(skel_path):
    """Convenience: return {anim_name: [(time, event_name), ...]}."""
    with io.open(skel_path, "rb") as f:
        data = f.read()
    parsed = parse_skel(data)
    return {name: anim["events"] for name, anim in parsed["animations"].items()}


if __name__ == "__main__":
    import sys as _sys
    for p in _sys.argv[1:]:
        print(p)
        for n, evs in extract_attack_events(p).items():
            print("  ", n, evs)
