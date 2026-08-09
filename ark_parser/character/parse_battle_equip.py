#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse Arknights battle_equip_table binary to JSON.

battle_equip_table = Torappu.BattleUniEquipDB (dump.cs:121200),
a SimpleKVTable<BattleEquipPack> keyed by equip id (uniequip_* / 模组战斗数据包).

Structure (dump.cs):
  BattleEquipPack                 169569  { phases: List<BattleEquipPerLevelPack> }
  BattleEquipPerLevelPack         169554  { equipLevel, parts: List<BattleUniEquipData>,
                                            attributeBlackboard, tokenAttributeBlackboard }
  BattleUniEquipData              169535  { resKey, target: UniEquipTarget, isToken,
                                            validInGameTag, validInMapTag,
                                            addOrOverrideTalentDataBundle,
                                            overrideTraitDataBundle }
  Blackboard : List<DataPair>     162474  DataPair { key, value(float), valueStr }

Binary format: Arknights custom FlatBuffers variant (see root AGENTS.md and
ark_parser/enemy/parse_enemy_tables.py for the reference reader).

Usage:
    python parse_battle_equip.py                  # full parse -> data/battle_equip.json
    python parse_battle_equip.py --dump <equipId> # debug dump one entry
"""

import json
import os
import struct
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TABLES_DIR = os.path.join(SCRIPT_DIR, "..", "..", "data", "tables")
OUT_DIR = os.path.join(SCRIPT_DIR, "data")

BATTLE_EQUIP = os.path.join(TABLES_DIR, "battle_equip_table91e6b6.bin")

MAX_DEPTH = 10

# UniEquipTarget enum (dump.cs:169520)
UNI_EQUIP_TARGET = {
    0: "NONE",
    1: "TRAIT",
    2: "TRAIT_DATA_ONLY",
    3: "TALENT",
    4: "TALENT_DATA_ONLY",
    5: "DISPLAY",
    6: "OVERWRITE_BATTLE_DATA",
}


def i2f(val):
    """Reinterpret an int32/uint32 as IEEE754 float (blackboard display rule)."""
    if isinstance(val, int) and -(2 ** 31) <= val < 2 ** 32:
        val &= 0xFFFFFFFF
        f = struct.unpack('<f', struct.pack('<I', val))[0]
        return round(f, 4)
    return val


class FB:
    """Generic reader for the Arknights FlatBuffers variant."""

    def __init__(self, path):
        self.path = path
        self.d = open(path, 'rb').read()
        self.size = len(self.d)
        name_len = self.u32(0)
        self.name = self.d[4:4 + name_len].decode('ascii', 'replace')
        # header = align4(4 + name_len) + 132 (128B obfuscation + u32 tag)
        self.start = ((4 + name_len + 3) & ~3) + 132
        root_off = self.u32(self.start)
        self.root = self.start + root_off

    # ---- primitives ----
    def u16(self, p):
        return struct.unpack_from('<H', self.d, p)[0]

    def u32(self, p):
        return struct.unpack_from('<I', self.d, p)[0]

    def i32(self, p):
        return struct.unpack_from('<i', self.d, p)[0]

    # ---- vtable ----
    def table_fields(self, tpos):
        """Return list of absolute field positions (None for absent fields)."""
        soff = self.i32(tpos)
        vpos = tpos - soff
        if not (0 <= vpos < self.size - 4):
            raise ValueError(f'bad vtable pos {vpos:#x} for table {tpos:#x}')
        vts = self.u16(vpos)
        objsz = self.u16(vpos + 2)
        if vts < 4 or vts > 512 or vts % 2 or objsz < 4 or objsz > 8192:
            raise ValueError(f'bad vtable header at {vpos:#x}: vts={vts} obj={objsz}')
        if vpos + vts > self.size:
            raise ValueError(f'vtable overruns file at {vpos:#x}')
        fields = []
        for i in range((vts - 4) // 2):
            fo = self.u16(vpos + 4 + 2 * i)
            if fo == 0:
                fields.append(None)
            elif fo >= objsz or tpos + fo >= self.size:
                fields.append(None)
            else:
                fields.append(tpos + fo)
        return fields

    def is_table(self, p):
        try:
            self.table_fields(p)
            return True
        except ValueError:
            return False

    # ---- string ----
    def read_string(self, p):
        slen = self.u32(p)
        raw = self.d[p + 4:p + 4 + slen]
        return raw.decode('utf-8')

    def is_string(self, p):
        if p < 0 or p + 4 > self.size:
            return False
        slen = self.u32(p)
        if slen < 1 or slen > 65536 or p + 4 + slen >= self.size:
            return False
        if self.d[p + 4 + slen] != 0:
            return False
        try:
            s = self.d[p + 4:p + 4 + slen].decode('utf-8')
        except UnicodeDecodeError:
            return False
        for ch in s:
            o = ord(ch)
            if o < 0x20 and ch not in '\n\t':
                return False
        return True

    # ---- generic value ----
    def parse_value(self, pos, depth=0):
        """Parse the value stored in a 4-byte slot (uoffset or inline scalar)."""
        rel = self.i32(pos)
        target = pos + rel
        if rel != 0 and 4 <= target < self.size - 4 and depth < MAX_DEPTH:
            if self.is_string(target):
                return self.read_string(target)
            if self.is_table(target):
                return self.parse_table(target, depth + 1)
            vec = self.try_vector(target, depth)
            if vec is not None:
                return vec
        return rel  # inline scalar (int/float bits/bool/enum)

    def try_vector(self, p, depth):
        cnt = self.u32(p)
        if cnt < 1 or cnt > 200000 or p + 4 + 4 * cnt > self.size:
            return None
        first = p + 4
        rel0 = self.i32(first)
        t0 = first + rel0
        if rel0 != 0 and 4 <= t0 < self.size - 4:
            if self.is_string(t0) or self.is_table(t0):
                return [self.parse_value(p + 4 + 4 * i, depth + 1) for i in range(cnt)]
        vals = [self.i32(p + 4 + 4 * i) for i in range(cnt)]
        if all(-100000 <= v <= 100000 for v in vals):
            return vals
        if all(0x3A83126F <= (v & 0xFFFFFFFF) <= 0x4F000000 or (v & 0xFFFFFFFF) < 0x100
               for v in vals):
            return [i2f(v) for v in vals]
        return None

    def parse_table(self, tpos, depth=0):
        fields = self.table_fields(tpos)
        out = {}
        for idx, fpos in enumerate(fields):
            if fpos is None:
                continue
            out[idx] = self.parse_value(fpos, depth)
        return out


def open_table(path):
    fb = FB(path)
    print(f'{os.path.basename(path)}: name={fb.name} start={fb.start:#x} '
          f'root={fb.root:#x} size={fb.size:#x}')
    return fb


def read_dict(fb, vec_pos):
    """Read vector of {key, value} entry tables -> list of (key, value_pos)."""
    cnt = fb.u32(vec_pos)
    entries = []
    for i in range(cnt):
        slot = vec_pos + 4 + 4 * i
        epos = slot + fb.i32(slot)
        fields = fb.table_fields(epos)
        if len(fields) < 2 or fields[0] is None or fields[1] is None:
            raise ValueError(f'entry {i} at {epos:#x} malformed: {fields}')
        key = fb.read_string(fields[0] + fb.i32(fields[0]))
        entries.append((key, fields[1]))
    return entries


# ---------------------------------------------------------------------------
# semantic post-processing (generic field-index dict -> named structure)
# ---------------------------------------------------------------------------

def is_blackboard_pairs(node):
    """Heuristic: [ {0: str key, 1: number, 2?: str}, ... ] => Blackboard."""
    if not isinstance(node, list) or not node:
        return False
    for item in node:
        if not isinstance(item, dict):
            return False
        keys = set(item.keys())
        if not keys or not keys <= {0, 1, 2}:
            return False
        if 0 not in item or not isinstance(item[0], str):
            return False
        if 1 in item and not isinstance(item[1], (int, float)):
            return False
    return True


def convert_blackboard(node):
    """Blackboard (List<DataPair{key,value,valueStr}>) -> {key: float|str}."""
    out = {}
    for item in node:
        k = item[0]
        if 2 in item and isinstance(item[2], str):
            out[k] = item[2]  # string-valued pair
        elif 1 in item:
            out[k] = i2f(item[1])
        else:
            out[k] = 0.0
    return out


def remap(node, names):
    """Rename numeric field keys using a {index: name} map."""
    if not isinstance(node, dict):
        return node
    return {names.get(k, str(k)): v for k, v in node.items()}


UNLOCK_COND_NAMES = {0: 'phase', 1: 'level'}

# TalentData (191011) + EquipTalentData (191052) layout
TALENT_NAMES = {
    0: 'unlockCondition',
    1: 'requiredPotentialRank',
    2: 'prefabKey',
    3: 'name',
    4: 'description',
    5: 'rangeId',
    6: 'blackboard',
    7: 'tokenKey',
    8: 'isHideTalent',
    9: 'displayRangeId',
    10: 'upgradeDescription',
    11: 'talentIndex',
    12: 'validModeIndices',
}

# TraitData (164936) + EquipTraitData (164970) layout
TRAIT_NAMES = {
    0: 'unlockCondition',
    1: 'requiredPotentialRank',
    2: 'blackboard',
    3: 'overrideDescripton',
    4: 'prefabKey',
    5: 'rangeId',
    6: 'additionalDescription',
}

# BattleUniEquipData (169535)
PART_NAMES = {
    0: 'resKey',
    1: 'target',
    2: 'isToken',
    3: 'validInGameTag',
    4: 'validInMapTag',
    5: 'addOrOverrideTalentDataBundle',
    6: 'overrideTraitDataBundle',
}

# BattleEquipPerLevelPack (169554)
PHASE_NAMES = {
    0: 'equipLevel',
    1: 'parts',
    2: 'attributeBlackboard',
    3: 'tokenAttributeBlackboard',
}


def fix_talent(node):
    if not isinstance(node, dict):
        return node
    node = remap(node, TALENT_NAMES)
    if isinstance(node.get('unlockCondition'), dict):
        node['unlockCondition'] = remap(node['unlockCondition'], UNLOCK_COND_NAMES)
    if is_blackboard_pairs(node.get('blackboard')):
        node['blackboard'] = convert_blackboard(node['blackboard'])
    return node


def fix_trait(node):
    if not isinstance(node, dict):
        return node
    node = remap(node, TRAIT_NAMES)
    if isinstance(node.get('unlockCondition'), dict):
        node['unlockCondition'] = remap(node['unlockCondition'], UNLOCK_COND_NAMES)
    if is_blackboard_pairs(node.get('blackboard')):
        node['blackboard'] = convert_blackboard(node['blackboard'])
    return node


def fix_bundle(node, kind):
    """EquipTalentDataBundle / EquipTraitDataBundle: pick the candidates list."""
    if not isinstance(node, dict):
        return node
    fixer = fix_talent if kind == 'talent' else fix_trait
    out = {}
    for k, v in node.items():
        if isinstance(v, list):
            out['candidates'] = [fixer(c) for c in v]
        else:
            out[str(k)] = v
    return out


def fix_part(node):
    if not isinstance(node, dict):
        return node
    node = remap(node, PART_NAMES)
    if isinstance(node.get('target'), int):
        node['target'] = UNI_EQUIP_TARGET.get(node['target'], node['target'])
    if 'isToken' in node:
        node['isToken'] = bool(node['isToken'])
    if isinstance(node.get('addOrOverrideTalentDataBundle'), dict):
        node['addOrOverrideTalentDataBundle'] = fix_bundle(
            node['addOrOverrideTalentDataBundle'], 'talent')
    if isinstance(node.get('overrideTraitDataBundle'), dict):
        node['overrideTraitDataBundle'] = fix_bundle(
            node['overrideTraitDataBundle'], 'trait')
    return node


def fix_phase(node):
    if not isinstance(node, dict):
        return node
    node = remap(node, PHASE_NAMES)
    if isinstance(node.get('parts'), list):
        node['parts'] = [fix_part(p) for p in node['parts']]
    if is_blackboard_pairs(node.get('attributeBlackboard')):
        node['attributeBlackboard'] = convert_blackboard(node['attributeBlackboard'])
    tok = node.get('tokenAttributeBlackboard')
    if isinstance(tok, list):
        # Dictionary<string, Blackboard> -> list of entry tables {0: key, 1: bb}
        conv = {}
        for entry in tok:
            if isinstance(entry, dict) and 0 in entry and isinstance(entry[0], str):
                bb = entry.get(1)
                conv[entry[0]] = convert_blackboard(bb) if is_blackboard_pairs(bb) else bb
        node['tokenAttributeBlackboard'] = conv
    return node


def fix_pack(node):
    if not isinstance(node, dict):
        return node
    phases = node.get(0)
    out = {}
    if isinstance(phases, list):
        out['phases'] = [fix_phase(p) for p in phases]
    for k, v in node.items():
        if k != 0:
            out[str(k)] = v
    return out


def main_dump(fb, equip_id):
    fields = fb.table_fields(fb.root)
    vec = fields[0] + fb.i32(fields[0])
    entries = read_dict(fb, vec)
    print('dict entries:', len(entries))
    for key, vpos in entries:
        if key == equip_id:
            raw = fb.parse_value(vpos)
            print('== RAW ==')
            print(json.dumps(raw, ensure_ascii=False, indent=1, default=str))
            print('== FIXED ==')
            print(json.dumps(fix_pack(raw), ensure_ascii=False, indent=1, default=str))
            return
    print(f'{equip_id} not found; first 10 keys: {[k for k, _ in entries[:10]]}')


def main():
    fb = open_table(BATTLE_EQUIP)
    fields = fb.table_fields(fb.root)
    vec = fields[0] + fb.i32(fields[0])
    entries = read_dict(fb, vec)
    print('dict entries:', len(entries))

    result = {}
    for i, (key, vpos) in enumerate(entries):
        raw = fb.parse_value(vpos)
        result[key] = fix_pack(raw)
        if (i + 1) % 500 == 0:
            print(f'  {i + 1}/{len(entries)}')

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'battle_equip.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f'wrote {out_path} ({len(result)} entries)')


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '--dump':
        fb = open_table(BATTLE_EQUIP)
        main_dump(fb, sys.argv[2])
    else:
        main()
