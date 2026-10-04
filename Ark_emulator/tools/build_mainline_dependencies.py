"""Resolve native stage dependencies into an auditable, non-executable plan."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEFAULT_DB = ROOT.parent/"unpack_work/campaign_tables/enemy_database.json"
PIN = "56aee3d6c5a29c3a0d192456d70d14252cbb0804"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def merge_defined(base, layer):
    """Undefined DB values inherit; defined zero and false must override."""
    result = deepcopy(base)
    for key, value in layer.items():
        if isinstance(value, dict) and "m_defined" in value:
            if type(value["m_defined"]) is not bool or "m_value" not in value:
                raise ValueError(f"invalid native defined-value wrapper: {key}")
            if value["m_defined"]:
                result[key] = deepcopy(value["m_value"])
        elif isinstance(value, dict):
            result[key] = merge_defined(result.get(key, {}), value)
        elif value is not None:
            result[key] = deepcopy(value)
    return result


def resolve_enemy(database, reference):
    if reference.get("useDb") is not True:
        raise ValueError("inline native enemies require a separate explicit converter")
    key, level = reference["id"], reference.get("level", 0)
    rows = database.get(key)
    if not rows:
        raise ValueError(f"native enemy DB entry is missing: {key}")
    selected = sorted((row for row in rows if row["level"] <= level), key=lambda row: row["level"])
    if not selected or selected[-1]["level"] != level:
        raise ValueError(f"native enemy level is missing: {key}@{level}")
    result = {}
    for row in selected:
        result = merge_defined(result, row["enemyData"])
    if reference.get("overwrittenData"):
        result = merge_defined(result, reference["overwrittenData"])
    return {"native_id": key, "native_level": level, "resolved": result,
            "raw_rows": deepcopy(selected), "stage_override": deepcopy(reference.get("overwrittenData"))}


def map_plan(native):
    grid, palette = native["mapData"]["map"], native["mapData"]["tiles"]
    if not grid or not grid[0] or any(len(row) != len(grid[0]) for row in grid):
        raise ValueError("native map must be a nonempty rectangular index matrix")
    tiles = []
    build = {"NONE": 0, "MELEE": 1, "RANGED": 2, "ALL": 3}
    passing = {"NONE": 0, "WALK_ONLY": 1, "FLY_ONLY": 2, "ALL": 3}
    for row in grid:
        for index in row:
            if type(index) is not int or not 0 <= index < len(palette):
                raise ValueError("native tile index is outside the palette")
            tile = palette[index]
            if tile["buildableType"] not in build or tile["passableMask"] not in passing:
                raise ValueError("unknown native tile mask")
            tiles.append({"tileKey": tile["tileKey"], "buildableType": build[tile["buildableType"]],
                          "passableMask": passing[tile["passableMask"]],
                          "heightType": tile["heightType"], "blackboard": deepcopy(tile.get("blackboard")),
                          "effects": deepcopy(tile.get("effects"))})
    return {"rows": len(grid), "cols": len(grid[0]), "tiles": tiles,
            "coordinate_conversion": "map rows are top-down; native route row -> rows-1-row",
            "native_block_edges": deepcopy(native["mapData"].get("blockEdges")),
            "native_tags": deepcopy(native["mapData"].get("tags"))}


def build(level_id="level_main_00-10", database_path=DEFAULT_DB):
    lock_path = ROOT/"packages/campaign/enemy_sources.lock.json"
    lock = read(lock_path)
    if lock.get("commit") != PIN or sha(database_path) != lock.get("sha256"):
        raise ValueError("enemy database does not match the pinned source identity")
    native_path = ROOT/"packages/campaign/native_reference"/f"{level_id}.json"
    native, database = read(native_path), read(database_path)
    refs = {item["id"]: item for item in native["enemyDbRefs"]}
    enemies = {key: resolve_enemy(database, ref) for key, ref in refs.items()}
    spawns, controls, route_indices = Counter(), Counter(), set()
    for wave in native["waves"]:
        for fragment in wave["fragments"]:
            for action in fragment["actions"]:
                kind = action["actionType"]
                if kind == "SPAWN":
                    if action["key"] not in enemies:
                        raise ValueError(f"spawn refers to unresolved native enemy: {action['key']}")
                    index = action["routeIndex"]
                    if type(index) is not int or not 0 <= index < len(native["routes"]):
                        raise ValueError("spawn route index is invalid")
                    route_indices.add(index)
                    spawns[action["key"]] += action["count"]
                else:
                    controls[kind] += action.get("count", 1)
    normalized = read(ROOT/"packages/campaign/operators.normalized.json")
    skills = read(ROOT/"packages/campaign/skills.myrtle.json")
    required = {"movement", "blocking", "physical_damage", "resources", "deployment", "lifecycle", "replay"}
    gaps = ["fixed_roster_talents_and_native_attack_clocks_not_fully_converted",
            "selected_skill_models_partial_not_native_complete", "native_control_actions_require_explicit_model",
            "native_enemy_animation_scaling_and_client_hit_timing_pending"]
    available_models = []
    from tools.build_campaign_squad import BINDINGS
    for character_id, (name, _, skill_id, _) in BINDINGS.items():
        path = ROOT/f"packages/campaign/skills.{name}.json"
        if path.exists():
            available_models.append({"character_id": character_id, "selected_skill_ability": skill_id,
                "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path),
                "status": read(path).get("status"), "native_complete": False})
    for enemy in enemies.values():
        data = enemy["resolved"]
        if data.get("motion") == "FLY":
            required.add("flying")
        if data.get("skills") or data.get("talentBlackboard"):
            required.add("native_enemy_skills_and_talents")
            gaps.append(f"enemy_behaviors_require_conversion:{enemy['native_id']}")
    for row in normalized["operators"]:
        required.add("selected_skill:"+row["selected_skill"]["skill_id"])
    masks = {"NONE": 0, "NORMAL": 1, "FOUR_STAR": 2, "EASY": 4, "SIX_STAR": 8, "ALL": 15}
    applied_runes, inactive_runes = [], []
    for rune in native.get("runes") or []:
        value = rune["difficultyMask"]
        value = masks[value] if isinstance(value, str) and value in masks else value
        if type(value) is not int:
            raise ValueError("unknown native rune difficulty mask")
        (applied_runes if value & 1 else inactive_runes).append(deepcopy(rune))
    if applied_runes:
        gaps.append("applicable_native_runes_require_explicit_conversion")
    return {"schema": "ark-sim/mainline-dependency-plan/v1", "status": "dependencies_resolved_not_executable",
            "runnable": False, "model_validated": False, "native_level_id": level_id, "difficulty": 1,
            "source": {"repository": "ArknightsAssets/ArknightsGamedata", "commit": PIN,
                       "native_level_sha256": sha(native_path), "enemy_database_sha256": sha(database_path),
                       "enemy_source_lock_sha256": sha(lock_path),
                       "operator_normalized_sha256": sha(ROOT/"packages/campaign/operators.normalized.json"),
                       "skill_prototype_sha256": sha(ROOT/"packages/campaign/skills.myrtle.json")},
            "map_plan": map_plan(native), "native_options": deepcopy(native["options"]),
            "native_wave_script": deepcopy(native["waves"]), "spawn_count": sum(spawns.values()),
            "spawn_counts_by_key": dict(spawns), "control_counts": dict(controls),
            "used_routes": {str(index): deepcopy(native["routes"][index]) for index in sorted(route_indices)},
            "resolved_enemies": list(enemies.values()),
            "native_runes": deepcopy(native.get("runes")), "native_global_buffs": deepcopy(native.get("globalBuffs")),
            "applicable_runes": applied_runes, "inactive_runes": inactive_runes,
            "native_predefines": deepcopy(native.get("predefines")), "native_branches": deepcopy(native.get("branches")),
            "roster": [{"character_id": row["character_id"], "config": row["config"], "stats": row["stats"],
                        "selected_skill": row["selected_skill"], "talents": row["talents"], "gaps": row["gaps"]}
                       for row in normalized["operators"]],
            "required_mechanics": sorted(required), "pending_conversion": gaps,
            "available_selected_skill_models": available_models,
            "first_skill_prototype_status": skills.get("status", "partially_implemented")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", default="level_main_00-10")
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build(args.level, args.database)
    output = args.output or ROOT/"packages/campaign/mainline_dependencies"/f"{args.level}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"level": args.level, "spawn_count": result["spawn_count"],
                     "enemy_variants": len(result["resolved_enemies"]), "runnable": False}))


if __name__ == "__main__":
    main()
