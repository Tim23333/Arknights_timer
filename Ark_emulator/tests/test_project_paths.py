"""Portable repository-relative path tests."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator.loader import DataStore
from ark_emulator.project_paths import (
    CHARACTER_DATA_DIR,
    ENEMY_DATA_DIR,
    LEVEL_ASSETS_INDEX,
    PROJECT_ROOT,
    resolve_project_path,
)


def test_default_data_paths_follow_current_checkout():
    expected_root = Path(__file__).resolve().parents[2]
    assert PROJECT_ROOT == expected_root
    assert ENEMY_DATA_DIR == expected_root / "ark_parser" / "enemy" / "data"
    assert CHARACTER_DATA_DIR == expected_root / "ark_parser" / "character" / "data"
    assert Path(DataStore().data_dir) == ENEMY_DATA_DIR


def test_level_asset_index_contains_only_project_relative_paths():
    index = json.loads(LEVEL_ASSETS_INDEX.read_text(encoding="utf-8"))
    assert index
    assert all(not Path(value).is_absolute() for value in index.values())
    assert all(value.startswith("unpack_work/") for value in index.values())


def test_relative_index_path_resolves_from_project_root():
    relative = "unpack_work/level_assets_full/example.bytes"
    assert resolve_project_path(relative) == PROJECT_ROOT / relative
