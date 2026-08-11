#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert official CN gamedata level JSONs into the emulator's parsed
level format.

Source: Kengxxiao/ArknightsGameData zh_CN/gamedata/levels (the human
readable LevelData export the binary parser was validated against).
The parsed binary format (extract_level_data.py) differs only in
representation:
  - mapData.map: nested list -> {rows, cols, cells}
  - tile enums: strings -> ints (dump.cs TileData enums; NONE/ALL ->
    null, matching the binary parser's absent-field output)
  - waves actionType/randomType/refreshType, route motionMode and
    checkpoint type: strings -> {"value": N, "name": S}
  - enemyDbRefs.overwrittenData: {m_defined, m_value} -> value / null
  - predefines kept in full (the parsed format only stores counts)

Only levels missing from the target dir are written (--all converts
everything, overwriting local files).
"""

import argparse
import glob
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(SCRIPT_DIR, "data")

# dump.cs enums (Torappu.TileData / SharedConsts)
HEIGHT_TYPE = {"LOWLAND": 0, "HIGHLAND": 1}
BUILDABLE_TYPE = {"NONE": None, "MELEE": 1, "RANGED": 2, "ALL": 3}
PASSABLE_MASK = {"NONE": 0, "WALK_ONLY": 1, "FLY_ONLY": 2, "ALL": 3}
PLAYER_SIDE_MASK = {"ALL": None, "SIDE_A": 2, "SIDE_B": 4, "NONE": 255}
ADV_BUILDABLE_MASK = {
    "NONE": 0, "DEFAULT": 1, "DEEP_SEA": 2, "TIDE_SEA": 4, "NIGHT": 8,
    "HIDE": 16, "WOODRD_HOLE": 32, "RIDGE_FIELD": 64, "ENEMY_FTPRG": 128,
    "RED_FOG": 256, "ACT47SIDE_DURING_BALLOON_FLOAT": 512,
    "ACT47SIDE_BANNED": 1024,
}
MOTION_MODE = {"WALK": 0, "FLY": 1}

# extract_level_data.py enum dicts, reversed for name -> value
ACTION_TYPE = {v: k for k, v in {
    0: "SPAWN", 1: "PREVIEW_CURSOR", 2: "STORY", 3: "TUTORIAL",
    4: "PLAY_BGM", 5: "DISPLAY_ENEMY_INFO", 6: "ACTIVATE_PREDEFINED",
    7: "PLAY_OPERA", 8: "TRIGGER_PREDEFINED", 9: "BATTLE_EVENTS",
    10: "WITHDRAW_PREDEFINED", 11: "DIALOG", 12: "SHOW_ALL_HIDDEN_CARDS",
    13: "EMPTY", 14: "E_NUM",
}.items()}
CHECKPOINT_TYPE = {v: k for k, v in {
    0: "MOVE", 1: "WAIT_FOR_SECONDS", 2: "WAIT_FOR_PLAY_TIME",
    3: "WAIT_CURRENT_FRAGMENT_TIME", 4: "WAIT_CURRENT_WAVE_TIME",
    5: "DISAPPEAR", 6: "APPEAR_AT_POS", 7: "ALERT", 8: "PATROL_MOVE",
    9: "WAIT_BOSSRUSH_WAVE", 10: "MAP_OFFSET_MOVE", 11: "INVALID",
}.items()}
RANDOM_TYPE = {v: k for k, v in {
    0: "ALWAYS", 1: "PER_DAY", 2: "NEVER", 3: "PER_SETTLE_DAY",
    4: "PER_SEASON",
}.items()}
DIFFICULTY = {v: k for k, v in {
    0: "NONE", 1: "NORMAL", 2: "FOUR_STAR", 4: "EASY", 8: "SIX_STAR",
    15: "ALL",
}.items()}
BUILDABLE_MASK = {"NONE": 0, "MELEE": 1, "RANGED": 2, "ALL": 3}


def _enum(v, table):
    """str enum -> {"value": N, "name": S}; dicts pass through."""
    if isinstance(v, dict) or v is None:
        return v
    if isinstance(v, str):
        n = table.get(v)
        if n is not None:
            return {"value": n, "name": v}
    return v


def _unwrap(v):
    """{m_defined, m_value} -> value / null (recursive)."""
    if isinstance(v, dict):
        if "m_defined" in v:
            return v.get("m_value") if v.get("m_defined") else None
        return {k: _unwrap(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_unwrap(x) for x in v]
    return v


def convert_level(d):
    """Mutate an official level dict into the parsed representation."""
    m = d.get("mapData")
    if isinstance(m, dict):
        grid = m.get("map")
        if isinstance(grid, list) and grid and isinstance(grid[0], list):
            rows = len(grid)
            cols = len(grid[0]) if rows else 0
            m["map"] = {"rows": rows, "cols": cols,
                        "cells": [c for row in grid for c in row]}
        elif grid is None:
            m["map"] = {"rows": 0, "cols": 0, "cells": []}
        for t in m.get("tiles") or []:
            if not isinstance(t, dict):
                continue
            if isinstance(t.get("heightType"), str):
                t["heightType"] = HEIGHT_TYPE.get(t["heightType"])
            if isinstance(t.get("buildableType"), str):
                t["buildableType"] = BUILDABLE_TYPE.get(t["buildableType"])
            if isinstance(t.get("passableMask"), str):
                t["passableMask"] = PASSABLE_MASK.get(t["passableMask"])
            if isinstance(t.get("playerSideMask"), str):
                t["playerSideMask"] = PLAYER_SIDE_MASK.get(
                    t["playerSideMask"])
            if isinstance(t.get("advancedBuildableMask"), str):
                t["advancedBuildableMask"] = ADV_BUILDABLE_MASK.get(
                    t["advancedBuildableMask"])
    for w in d.get("waves") or []:
        if not isinstance(w, dict):
            continue
        for fr in w.get("fragments") or []:
            if not isinstance(fr, dict):
                continue
            for a in fr.get("actions") or []:
                if not isinstance(a, dict):
                    continue
                a["actionType"] = _enum(a.get("actionType"), ACTION_TYPE)
                a["randomType"] = _enum(a.get("randomType"), RANDOM_TYPE)
                a["refreshType"] = _enum(a.get("refreshType"), RANDOM_TYPE)
    for r in d.get("routes") or []:
        if not isinstance(r, dict):
            continue
        if isinstance(r.get("motionMode"), str):
            r["motionMode"] = _enum(r["motionMode"], MOTION_MODE)
        for cp in r.get("checkpoints") or []:
            if isinstance(cp, dict):
                cp["type"] = _enum(cp.get("type"), CHECKPOINT_TYPE)
    for e in d.get("enemyDbRefs") or []:
        if not isinstance(e, dict):
            continue
        if isinstance(e.get("overwrittenData"), dict):
            e["overwrittenData"] = _unwrap(e["overwrittenData"])
    for r in (d.get("runes") or []) + (d.get("optionalRunes") or []):
        if not isinstance(r, dict):
            continue
        if isinstance(r.get("difficultyMask"), str):
            r["difficultyMask"] = _enum(r["difficultyMask"], DIFFICULTY)
        if isinstance(r.get("buildableMask"), str):
            r["buildableMask"] = BUILDABLE_MASK.get(r["buildableMask"])
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True,
                    help="official gamedata levels dir (recursive)")
    ap.add_argument("--out", default=os.path.join(DATA, "levels"))
    ap.add_argument("--index", default=os.path.join(DATA,
                                                     "level_data_index.json"))
    ap.add_argument("--all", action="store_true",
                    help="convert every level (overwrite existing)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    existing = {os.path.splitext(f)[0] for f in os.listdir(args.out)
                if f.endswith(".json")}
    files = sorted(
        f for f in glob.glob(os.path.join(args.src, "**", "*.json"),
                             recursive=True)
        if os.path.basename(f).startswith("level_")
        and not os.path.basename(f).startswith("level_enemydata")
        and "dialog" not in os.path.basename(f))
    converted = []
    skipped = failed = 0
    for path in files:
        name = os.path.splitext(os.path.basename(path))[0]
        if not args.all and name in existing:
            skipped += 1
            continue
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            convert_level(d)
            d["_meta"] = {"file": os.path.basename(path),
                          "size": os.path.getsize(path),
                          "source": "official_gamedata"}
            with open(os.path.join(args.out, name + ".json"), "w",
                      encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            converted.append(name)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"[ERR] {name}: {exc}")

    if converted and args.index:
        try:
            with open(args.index, encoding="utf-8") as f:
                idx = json.load(f)
        except Exception:
            idx = []
        have = {e.get("levelId") for e in idx if isinstance(e, dict)}
        for name in converted:
            if name not in have:
                idx.append({"levelId": name, "file": name + ".json",
                            "size": 0, "signHeader": 0,
                            "source": "official_gamedata"})
        with open(args.index, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False)

    print(f"converted={len(converted)} skipped={skipped} failed={failed}")
    if converted:
        print("new levels:", ", ".join(converted[:15]),
              ("..." if len(converted) > 15 else ""))


if __name__ == "__main__":
    main()
