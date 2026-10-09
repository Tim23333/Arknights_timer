"""Extract Arknights data tables from unpacked AB files.

Usage:
    python extract_tables.py

Scans data/anon/ for CAB files and extracts known data tables to data/tables/.
Table identifiers are matched by prefix (hash suffix may change between game versions).
"""

import os
import re
import shutil
import struct
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
ANON_DIR = SCRIPT_DIR / "data" / "anon"
TABLES_DIR = SCRIPT_DIR / "data" / "tables"

# Known table name prefixes (hash suffix changes between game versions)
TABLE_PREFIXES = [
    "character_table",
    "skill_table",
    "stage_table",
    "activity_table",
    "charword_table",
    "handbook_info_table",
    "uniequip_table",
    "battle_equip_table",
    "skin_table",
    "retro_table",
    "roguelike_topic_table",
    "sandbox_perm_table",
    "building_data",
    "enemy_handbook_table",
    "enemy_database",
    # 热更包中出现的补充表（PersistentData/Bundles/anon 解包）
    "item_table",
    "gacha_table",
    "medal_table",
    "story_table",
    "zone_table",
    "shop_client_table",
    "climb_tower_table",
    "arkvent_table",
    "battle_misc_table",
    "display_meta_table",
    "extra_battlelog_table",
    "hotupdate_meta_table",
]

# Compiled pattern: match any table prefix followed by hex hash
TABLE_PATTERN = re.compile(rf"({'|'.join(TABLE_PREFIXES)})[a-f0-9]{{4,}}")
TABLE_FULL_PATTERN = re.compile(
    rf"^({'|'.join(TABLE_PREFIXES)})[a-f0-9]{{4,}}$")


def scan_cab_file(filepath: Path) -> str | None:
    """Read first 8KB of file and extract table identifier."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(8192)
        # exportRaw 剥离版以 [u32 名称长度][表名] 开头。优先按长度精确读取，
        # 避免签名头首字节恰为 ASCII 十六进制字符时被正则误拼进表 ID。
        if len(header) >= 4:
            name_len = struct.unpack_from("<I", header, 0)[0]
            if 0 < name_len <= 256 and 4 + name_len <= len(header):
                table_id = header[4:4 + name_len].decode("ascii", errors="ignore")
                if TABLE_FULL_PATTERN.fullmatch(table_id):
                    return table_id
        # Find ASCII strings in header
        text = header.decode("ascii", errors="ignore")
        match = TABLE_PATTERN.search(text)
        return match.group(0) if match else None
    except Exception:
        return None


def extract_tables(sources, output: Path, *, stable_names=True):
    """Merge sources in supplied priority order, keyed by logical table prefix."""
    found = {}
    for source in sources:
        source = Path(source)
        candidates = sorted(source.rglob('*')) if source.is_dir() else [source]
        for path in candidates:
            if not path.is_file() or path.stat().st_size < 4:
                continue
            if not (path.name.startswith('CAB-') or path.suffix in ('.dat', '.bin')):
                continue
            table_id = scan_cab_file(path)
            if table_id:
                prefix = TABLE_FULL_PATTERN.fullmatch(table_id).group(1)
                found[prefix] = (table_id, path)
    if not found:
        raise ValueError('No valid exportRaw tables found; existing output was preserved')
    output.mkdir(parents=True, exist_ok=True)
    provenance = {}
    for prefix, (table_id, source) in sorted(found.items()):
        name = prefix if stable_names else table_id
        destination = output / f'{name}.bin'
        shutil.copy2(source, destination)
        # Only remove superseded versions of this logical table after a valid copy.
        for previous in output.glob(f'{prefix}*.bin'):
            if previous != destination and re.fullmatch(
                    re.escape(prefix) + r'(?:[a-fA-F0-9]+)?\.bin', previous.name):
                previous.unlink()
        provenance[prefix] = {'table_id': table_id, 'source': str(source),
                              'file': destination.name}
    return provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, action='append',
                        help='Ordered exportRaw directories; later sources override earlier ones')
    parser.add_argument('--out', type=Path, default=TABLES_DIR)
    args = parser.parse_args(argv)
    if args.source:
        rows = extract_tables(args.source, args.out)
        print(f'Extracted {len(rows)} logical tables -> {args.out}')
        return rows
    if not ANON_DIR.exists():
        print(f"Error: {ANON_DIR} not found")
        print("Please extract AB files using AssetStudio-Arknights first")
        return

    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {ANON_DIR} for data tables...\n")

    found = extract_tables(sorted(ANON_DIR.glob('*.bin_unpacked')), args.out)
    print(f"\nDone: Extracted {len(found)} tables to {args.out}")
    return found


if __name__ == "__main__":
    main()
