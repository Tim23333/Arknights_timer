"""Compose 0-11 native source conversion with the same fixed M7 squad."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_m7_mainline_model import build as first_model, sha
from tools.build_mainline_draft import translate
from tools.build_mainline_dependencies import build as plan_for

OUTPUT = ROOT/"packages/campaign/mainline_models/level_main_00-11.m7.json"


def build():
    result = first_model()
    draft, plan = translate("level_main_00-11"), plan_for("level_main_00-11")
    source_path = ROOT/"packages/campaign/sources.00_11.reference.json"
    attacks_path = ROOT/"packages/campaign/enemies.00_11.attacks.json"
    controls_path = ROOT/"packages/campaign/controls.00_11.model.json"
    source, attacks, control = (json.loads(p.read_bytes()) for p in (source_path, attacks_path, controls_path))
    if any(plan["native_predefines"].values()) or plan["applicable_runes"] or plan["native_branches"] or plan["native_global_buffs"]:
        raise ValueError("0-11 nonempty native special content requires conversion")
    if source["native_exclude_char_ids"]:
        raise ValueError("0-11 native roster exclusions require explicit handling")
    result["manifest"]["id"] = "package/campaign/model/level_main_00-11/m7"
    meta = result["manifest"]["metadata"]
    meta.update(native_options=plan["native_options"], native_random_seed=source["native_random_seed"],
        dependency_source=plan["source"], enemy_model=attacks["manifest"]["metadata"], control_model=control,
        inactive_native_runes=plan["inactive_runes"])
    meta["m7_source_identities"].update(source_00_11=sha(source_path), attacks_00_11=sha(attacks_path), controls_00_11=sha(controls_path))
    meta["pending"].append("native_managed_wave_completion_gating_not_converted")
    meta["schedule_profile"] = {"id": "flat_last_action_schedule_v1", "native_wave_gating_verified": False}
    result["entities"] = [e for e in result["entities"] if "enemy" not in e.get("tags", [])]
    movers = {r["native_id"]: r["animation"]["root_mover_components"] for r in source["enemies"]}
    for entity in draft["entities"]:
        entity["rules"] = {"attributes.effective": "rule/support_temporal"}
        entity["components"]["attributes"]["layers"] = ["flat", "direct_ratio", "final_ratio", "sluggish", "fragility"]
        components = movers[entity["metadata"]["native_id"]]
        if len(components) != 1:
            raise ValueError("exact native enemy mover must be unique")
        fields = components[0]["fields"]
        entity["components"]["spatial"]["steering"] = {"rule": "rule/m7_steering_velocity",
            "parameters": {"response_factor": fields["_steeringFactor"], "max_acceleration": fields["_maxSteeringForce"], "arrival_radius": .05}}
        result["entities"].append(entity)
    for section in ("abilities", "selectors"):
        result[section] = [r for r in result[section] if not r["id"].startswith(("ability/enemy_", "selector/enemy_"))]
        result[section].extend(deepcopy(attacks[section]))
    scene = deepcopy(draft["scenarioDraft"])
    scene["id"] = "scenario/campaign_model/level_main_00-11/m7"
    scene.pop("dependencies")
    scene["scheduledEffects"] = deepcopy(control["scheduledEffects"])
    scene["seed"] = source["native_random_seed"]
    scene["rules"]["movement.path"] = "rule/m7_diagonal_path"
    scene["metadata"].update(runnable=True, model_validated=False, formal_mainline_approved=False, m7_profiles=True)
    unsupported = sorted({cp["type"] for wave in scene["waves"] for cp in wave["route"]["checkpoints"]
                          if cp.get("type") not in {"MOVE", "WAIT_FOR_SECONDS", 0, 1}})
    if unsupported:
        result["status"] = "draft_unresolved_checkpoint_dependencies"
        scene["metadata"]["runnable"] = False
        scene["metadata"]["pending_checkpoint_types"] = unsupported
    for wave in scene["waves"]:
        route = wave["route"]
        wave["placement"] = {"rule": "rule/m7_spawn_rectangle", "stream": "spawn", "sample_axes": ["col", "row"],
            "sample_zero_range": False, "random_range": {"row": route["spawnRandomRange"]["y"], "col": route["spawnRandomRange"]["x"]},
            "offset": {"row": -route["spawnOffset"]["y"], "col": route["spawnOffset"]["x"]}}
    result["scenarioDraft"] = scene
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = build()
    if args.check:
        if json.loads(OUTPUT.read_bytes()) != value:
            raise SystemExit("0-11 M7 composition changed")
    else:
        OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
    print("0-11 M7 content composed; execution and independent acceptance remain pending.")
