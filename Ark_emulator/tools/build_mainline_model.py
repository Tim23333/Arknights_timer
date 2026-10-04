"""Compose the first native stage and squad under explicit partial profiles."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_mainline_draft import translate
from tools.build_campaign_squad import build as squad
from tools.build_campaign_enemy_attacks import build as attacks
from tools.build_mainline_control_model import build as controls
from tools.build_mainline_dependencies import build as dependencies

OUTPUT = ROOT/"packages/campaign/mainline_models/level_main_00-10.json"
SECTIONS = ("entities", "abilities", "buffs", "selectors", "rules", "behaviors", "policies")


def build():
    draft, team, enemies, control = translate(), squad(), attacks(), controls()
    meta = draft["manifest"]["metadata"]
    plan = dependencies()
    native = json.loads((ROOT/"packages/campaign/native_reference/level_main_00-10.json").read_text(encoding="utf8"))
    if plan["applicable_runes"] or meta["native_branches"] or plan["native_global_buffs"]:
        # Unsupported semantics must not disappear in an executable draft.
        raise ValueError("native runes or branches require conversion")
    predefines = meta["native_predefines"]
    if any(predefines.values()):
        raise ValueError("native predefines require conversion")
    result = {"schemaVersion": 2, "status": "executable_partial_model_not_accepted",
        "manifest": {"id": "package/campaign/model/level_main_00-10", "version": "0.1.0",
            "requires": ["preset/ark_standard"], "metadata": {
                "formal_mainline_approved": False, "complete_operator_count": 0, "client_validated": False,
                "control_model": control, "squad_model": team["manifest"]["metadata"],
                "enemy_model": enemies["manifest"]["metadata"], "dependency_source": meta["dependency_plan_source"],
                "inactive_native_runes": plan["inactive_runes"],
                "native_options": plan["native_options"], "native_random_seed": native.get("randomSeed"),
                "movement_and_rng_profile": {"native_random_seed_binding_verified": False,
                    "spawn_jitter": "source_retained_not_executed",
                    "path": "four_neighbor_grid_with_declared_waypoints",
                    "steering": "model_path_clock_not_native_steering"},
                "pending": ["native_operator_clock_and_source_alignment", "independent_full_stage_review_and_execution",
                            "unsupported_native_options_assessment", "native_wave_ui_callback_timing",
                            "native_random_seed_role_and_binding", "native_spawn_random_range",
                            "native_diagonal_and_steering_semantics"]}}}
    for section in SECTIONS:
        found = {}
        for package in (draft, team, enemies):
            for row in package.get(section, []):
                if row["id"] in found and found[row["id"]] != row:
                    raise ValueError(f"conflicting stage model definition: {row['id']}")
                found[row["id"]] = deepcopy(row)
        if found:
            result[section] = [found[k] for k in sorted(found)]
    preset = json.loads((ROOT/"ark_sim/content/presets/ark_standard.json").read_text(encoding="utf8"))
    layers = next(r["attribute_layers"] for r in preset["rulesets"] if r["id"] == "ruleset/ark_standard")
    for entity in result["entities"]:
        if "enemy" in entity.get("tags", []):
            entity.setdefault("rules", {})["attributes.effective"] = "rule/support_temporal"
            entity["components"]["attributes"]["layers"] = list(dict.fromkeys([*layers, "sluggish", "fragility"]))
    scene = deepcopy(draft["scenarioDraft"])
    scene["id"] = "scenario/campaign_model/level_main_00-10"
    scene.pop("dependencies")
    scene["scheduledEffects"] = deepcopy(control["scheduledEffects"])
    scene["metadata"].update(runnable=True, model_validated=False, formal_mainline_approved=False,
        model_status="partial_integration", native_ui_policy=control["model_policy"])
    result["scenarioDraft"] = scene
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = build()
    if args.check:
        if json.loads(OUTPUT.read_text(encoding="utf8")) != value:
            raise SystemExit("stage model sources changed")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
    print("0-10 executable integration model; formal acceptance remains pending.")
