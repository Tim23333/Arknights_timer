"""Level predefined instances (predefines) parser + spawner.

Level assets carry ``predefines`` (field 16 of the LevelData FB root):
  characterInsts / tokenInsts : PredefinedCharacter[]
  characterCards / tokenCards : PredefinedCard[]

PredefinedCharacter FB layout follows the C# declaration order
(dump.cs LevelData.PredefinedData.PredefinedCharacter):
  0 position {row, col}, 1 direction (SharedConsts.Direction),
  2 hidden (bool), 3 alias (str), 4 uniEquipIds, 5 showSpIllust,
  6 masterInfos, 7 inst {0 characterKey, 1 level, 2 phase, 3 favor,
  4 potentialRank}, 8 skillIndex, 9 mainSkillLvl, 10 skinId, 11 tmplId,
  12 overrideSkillBlackboard, 13 overrideTalents.
"""

import io as _io
import json
import os
import struct

from .project_paths import LEVEL_ASSETS_INDEX, resolve_project_path


_INDEX = str(LEVEL_ASSETS_INDEX)
_index_cache = None


def _asset_path(level_id):
    global _index_cache
    if _index_cache is None:
        with _io.open(_INDEX, encoding="utf-8") as f:
            _index_cache = json.load(f)
    path = _index_cache.get(level_id)
    return str(resolve_project_path(path)) if path else None


class _FB:
    """Minimal LevelData FB reader (128B obfuscation header variant)."""

    def __init__(self, data):
        self.d = data
        self.size = len(data)
        self.start = 128 if len(data) > 128 else 0
        if self.start + 4 > self.size:
            raise ValueError("level asset too small")
        root_off = self.u32(self.start)
        self.root = self.start + root_off

    def u16(self, p):
        return struct.unpack_from('<H', self.d, p)[0]

    def u32(self, p):
        return struct.unpack_from('<I', self.d, p)[0]

    def i32(self, p):
        return struct.unpack_from('<i', self.d, p)[0]

    def table_fields(self, tpos):
        soff = self.i32(tpos)
        vpos = tpos - soff
        if not (0 <= vpos < self.size - 4):
            raise ValueError("bad vtable pos")
        vts = self.u16(vpos)
        objsz = self.u16(vpos + 2)
        if vts < 4 or vts > 1024 or vts % 2:
            raise ValueError("bad vtable header")
        out = []
        for i in range((vts - 4) // 2):
            fo = self.u16(vpos + 4 + 2 * i)
            out.append(tpos + fo if fo else None)
        return out

    def is_string(self, p):
        if p < 0 or p + 4 > self.size:
            return False
        ln = self.u32(p)
        if not (0 < ln < 65536) or p + 4 + ln >= self.size:
            return False
        return self.d[p + 4 + ln] == 0

    def read_string(self, p):
        ln = self.u32(p)
        return self.d[p + 4:p + 4 + ln].decode('utf-8', 'replace')

    def target(self, p):
        return p + self.i32(p)


def _parse_inst(fb, tpos):
    """Parse a PredefinedCharacter/PredefinedInst table."""
    fields = fb.table_fields(tpos)
    out = {}
    if len(fields) > 0 and fields[0] is not None:
        pt = fb.target(fields[0])
        try:
            pf = fb.table_fields(pt)
            out["row"] = fb.i32(pf[0]) if len(pf) > 0 and pf[0] else 0
            out["col"] = fb.i32(pf[1]) if len(pf) > 1 and pf[1] else 0
        except Exception:
            pass
    if len(fields) > 1 and fields[1] is not None:
        out["direction"] = fb.i32(fields[1])
    if len(fields) > 2 and fields[2] is not None:
        out["hidden"] = bool(fb.d[fields[2]])
    if len(fields) > 3 and fields[3] is not None:
        t = fb.target(fields[3])
        if fb.is_string(t):
            out["alias"] = fb.read_string(t)
    if len(fields) > 7 and fields[7] is not None:
        it = fb.target(fields[7])
        try:
            inf = fb.table_fields(it)
            if inf and inf[0]:
                t = fb.target(inf[0])
                if fb.is_string(t):
                    out["characterKey"] = fb.read_string(t)
            if len(inf) > 1 and inf[1]:
                out["level"] = fb.i32(inf[1])
            if len(inf) > 2 and inf[2]:
                out["phase"] = fb.i32(inf[2])
            if len(inf) > 4 and inf[4]:
                out["potentialRank"] = fb.i32(inf[4])
        except Exception:
            pass
    if len(fields) > 8 and fields[8] is not None:
        out["skillIndex"] = fb.i32(fields[8])
    if len(fields) > 9 and fields[9] is not None:
        out["mainSkillLvl"] = fb.i32(fields[9])
    out.setdefault("level", 1)
    out.setdefault("phase", 0)
    out.setdefault("potentialRank", 0)
    out.setdefault("skillIndex", 0)
    out.setdefault("mainSkillLvl", 1)
    out.setdefault("hidden", False)
    out.setdefault("direction", 0)
    return out


def _parse_inst_list(fb, field_pos):
    if field_pos is None:
        return []
    vec = fb.target(field_pos)
    if vec + 4 > fb.size:
        return []
    cnt = fb.u32(vec)
    out = []
    for j in range(cnt):
        slot = vec + 4 + 4 * j
        if slot + 4 > fb.size:
            break
        t = fb.target(slot)
        try:
            out.append(_parse_inst(fb, t))
        except Exception:
            continue
    return out


def parse_level_predefines(level_id):
    """Parse a level asset's predefines. Returns
    {tokenInsts: [...], characterInsts: [...]} or {} on failure."""
    path = _asset_path(level_id)
    if not path or not os.path.exists(path):
        return {}
    data = open(path, 'rb').read()
    try:
        fb = _FB(data)
        root_fields = fb.table_fields(fb.root)
        if len(root_fields) <= 16 or root_fields[16] is None:
            return {}
        pp = fb.target(root_fields[16])
        pf = fb.table_fields(pp)
        result = {}
        if len(pf) > 0:
            result["characterInsts"] = _parse_inst_list(fb, pf[0])
        if len(pf) > 1:
            result["tokenInsts"] = _parse_inst_list(fb, pf[1])
        return result
    except Exception:
        return {}


_PREDEF_DIRECTION = {"UP": 0, "RIGHT": 1, "DOWN": 2, "LEFT": 3, "E_NUM": 4}
_PREDEF_PHASE = {"PHASE_0": 0, "PHASE_1": 1, "PHASE_2": 2}


def _predef_inst(c):
    """Normalise one official gamedata PredefinedCharacter / token entry
    into the binary-parser shape (row/col/direction/hidden/alias/
    characterKey/level/phase/potentialRank/skillIndex/mainSkillLvl)."""
    if not isinstance(c, dict):
        return None
    pos = c.get("position") or {}
    inst = c.get("inst") or {}
    direction = c.get("direction")
    if isinstance(direction, str):
        direction = _PREDEF_DIRECTION.get(direction, 0)
    phase = inst.get("phase")
    if isinstance(phase, str):
        phase = _PREDEF_PHASE.get(phase, 0)
    return {
        "row": int(pos.get("row") or 0),
        "col": int(pos.get("col") or 0),
        "direction": int(direction or 0),
        "hidden": bool(c.get("hidden")),
        "alias": c.get("alias"),
        "characterKey": inst.get("characterKey"),
        "level": int(inst.get("level") or 1),
        "phase": int(phase or 0),
        "potentialRank": int(inst.get("potentialRank") or 0),
        "skillIndex": int(c.get("skillIndex") or 0),
        "mainSkillLvl": int(c.get("mainSkillLvl") or 1),
    }


def predefines_from_raw(raw):
    """Fallback for levels without a binary asset (official gamedata
    levels): convert the raw level JSON's full ``predefines`` section into
    the spawner shape.  Returns {characterInsts, tokenInsts}."""
    p = (raw or {}).get("predefines") or {}
    chars = []
    for c in p.get("characterInsts") or []:
        e = _predef_inst(c)
        if e is not None and e.get("characterKey"):
            chars.append(e)
    tokens = []
    tk = p.get("tokenInsts")
    if isinstance(tk, dict):
        tk = tk.values() if tk else []
    for t in tk or []:
        e = _predef_inst(t)
        if e is not None and e.get("characterKey"):
            tokens.append(e)
    return {"characterInsts": chars, "tokenInsts": tokens}
