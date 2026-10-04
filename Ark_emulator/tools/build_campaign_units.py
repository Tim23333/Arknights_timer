"""Translate fixed roster base units without inventing missing attack evidence.

This is a base-unit model, not a complete operator or mainline approval. Selected
skills and talents remain explicit integration dependencies in the report.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "packages/campaign/units.base.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attack_plan(row, unit, ranges, bindings=None):
    native = row["base_attack_fields"]
    evidence = row["animation_evidence"]
    default = next(m["attack"] for m in evidence["modes"] if m["mode"] == "Default")
    animation = default.get("animKey") or default.get("oneshotAnim")
    events = [e for e in evidence.get("anims", {}).get(animation, {}).get("ev", []) if e["n"] == "OnAttack"]
    bound = (bindings or {}).get("operators", {}).get(row["character_id"])
    binding_pending = []
    if bound:
        mode = bound["modes"][0]
        if mode["attack_path_id"] != row["attack_path_id"] or bound["charpack_source"]["sha256"] != row["source"]["sha256"]:
            raise ValueError("Animation binding refers to a different native attack")
        front, back = mode["bindings_by_face"]["front"], mode["bindings_by_face"]["back"]
        if front["events"] != back["events"]:
            raise ValueError("Face-specific attack timing needs an explicit direction adapter")
        animation = front["animation_name"]
        events = [{"n": e["name"], "f": e["frame"], "t": e["seconds"]} for e in front["events"] if e["name"] == "OnAttack"]
        binding_pending = list(bound["pending"]) + list(mode["pending"])
    pending = []
    if not events:
        pending.append("native_attack_animation_event_unresolved")
    projectile = native.get("_projectileKey")
    projectile_binding = (bindings or {}).get("projectiles", {}).get(projectile)
    projectile_speed = projectile_binding["speed"] if projectile_binding else default.get("projectileSpeed")
    if projectile and not projectile_speed:
        pending.append("native_projectile_travel_unresolved")
    identifier = row["character_id"]
    phase = unit["raw_character"]["phases"][unit["config"]["elite_phase"]]
    range_id = phase["rangeId"]
    if range_id not in ranges:
        raise ValueError(f"Missing range {range_id}")
    offsets = [[-cell["row"], cell["col"]] for cell in ranges[range_id]["grids"]]
    selector_fields = [c["fields"] for c in row["components"].values() if "_targetSide" in c["fields"]]
    if len(selector_fields) > 1:
        raise ValueError(f"Ambiguous base selector for {identifier}")
    native_selector = selector_fields[0] if selector_fields else {}
    healing = unit["raw_character"]["profession"] == "MEDIC"
    # Frozen implicit combat selectors default to one ordinary attack target.
    # Their native priority/filter details remain separate pending dependencies.
    count = native_selector.get("_maxNum", 1) if native_selector.get("_limitTargetNum", 1) else None
    selector = {"id": f"selector/{identifier}/normal_attack", "kind": "selector",
        "region": {"type": "grid_offsets", "offsets": offsets},
        "filters": [{"tag": "player" if healing else "enemy"}, {"state": "alive"}],
        "metadata": {"native_range_id": range_id, "native_selector_fields": native_selector,
                     "priority_and_immunity_model_pending": True}}
    if native_selector.get("_targetMotion") == 1 or unit["raw_character"]["position"] == "MELEE" and not native_selector:
        selector["filters"].append({"tag": "ground"})
        selector["parameters"] = {"include_blocked": True}
    if native_selector.get("_limitedMaxTargetNumToBlockedCnt"):
        selector["limit_attribute"] = "block_count"
    elif count is not None:
        selector["limit"] = count
    ability = {"id": f"ability/{identifier}/normal_attack", "kind": "ability",
        "activation": {"mode": "automatic_attack"}, "selector": selector["id"],
        "parameters": {"healing": healing}, "timeline": [],
        "metadata": {"native_animation": animation, "native_attack_fields": native,
            "native_prefab_pre_delay": native.get("_preDelay"),
            "timing_policy": "unscaled_native_animation_event_probe", "client_fsm_timing_verified": False}}
    if bound:
        ability["metadata"]["exact_animation_binding"] = mode
        ability["metadata"]["pending_native_callback_alignment"] = binding_pending
    if projectile and projectile_speed:
        ability["parameters"]["projectile_speed"] = projectile_speed
    if not pending:
        for event in events:
            effect = {"op": "heal" if healing else "damage", "scale": native.get("_atkScale", 1)}
            if not healing:
                effect["damage_type"] = {1: "physical", 2: "arts", 3: "true"}[native["_damageType"]]
            ability["timeline"].append({"at_seconds": event["f"] / 30, "effect": effect})
    return selector, ability if not pending else None, pending


def build():
    normal_path = ROOT / "packages/campaign/operators.normalized.json"
    attack_path = ROOT / "packages/campaign/attacks.reference.json"
    range_path = ROOT / "ark_emulator/data_range_table.json"
    bindings_path = ROOT / "packages/campaign/animation_bindings.reference.json"
    bindings = load(bindings_path)
    # A checksum of the supplied JSON cannot prove that derived timing agrees
    # with its evidence. Rebuild from current assets and controlled reader;
    # this also locks extractor/library identities and rejects forged aliases.
    from tools.extract_campaign_animation_bindings import build as rebuild_bindings
    if bindings != rebuild_bindings():
        raise ValueError("Animation binding source/evidence identity mismatch")
    normal, attacks, ranges = load(normal_path), load(attack_path), load(range_path)
    if attacks["normalized_sha256"] != sha(normal_path):
        raise ValueError("Normal attack sources refer to a different normalized roster")
    by_id = {r["character_id"]: r for r in attacks["operators"]}
    entities, abilities, selectors, report = [], [], [], []
    mapping = {"maxHp": "max_hp", "atk": "atk", "def": "def", "magicResistance": "mres",
               "baseAttackTime": "attack_interval", "moveSpeed": "move_speed", "blockCnt": "block_count",
               "cost": "deploy_cost", "respawnTime": "redeploy_time", "massLevel": "mass_level",
               "spRecoveryPerSec": "sp_recovery_rate"}
    for row in normal["operators"]:
        identifier = row["character_id"]
        stats = row["stats"]["model_stats"]
        base = {dest: stats[src] for src, dest in mapping.items()}
        base.update(attack_speed_ratio=stats["attackSpeed"] / 100, block_cost=1)
        selector, ability, missing = attack_plan(by_id[identifier], row, ranges, bindings)
        selectors.append(selector)
        if ability:
            abilities.append(ability)
        native_skill = row["selected_skill"]["skill_id"]
        report.append({"character_id": identifier, "normal_attack_converted": ability is not None,
            "missing_attack_evidence": missing, "selected_skill_integration": native_skill,
            "pending": ["selected_skill_integration", "all_applicable_talents", "native_selector_priority_and_immunity",
                        "client_animation_scaling_and_fsm", "source_version_alignment", *missing],
            "complete_operator": False})
        entities.append({"id": "unit/" + identifier, "kind": "entity", "tags": ["player", "ground"],
            "metadata": {"native_id": identifier, "config": row["config"], "selected_skill_native_id": native_skill,
                         "complete_operator": False, "client_formula_verified": False},
            "components": {"attributes": {"base": base},
                "resources": {"hp": {"initial": base["max_hp"], "capacity_attribute": "max_hp", "role": "health"}},
                "abilities": [f"ability/{identifier}/normal_attack"],
                "deployable": {"policy": "policy/ark_ground_deploy", "terrain": "ground" if row["raw_character"]["position"] == "MELEE" else "high"},
                "lifecycle": {"policy": "policy/ark_lifecycle"}, "behavior": {"machine": "behavior/player_combat"}, "spatial": {}}})
    return {"schemaVersion": 2, "status": "partial_base_unit_models",
        "manifest": {"id": "package/campaign/base_units", "version": "0.1.0", "requires": ["preset/ark_standard"],
            "metadata": {"runnable": False, "complete_operator_count": 0, "sources": {"normalized": sha(normal_path), "attacks": sha(attack_path),
                 "offline_range_json": sha(range_path), "animation_bindings": sha(bindings_path)}, "conversion": report}},
        "entities": entities, "abilities": abilities, "selectors": selectors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != data:
            raise SystemExit("Base unit model source/artifact mismatch")
    else:
        OUTPUT.write_text(data, encoding="utf-8")
    print("Twelve source-backed base attacks checked; full-operator and client callback dependencies remain explicit.")
