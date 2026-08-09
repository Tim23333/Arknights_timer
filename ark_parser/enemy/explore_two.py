#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deeper exploration: dump EnemyData field targets recursively."""
import struct, sys

path = r'G:/Arknights/data/tables/enemy_databasea5b667.bin'
d = open(path, 'rb').read()
size = len(d)

def u16(p): return struct.unpack_from('<H', d, p)[0]
def u32(p): return struct.unpack_from('<I', d, p)[0]
def i32(p): return struct.unpack_from('<i', d, p)[0]
def f32(p): return struct.unpack_from('<f', d, p)[0]
def hx(p, n): return ' '.join(f'{b:02x}' for b in d[p:p+n])

name_len = u32(0)
start = ((4 + name_len + 3) & ~3) + 132
root = start + u32(start)

def vtable(tpos):
    soff = i32(tpos)
    vpos = tpos - soff
    if not (0 <= vpos < size - 4): raise ValueError('bad vpos')
    vts = u16(vpos); objsz = u16(vpos + 2)
    if vts < 4 or vts > 512 or vts % 2 or objsz < 4 or objsz > 8192: raise ValueError('bad vt hdr')
    fields = []
    for i in range((vts - 4) // 2):
        fo = u16(vpos + 4 + 2 * i)
        fields.append(None if fo == 0 else tpos + fo)
    return vpos, vts, objsz, fields

def probe_str(p):
    if not (0 <= p < size - 4): return None
    sl = u32(p)
    if 1 <= sl <= 4000 and p + 4 + sl < size and d[p+4+sl] == 0:
        try:
            s = d[p+4:p+4+sl].decode('utf-8')
            if all(ord(c) >= 0x20 or c in '\n\t' for c in s):
                return s
        except UnicodeDecodeError:
            pass
    return None

def is_table(p):
    try: vtable(p); return True
    except ValueError: return False

def show(tpos, label, depth, maxdepth):
    pad = '  ' * depth
    try:
        vpos, vts, objsz, fields = vtable(tpos)
    except ValueError as e:
        print(f'{pad}{label} @{tpos:#x} NOT table: {e} raw[{hx(tpos,16)}]')
        return
    print(f'{pad}{label} tbl@{tpos:#x} vt={vts} obj={objsz} nf={len(fields)} raw[{hx(tpos, min(objsz,40))}]')
    for i, fp in enumerate(fields):
        if fp is None: continue
        rel = i32(fp); tgt = fp + rel
        line = f'{pad}  f{i} @{fp:#x}: i32={rel}'
        s = probe_str(tgt) if 0 <= tgt < size else None
        if s is not None:
            print(line + f' -> STR {s!r}')
            continue
        if rel != 0 and 0 <= tgt < size - 4 and is_table(tgt):
            print(line + f' -> TBL @{tgt:#x}')
            if depth < maxdepth:
                show(tgt, f'f{i}', depth + 1, maxdepth)
            continue
        # vector probe
        if rel != 0 and 0 <= tgt < size - 4:
            cnt = u32(tgt)
            if 1 <= cnt <= 100 and tgt + 4 + 4*cnt <= size:
                first = tgt + 4
                r0 = i32(first); t0 = first + r0
                s0 = probe_str(t0) if 0 <= t0 < size else None
                if s0 is not None:
                    print(line + f' -> VEC<str> cnt={cnt} [0]={s0!r}')
                    continue
                if 0 <= t0 < size and is_table(t0):
                    print(line + f' -> VEC<tbl> cnt={cnt}')
                    if depth < maxdepth:
                        for j in range(min(cnt, 3)):
                            eslot = tgt + 4 + 4*j
                            show(eslot + i32(eslot), f'[{j}]', depth + 1, maxdepth)
                    continue
        print(line + f' f32={f32(fp):.6g}')

key = sys.argv[1] if len(sys.argv) > 1 else 'enemy_1007_slime'
lvl = int(sys.argv[2]) if len(sys.argv) > 2 else 0
fields = vtable(root)[3]
vec = fields[0] + i32(fields[0])
cnt = u32(vec)
for i in range(cnt):
    slot = vec + 4 + 4 * i
    epos = slot + i32(slot)
    ef = vtable(epos)[3]
    k = probe_str(ef[0] + i32(ef[0]))
    if k == key:
        vslot = ef[1]
        vtgt = vslot + i32(vslot)
        lslot = vtgt + 4 + 4 * lvl
        ltpos = lslot + i32(lslot)
        print(f'== {key} level[{lvl}]')
        show(ltpos, 'EnemyLevel', 0, 4)
        break
