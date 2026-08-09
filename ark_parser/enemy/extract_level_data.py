#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract Arknights LevelData assets to JSON (research artifact).

Level TextAssets are exported from the game AB bundles by ArknightsStudioCLI:
    ArknightsStudioCLI.exe "<game>/StreamingAssets/AB/Windows/anon" \
        -t textAsset --filter-by-name "level_" -g none -o <src>

Level file format (Only Sign, confirmed against CN gamedata reference JSONs):
    [128B signature header] + FlatBuffers LevelData
The 128-byte header is stripped when present; payload is parsed with the
shared FB reader (extract_enemy_data.FB) plus bounded schema parsers below.

Root field mapping (verified on level_main_01-01 vs
ArknightsAssets/ArknightsGamedata cn/gamedata/levels/obt/main/*.json):
    0 options, 1 levelId, 2 mapId, 3 bgmEvent, 4 environmentSe, 5 mapData,
    6 tilesDisallowToLocate, 7 runes, 8 optionalRunes, 9 globalBuffs,
    10 routes, 11 extraRoutes, 12 enemies, 13 enemyDbRefs, 14 waves,
    15 branches, 16 predefines, 17 hardPredefines, 18 excludeCharIdList,
    19 randomSeed, 20 operaConfig, 21 cameraPlugin.

Parsing is strictly bounded (node budget + shallow dedicated parsers for
mapData/routes/predefines) so the bulk run stays fast and output stays small.

Usage:
    python extract_level_data.py [--src DIR] [--out DIR] [--limit N]
                                 [--level ID] [--raw] [--budget N]
"""

import argparse
import json
import os
import struct
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import extract_enemy_data as E  # noqa: E402

FB = E.FB
i2f = E.i2f
parse_blackboard = E.parse_blackboard
parse_enemy_data = E.parse_enemy_data

DEFAULT_SRC = r"G:\Arknights\unpack_work\level_assets_all"
DEFAULT_OUT = os.path.join(SCRIPT_DIR, "data", "levels")

LEVEL_NAMES = [
    "options", "levelId", "mapId", "bgmEvent", "environmentSe", "mapData",
    "tilesDisallowToLocate", "runes", "optionalRunes", "globalBuffs", "routes",
    "extraRoutes", "enemies", "enemyDbRefs", "waves", "branches", "predefines",
    "hardPredefines", "excludeCharIdList", "randomSeed", "operaConfig",
    "cameraPlugin",
]

ACTION_TYPE = {0: "SPAWN", 1: "PREVIEW_CURSOR", 2: "STORY", 3: "TUTORIAL",
               4: "PLAY_BGM", 5: "DISPLAY_ENEMY_INFO", 6: "ACTIVATE_PREDEFINED",
               7: "PLAY_OPERA", 8: "TRIGGER_PREDEFINED", 9: "BATTLE_EVENTS",
               10: "WITHDRAW_PREDEFINED", 11: "DIALOG", 12: "SHOW_ALL_HIDDEN_CARDS",
               13: "EMPTY", 14: "E_NUM"}
CHECKPOINT_TYPE = {0: "MOVE", 1: "WAIT_FOR_SECONDS", 2: "WAIT_FOR_PLAY_TIME",
                   3: "WAIT_CURRENT_FRAGMENT_TIME", 4: "WAIT_CURRENT_WAVE_TIME",
                   5: "DISAPPEAR", 6: "APPEAR_AT_POS", 7: "ALERT",
                   8: "PATROL_MOVE", 9: "WAIT_BOSSRUSH_WAVE",
                   10: "MAP_OFFSET_MOVE", 11: "INVALID"}
DIFFICULTY = {0: "NONE", 1: "NORMAL", 2: "FOUR_STAR", 4: "EASY",
              8: "SIX_STAR", 15: "ALL"}
MOTION_MODE = {0: "WALK", 1: "FLY", 2: "E_NUM"}
SOURCE_APPLY_WAY = {0: "NONE", 1: "MELEE", 2: "RANGED", 3: "ALL"}
SP_TYPE = {0: "NONE", 1: "INCREASE_WITH_TIME", 2: "INCREASE_WHEN_ATTACK",
           4: "INCREASE_WHEN_TAKEN_DAMAGE", 6: "ATTACK_OR_DAMAGE", 7: "ALL"}
RANDOM_TYPE = {0: "ALWAYS", 1: "PER_DAY", 2: "NEVER", 3: "PER_SETTLE_DAY", 4: "PER_SEASON"}


class BudgetExceeded(Exception):
    pass


class LevelFB(FB):
    """FB reader over a level payload with a node budget guard."""

    def __init__(self, data, path="<level>", budget=200000):
        self.path = path
        self.d = data
        self.size = len(data)
        self.start = 0
        self.root = self.u32(0)
        self.budget = budget
        self.node_count = 0

    def _bump(self):
        self.node_count += 1
        if self.node_count > self.budget:
            raise BudgetExceeded()

    def parse_table(self, tpos, depth=0):
        self._bump()
        return super().parse_table(tpos, depth)

    def parse_value(self, pos, depth=0):
        self._bump()
        return super().parse_value(pos, depth)


def _str(fb, f, i):
    if i >= len(f) or f[i] is None:
        return None
    t = fb.target_of(f[i])
    if fb.is_string(t):
        return fb.read_string(t)
    return None


def _int(fb, f, i):
    if i >= len(f) or f[i] is None:
        return None
    return fb.i32(f[i])


def _bool(fb, f, i):
    v = _int(fb, f, i)
    return bool(v) if v is not None else None


def _bool_byte(fb, f, i):
    """1-byte inline bool (custom FB stores bools as single bytes; reading
    them as i32 leaks adjacent bytes - see 10_level_schema_calibration.md)."""
    if i >= len(f) or f[i] is None:
        return False
    pos = f[i]
    if 0 <= pos < fb.size:
        return fb.d[pos] != 0
    return False


def _float(fb, f, i):
    v = _int(fb, f, i)
    return i2f(v) if v is not None else None


def _enum(fb, f, i, table):
    v = _int(fb, f, i)
    if v is None:
        return None
    return {"value": v, "name": table.get(v, "?")}


def _vec(fb, f, i):
    if i >= len(f) or f[i] is None:
        return None
    t = fb.target_of(f[i])
    if not fb.is_vector(t):
        return None
    return fb.vector(t)


def _vec_len(fb, f, i):
    v = _vec(fb, f, i)
    return len(v) if v is not None else 0


def parse_grid_position(fb, pos):
    f = fb.table_fields(pos)
    return {"row": _int(fb, f, 0) or 0, "col": _int(fb, f, 1) or 0}


def parse_vector2(fb, pos):
    f = fb.table_fields(pos)
    return {"x": _float(fb, f, 0) or 0.0, "y": _float(fb, f, 1) or 0.0}


def parse_options(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    fields = [("characterLimit", "i"), ("maxLifePoint", "i"), ("initialCost", "i"),
              ("maxCost", "i"), ("costIncreaseTime", "f"), ("moveMultiplier", "f"),
              ("steeringEnabled", "b"), ("isTrainingLevel", "b"),
              ("isHardTrainingLevel", "b"), ("isPredefinedCardsSelectable", "b"),
              ("displayRestTime", "b"), ("maxPlayTime", "f"),
              ("functionDisableMask", "i"), ("configBlackBoard", "bb"),
              ("enemyTauntLevelPow", "i"), ("deployCostPostDelta", "i"),
              ("deployCostPostDeltaMinCost", "i")]
    for i, (nm, kind) in enumerate(fields):
        if i >= len(f) or f[i] is None:
            continue
        if kind == "i":
            out[nm] = _int(fb, f, i)
        elif kind == "f":
            out[nm] = _float(fb, f, i)
        elif kind == "b":
            out[nm] = _bool(fb, f, i)
        elif kind == "bb":
            t = fb.target_of(f[i])
            out[nm] = parse_blackboard(fb, t) if fb.is_vector(t) else None
    return out


def parse_rune(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    out["difficultyMask"] = _enum(fb, f, 0, DIFFICULTY)
    out["key"] = _str(fb, f, 1)
    out["professionMask"] = _int(fb, f, 2)
    out["buildableMask"] = _int(fb, f, 3)
    if 4 < len(f) and f[4] is not None:
        t = fb.target_of(f[4])
        out["blackboard"] = parse_blackboard(fb, t) if fb.is_vector(t) else None
    return out


def parse_runes(fb, pos):
    if not fb.is_vector(pos):
        return []
    out = []
    for slot in fb.vector(pos):
        rpos = slot + fb.i32(slot)
        if fb.is_table(rpos):
            out.append(parse_rune(fb, rpos))
    return out


def parse_enemy_db_ref(fb, pos):
    f = fb.table_fields(pos)
    lvl = _int(fb, f, 2)
    out = {"useDb": _bool(fb, f, 0), "id": _str(fb, f, 1),
           "level": 0 if lvl is None else lvl, "overwrittenData": None}
    if 3 < len(f) and f[3] is not None:
        t = fb.target_of(f[3])
        if fb.is_table(t):
            out["overwrittenData"] = parse_enemy_data(fb, t)
    return out


def parse_enemy_db_refs(fb, pos):
    if not fb.is_vector(pos):
        return []
    out = []
    for slot in fb.vector(pos):
        epos = slot + fb.i32(slot)
        if fb.is_table(epos):
            out.append(parse_enemy_db_ref(fb, epos))
    return out


def parse_action(fb, pos, keep_raw=False):
    """ActionData full schema (calibrated vs CN reference JSONs, see
    10_level_schema_calibration.md). Binary order = C# order minus
    useExtraRoute; bools are 1-byte inline (present only when true)."""
    f = fb.table_fields(pos)
    out = {}
    at = _int(fb, f, 0)
    if at is None:
        at = 0  # SPAWN default, field omitted by flatbuffers
    out["actionType"] = {"value": at, "name": ACTION_TYPE.get(at, "?")}
    out["managedByScheduler"] = _bool_byte(fb, f, 1)
    out["key"] = _str(fb, f, 2)
    out["count"] = _int(fb, f, 3)
    out["preDelay"] = _float(fb, f, 4)
    out["interval"] = _float(fb, f, 5)
    out["routeIndex"] = _int(fb, f, 6)
    out["blockFragment"] = _bool_byte(fb, f, 7)
    out["autoPreviewRoute"] = _bool_byte(fb, f, 8)
    out["autoDisplayEnemyInfo"] = _bool_byte(fb, f, 9)
    out["isUnharmfulAndAlwaysCountAsKilled"] = _bool_byte(fb, f, 10)
    out["hiddenGroup"] = _str(fb, f, 11)
    out["randomSpawnGroupKey"] = _str(fb, f, 12)
    out["randomSpawnGroupPackKey"] = _str(fb, f, 13)
    rt = _int(fb, f, 14)
    out["randomType"] = {"value": rt if rt is not None else 0,
                         "name": RANDOM_TYPE.get(rt if rt is not None else 0, "?")}
    rst = _int(fb, f, 15)
    out["refreshType"] = {"value": rst if rst is not None else 0,
                          "name": RANDOM_TYPE.get(rst if rst is not None else 0, "?")}
    out["weight"] = _int(fb, f, 16)
    out["dontBlockWave"] = _bool_byte(fb, f, 17)
    out["forceBlockWaveInBranch"] = _bool_byte(fb, f, 18)
    out["notCountInTotal"] = _bool_byte(fb, f, 20)
    if len(f) > 21 and f[21] is not None:
        t2 = fb.target_of(f[21])
        if fb.is_table(t2):
            out["extraMeta"] = fb.parse_table(t2, 1)
        else:
            out["extraMeta"] = fb.parse_value(f[21])
    if keep_raw:
        raw = {}
        for i, fp in enumerate(f):
            if fp is not None:
                raw[i] = fb.parse_value(fp)
        out["_raw"] = raw
    return out



def parse_fragment(fb, pos, keep_raw=False):
    f = fb.table_fields(pos)
    out = {"preDelay": _float(fb, f, 0)}
    vec = _vec(fb, f, 1)
    if vec is not None:
        acts = []
        for slot in vec:
            apos = slot + fb.i32(slot)
            if fb.is_table(apos):
                acts.append(parse_action(fb, apos, keep_raw))
        out["actions"] = acts
    return out


def parse_wave(fb, pos, keep_raw=False):
    f = fb.table_fields(pos)
    out = {"preDelay": _float(fb, f, 0), "postDelay": _float(fb, f, 1),
           "maxTimeWaitingForNextWave": _float(fb, f, 2),
           "advancedWaveTag": _str(fb, f, 4)}
    vec = _vec(fb, f, 3)
    if vec is not None:
        frags = []
        for slot in vec:
            fpos = slot + fb.i32(slot)
            if fb.is_table(fpos):
                frags.append(parse_fragment(fb, fpos, keep_raw))
        out["fragments"] = frags
    return out


def parse_waves(fb, pos, keep_raw=False):
    if not fb.is_vector(pos):
        return []
    out = []
    for slot in fb.vector(pos):
        wpos = slot + fb.i32(slot)
        if fb.is_table(wpos):
            out.append(parse_wave(fb, wpos, keep_raw))
    return out


def parse_checkpoint(fb, pos):
    f = fb.table_fields(pos)
    out = {}
    out["type"] = _enum(fb, f, 0, CHECKPOINT_TYPE)
    out["time"] = _float(fb, f, 1)
    if 2 < len(f) and f[2] is not None:
        t = fb.target_of(f[2])
        out["position"] = parse_grid_position(fb, t) if fb.is_table(t) else None
    if 3 < len(f) and f[3] is not None:
        t = fb.target_of(f[3])
        out["reachOffset"] = parse_vector2(fb, t) if fb.is_table(t) else None
    out["randomizeReachOffset"] = _bool(fb, f, 4)
    out["reachDistance"] = _float(fb, f, 5)
    return out


def parse_route(fb, pos):
    f = fb.table_fields(pos)
    out = {"motionMode": _enum(fb, f, 0, MOTION_MODE)}
    for i, nm in ((1, "startPosition"), (2, "endPosition")):
        if i < len(f) and f[i] is not None:
            t = fb.target_of(f[i])
            out[nm] = parse_grid_position(fb, t) if fb.is_table(t) else None
    for i, nm in ((3, "spawnRandomRange"), (4, "spawnOffset")):
        if i < len(f) and f[i] is not None:
            t = fb.target_of(f[i])
            out[nm] = parse_vector2(fb, t) if fb.is_table(t) else None
    vec = _vec(fb, f, 5)
    if vec is not None:
        cps = []
        for slot in vec:
            cpos = slot + fb.i32(slot)
            if fb.is_table(cpos):
                cps.append(parse_checkpoint(fb, cpos))
        out["checkpoints"] = cps
        out["checkpointCount"] = len(cps)
    out["allowDiagonalMove"] = _bool_byte(fb, f, 6)
    out["visitEveryTileCenter"] = _bool_byte(fb, f, 7)
    out["visitEveryNodeCenter"] = _bool_byte(fb, f, 8)
    out["visitEveryCheckPoint"] = _bool_byte(fb, f, 9)
    return out


def parse_routes(fb, pos):
    if not fb.is_vector(pos):
        return []
    out = []
    for slot in fb.vector(pos):
        rpos = slot + fb.i32(slot)
        if fb.is_table(rpos):
            out.append(parse_route(fb, rpos))
    return out


def parse_tile(fb, pos):
    f = fb.table_fields(pos)
    out = {"tileKey": _str(fb, f, 0), "heightType": _int(fb, f, 1),
           "buildableType": _int(fb, f, 2), "passableMask": _int(fb, f, 3),
           "playerSideMask": _int(fb, f, 4),
           "advancedBuildableMask": _int(fb, f, 5)}
    if 6 < len(f) and f[6] is not None:
        t = fb.target_of(f[6])
        out["blackboard"] = parse_blackboard(fb, t) if fb.is_vector(t) else None
    if 7 < len(f) and f[7] is not None:
        t = fb.target_of(f[7])
        if fb.is_vector(t):
            eff = []
            for slot in fb.vector(t):
                epos = slot + fb.i32(slot)
                if fb.is_table(epos):
                    ef = fb.table_fields(epos)
                    eff.append(_str(fb, ef, 0))
            out["effects"] = eff
    return out


def parse_map_data(fb, pos):
    """MapData compact: tile grid + edges + tags (bounded, linear)."""
    f = fb.table_fields(pos)
    out = {}
    if len(f) > 0 and f[0] is not None:
        t = fb.target_of(f[0])
        if fb.is_table(t):
            mf = fb.table_fields(t)
            rows = _int(fb, mf, 0)
            cols = _int(fb, mf, 1)
            out["map"] = {"rows": rows, "cols": cols, "cells": None}
            if len(mf) > 2 and mf[2] is not None:
                mv = fb.target_of(mf[2])
                if fb.is_vector(mv):
                    cnt = fb.u32(mv)
                    cells = [struct.unpack_from("<H", fb.d, mv + 4 + 2 * i)[0]
                             for i in range(cnt)]
                    out["map"]["cells"] = cells
    vec = _vec(fb, f, 1)
    if vec is not None:
        tiles = []
        for slot in vec:
            tpos = slot + fb.i32(slot)
            if fb.is_table(tpos):
                tiles.append(parse_tile(fb, tpos))
        out["tiles"] = tiles
        out["tileCount"] = len(tiles)
    vec = _vec(fb, f, 2)
    if vec is not None:
        edges = []
        for slot in vec:
            epos = slot + fb.i32(slot)
            if fb.is_table(epos):
                ef = fb.table_fields(epos)
                e = {}
                if len(ef) > 0 and ef[0] is not None:
                    t = fb.target_of(ef[0])
                    e["pos"] = parse_grid_position(fb, t) if fb.is_table(t) else None
                e["direction"] = _int(fb, ef, 1)
                e["blockMask"] = _int(fb, ef, 2)
                edges.append(e)
        out["blockEdges"] = edges
    for i, nm in ((3, "tags"), (5, "layerRects")):
        vec = _vec(fb, f, i)
        if vec is not None:
            out[nm] = [fb.parse_value(s) for s in vec[:2000]]
    return out


def parse_predefines_summary(fb, pos):
    """Predefined data: counts only (full chars are out of enemy-sim scope)."""
    f = fb.table_fields(pos)
    return {nm: _vec_len(fb, f, i) for i, nm in
            ((0, "characterInsts"), (1, "tokenInsts"),
             (2, "characterCards"), (3, "tokenCards"))}


def parse_branches(fb, pos):
    """branches: ListDict<string, BranchData> -> {key: {phases: [...]}}.
    BranchData{phases: PhaseData[]}, PhaseData{preDelay, actions[]}
    (same ActionData as waves)."""
    if not fb.is_vector(pos):
        return {}
    out = {}
    for key, vpos in fb.read_dict(pos):
        t2 = vpos + fb.i32(vpos)
        if not fb.is_table(t2):
            continue
        bf = fb.table_fields(t2)
        phases = []
        vec = _vec(fb, bf, 0)
        if vec is not None:
            for slot in vec:
                ppos = slot + fb.i32(slot)
                if not fb.is_table(ppos):
                    continue
                pf = fb.table_fields(ppos)
                ph = {"preDelay": _float(fb, pf, 0), "actions": []}
                avec = _vec(fb, pf, 1)
                if avec is not None:
                    acts = []
                    for aslot in avec:
                        apos = aslot + fb.i32(aslot)
                        if fb.is_table(apos):
                            acts.append(parse_action(fb, apos, False))
                    ph["actions"] = acts
                phases.append(ph)
        out[key] = {"phases": phases}
    return out


def parse_optional_runes(fb, pos):
    """optionalRunes: Dictionary<string, List<LegacyInLevelRuneData>>."""
    if not fb.is_vector(pos):
        return {}
    out = {}
    for key, vpos in fb.read_dict(pos):
        t2 = vpos + fb.i32(vpos)
        if fb.is_vector(t2):
            out[key] = parse_runes(fb, t2)
    return out


def parse_level(fb, pos, keep_raw=False):
    f = fb.table_fields(pos)
    out = {"levelId": _str(fb, f, 1), "mapId": _str(fb, f, 2),
           "bgmEvent": _str(fb, f, 3), "environmentSe": _str(fb, f, 4),
           "operaConfig": _str(fb, f, 20), "cameraPlugin": _str(fb, f, 21)}
    if len(f) > 0 and f[0] is not None:
        t = fb.target_of(f[0])
        out["options"] = parse_options(fb, t) if fb.is_table(t) else None
    if 5 < len(f) and f[5] is not None:
        t = fb.target_of(f[5])
        out["mapData"] = parse_map_data(fb, t) if fb.is_table(t) else None
    if 6 < len(f) and f[6] is not None:
        t = fb.target_of(f[6])
        if fb.is_vector(t):
            out["tilesDisallowToLocate"] = [
                {"row": v.get(0), "col": v.get(1)} if isinstance(v, dict) else v
                for v in fb.vector(t)[:5000]]
    if 7 < len(f) and f[7] is not None:
        t = fb.target_of(f[7])
        out["runes"] = parse_runes(fb, t) if fb.is_vector(t) else []
    if 8 < len(f) and f[8] is not None:
        t = fb.target_of(f[8])
        out["optionalRunes"] = parse_optional_runes(fb, t) if fb.is_vector(t) else {}
    if 9 < len(f) and f[9] is not None:
        t = fb.target_of(f[9])
        if fb.is_vector(t):
            buffs = []
            for slot in fb.vector(t):
                bpos = slot + fb.i32(slot)
                if fb.is_table(bpos):
                    bf = fb.table_fields(bpos)
                    b = {"prefabKey": _str(fb, bf, 0)}
                    if len(bf) > 1 and bf[1] is not None:
                        bb = fb.target_of(bf[1])
                        b["blackboard"] = parse_blackboard(fb, bb) if fb.is_vector(bb) else None
                    buffs.append(b)
            out["globalBuffs"] = buffs
    if 10 < len(f) and f[10] is not None:
        t = fb.target_of(f[10])
        out["routes"] = parse_routes(fb, t) if fb.is_vector(t) else []
    if 11 < len(f) and f[11] is not None:
        t = fb.target_of(f[11])
        out["extraRoutes"] = parse_routes(fb, t) if fb.is_vector(t) else []
    if 12 < len(f) and f[12] is not None:
        t = fb.target_of(f[12])
        if fb.is_vector(t):
            enemies = []
            for slot in fb.vector(t):
                epos = slot + fb.i32(slot)
                if fb.is_table(epos):
                    enemies.append(parse_enemy_data(fb, epos))
            out["enemies"] = enemies
    if 13 < len(f) and f[13] is not None:
        t = fb.target_of(f[13])
        out["enemyDbRefs"] = parse_enemy_db_refs(fb, t) if fb.is_vector(t) else []
    if 14 < len(f) and f[14] is not None:
        t = fb.target_of(f[14])
        out["waves"] = parse_waves(fb, t, keep_raw) if fb.is_vector(t) else []
    if 15 < len(f) and f[15] is not None:
        t = fb.target_of(f[15])
        out["branches"] = parse_branches(fb, t) if fb.is_vector(t) else None
    for i, nm in ((16, "predefines"), (17, "hardPredefines")):
        if i < len(f) and f[i] is not None:
            t = fb.target_of(f[i])
            out[nm] = parse_predefines_summary(fb, t) if fb.is_table(t) else None
    if 18 < len(f) and f[18] is not None:
        t = fb.target_of(f[18])
        if fb.is_vector(t):
            out["excludeCharIdList"] = [fb.parse_value(s) for s in fb.vector(t)[:1000]]
    out["randomSeed"] = _int(fb, f, 19)
    return out


def looks_like_text(data):
    try:
        s = data[:512].decode("utf-8")
    except UnicodeDecodeError:
        return False
    return all(ch.isprintable() or ch in "\r\n\t" for ch in s)


def parse_level_file(path, keep_raw=False, timeout=15.0, budget=200000):
    data = open(path, "rb").read()
    if not data or looks_like_text(data):
        return None, 0, False
    t0 = time.monotonic()
    tried = [128] if len(data) > 128 else [0]
    if 0 not in tried:
        tried.append(0)
    for off in tried:
        if len(data) <= off + 16:
            continue
        if time.monotonic() - t0 > timeout:
            return None, 0, False
        try:
            fb = LevelFB(data[off:], path, budget=budget)
            root_fields = fb.table_fields(fb.root)
            present = [i for i, fp in enumerate(root_fields) if fp is not None]
            if len(present) < 3:
                continue
            if not any(i in present for i in (0, 3, 5, 7, 10, 13, 14, 19)):
                continue
            lv = parse_level(fb, fb.root, keep_raw)
            return lv, off, False
        except BudgetExceeded:
            return None, 0, True
        except Exception:
            continue
    return None, 0, False


def summarize(lv, src):
    stem = os.path.splitext(os.path.basename(src))[0]
    return {
        "file": os.path.basename(src),
        "levelId": stem,
        "inFileLevelId": lv.get("levelId"),
        "mapId": lv.get("mapId"),
        "bgmEvent": lv.get("bgmEvent"),
        "randomSeed": lv.get("randomSeed"),
        "options": lv.get("options"),
        "runes": [r.get("key") for r in (lv.get("runes") or [])],
        "enemyDbRefs": [
            {"id": r.get("id"), "level": r.get("level"), "useDb": r.get("useDb")}
            for r in (lv.get("enemyDbRefs") or [])
        ],
        "enemyCount": len(lv.get("enemies") or []),
        "routeCount": len(lv.get("routes") or []),
        "waveCount": len(lv.get("waves") or []),
        "tileCount": (lv.get("mapData") or {}).get("tileCount", 0),
        "actions": [
            [(a.get("actionType") or {}).get("name") for a in (fr.get("actions") or [])]
            for w in (lv.get("waves") or [])
            for fr in (w.get("fragments") or [])
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--level", default=None, help="parse only one level id")
    ap.add_argument("--raw", action="store_true",
                    help="keep raw generic action fields (slow, big)")
    ap.add_argument("--budget", type=int, default=200000,
                    help="max parsed nodes per level")
    args = ap.parse_args()

    # Level payloads are big and deeply nested; a low cap keeps the bulk run
    # fast while preserving root-level and calibrated nested structure.
    E.MAX_DEPTH = 5

    os.makedirs(args.out, exist_ok=True)
    files = sorted(
        f for f in os.listdir(args.src)
        if f.startswith("level_") and not f.endswith((".py", ".json"))
        and not any(m in f for m in ("_BEG", "_END", "_beg", "_end", "dialog_"))
    )
    if args.level:
        files = [f for f in files if args.level in f]
    if args.limit:
        files = files[: args.limit]

    index = []
    ok = fail = too_complex = 0
    for i, fn in enumerate(files, 1):
        src = os.path.join(args.src, fn)
        try:
            lv, off, complex_flag = parse_level_file(
                src, keep_raw=args.raw, budget=args.budget)
        except Exception as e:
            lv, off, complex_flag = None, 0, False
            print(f"[ERR] {fn}: {e}")
        if lv is None:
            fail += 1
            if complex_flag:
                too_complex += 1
            continue
        ok += 1
        stem = os.path.splitext(fn)[0]
        lid = lv.get("levelId") or stem
        safe = "".join(c if c not in '\\/:*?"<>|' else "_" for c in stem)
        lv["_meta"] = {"file": fn, "size": os.path.getsize(src),
                       "signHeader": off, "levelId": lid,
                       "inFileLevelId": lv.get("levelId")}
        out = os.path.join(args.out, safe + ".json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(lv, f, ensure_ascii=False, separators=(",", ":"))
        index.append(summarize(lv, src))
        if i % 500 == 0 or i == len(files):
            print(f"[{i}/{len(files)}] ok={ok} fail={fail} "
                  f"tooComplex={too_complex}")

    idx_path = os.path.join(SCRIPT_DIR, "data", "level_data_index.json")
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    print(f"done: {ok} parsed, {fail} failed ({too_complex} too complex) -> {args.out}")
    print(f"index -> {idx_path}")


if __name__ == "__main__":
    main()
