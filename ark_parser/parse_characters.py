"""Arknights character_table parser - fast scan + selective deep parse."""
import struct
import json
import sys


def read_string(data, pos):
    if pos < 0 or pos + 4 > len(data):
        return None
    strlen = struct.unpack_from('<I', data, pos)[0]
    if strlen == 0 or strlen > 50000 or pos + 4 + strlen > len(data):
        return None
    raw = data[pos + 4:pos + 4 + strlen]
    try:
        s = raw.decode('utf-8')
        if sum(1 for c in s if c.isprintable() or c in '\n\t') < len(s) * 0.5:
            return None
        return s
    except:
        return None


def read_field_shallow(data, table_pos, field_offset):
    """Read a field value without deep recursion."""
    if field_offset == 0:
        return None
    fp = table_pos + field_offset
    if fp + 4 > len(data):
        return None

    rel = struct.unpack_from('<i', data, fp)[0]
    target = fp + rel

    if target < 0 or target >= len(data) - 4:
        return rel

    # Try string
    s = read_string(data, target)
    if s is not None:
        return s

    # Try table (negative soffset)
    soff = struct.unpack_from('<i', data, target)[0]
    if soff < 0:
        vtp = target - soff
        if 0 < vtp < len(data) - 4:
            vts = struct.unpack_from('<H', data, vtp)[0]
            if 8 <= vts <= 800 and vts % 2 == 0:
                nf = (vts - 4) // 2
                if 0 < nf <= 80:
                    return {'_t': target, 'nf': nf}

    # Try vector
    count = struct.unpack_from('<I', data, target)[0]
    if 0 < count < 5000:
        return {'_v': target, 'n': count}

    return rel


def parse_table_deep(data, table_pos, nf, depth=0, max_depth=3):
    """Deep parse a table with recursion limit."""
    if depth > max_depth:
        return '<max_depth>'

    # Find vtable
    soff = struct.unpack_from('<i', data, table_pos)[0]
    if soff >= 0:
        return None
    vtp = table_pos - soff
    if vtp < 0 or vtp >= len(data) - 4:
        return None
    vts = struct.unpack_from('<H', data, vtp)[0]
    actual_nf = (vts - 4) // 2

    result = {}
    for i in range(min(nf, actual_nf)):
        fo = struct.unpack_from('<H', data, vtp + 4 + i * 2)[0]
        if fo == 0:
            result[f'f{i}'] = None
            continue

        fp = table_pos + fo
        if fp + 4 > len(data):
            result[f'f{i}'] = None
            continue

        rel = struct.unpack_from('<i', data, fp)[0]
        target = fp + rel

        if target < 0 or target >= len(data) - 4:
            result[f'f{i}'] = rel
            continue

        # String
        s = read_string(data, target)
        if s is not None:
            result[f'f{i}'] = s
            continue

        # Table
        soff2 = struct.unpack_from('<i', data, target)[0]
        if soff2 < 0:
            vtp2 = target - soff2
            if 0 < vtp2 < len(data) - 4:
                vts2 = struct.unpack_from('<H', data, vtp2)[0]
                if 8 <= vts2 <= 800 and vts2 % 2 == 0:
                    nf2 = (vts2 - 4) // 2
                    if 0 < nf2 <= 80:
                        result[f'f{i}'] = parse_table_deep(data, target, nf2, depth + 1, max_depth)
                        continue

        # Vector
        count = struct.unpack_from('<I', data, target)[0]
        if 0 < count < 500:
            vec = []
            for j in range(count):
                ep = target + 4 + j * 4
                if ep + 4 > len(data):
                    vec.append(None)
                    continue
                erel = struct.unpack_from('<i', data, ep)[0]
                etarget = ep + erel
                es = read_string(data, etarget)
                if es is not None:
                    vec.append(es)
                else:
                    vec.append(erel)
            result[f'f{i}'] = vec
            continue

        result[f'f{i}'] = rel

    return result


def find_entries(data, start, end):
    """Find dictionary entries. Returns {char_id: (table_pos, fo1)}."""
    entries = {}
    size = len(data)

    for pos in range(start, min(end, size - 8), 4):
        soff = struct.unpack_from('<i', data, pos)[0]
        if soff >= 0 or soff < -size:
            continue
        vtp = pos - soff
        if vtp < 0 or vtp >= size - 8:
            continue
        vts = struct.unpack_from('<H', data, vtp)[0]
        if vts < 8 or vts > 200 or vts % 2 != 0:
            continue
        nf = (vts - 4) // 2
        if nf < 2:
            continue
        obs = struct.unpack_from('<H', data, vtp + 2)[0]
        if obs < 4 or obs > 100000:
            continue

        fo0 = struct.unpack_from('<H', data, vtp + 4)[0]
        fo1 = struct.unpack_from('<H', data, vtp + 6)[0]
        if fo0 == 0 or fo1 == 0:
            continue

        # Check extra fields are zero
        all_zero = True
        for i in range(2, nf):
            if struct.unpack_from('<H', data, vtp + 4 + i * 2)[0] != 0:
                all_zero = False
                break
        if not all_zero:
            continue

        fp0 = pos + fo0
        if fp0 + 4 > size:
            continue
        val0 = struct.unpack_from('<i', data, fp0)[0]
        char_id = read_string(data, fp0 + val0)
        if not char_id or not char_id.startswith('char_') or len(char_id) > 30:
            continue
        if char_id in entries:
            continue

        entries[char_id] = (pos, fo1)

    return entries


# CharacterData field names (verified from actual binary data)
FIELD_NAMES = [
    'f0_vector', 'f1_int', 'f2_vector', 'f3_enum', 'f4_int',
    'f5_packed', 'f6_vector', 'f7_vector',
    'subProfessionId',  # 8: e.g. "counsellor", "corecaster"
    'f9_vector', 'f10_vector',
    'prefabKey',  # 11: e.g. "p_char_1045_svash2"
    'f12_vector',
    'nationId',  # 13: e.g. "kjerag", "rhodes"
    'name',  # 14: Chinese name, e.g. "凛御银灰"
    'f15_int',
    'description',  # 16: Chinese description
    'itemObtainApproach',  # 17: e.g. "招募寻访"
    'itemDesc',  # 18: Chinese item description
    'f19_misc',
    'f20_vector',
    'displayNumber',  # 21: e.g. "KJ01", "R001"
    'traitDesc',  # 22: Chinese trait description
    'nameEn',  # 23: e.g. "SilverAsh the Reignfrost"
    'f24_vector',
    'f25_int', 'f26_int', 'f27_int', 'f28_int', 'f29_int',
    'f30_int', 'f31_int', 'f32_int', 'f33_int',
    'f34_misc', 'f35_vector', 'f36_int',
    'talentData',  # 37: talent tables
    'f38_int', 'f39_int',
    'f40_table',
    'pot0_desc',  # 41: e.g. "-6"
    'pot0_value',  # 42: e.g. 20
    'f43_misc', 'f44_int', 'f45_int', 'pot0_id', 'f47_int',
    'f48_misc', 'f49_vector', 'f50_int',
    'f51_table',
    'f52_int', 'f53_int',
    'f54_table',
    'pot1_desc',  # 55: e.g. "-5"
    'pot1_value',  # 56: e.g. 20
    'f57_misc', 'f58_int', 'f59_int', 'pot1_id', 'f61_int',
    'f62_misc', 'f63_vector', 'f64_int',
    'f65_table',
    'f66_int', 'f67_int',
    'f68_table',
    'pot2_desc',  # 69: e.g. "-4"
    'pot2_value',  # 70: e.g. 20
    'f71_misc', 'f72_int', 'f73_int', 'pot2_id', 'f75_int',
]


def main():
    table_file = 'G:/Arknights/data/tables/character_tabled88efb.bin'
    if len(sys.argv) > 1:
        table_file = sys.argv[1]

    with open(table_file, 'rb') as f:
        data = f.read()

    print(f'File size: {len(data)}', file=sys.stderr)

    # Step 1: Find all entries
    print('Scanning...', file=sys.stderr)
    positions = {}
    for name, start, end in [('R0', 311764, 338788), ('R1', 500576, 2319636),
                              ('G1', 4676, 311764), ('G2', 338788, 500576)]:
        found = find_entries(data, start, end)
        print(f'  {name}: {len(found)}', file=sys.stderr)
        positions.update(found)
    print(f'Total: {len(positions)}', file=sys.stderr)

    # Step 2: Shallow parse all entries
    output = {}
    total = len(positions)
    for i, (char_id, (table_pos, fo1)) in enumerate(sorted(positions.items())):
        if i % 100 == 0:
            print(f'  Parsing {i}/{total}...', file=sys.stderr)

        fp1 = table_pos + fo1
        if fp1 + 4 > len(data):
            output[char_id] = None
            continue

        rel = struct.unpack_from('<i', data, fp1)[0]
        target = fp1 + rel

        if target < 0 or target >= len(data) - 4:
            output[char_id] = rel
            continue

        # Check if it's a table
        soff = struct.unpack_from('<i', data, target)[0]
        if soff < 0:
            vtp = target - soff
            if 0 < vtp < len(data) - 4:
                vts = struct.unpack_from('<H', data, vtp)[0]
                if 8 <= vts <= 800 and vts % 2 == 0:
                    nf = (vts - 4) // 2
                    result = {}
                    for fi in range(nf):
                        fo = struct.unpack_from('<H', data, vtp + 4 + fi * 2)[0]
                        result[FIELD_NAMES[fi] if fi < len(FIELD_NAMES) else f'f{fi}'] = \
                            read_field_shallow(data, target, fo)
                    output[char_id] = result
                    continue

        # Check if it's a vector
        count = struct.unpack_from('<I', data, target)[0]
        if 0 < count < 500:
            result = {}
            for fi in range(count):
                ep = target + 4 + fi * 4
                if ep + 4 > len(data):
                    result[FIELD_NAMES[fi] if fi < len(FIELD_NAMES) else f'f{fi}'] = None
                    continue
                rel2 = struct.unpack_from('<i', data, ep)[0]
                target2 = ep + rel2
                if target2 < 0 or target2 >= len(data) - 4:
                    result[FIELD_NAMES[fi] if fi < len(FIELD_NAMES) else f'f{fi}'] = rel2
                    continue
                s = read_string(data, target2)
                if s is not None:
                    result[FIELD_NAMES[fi] if fi < len(FIELD_NAMES) else f'f{fi}'] = s
                else:
                    # Check for nested table/vector
                    soff2 = struct.unpack_from('<i', data, target2)[0]
                    if soff2 < 0:
                        vtp2 = target2 - soff2
                        if 0 < vtp2 < len(data) - 4:
                            vts2 = struct.unpack_from('<H', data, vtp2)[0]
                            if 8 <= vts2 <= 800 and vts2 % 2 == 0:
                                nf2 = (vts2 - 4) // 2
                                result[FIELD_NAMES[fi] if fi < len(FIELD_NAMES) else f'f{fi}'] = {'_t': target2, 'nf': nf2}
                                continue
                    count2 = struct.unpack_from('<I', data, target2)[0]
                    if 0 < count2 < 500:
                        result[FIELD_NAMES[fi] if fi < len(FIELD_NAMES) else f'f{fi}'] = {'_v': target2, 'n': count2}
                        continue
                    result[FIELD_NAMES[fi] if fi < len(FIELD_NAMES) else f'f{fi}'] = rel2
            output[char_id] = result
            continue

        output[char_id] = rel

    out_path = 'G:/Arknights/ark_parser/characters.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f'Output: {out_path} ({len(output)} characters)', file=sys.stderr)


if __name__ == '__main__':
    main()
