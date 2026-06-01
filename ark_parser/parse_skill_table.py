"""Parse Arknights skill_table FlatBuffers binary."""
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


def parse_value(data, pos, depth=0):
    if depth > 5 or pos < 0 or pos + 4 > len(data):
        return None
    rel = struct.unpack_from('<i', data, pos)[0]
    target = pos + rel
    if target < 0 or target >= len(data) - 4:
        return rel
    s = read_string(data, target)
    if s is not None:
        return s
    soff = struct.unpack_from('<i', data, target)[0]
    if soff < 0:
        vtp = target - soff
        if 0 < vtp < len(data) - 4:
            vts = struct.unpack_from('<H', data, vtp)[0]
            if 8 <= vts <= 800 and vts % 2 == 0:
                nf = (vts - 4) // 2
                if 0 < nf <= 80:
                    result = {}
                    for i in range(nf):
                        fo = struct.unpack_from('<H', data, vtp + 4 + i * 2)[0]
                        result[f'f{i}'] = parse_value(data, target + fo, depth + 1) if fo else None
                    return result
    count = struct.unpack_from('<I', data, target)[0]
    if 0 < count < 1000:
        return [parse_value(data, target + 4 + i * 4, depth + 1) for i in range(count)]
    return rel


def find_entries(data, start, end):
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
        all_zero = all(struct.unpack_from('<H', data, vtp + 4 + i * 2)[0] == 0 for i in range(2, nf))
        if not all_zero:
            continue
        fp0 = pos + fo0
        if fp0 + 4 > size:
            continue
        val0 = struct.unpack_from('<i', data, fp0)[0]
        key = read_string(data, fp0 + val0)
        if not key or len(key) > 50:
            continue
        if key in entries:
            continue
        entries[key] = (pos, fo1)
    return entries


def main():
    with open('G:/Arknights/data/tables/skill_tableafb859.bin', 'rb') as f:
        data = f.read()

    print(f'File size: {len(data)}', file=sys.stderr)

    # Scan all regions
    regions = [
        ('R0', 253360, 1345388),
        ('R1', 1357276, 1420240),
        ('R2', 1433252, 4253088),
    ]

    positions = {}
    for name, start, end in regions:
        found = find_entries(data, start, end)
        print(f'  {name}: {len(found)} entries', file=sys.stderr)
        positions.update(found)

    print(f'Total: {len(positions)} unique skills', file=sys.stderr)

    # Parse all entries
    output = {}
    total = len(positions)
    for i, (key, (table_pos, fo1)) in enumerate(sorted(positions.items())):
        if i % 200 == 0:
            print(f'  Parsing {i}/{total}...', file=sys.stderr)
        fp1 = table_pos + fo1
        output[key] = parse_value(data, fp1, depth=0)

    out_path = 'G:/Arknights/ark_parser/skills.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f'Output: {out_path} ({len(output)} skills)', file=sys.stderr)


if __name__ == '__main__':
    main()
