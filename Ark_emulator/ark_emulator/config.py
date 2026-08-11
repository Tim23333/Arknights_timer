"""Simulation configuration: level selection, squad, custom enemies.

This is the public input contract for the simulator UI/AI layer:
  - level_id / stage_id : which level to load
  - squad              : list of {char_id, level, potential, skill_levels}
  - custom_enemies     : override/add enemies in a level
  - seed               : deterministic RNG seed
"""

import io
import json
import os


def list_levels(data_dir=None):
    """Return available level ids (from stage_sim_bundle)."""
    from .loader import DataStore
    store = DataStore(data_dir) if data_dir else DataStore()
    return sorted(store.bundle.get("levels", {}).keys())


def list_stages(data_dir=None):
    """Return stage id -> level id mapping (filtered to playable stages)."""
    from .loader import DataStore
    store = DataStore(data_dir) if data_dir else DataStore()
    stages = store.bundle.get("stages") or {}
    out = {}
    for sid, info in stages.items():
        lid = info.get("levelId") if isinstance(info, dict) else None
        if lid:
            out[sid] = lid
    return out


def search_levels(keyword, data_dir=None):
    """Search levels by keyword (stage/level name, id fragment)."""
    from .loader import DataStore
    store = DataStore(data_dir) if data_dir else DataStore()
    stages = store.bundle.get("stages") or {}
    hits = []
    kw = keyword.lower()
    for sid, info in stages.items():
        lid = info.get("levelId") if isinstance(info, dict) else None
        name = info.get("name") if isinstance(info, dict) else ""
        if lid and (kw in sid.lower() or kw in lid.lower() or
                    kw in str(name).lower()):
            hits.append({"stageId": sid, "levelId": lid, "name": name})
    return hits


def squad_from_file(path):
    """Load squad config from JSON file:
    [{"charId": "char_002_amiya", "level": 50, "potential": 0,
      "skillLevels": [7, 7, 7], "phase": 2,
      "moduleId": "uniequip_002_amiya", "moduleLevel": 3}]"""
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def save_squad(squad, path):
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(squad, f, ensure_ascii=False, indent=1)
