#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shallow field probe: print each field of a table entry with type guess."""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'enemy'))
from parse_enemy_tables import FB, read_dict, i2f


def vec_info(fb, p):
    cnt = fb.u32(p)
    return cnt


def probe(fb, tpos, indent=0, max_depth=2):
    pad = '  ' * indent
    try:
        fields = fb.table_fields(tpos)
    except ValueError as e:
        print(pad, 'BAD TABLE', e)
        return
    print(pad + f'table@{tpos:#x} fields={len(fields)}')
    for idx, fpos in enumerate(fields):
        if fpos is None:
            continue
        rel = fb.i32(fpos)
        tgt = fpos + rel
        kind = 'scalar'
        preview = ''
        if rel != 0 and 4 <= tgt < fb.size - 4:
            if fb.is_string(tgt):
                kind = 'string'
                s = fb.read_string(tgt)
                preview = repr(s[:60])
            elif fb.is_table(tgt):
                kind = 'table'
                sub = fb.table_fields(tgt)
                preview = f'fields={len(sub)}'
            else:
                cnt = fb.u32(tgt)
                if 0 < cnt < 100000 and tgt + 4 + 4 * cnt <= fb.size:
                    kind = 'vector'
                    preview = f'count={cnt}'
                    # peek first element
                    r0 = fb.i32(tgt + 4)
                    t0 = tgt + 4 + r0
                    if r0 != 0 and 4 <= t0 < fb.size - 4:
                        if fb.is_string(t0):
                            preview += ' of string, e[0]=' + repr(fb.read_string(t0)[:40])
                        elif fb.is_table(t0):
                            preview += f' of table(fields={len(fb.table_fields(t0))})'
                        else:
                            preview += f' e[0]rel={r0}'
                    else:
                        v0 = fb.i32(tgt + 4)
                        preview += f' of scalar e[0]={v0} (f={i2f(v0)})'
        print(pad + f'  f{idx}: @{fpos:#x} {kind} {preview}' if kind != 'scalar'
              else pad + f'  f{idx}: @{fpos:#x} scalar={rel} (f={i2f(rel)})')


def main():
    table = sys.argv[1]  # char or skill
    key = sys.argv[2]
    path = {'char': 'data/tables/character_table9fc534.bin',
            'skill': 'data/tables/skill_tableafb859.bin'}[table]
    fb = FB(path)
    fields = fb.table_fields(fb.root)
    vec = fields[0] + fb.i32(fields[0])
    entries = dict(read_dict(fb, vec))
    vpos = entries[key]
    rel = fb.i32(vpos)
    print(f'== {key} value slot @{vpos:#x} rel={rel}')
    probe(fb, vpos + rel)


if __name__ == '__main__':
    main()
