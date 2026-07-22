"""Deep parse a specific character entry from character_table."""
import os
import struct
import json
import sys

MAX_DEPTH = 6


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


def parse_value(data, pos, depth=0):
    """Recursively parse a FlatBuffers value."""
    if depth > MAX_DEPTH or pos < 0 or pos + 4 > len(data):
        return None

    rel = struct.unpack_from('<i', data, pos)[0]
    target = pos + rel

    if target < 0 or target >= len(data) - 4:
        return rel

    # String
    s = read_string(data, target)
    if s is not None:
        return s

    # Table (negative soffset → vtable)
    soff = struct.unpack_from('<i', data, target)[0]
    if soff < 0:
        vtp = target - soff
        if 0 < vtp < len(data) - 4:
            vts = struct.unpack_from('<H', data, vtp)[0]
            if 8 <= vts <= 800 and vts % 2 == 0:
                nf = (vts - 4) // 2
                if 0 < nf <= 80:
                    return parse_table(data, target, vtp, nf, depth + 1)

    # Vector
    count = struct.unpack_from('<I', data, target)[0]
    if 0 < count < 1000:
        return parse_vector(data, target, count, depth + 1)

    return rel


def parse_table(data, table_pos, vtp, nf, depth=0):
    """Recursively parse a FlatBuffers table."""
    result = {}
    for i in range(nf):
        fo = struct.unpack_from('<H', data, vtp + 4 + i * 2)[0]
        if fo == 0:
            result[f'f{i}'] = None
        else:
            result[f'f{i}'] = parse_value(data, table_pos + fo, depth)
    return result


def parse_vector(data, vec_pos, count, depth=0):
    """Recursively parse a FlatBuffers vector."""
    result = []
    for i in range(count):
        ep = vec_pos + 4 + i * 4
        if ep + 4 > len(data):
            result.append(None)
            continue
        result.append(parse_value(data, ep, depth))
    return result


def find_entry(data, char_id):
    """Find a specific character entry and return its data table position."""
    size = len(data)

    # Scan all regions (full file range)
    regions = [(4000, size - 8)]

    for start, end in regions:
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
            found_id = read_string(data, fp0 + val0)
            if found_id == char_id:
                return (pos, fo1)

    return None


def main():
    char_id = 'char_1045_svash2'
    if len(sys.argv) > 1:
        char_id = sys.argv[1]

    with open('G:/Arknights/data/tables/character_tabled88efb.bin', 'rb') as f:
        data = f.read()

    print(f'Searching for {char_id}...', file=sys.stderr)
    result = find_entry(data, char_id)
    if result is None:
        print(f'Character {char_id} not found!', file=sys.stderr)
        return

    table_pos, fo1 = result
    print(f'Found at table_pos={table_pos}, fo1={fo1}', file=sys.stderr)

    # Deep parse the character data
    fp1 = table_pos + fo1
    parsed = parse_value(data, fp1, depth=0)

    # Output to folder named after character ID
    out_dir = f'G:/Arknights/ark_parser/{char_id}'
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f'{char_id}_deep.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False, default=str)
    print(f'Output: {out_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
