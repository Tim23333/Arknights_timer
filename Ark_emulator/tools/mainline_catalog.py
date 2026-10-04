"""Offline, JSON-only mainline selection. Never imports either simulator.

Run from Ark_emulator: ..\\.venv\\Scripts\\python.exe tools/mainline_catalog.py
An optional --rawlevel-root supplies genuine LevelData JSON, independently of
the lossy local binary extraction. Missing required inputs are fatal.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STANDARD_ID = re.compile(r"main_(\d+)-(\d+)$")
VARIANT_ID = re.compile(r"(main|easy|tough)_(\d+)-(\d+)(.*)$")


def load_json(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Required campaign source missing: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source(path: Path, root: Path = ROOT) -> dict:
    return {"path": Path(os.path.relpath(path.resolve(), root.resolve())).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def enum_name(value):
    return value.get("name", f"UNKNOWN_{value.get('value')}") if isinstance(value, dict) else value


def dependency_summary(data: dict) -> dict:
    actions = [a for w in data.get("waves", []) for f in w.get("fragments", [])
               for a in f.get("actions", [])]
    kinds = Counter(enum_name(a.get("actionType")) for a in actions)
    spawn_count = sum(a.get("count", 0) or 0 for a in actions
                      if enum_name(a.get("actionType")) == "SPAWN")
    routes = data.get("routes", []) + data.get("extraRoutes", [])
    gaps = []
    if any(enum_name(r.get("motionMode")) in ("E_NUM", None) for r in routes):
        gaps.append("invalid_or_missing_motion_mode")
    if routes and all(r.get("startPosition") == r.get("endPosition") == {"row": 0, "col": 0}
                      and not r.get("checkpoints") for r in routes):
        gaps.append("all_routes_zero_endpoints_without_checkpoints")
    invalid_count = sum(enum_name(r.get("motionMode")) in ("E_NUM", None) for r in routes)
    used = sorted({a["routeIndex"] for a in actions if enum_name(a.get("actionType")) == "SPAWN"
                   and isinstance(a.get("routeIndex"), int)})
    return {"enemy_refs": [{"id": r.get("id"), "level": r.get("level"),
                             "useDb": r.get("useDb"),
                             "has_overrides": bool(r.get("overwrittenData"))}
                            for r in data.get("enemyDbRefs", [])],
            "spawn_action_count": kinds.get("SPAWN", 0), "declared_spawn_count": spawn_count,
            "wave_count": len(data.get("waves", [])), "route_count": len(data.get("routes", [])),
            "extra_route_count": len(data.get("extraRoutes", [])), "used_spawn_route_indices": used,
            "invalid_motion_route_count": invalid_count,
            "checkpoint_count": sum(len(r.get("checkpoints") or []) for r in routes),
            "control_action_counts": {k: v for k, v in sorted(kinds.items(), key=lambda x: str(x[0]))
                                      if k != "SPAWN"},
            "route_geometry_gaps": gaps,
            "predefines": data.get("predefines"), "options": data.get("options", {})}


def standard_order(stage_id: str) -> tuple[int, int]:
    match = STANDARD_ID.fullmatch(stage_id)
    if not match:
        raise ValueError(f"Not a standard mainline native ID: {stage_id}")
    return tuple(map(int, match.groups()))


def select_tail_pairs(stages: dict) -> dict[int, list[str]]:
    """Native sequence is the documented selection policy, never code sorting."""
    chapters = defaultdict(list)
    for sid, record in stages.items():
        if STANDARD_ID.fullmatch(sid) and record.get("difficulty") == 1:
            chapters[standard_order(sid)[0]].append(sid)
    return {chapter: sorted(ids, key=standard_order)[-2:]
            for chapter, ids in sorted(chapters.items())}


def build_catalog(root: Path = ROOT, rawlevel_root: Path | None = None) -> dict:
    data_root = root.parent / "ark_parser/enemy/data"
    files = [data_root / n for n in ("stage_sim_bundle.json", "levels_index.json", "level_data_index.json")]
    bundle, levels_index, data_index = [load_json(p) for p in files]
    stages = bundle["stages"]
    level_lookup = {r["name"]: r for r in levels_index}
    data_lookup = {r["levelId"]: r for r in data_index}
    tails = select_tail_pairs(stages)
    selected = {s for pair in tails.values() for s in pair}
    variants = defaultdict(list)
    legacy_index_path = root / "ark_emulator/data_level_assets_index.json"
    legacy_index = load_json(legacy_index_path) if legacy_index_path.exists() else {}
    for sid, r in stages.items():
        m = VARIANT_ID.fullmatch(sid)
        if m:
            variants[tuple(map(int, m.groups()[1:3]))].append(
                {"native_id": sid, "level_id": r.get("levelId"), "difficulty": r.get("difficulty"),
                 "variant": m[1], "suffix": m[4], "code": r.get("code")})
    raw_lookup = {}
    if rawlevel_root is not None:
        if not rawlevel_root.is_dir():
            raise FileNotFoundError(f"Raw LevelData directory missing: {rawlevel_root}")
        for p in sorted(rawlevel_root.rglob("*")):
            if p.suffix in (".json", ".bytes") and p.stem.startswith("level_main_"):
                raw_lookup.setdefault(p.stem, []).append(p)
    records = []
    ambiguities = []
    for sid in sorted((s for s in stages if STANDARD_ID.fullmatch(s) and stages[s].get("difficulty") == 1),
                      key=standard_order):
        r = stages[sid]
        ch, seq = standard_order(sid)
        lid = r.get("levelId")
        parsed_path = data_root / "levels" / f"{lid}.json"
        raw_paths = raw_lookup.get(lid, [])
        row = {"chapter": ch, "native_sequence": seq, "native_id": sid, "code": r.get("code"),
               "level_id": lid, "selected": sid in selected,
               "variants": sorted(variants[(ch, seq)], key=lambda x: x["native_id"]),
               "level_index_path": level_lookup.get(lid, {}).get("path"),
               "parsed_level_source": source(parsed_path, root) if parsed_path.exists() else None,
               "rawlevel_sources": [source(p, root) for p in raw_paths],
               "legacy_asset_index_path": legacy_index.get(lid),
               "legacy_asset_index_target_exists": bool(legacy_index.get(lid) and
                    (root.parent / legacy_index[lid]).exists()),
               "dependency_status": "not_imported", "v2_status": "not_validated"}
        issues = []
        if lid not in level_lookup or sid not in level_lookup.get(lid, {}).get("stageIds", []):
            issues.append("levels_index_stage_link_missing")
        if lid not in data_lookup:
            issues.append("level_data_index_missing")
        if r.get("stageType") is None:
            issues.append("stage_type_missing_in_bundle")
        if not r.get("parsed"):
            issues.append("bundle_level_not_parsed")
        if not raw_paths:
            issues.append("original_rawlevel_json_unavailable")
        if len(raw_paths) > 1:
            issues.append("multiple_rawlevel_sources_require_choice")
        if sid in selected:
            binary_paths = sorted((root.parent / "unpack_work/release_20260831").glob(f"*_raw/{lid}.dat"))
            row["original_binary_level_sources"] = [source(p, root) for p in binary_paths]
            if not parsed_path.exists() and not raw_paths:
                row["status"] = "missing_level_source"
            else:
                p = raw_paths[0] if len(raw_paths) == 1 else parsed_path
                row["dependency_summary"] = dependency_summary(load_json(p))
                row["dependency_summary_source"] = source(p, root)
                gaps = row["dependency_summary"]["route_geometry_gaps"]
                issues.extend(gaps)
                row["status"] = "source_available_with_geometry_gaps" if gaps else "source_available_unvalidated"
                if not row["dependency_summary"]["spawn_action_count"]:
                    issues.append("selected_mainline_has_no_spawn_actions")
        else:
            row["status"] = "catalogued_not_selected"
        row["ambiguities"] = issues
        records.append(row)
    for ch, ids in tails.items():
        if len(ids) < 2:
            ambiguities.append({"chapter": ch, "issue": "fewer_than_two_standard_stages"})
    tables = sorted((root.parent / "data/tables").glob("stage_table*.bin"))
    return {"schema": "ark_sim.mainline_catalog.v1", "offline_only": True,
            "selection_policy": "unsuffixed main_CC-NN; difficulty=1; native sequence numeric; last two per chapter",
            "sources": [source(p, root) for p in files] +
                       ([source(legacy_index_path, root)] if legacy_index_path.exists() else []),
            "binary_stage_table_inventory": [source(p, root) for p in tables],
            "binary_stage_tables_parsed_by_this_tool": False,
            "chapters": [{"chapter": ch, "selected_native_ids": ids,
                          "selected_codes": [stages[s]["code"] for s in ids]} for ch, ids in tails.items()],
            "ambiguities": ambiguities, "stages": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rawlevel-root", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "packages/campaign/mainline_catalog.json")
    args = parser.parse_args()
    catalog = build_catalog(rawlevel_root=args.rawlevel_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Catalogued {len(catalog['stages'])} standard stages; selected {sum(len(c['selected_native_ids']) for c in catalog['chapters'])}; {args.output}")


if __name__ == "__main__":
    main()
