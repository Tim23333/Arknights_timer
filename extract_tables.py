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


def main():
    if not ANON_DIR.exists():
        print(f"Error: {ANON_DIR} not found")
        print("Please extract AB files using AssetStudio-Arknights first")
        return

    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    # Clear old tables
    for old in TABLES_DIR.glob("*.bin"):
        old.unlink()

    print(f"Scanning {ANON_DIR} for data tables...\n")

    found = {}
    min_size = 4 * 1024  # 4KB（热更小表如 hotupdate_meta 只有几 KB）

    # 按目录名排序扫描，后扫到的覆盖先扫到的：
    # 命名约定 base_* < zz_hot_*，保证热更表覆盖基础包同名表。
    for bin_dir in sorted(ANON_DIR.glob("*.bin_unpacked")):
        for cab_file in bin_dir.glob("CAB-*"):
            if not cab_file.is_file():
                continue
            if cab_file.stat().st_size < min_size:
                continue

            table_id = scan_cab_file(cab_file)
            if table_id:
                found[table_id] = cab_file

    # Copy found tables
    for table_id, src in sorted(found.items()):
        dst = TABLES_DIR / f"{table_id}.bin"
        shutil.copy2(src, dst)
        size_mb = src.stat().st_size / (1024 * 1024)
        print(f"  {table_id} ({size_mb:.1f} MB)")

    print(f"\nDone: Extracted {len(found)} tables to {TABLES_DIR}")


if __name__ == "__main__":
    main()
