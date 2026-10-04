"""Compose source-backed skill prototypes through V2 JSON primitives only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "packages/campaign/roster.reference.json"
CHARPACK = ROOT.parent / "data/charpack/char_151_myrtle.ab_unpacked/CAB-fc838138a094ccfeb005a5422115e724"
RANGES = ROOT / "ark_emulator/data_range_table.json"  # Offline JSON input only.
OUTPUT = ROOT / "packages/campaign/skills.myrtle.json"
NORMALIZED = ROOT / "packages/campaign/operators.normalized.json"
SOURCE_LOCK = ROOT / "packages/campaign/operator_sources.lock.json"
DUMP = ROOT.parent / "Ark_data/dump.cs"
SKILL = "ability/campaign_myrtle_s2"


def identity(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_components(path=CHARPACK):
    import UnityPy
    wanted = {6228503509698720609, 4170900438269670241, 673272970802344801,
              -4407543729288334495, -661438494929734815}
    result = {}
    for obj in UnityPy.load(str(path)).objects:
        if obj.path_id in wanted:
            tree = obj.read_typetree()
            result[str(obj.path_id)] = {"script_path_id": tree.get("m_Script", {}).get("m_PathID"),
                "fields": {k: v for k, v in tree.items() if not k.startswith("m_")}}
    if len(result) != len(wanted):
        raise ValueError("native Myrtle mode/heal/selector components missing")
    root = result["6228503509698720609"]["fields"]
    mode = result["4170900438269670241"]["fields"]
    if root["_modes"][2]["m_PathID"] != 4170900438269670241 or mode["_attack"]["m_PathID"] != 673272970802344801:
        raise ValueError("native mode 2 no longer binds the selected healing attack")
    return result


def native_enums():
    constants = {"public const FilterUtil.FilterType HP_RATIO_NOT_FULL_ASC": None,
                 "public const AttributeType BLOCK_CNT": None,
                 "public const AttributeModifierData.AttributeModifier.FormulaItemType FINAL_SCALER": None}
    with DUMP.open(encoding="utf-8") as source:
        for line in source:
            for key in constants:
                if line.strip().startswith(key + " ="):
                    constants[key] = int(line.split("=", 1)[1].strip().rstrip(";"))
    if list(constants.values()) != [3, 5, 3]:
        raise ValueError("native healing/filter/block modifier enum mapping changed")
    return constants


def build(character_id="char_151_myrtle"):
    reference = json.loads(REFERENCE.read_bytes())
    if character_id != "char_151_myrtle":
        selected = next((r for r in reference["roster"] if r["character_id"] == character_id), None)
        if selected is None:
            raise ValueError("operator is outside the fixed campaign roster")
        raise ValueError(f"selected skill recipe not implemented: {selected['config']['skill_id']}; "
                         f"requires independently validated {', '.join(selected['candidate_mechanisms'])}")
    row = next(r for r in reference["roster"] if r["character_id"] == "char_151_myrtle")
    normalized = json.loads(NORMALIZED.read_bytes())
    official = next(r for r in normalized["operators"] if r["character_id"] == "char_151_myrtle")
    level = official["selected_skill"]["level"]
    if (official["config"] != row["config"] or official["selected_skill"]["native_level_index"] != 9
            or level["spData"]["spType"] != "INCREASE_WITH_TIME"
            or level["spData"]["maxChargeTime"] != 1
            or level["skillType"] != "MANUAL"):
        raise ValueError("normalized official configuration or selected skill type disagrees with frozen recipe")
    for key in ("duration", "rangeId", "prefabId"):
        if level[key] != row["skill_level"][key]:
            raise ValueError(f"official skill field disagrees with frozen local table: {key}")
    for key in ("spCost", "initSp", "increment"):
        if level["spData"][key] != row["skill_level"]["spData"][key]:
            raise ValueError(f"official skill SP disagrees with frozen local table: {key}")
    values = {r["key"]: r["value"] for r in level["blackboard"]}
    if values != {r["key"]: r["value"] for r in row["skill_level"]["blackboard"]}:
        raise ValueError("official skill blackboard disagrees with frozen local table")
    enums = native_enums()
    prefab = reference["frozen"]["prefab_catalog"][level["prefabId"]]
    linked = {(c["cabin"], c["pathID"]): c for c in reference["frozen"]["linked_components"]}
    for component in prefab["components"]:
        if linked.get((component["cabin"], component["pathID"])) != component:
            raise ValueError("selected native skill prefab differs from frozen CAB dependency closure")
    native = native_components()
    healing = native["673272970802344801"]["fields"]
    target = native["-4407543729288334495"]["fields"]
    trigger = native["-661438494929734815"]["fields"]
    attack = next(c["fields"] for c in prefab["components"] if c["class"] == "AttackAbility")
    buffs = [b for c in prefab["components"] for b in c["fields"].get("_buffs", [])]
    periodic = next(b for b in buffs if b.get("templateKey") == "periodic_cost")
    if (attack["_attackBlackboardModeIndex"] != 2 or attack["_allowSpRecoveryWhenAffecting"] != 0
            or periodic["triggerInterval"] != 1 or periodic["waitFirstTriggerInterval"] != 1
            or target["_maxNum"] != 1 or target["_limitTargetNum"] != 1
            or target["_postFilter"] != enums["public const FilterUtil.FilterType HP_RATIO_NOT_FULL_ASC"]
            or target["_excludeOwner"] != 0 or trigger["_keepTarget"] != 0):
        raise ValueError("native timing/SP/target assumptions changed; re-review recipe")
    duration, interval = level["duration"], values["interval"]
    count = int(values["value"] / values["cost"])
    if count * interval != duration or healing["_cooldown"] != interval:
        raise ValueError("periodic recipe needs an independently reviewed nonuniform schedule")
    grids = json.loads(RANGES.read_bytes())[level["rangeId"]]["grids"]
    timeline = [
        {"at": 0, "effect": {"op": "apply_buff", "target": "source", "buff": "buff/campaign_myrtle_no_block"}},
        {"at_seconds": interval, "repeat": {"count": count, "interval_seconds": interval},
         "effect": {"op": "modify_resource", "target": "battle", "resource": "dp", "delta": values["cost"]}},
        {"at_seconds": healing["_preDelay"], "repeat": {"count": count, "interval_seconds": healing["_cooldown"]},
         "effect": {"op": "heal", "target": "selected", "scale": values["attack@heal_scale"]}},
    ]
    parameters = {"healing": True, "blocks_attacks": True}
    ability = {"id": SKILL, "kind": "ability", "metadata": {"native_skill_id": row["config"]["skill_id"],
               "status": "partially_implemented"}, "activation": {"mode": "manual",
               "costs": [{"resource": "sp", "amount": level["spData"]["spCost"]}]},
               "duration_seconds": duration, "parameters": parameters,
               "selector": "selector/campaign_myrtle_heal", "target_capture": "each_hit", "timeline": timeline}
    caster = {"id": "unit/campaign_myrtle_fixture", "kind": "entity", "tags": ["player"],
              "metadata": {"status": "partially_implemented", "synthetic_attributes": True}, "components": {
              "attributes": {"base": {"atk": 100, "max_hp": 1000, "def": 0, "mres": 0,
                                      "block_count": 1, "attack_interval": 1, "attack_speed_ratio": 1}},
              "resources": {"hp": {"initial": 1000, "capacity": 1000, "role": "health"},
                  "sp": {"initial": level["spData"]["initSp"], "capacity": level["spData"]["spCost"],
                         "recovery_rate": level["spData"]["increment"],
                         "recovery": {"mode": "periodic", "interval_seconds": 1},
                         "parameters": {"freeze_while_cast": True, "freeze_cast_modes": ["manual"], "pause_at_full": True}}},
              "spatial": {}, "behavior": {"machine": "behavior/player_combat"},
              "abilities": ["ability/campaign_myrtle_fixture_attack", SKILL]}}
    ally = {"id": "unit/campaign_myrtle_ally", "kind": "entity", "tags": ["player"], "components": {
        "attributes": {"base": {"max_hp": 2000}}, "resources": {"hp": {"initial": 100, "capacity": 2000, "role": "health"}}, "spatial": {}}}
    enemy = {"id": "unit/campaign_myrtle_target", "kind": "entity", "tags": ["enemy"], "components": {
        "attributes": {"base": {"max_hp": 999999, "def": 0, "mres": 0}},
        "resources": {"hp": {"initial": 999999, "capacity": 999999, "role": "health"}}, "spatial": {}}}
    return {"schemaVersion": 2, "status": "partially_implemented", "manifest": {
        "id": "package/campaign_myrtle_s2_prototype", "version": "1", "metadata": {
            "official_unit_config_imported": False, "client_validated": False,
            "source_hashes": {"roster_reference": identity(REFERENCE), "charpack": identity(CHARPACK),
                              "offline_range_json": identity(RANGES), "official_normalized": identity(NORMALIZED),
                              "official_source_lock": identity(SOURCE_LOCK), "native_enum_dump": identity(DUMP)},
            "official_selected_skill": official["selected_skill"], "native_enum_evidence": enums,
            "native_char_components": native, "native_skill_prefab": prefab,
            "native_skill_level": level, "scope": "skill composition prototype; not mainline conversion",
            "timing_limits": ["DP endpoint at16 is an explicit model settlement policy, client same-tick expiry order pending",
                              "heal first hit follows mode2 component preDelay; animation/FSM client alignment pending",
                              "talent25HP regeneration, official attributes/trust and deploy lifecycle pending"]}},
        "entities": [caster, ally, enemy], "abilities": [ability,
            {"id": "ability/campaign_myrtle_fixture_attack", "kind": "ability", "activation": {"mode": "automatic_attack"},
             "selector": "selector/campaign_myrtle_enemy", "timeline": [{"at": 0, "effect": {"op": "damage", "damage_type": "physical"}}]}],
        "buffs": [{"id": "buff/campaign_myrtle_no_block", "kind": "buff", "duration_seconds": duration,
                   "modifiers": [{"attribute": "block_count", "layer": "final_ratio", "value": -1}]}],
        "selectors": [{"id": "selector/campaign_myrtle_heal", "kind": "selector",
                       "region": {"type": "grid_offsets", "offsets": [[g["row"], g["col"]] for g in grids], "rotate_with_facing": False},
                       "filters": [{"tag": "player"}, {"state": "alive"}], "limit": target["_maxNum"]},
                      {"id": "selector/campaign_myrtle_enemy", "kind": "selector", "region": {"type": "all"},
                       "filters": [{"tag": "enemy"}, {"state": "alive"}], "limit": 1}],
        "scenarioDraft": {"id": "scenario/campaign_myrtle_s2_prototype", "ruleset": "ruleset/ark_standard",
            "metadata": {"status": "partially_implemented", "not_formal_mainline": True}, "map": {"rows": 5, "cols": 5},
            "resources": {"dp": {"initial": 0, "capacity": 99}}, "initialEntities": [
                {"definition": caster["id"], "instanceAlias": "myrtle", "position": {"row": 2, "col": 2}},
                {"definition": ally["id"], "instanceAlias": "ally", "position": {"row": 2, "col": 3}},
                {"definition": enemy["id"], "instanceAlias": "target", "position": {"row": 3, "col": 3}}]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--operator", default="char_151_myrtle")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build(args.operator)
    if args.check:
        if json.loads(args.output.read_bytes()) != result:
            raise ValueError("prototype source or output identity changed")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "status": "partially_implemented"}))


if __name__ == "__main__":
    main()
