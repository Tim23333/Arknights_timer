"""Partial support skill recipes with raw prefab evidence and explicit gaps."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED = ROOT / "packages/campaign/operators.normalized.json"
REFERENCE = ROOT / "packages/campaign/roster.reference.json"
RANGES = ROOT / "ark_emulator/data_range_table.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_character(cid):
    import UnityPy
    paths = [p for p in (ROOT.parent / "data/charpack" / (cid + ".ab_unpacked")).glob("CAB-*") if not p.name.endswith(".resS")]
    if len(paths) != 1:
        raise ValueError("native charpack source is missing or ambiguous")
    rows = {}
    for obj in UnityPy.load(str(paths[0])).objects:
        if obj.type.name == "MonoBehaviour":
            tree = obj.read_typetree()
            rows[str(obj.path_id)] = {"script_path_id": tree.get("m_Script", {}).get("m_PathID"),
                "fields": {k: v for k, v in tree.items() if not k.startswith("m_")}}
    return paths[0], rows


def source(cid):
    normalized = json.loads(NORMALIZED.read_bytes())
    row = next(r for r in normalized["operators"] if r["character_id"] == cid)
    level = row["selected_skill"]["level"]
    frozen = json.loads(REFERENCE.read_bytes())["frozen"]
    prefab = frozen["prefab_catalog"][level["prefabId"]]
    linked = {(c["cabin"], c["pathID"]): c for c in frozen["linked_components"]}
    if any(linked.get((c["cabin"], c["pathID"])) != c for c in prefab["components"]):
        raise ValueError("native skill dependency closure mismatch")
    path, character = raw_character(cid)
    return row, level, prefab, character, {"normalized": sha(NORMALIZED), "roster_reference": sha(REFERENCE),
        "range_json": sha(RANGES), "charpack": sha(path)}


def common(cid, row, level, prefab, character, hashes, gaps):
    return {"schemaVersion": 2, "status": "partially_implemented", "manifest": {
        "id": "package/support_" + cid, "version": "1", "metadata": {
            "status": "partially_implemented", "synthetic_attributes": True, "client_validated": False,
            "official_unit_complete": False, "source_hashes": hashes, "native_selected_skill": row["selected_skill"],
            "native_talents": row["talents"], "native_skill_prefab": prefab, "native_character_components": character,
            "pending_mechanics": gaps}}, "entities": [], "abilities": [], "buffs": [], "selectors": [], "rules": []}


def build_liskam(*, require_complete=False):
    cid = "char_107_liskam"
    row, level, prefab, character, hashes = source(cid)
    values = {b["key"]: b["value"] for b in level["blackboard"]}
    native_buffs = [b for c in prefab["components"] for b in c["fields"].get("_buffs", [])]
    if (level["skillType"] != "AUTO" or level["spData"]["spType"] != "INCREASE_WHEN_TAKEN_DAMAGE"
            or level["spData"]["maxChargeTime"] != 1
            or not any(b["templateKey"] == "damage_block_once" and b["lifeTimeType"] == 1 for b in native_buffs)):
        raise ValueError("native shield/SP assumptions changed")
    gaps = ["native_waitForAttackEvent_activation_frame_pending", "native_blocked_hit_SP_semantics_pending",
            "random_neighbor_and_self_SP_talent_pending", "native_normal_attack_and_full_unit_config_pending",
            "incoming_damage_effects_must_bind_guard_pipeline"]
    if require_complete:
        raise ValueError("complete Liskarm recipe unsupported: " + "; ".join(gaps))
    package = common(cid, row, level, prefab, character, hashes, gaps)
    shield_rule = {"id": "rule/liskam_one_block", "kind": "calculation_rule", "contract": "damage.pipeline",
        "metadata": {"input_bindings": {"attack": {"entity": "source", "attribute_role": "attack"},
                      "defense": {"entity": "target", "attribute_role": "defense"},
                      "resistance": {"entity": "target", "attribute_role": "resistance"}}},
        "implementation": {"type": "graph", "nodes": [
            {"id": "native", "rule": "rule/ark_damage_pipeline", "inputs": {
                "source": "inputs.source", "target": "inputs.target", "effect": "inputs.effect",
                "samples": "inputs.samples", "states": "inputs.states"}},
            {"id": "settlement", "expression":
            "{'accepted': True, 'amount': 0, 'allocations': [{'target': 'target', 'resource': 'shield_charge', 'amount': 1}], 'events': []} "
            "if inputs.target.components.resources.shield_charge.current > 0 else nodes.native"}],
            "output": "nodes.settlement"}}
    package["rules"] = [shield_rule, {"id": "rule/liskam_taken_sp", "kind": "calculation_rule", "contract": "resource.recovery",
        "implementation": {"type": "expression", "expression": "inputs.current + inputs.parameters.amount"}}]
    unit = {"id": "unit/liskam_support_fixture", "kind": "entity", "tags": ["player"],
        "components": {"attributes": {"base": {"max_hp": 100000, "atk": 100, "def": 100, "mres": 0}},
            "spatial": {}, "resources": {"hp": {"initial": 100000, "capacity": 100000, "role": "health"},
                "shield_charge": {"initial": 0, "capacity": 1}, "sp": {"initial": level["spData"]["initSp"], "capacity": level["spData"]["spCost"],
                    "recovery_rule": "rule/liskam_taken_sp", "recovery": {"mode": "event", "event": "damage.accepted", "owner_role": "target", "amount": 1},
                    "parameters": {"freeze_while_cast": True, "freeze_cast_modes": ["manual"]}}},
            "abilities": ["ability/liskam_s1"]}}
    package["entities"] = [unit, {"id": "unit/support_attacker", "kind": "entity", "tags": ["enemy"], "components": {
        "attributes": {"base": {"atk": 150, "max_hp": 1000, "def": 0, "mres": 0}}, "spatial": {},
        "resources": {"hp": {"initial": 1000, "capacity": 1000, "role": "health"}}, "abilities": ["ability/support_hit"]}}]
    package["abilities"] = [{"id": "ability/liskam_s1", "kind": "ability", "metadata": {"native_skill_id": row["config"]["skill_id"], "status": "partially_implemented"},
        "activation": {"mode": "manual", "costs": [{"resource": "sp", "amount": level["spData"]["spCost"]}],
                       "parameters": {"auto_when_ready": True, "auto_only": True, "blocks_attacks": False}, "on_start": [
            {"op": "apply_buff", "target": "source", "buff": "buff/liskam_def"},
            {"op": "modify_resource", "target": "source", "resource": "shield_charge", "delta": 1}]},
        "duration_seconds": values["duration"], "timeline": [
            {"at_seconds": values["duration"], "effect": {"op": "modify_resource", "target": "source", "resource": "shield_charge", "delta": -1}}]},
        {"id": "ability/support_hit", "kind": "ability", "activation": {"mode": "manual"},
         "selector": "selector/liskam_target", "timeline": [{"at": 0, "effect": {"op": "damage", "damage_type": "physical",
             "rules": {"damage.pipeline": shield_rule["id"]}}}]}]
    package["buffs"] = [{"id": "buff/liskam_def", "kind": "buff", "duration_seconds": values["duration"],
        "modifiers": [{"attribute": "def", "layer": "direct_ratio", "value": values["def"]}]}]
    package["selectors"] = [{"id": "selector/liskam_target", "kind": "selector", "region": {"type": "all"},
        "filters": [{"tag": "player"}, {"state": "alive"}], "limit": 1}]
    package["scenarioDraft"] = {"id": "scenario/liskam_support_fixture", "ruleset": "ruleset/ark_standard",
        "metadata": {"status": "partially_implemented", "not_formal_mainline": True}, "map": {"rows": 2, "cols": 2},
        "initialEntities": [{"definition": unit["id"], "instanceAlias": "liskam", "position": {"row": 0, "col": 0}},
                            {"definition": "unit/support_attacker", "instanceAlias": "attacker", "position": {"row": 0, "col": 1}}]}
    return package


def build_plosis(*, require_complete=False):
    cid = "char_128_plosis"
    row, level, prefab, character, hashes = source(cid)
    root = character["5905979480863349313"]["fields"]
    mode = character[str(root["_modes"][1]["m_PathID"])]["fields"]
    healing = character[str(mode["_attack"]["m_PathID"])]["fields"]
    target = character[str(healing["_selector"]["m_PathID"])]["fields"]
    if target["_maxNum"] != 3 or target["_postFilter"] != 3 or target["_excludeOwner"] != 0:
        raise ValueError("native three-target heal assumptions changed")
    gaps = ["skill_cadence_ramp_not_reconstructed_from_native_FSM", "only_first_mode1_heal_packet_implemented",
            "SP_aura_membership_highest_effect_and_exit_cleanup_pending", "normal_heal_mode_restore_pending",
            "native_animation_event_alignment_and_full_unit_stats_pending"]
    if require_complete:
        raise ValueError("complete Ptilopsis recipe unsupported: " + "; ".join(gaps))
    package = common(cid, row, level, prefab, character, hashes, gaps)
    grids = json.loads(RANGES.read_bytes())[level["rangeId"]]["grids"]
    unit = {"id": "unit/plosis_support_fixture", "kind": "entity", "tags": ["player"], "components": {
        "attributes": {"base": {"atk": 100, "max_hp": 1000}}, "spatial": {},
        "resources": {"hp": {"initial": 1000, "capacity": 1000, "role": "health"}, "sp": {
            "initial": level["spData"]["initSp"], "capacity": level["spData"]["spCost"], "recovery_rate": 1,
            "recovery": {"mode": "periodic", "interval_seconds": 1},
            "parameters": {"freeze_while_cast": True, "freeze_cast_modes": ["manual"]}}}, "abilities": ["ability/plosis_s2_first_packet"]}}
    ally = {"id": "unit/support_ally", "kind": "entity", "tags": ["player"], "components": {
        "attributes": {"base": {"max_hp": 10000}}, "spatial": {},
        "resources": {"hp": {"initial": 100, "capacity": 10000, "role": "health"}}}}
    package["entities"] = [unit, ally]
    package["abilities"] = [{"id": "ability/plosis_s2_first_packet", "kind": "ability",
        "metadata": {"native_skill_id": row["config"]["skill_id"], "status": "partially_implemented", "first_packet_only": True},
        "activation": {"mode": "manual", "costs": [{"resource": "sp", "amount": level["spData"]["spCost"]}]},
        "duration_seconds": level["duration"], "parameters": {"healing": True},
        "selector": "selector/plosis_s2", "target_capture": "each_hit", "timeline": [
            {"at_seconds": healing["_preDelay"], "effect": {"op": "heal", "scale": 1}}]}]
    package["selectors"] = [{"id": "selector/plosis_s2", "kind": "selector",
        "region": {"type": "grid_offsets", "offsets": [[g["row"], g["col"]] for g in grids], "rotate_with_facing": True},
        "filters": [{"tag": "player"}, {"state": "alive"}], "limit": 3}]
    package["scenarioDraft"] = {"id": "scenario/plosis_support_fixture", "ruleset": "ruleset/ark_standard",
        "metadata": {"status": "partially_implemented", "not_formal_mainline": True}, "map": {"rows": 9, "cols": 9},
        "initialEntities": [{"definition": unit["id"], "instanceAlias": "plosis", "position": {"row": 4, "col": 4}, "facing": "right"}] + [
            {"definition": ally["id"], "instanceAlias": f"ally{i}", "position": {"row": 4, "col": 4+i}} for i in range(1, 4)]}
    return package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for key, function in (("liskam", build_liskam), ("plosis", build_plosis)):
        value = function()
        path = ROOT / f"packages/campaign/skills.{key}.json"
        if args.check:
            if json.loads(path.read_bytes()) != value:
                raise ValueError("support recipe identity changed")
        else:
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(path), "status": "partially_implemented"}))


if __name__ == "__main__":
    main()
