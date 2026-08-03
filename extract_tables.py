"""Extract Arknights data tables from unpacked AB files.

Usage:
    python extract_tables.py

Scans data/anon/ for CAB files and extracts known data tables to data/tables/.
Table identifiers are matched by prefix (hash suffix may change between game versions).
"""

import os
import re
import shutil
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
]

# Compiled pattern: match any table prefix followed by hex hash
TABLE_PATTERN = re.compile(rf"({'|'.join(TABLE_PREFIXES)})[a-f0-9]{{4,}}")


def scan_cab_file(filepath: Path) -> str | None:
    """Read first 8KB of file and extract table identifier."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(8192)
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
    min_size = 512 * 1024  # 512KB

    # Scan all unpacked AB directories
    for bin_dir in ANON_DIR.glob("*.bin_unpacked"):
        for cab_file in bin_dir.glob("CAB-*"):
            if not cab_file.is_file():
                continue
            if cab_file.stat().st_size < min_size:
                continue

            table_id = scan_cab_file(cab_file)
            if table_id and table_id not in found:
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
