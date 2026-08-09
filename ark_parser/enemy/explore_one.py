#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Explore raw binary structure of one enemy entry (diagnostic)."""
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
print(f'start={start:#x} root={root:#x} size={size:#x}')

def vtable(tpos):
    soff = i32(tpos)
    vpos = tpos - soff
    vts = u16(vpos); objsz = u16(vpos + 2)
    fields = []
    for i in range((vts - 4) // 2):
        fo = u16(vpos + 4 + 2 * i)
        fields.append(None if fo == 0 else tpos + fo)
    return vpos, vts, objsz, fields

def probe_str(p):
    if not (0 <= p < size - 4): return None
    sl = u32(p)
    if 1 <= sl <= 200 and p + 4 + sl < size and d[p+4+sl] == 0:
        try:
            s = d[p+4:p+4+sl].decode('utf-8')
            if all(ord(c) >= 0x20 or c in '\n\t' for c in s):
                return s
        except UnicodeDecodeError:
            pass
    return None

def show_table(tpos, label, depth=0):
    pad = '  ' * depth
    vpos, vts, objsz, fields = vtable(tpos)
    print(f'{pad}{label} table@{tpos:#x} vtable@{vpos:#x} vts={vts} objsz={objsz} nfields={len(fields)}')
    print(f'{pad}  raw[{hx(tpos, min(objsz,64))}]')
    for i, fp in enumerate(fields):
        if fp is None:
            continue
        rel = i32(fp); tgt = fp + rel
        s = probe_str(tgt) if 0 <= tgt < size else None
        info = f'{pad}  f{i} @{fp:#x}: i32={rel} tgt={tgt:#x} f32={f32(fp):.4g}'
        if s is not None:
            info += f' STR={s!r}'
        print(info)

# dict walk
fields = vtable(root)[3]
vec = fields[0] + i32(fields[0])
cnt = u32(vec)
print('dict cnt', cnt)
target_key = sys.argv[1] if len(sys.argv) > 1 else 'enemy_1007_slime'
for i in range(cnt):
    slot = vec + 4 + 4 * i
    epos = slot + i32(slot)
    ef = vtable(epos)[3]
    key = None
    krel = i32(ef[0])
    key = probe_str(ef[0] + krel)
    if key == target_key:
        print(f'== entry {key} entrytable@{epos:#x}')
        show_table(epos, 'entry')
        vslot = ef[1]
        vtgt = vslot + i32(vslot)
        vcnt = u32(vtgt)
        print(f'  levels vector @{vtgt:#x} cnt={vcnt}')
        for li in range(vcnt):
            lslot = vtgt + 4 + 4 * li
            ltpos = lslot + i32(lslot)
            show_table(ltpos, f'level[{li}]', 1)
            # walk into each table field
            lf = vtable(ltpos)[3]
            for fi, fp in enumerate(lf):
                if fp is None: continue
                tgt = fp + i32(fp)
                if 0 <= tgt < size - 4:
                    try:
                        show_table(tgt, f'level[{li}].f{fi}', 2)
                    except Exception as e:
                        print(f'    level[{li}].f{fi} not table: {e}')
        break
