#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse Arknights enemy_database / enemy_handbook_table binary tables to JSON.

Binary format: Arknights custom FlatBuffers variant (see root AGENTS.md).
  [u32 name_len][table name bytes][pad to 4][128B obfuscation][u32?]
  then a FlatBuffers buffer:
    u32 root_uoffset -> root table
    table: i32 soffset -> vtable at (table_pos - soffset); soffset may be
           negative meaning vtable sits AFTER the table.
    vtable: u16 vtable_size, u16 object_size, u16 field_offset[field_id]
            (field_offset == 0 means the field is absent/undefined)
    string: u32 byte_len + utf-8 bytes + NUL
    vector: u32 count + count slots (uoffset32 for tables/strings, inline
            scalars for int/float vectors)
Dictionary entries are 2-field tables: field0 = key(string), field1 = value.

Usage:
    python parse_enemy_tables.py            # parse both tables, write JSON
    python parse_enemy_tables.py --dump enemy_1001_golem   # debug dump one enemy
"""

import json
import os
import struct
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TABLES_DIR = os.path.join(SCRIPT_DIR, "..", "..", "data", "tables")
OUT_DIR = os.path.join(SCRIPT_DIR, "data")

ENEMY_DB = os.path.join(TABLES_DIR, "enemy_databasea5b667.bin")
ENEMY_HB = os.path.join(TABLES_DIR, "enemy_handbook_table493349.bin")

MAX_DEPTH = 8


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

    def f32(self, p):
        return struct.unpack_from('<f', self.d, p)[0]

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
        # reject control chars other than common whitespace
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
        # vector of offsets? test first element
        first = p + 4
        rel0 = self.i32(first)
        t0 = first + rel0
        if rel0 != 0 and 4 <= t0 < self.size - 4:
            if self.is_string(t0) or self.is_table(t0):
                return [self.parse_value(p + 4 + 4 * i, depth + 1) for i in range(cnt)]
        # vector of scalars
        vals = [self.i32(p + 4 + 4 * i) for i in range(cnt)]
        # heuristics: scalars in an offset-vector region look random; accept only
        # if values are "small" (enum/bool/int vectors) or look like floats
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


def main_dump(fb, enemy_id):
    cnt_slot = None
    fields = fb.table_fields(fb.root)
    print('root fields:', [(i, hex(p) if p else None) for i, p in enumerate(fields)])
    vec = fields[0] + fb.i32(fields[0])
    entries = read_dict(fb, vec)
    print('dict entries:', len(entries))
    for key, vpos in entries:
        if key == enemy_id:
            print(f'== {key} value slot at {vpos:#x}')
            val = fb.parse_value(vpos)
            print(json.dumps(val, ensure_ascii=False, indent=1, default=str))
            return
    print(f'{enemy_id} not found; first 5 keys: {[k for k, _ in entries[:5]]}')


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '--dump':
        fb = open_table(ENEMY_DB)
        main_dump(fb, sys.argv[2])
    else:
        fb = open_table(ENEMY_DB)
        fields = fb.table_fields(fb.root)
        print('root fields:', fields)
        vec = fields[0] + fb.i32(fields[0])
        entries = read_dict(fb, vec)
        print('dict entries:', len(entries))
        print('first keys:', [k for k, _ in entries[:10]])
