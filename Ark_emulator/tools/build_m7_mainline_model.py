"""M7 composition over frozen M6 content with explicit spatial/roster profiles."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE = ROOT/"packages/campaign/mainline_models/level_main_00-10.json"
BASE_SHA = "6a0971d198ca89046ecb77387d9f2adc6786aea8b80c3fb8bd87ac9d7b667ee4"
OUTPUT = ROOT/"packages/campaign/mainline_models/level_main_00-10.m7.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    if sha(BASE) != BASE_SHA:
        raise ValueError("frozen M6 base content changed")
    result = json.loads(BASE.read_bytes())
    spatial_path = ROOT/"packages/campaign/spatial.profiles.json"
    roster_path = ROOT/"packages/campaign/roster.profiles.json"
    spatial, roster = json.loads(spatial_path.read_bytes()), json.loads(roster_path.read_bytes())
    result["manifest"]["id"] = "package/campaign/model/level_main_00-10/m7"
    result["manifest"]["version"] = "0.2.0"
    meta = result["manifest"]["metadata"]
    meta["m7_source_identities"] = {"frozen_m6": BASE_SHA, "spatial_proposal": sha(spatial_path), "roster_profiles": sha(roster_path)}
    meta["model_profiles"] = deepcopy(spatial["model_profiles"])
    meta["model_profiles"]["spawn"]["status"] = "implemented_model"
    meta["model_profiles"]["path"]["status"] = "implemented_model"
    meta["m7_integrated"] = ["sampled_spawn_position", "eight_neighbor_path", "kalts_preferred_heal_group", "relative_attack_facing", "capacity_change_invariant"]
    result["rules"].extend(deepcopy(roster["rules"]))
    result["rules"] += [
        {"id": "rule/m7_spawn_rectangle", "kind": "calculation_rule", "contract": "spawn.position",
         "implementation": {"type": "provider", "provider": "ark.spawn.uniform_rect"},
         "parameters": {"axis_signs": {"row": -1, "col": 1}}},
        {"id": "rule/m7_diagonal_path", "kind": "calculation_rule", "extends": "rule/ark_movement_path",
         "parameters": {"use_route_diagonal": True, "corner_cut": False}},
        {"id": "rule/m7_steering_velocity", "kind": "calculation_rule", "contract": "movement.steering",
         "implementation": {"type": "provider", "provider": "ark.movement.steering_velocity"}}]
    patches = roster["manifest"]["metadata"]["unit_patches"]
    for entity in result["entities"]:
        entity.setdefault("rules", {}).update(deepcopy(patches.get(entity["id"], {}).get("rules", {})))
        if "enemy" in entity.get("tags", []):
            fields = spatial["raw_enemy_movers"]["enemies"][entity["metadata"]["native_id"]]["fields"]
            entity["components"]["spatial"]["steering"] = {"rule": "rule/m7_steering_velocity",
                "parameters": {"response_factor": fields["_steeringFactor"], "max_acceleration": fields["_maxSteeringForce"], "arrival_radius": .05}}
    # Skill recipe fixtures were authored facing right. Production offsets are
    # character-relative and must follow the deployed facing in the squad.
    for selector in result["selectors"]:
        region = selector.get("region", {})
        if region.get("type") == "grid_offsets" and region.get("rotate_with_facing") is False:
            region["rotate_with_facing"] = True
            selector.setdefault("metadata", {})["m7_relative_facing_conversion"] = True
    ability_map = {row["id"]: row for row in result["abilities"]}
    selector_map = {row["id"]: row for row in result["selectors"]}
    for entity in result["entities"]:
        if "player" not in entity.get("tags", []) or entity["components"]["attributes"]["base"].get("block_count", 0) <= 0:
            continue
        for ability_id in entity["components"].get("abilities", []):
            selector = selector_map.get(ability_map[ability_id].get("selector"))
            if selector and any(f.get("tag") == "enemy" for f in selector.get("filters", [])):
                selector.setdefault("parameters", {})["include_blocked"] = True
                selector.setdefault("metadata", {})["m7_own_blocked_target_conversion"] = True
    scene = result["scenarioDraft"]
    scene["id"] = "scenario/campaign_model/level_main_00-10/m7"
    scene["seed"] = spatial["model_profiles"]["spawn"]["root_seed_choice"]
    scene.setdefault("rules", {})["movement.path"] = "rule/m7_diagonal_path"
    for wave in scene["waves"]:
        route = wave["route"]
        offset, extent = route["spawnOffset"], route["spawnRandomRange"]
        wave["placement"] = {"rule": "rule/m7_spawn_rectangle", "stream": "spawn",
            "sample_axes": ["col", "row"], "sample_zero_range": False,
            "offset": {"row": -offset["y"], "col": offset["x"]},
            "random_range": {"row": extent["y"], "col": extent["x"]}}
    scene["metadata"]["m7_profiles"] = True
    meta["movement_and_rng_profile"].update(spawn_jitter="explicit_cartesian_halfextent_model",
        path="eight_neighbor_no_corner_cut_model")
    meta["pending"] = [p for p in meta["pending"] if p not in {"native_spawn_random_range"}]
    meta["pending"] += ["spawn_distribution_and_rng_native_alignment", "diagonal_path_native_alignment"]
    meta["model_profiles"]["steering"] = {"id": "bounded_proportional_velocity_v1", "status": "implemented_model",
        "native_formula_verified": False, "interpretation": "declared response_factor/acceleration use raw mover constants",
        "arrival_radius": .05, "arrival_radius_is_model_choice": True,
        "body_collision": "point-body grid clipping", "native_body_and_separation_forces_pending": True}
    meta["movement_and_rng_profile"]["steering"] = "explicit_bounded_velocity_response_model"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = build()
    if args.check:
        if json.loads(OUTPUT.read_bytes()) != value:
            raise SystemExit("M7 model source/output mismatch")
    else:
        OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
    print("M7 source-backed model profiles composed; formal acceptance remains pending.")
