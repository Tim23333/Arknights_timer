#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a simulation-ready bundle from parsed LevelData (research artifact).

Inputs (under ark_parser/enemy/data/):
  levels/<levelId>.json          parsed LevelData (extract_level_data.py)
  level_data_index.json          index of parsed levels
  enemy_database.json            enemy id -> levels -> EnemyData
  stage_enemy_usage.json         stageId -> stage metadata (levelId)
  levels_index.json              stage_table-derived level id list

Outputs:
  stage_sim_bundle.json          { levels: {levelId: {...}}, enemyRoster: {...},
                                   stages: {stageId: {levelId, code, name}} }
  sim_coverage.json              coverage stats + missing categories

Wave timeline model (documented assumption): a SPAWN action in
wave w / fragment f produces `count` spawns of `key` at
  t = wave.preDelay + sum(prev wave preDelay?) ... simplified:
  t0 = wave.preDelay + fragment.preDelay + action.preDelay
  spawn times: t0 + i * interval (i = 0..count-1), route = routeIndex.
This additive model treats every preDelay as absolute offsets from battle
start within its parent; exact WaveScheduler semantics (fragment/action
completion chaining) may shift events slightly - see 02_stage_waves.md.

Usage:
    python build_sim_bundle.py [--levels-dir DIR] [--out DIR]
"""

import argparse
import json
import os
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(SCRIPT_DIR, "data")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def action_spawn_times(action, t_base):
    """Expand one action into (t, key, routeIndex, count) event times."""
    if not isinstance(action, dict):
        return []
    at = action.get("actionType") or {}
    atype = (at.get("name") if isinstance(at, dict) else at) or "SPAWN"
    t0 = t_base + (action.get("preDelay") or 0.0)
    interval = action.get("interval") or 0.0
    count = action.get("count") or 1
    route = action.get("routeIndex")
    out = []
    for i in range(max(1, int(count))):
        out.append({
            "t": round(t0 + i * interval, 3),
            "key": action.get("key"),
            "routeIndex": route,
            "actionType": atype,
            "seq": i,
        })
    return out


def wave_timeline(waves):
    """Flatten waves into absolute spawn/action events.

    Chained-wave model (matches the emulator, MECHANICS \u00a711):
      - waves are sequential: wave i starts after wave i-1's last event
        plus postDelay and the next wave's preDelay;
      - fragments are sequential: each starts after the previous fragment's
        final action, then waits its own preDelay;
      - intra-tick order: (t, wave, fragment, action, seq).
    """
    events = []
    wave_t = 0.0
    for wi, w in enumerate(waves or []):
        wave_start = wave_t + (w.get("preDelay") or 0.0)
        wave_end = 0.0
        fragment_cursor = wave_start
        for fi, fr in enumerate(w.get("fragments") or []):
            frag_start = fragment_cursor + (fr.get("preDelay") or 0.0)
            fragment_end = frag_start
            for ai, a in enumerate(fr.get("actions") or []):
                for ev in action_spawn_times(a, frag_start):
                    ev.update({"wave": wi, "fragment": fi, "action": ai})
                    events.append(ev)
                    if ev["t"] > fragment_end:
                        fragment_end = ev["t"]
            fragment_cursor = fragment_end
            if fragment_end > wave_end:
                wave_end = fragment_end
        wave_t = wave_end + (w.get("postDelay") or 0.0)
    return sorted(events, key=lambda e: (e["t"], e.get("wave", 0),
                                         e.get("fragment", 0),
                                         e.get("action", 0),
                                         e.get("seq", 0)))


def compact_enemy_database(db):
    roster = {}
    for eid, levels in db.items():
        lv0 = levels[0].get("data") or {} if levels else {}
        roster[eid] = {
            "name": lv0.get("name"),
            "prefabKey": lv0.get("prefabKey"),
            "attributes": lv0.get("attributes"),
            "skills": [s.get("prefabKey") for s in (lv0.get("skills") or [])],
            "talentBlackboard": lv0.get("talentBlackboard"),
            "levelCount": len(levels),
        }
    return roster


def build_level_summary(lv):
    out = {
        "levelId": lv.get("levelId"),
        "mapId": lv.get("mapId"),
        "bgmEvent": lv.get("bgmEvent"),
        "randomSeed": lv.get("randomSeed"),
        "options": lv.get("options"),
        "runes": lv.get("runes"),
        "enemyDbRefs": lv.get("enemyDbRefs"),
        "enemies": lv.get("enemies"),
        "routes": lv.get("routes"),
        "map": (lv.get("mapData") or {}).get("map"),
        "branches": lv.get("branches"),
        "optionalRunes": lv.get("optionalRunes"),
        "tileCount": (lv.get("mapData") or {}).get("tileCount", 0),
        "waveTimeline": wave_timeline(lv.get("waves")),
    }
    return out


def coverage(parsed_ids, all_level_ids):
    have = set(parsed_ids)
    def prefix(n):
        parts = n.split("_")
        return parts[1] if len(parts) > 2 and n.startswith("level_") else n
    all_pref = Counter(prefix(n) for n in all_level_ids)
    have_pref = Counter(prefix(n) for n in have)
    return {
        "parsedCount": len(have),
        "indexCount": len(all_level_ids),
        "coveredRatio": round(len(have & set(all_level_ids)) / max(1, len(all_level_ids)), 4),
        "byPrefix": {
            k: {"index": v, "parsed": have_pref.get(k, 0)}
            for k, v in sorted(all_pref.items())
        },
        "missingByPrefix": {
            k: v - have_pref.get(k, 0) for k, v in sorted(all_pref.items())
            if v - have_pref.get(k, 0) > 0
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels-dir", default=os.path.join(DATA, "levels"))
    ap.add_argument("--out", default=DATA)
    args = ap.parse_args()

    index = load(os.path.join(DATA, "level_data_index.json"))
    db = load(os.path.join(DATA, "enemy_database.json"))
    stages = load(os.path.join(DATA, "stage_enemy_usage.json"))
    all_levels = load(os.path.join(DATA, "levels_index.json"))
    all_level_ids = [e["name"] for e in all_levels]

    roster = compact_enemy_database(db)
    levels = {}
    missing = []
    for entry in index:
        lid = entry.get("levelId")
        p = os.path.join(args.levels_dir, lid + ".json")
        if not os.path.exists(p):
            missing.append(lid)
            continue
        lv = load(p)
        levels[lid] = build_level_summary(lv)

    stage_map = {}
    for sid, st in stages.items():
        raw_lv = st.get("levelId") or ""
        lv_id = raw_lv.split("/")[-1] or raw_lv
        stage_map[sid] = {
            "levelId": lv_id,
            "code": st.get("code"),
            "name": st.get("name"),
            "stageType": st.get("stageType"),
            "difficulty": st.get("difficulty"),
            "dangerLevel": st.get("dangerLevel"),
            "parsed": lv_id in levels,
        }

    bundle = {
        "meta": {
            "generatedBy": "build_sim_bundle.py",
            "waveModel": "chained: waves sequential (prev last event + "
                         "postDelay + preDelay); fragments sequential "
                         "(previous final action + fragment preDelay); spawns at "
                         "frag_start + action.preDelay + i*interval",
        },
        "levels": levels,
        "enemyRoster": roster,
        "stages": stage_map,
    }
    bundle_path = os.path.join(args.out, "stage_sim_bundle.json")
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, separators=(",", ":"))

    cov = coverage(list(levels.keys()), all_level_ids)
    cov["missingParsedFile"] = missing[:20]
    cov["stageCount"] = len(stage_map)
    cov["stageWithParsedLevel"] = sum(1 for s in stage_map.values() if s["parsed"])
    cov_path = os.path.join(args.out, "sim_coverage.json")
    with open(cov_path, "w", encoding="utf-8") as f:
        json.dump(cov, f, ensure_ascii=False, indent=1)

    print(f"levels: {len(levels)}  stages: {len(stage_map)}  "
          f"stages-parsed: {cov['stageWithParsedLevel']}")
    print(f"bundle -> {bundle_path}  coverage -> {cov_path}")


if __name__ == "__main__":
    main()
