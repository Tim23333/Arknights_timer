"""Source-backed aura prototypes with live membership, not fixed targets."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED = ROOT / "packages/campaign/operators.normalized.json"
REFERENCE = ROOT / "packages/campaign/roster.reference.json"
RANGES = ROOT / "ark_emulator/data_range_table.json"
FRAMES = ROOT.parent / "data/tables/effect_frames.json"
IDS = {"demkni": "char_202_demkni", "lisa": "char_358_lisa", "cgbird": "char_179_cgbird"}


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_source(name):
    import UnityPy
    cid = IDS[name]
    row = next(r for r in read(NORMALIZED)["operators"] if r["character_id"] == cid)
    old = next(r for r in read(REFERENCE)["roster"] if r["character_id"] == cid)
    level = row["selected_skill"]["level"]
    if row["config"] != old["config"] or row["selected_skill"]["native_level_index"] != 9:
        raise ValueError("fixed skill configuration mismatch")
    if level["skillType"] != "MANUAL" or level["spData"]["spType"] != "INCREASE_WITH_TIME" or level["spData"]["maxChargeTime"] != 1:
        raise ValueError("unsupported native skill/SP driver")
    for key in ("duration", "rangeId", "prefabId"):
        if level[key] != old["skill_level"][key]:
            raise ValueError("official/local selected duration/range/prefab differs")
    for key in ("spCost", "initSp", "increment"):
        if level["spData"][key] != old["skill_level"]["spData"][key]:
            raise ValueError("official/local selected SP parameters differ")
    bb = {b["key"]: b["value"] for b in level["blackboard"]}
    if bb != {b["key"]: b["value"] for b in old["skill_level"]["blackboard"]}:
        raise ValueError("official/local selected blackboard differs")
    frozen = read(REFERENCE)["frozen"]
    prefab = frozen["prefab_catalog"][level["prefabId"]]
    linked = {(c["cabin"], c["pathID"]): c for c in frozen["linked_components"]}
    closure, pending = {}, list(prefab["components"])
    def refs(value):
        if isinstance(value, dict):
            if value.get("m_FileID") == 0 and value.get("m_PathID"):
                yield value["m_PathID"]
            for child in value.values():
                yield from refs(child)
        elif isinstance(value, list):
            for child in value:
                yield from refs(child)
    while pending:
        c = pending.pop()
        if str(c["pathID"]) in closure:
            continue
        if linked.get((c["cabin"], c["pathID"])) != c:
            raise ValueError("native skill closure differs")
        closure[str(c["pathID"])] = c
        pending.extend(linked[(c["cabin"], key)] for key in refs(c["fields"]) if (c["cabin"], key) in linked)
    wrapper = next(c["fields"] for c in prefab["components"] if c["class"] == "AttackAbility")
    if wrapper["_allowSpRecoveryWhenAffecting"] != 0:
        raise ValueError("native skill SP freeze changed")
    paths = [p for p in (ROOT.parent / "data/charpack" / (cid + ".ab_unpacked")).glob("CAB-*") if not p.name.endswith(".resS")]
    if len(paths) != 1:
        raise ValueError("charpack source ambiguous")
    components = {}
    for obj in UnityPy.load(str(paths[0])).objects:
        if obj.type.name == "MonoBehaviour":
            t = obj.read_typetree()
            components[str(obj.path_id)] = {"script_path_id": t.get("m_Script", {}).get("m_PathID"),
                "fields": {k: v for k, v in t.items() if not k.startswith("m_")}}
    roots = [c["fields"] for c in components.values() if "_modes" in c["fields"]]
    if len(roots) != 1:
        raise ValueError("charpack mode root ambiguous")
    mode_pointer = roots[0]["_modes"][wrapper["_attackBlackboardModeIndex"]]
    if mode_pointer["m_FileID"] != 0:
        raise ValueError("native mode external reference pending")
    mode = components[str(mode_pointer["m_PathID"])]["fields"]
    if mode["_attack"]["m_FileID"] != 0:
        raise ValueError("native attack external reference pending")
    attack = components[str(mode["_attack"]["m_PathID"])]["fields"]
    aura_fields = [c["fields"] for c in closure.values() if "_removeBuffWhenTargetLeave" in c["fields"]]
    if not aura_fields or any(c["_removeBuffWhenTargetLeave"] != 1 or c["_removeBuffWhenAbilityDetached"] != 1 for c in aura_fields):
        raise ValueError("native aura membership/detach policy changed")
    return row, level, bb, components, attack, closure, {
        "normalized": sha(NORMALIZED), "roster": sha(REFERENCE), "charpack": sha(paths[0]),
        "range_json": sha(RANGES), "effect_frames": sha(FRAMES)}


def build(name, *, require_complete=False):
    row, level, bb, components, attack, closure, hashes = load_source(name)
    gaps = ["native_full_unit_config_talents_and_animation_alignment_pending", "ability_interrupt_to_native_detach_timing_pending",
            "range_coordinates_from_offline_JSON_need_current_range_table_calibration"]
    gaps += {"demkni": ["heal_SP_talent_and驻场_stacks_pending", "multiple_aura_amplification_stacking_native_order_pending",
                         "incoming_arts_effects_require_explicit_amplification_graph_binding"],
             "lisa": ["native_sluggish_infinite_DB_and_fragile_template_pending", "talent_0.03s_scan_and_highest_effect_pending",
                      "regeneration_client_continuous_or_terminal_tick_semantics_pending", "support_SP_aura_pending"],
             "cgbird": ["native_magic_dodge_probability_RNG_and_damage_rejection_pending", "Attack_C_animation_event_missing_in_current_frame_summary",
                        "native_three_target_healing_cadence_pending", "base_RES_talent_and_bird_summon_pending"]}[name]
    if require_complete:
        raise ValueError("complete aura recipe unsupported: " + "; ".join(gaps))
    aid = f"ability/{name}_s3"
    emitter = f"buff/{name}_emitter"
    member = f"buff/{name}_member"
    sid = f"selector/{name}_members"
    ranges = read(RANGES)[level["rangeId"]]
    package = {"schemaVersion": 2, "status": "partially_implemented", "manifest": {
        "id": f"package/{name}_aura_recipe", "version": "1", "metadata": {"client_validated": False,
        "synthetic_attributes": True, "official_unit_complete": False, "source_hashes": hashes,
        "native_selected_skill": row["selected_skill"], "native_talents": row["talents"],
        "native_char_components": components, "native_skill_components": closure, "native_range": ranges,
        "native_frame_evidence": read(FRAMES)["characters"][IDS[name]], "pending_mechanics": gaps}},
        "entities": [], "abilities": [], "buffs": [], "selectors": [], "rules": []}
    actor = {"id": f"unit/{name}_aura_fixture", "kind": "entity", "tags": ["player"], "metadata": {"status": "partially_implemented"},
        "components": {"spatial": {}, "lifecycle": {"policy": "policy/ark_lifecycle"},
        "attributes": {"base": {"atk": 100, "def": 10, "mres": 10, "max_hp": 5000, "move_speed": 1,
                                     "attack_interval": 1, "attack_speed_ratio": 1, "block_count": 1}},
        "resources": {"hp": {"initial": 5000, "capacity": 5000, "role": "health"},
                      "sp": {"initial": level["spData"]["initSp"], "capacity": level["spData"]["spCost"],
                             "recovery_rate": level["spData"]["increment"], "recovery": {"mode": "periodic", "interval_seconds": 1},
                             "parameters": {"pause_at_full": True, "freeze_while_cast": True, "freeze_cast_modes": ["manual"]}}},
        "abilities": [aid]}}
    ally = {"id": "unit/aura_ally", "kind": "entity", "tags": ["player"], "components": {
        "spatial": {}, "lifecycle": {"policy": "policy/ark_lifecycle"}, "attributes": {"base": {"max_hp": 5000, "def": 0, "mres": 10, "move_speed": 1}},
        "resources": {"hp": {"initial": 100, "capacity": 5000, "role": "health"}},
        "abilities": ["ability/aura_leave", "ability/aura_enter"]}}
    enemy = {"id": "unit/aura_enemy", "kind": "entity", "tags": ["enemy", "probe"], "components": {
        "spatial": {}, "lifecycle": {"policy": "policy/ark_lifecycle"}, "attributes": {"base": {"max_hp": 100000, "def": 0, "mres": 0,
                                "move_speed": 1, "arts_factor": 1}}, "resources": {"hp": {"initial": 100000, "capacity": 100000, "role": "health"}},
        "abilities": ["ability/aura_leave", "ability/aura_enter"]}}
    package["entities"] = [actor, ally, enemy]
    if name == "cgbird":
        ally["tags"].append("probe")
        enemy["tags"].remove("probe")
    package["selectors"] = [{"id": sid, "kind": "selector", "region": {"type": "grid_offsets",
        "offsets": [[g["row"], g["col"]] for g in ranges["grids"]], "rotate_with_facing": True},
        "filters": [{"tag": "enemy" if name == "demkni" else "player"}, {"state": "alive"}], "limit": None}]
    parent = {"id": emitter, "kind": "buff", "duration_seconds": level["duration"], "aura": {"selector": sid, "buff": member},
              "removal": {"on_source_death": "remove", "on_target_death": "remove"}}
    child = {"id": member, "kind": "buff", "stacking": {"mode": "independent"}, "removal": {"on_source_death": "remove"}}
    ability = {"id": aid, "kind": "ability", "metadata": {"native_skill_id": row["config"]["skill_id"], "status": "partially_implemented"},
        "activation": {"mode": "manual", "costs": [{"resource": "sp", "amount": level["spData"]["spCost"]}],
                       "on_start": [{"op": "apply_buff", "target": "source", "buff": emitter}]},
        "duration_seconds": level["duration"], "timeline": []}
    if name == "demkni":
        selector = components[str(attack["_selector"]["m_PathID"])]["fields"]
        if attack["_cooldown"] != 1 or selector["_limitTargetNum"] != 0 or selector["_postFilter"] != 3 or selector["_excludeOwner"] != 0:
            raise ValueError("native all-target healing cadence/filter changed")
        child["modifiers"] = [{"attribute": "move_speed", "layer": "final_ratio", "value": bb["demkni_s_3.move_speed"]},
                              {"attribute": "arts_factor", "layer": "final_ratio", "value": bb["demkni_s_3.damage_scale"] - 1}]
        healsid = "selector/demkni_heal"
        package["selectors"].append({**package["selectors"][0], "id": healsid, "filters": [{"tag": "player"}, {"state": "alive"}]})
        ability.update(selector=healsid, target_capture="each_hit", parameters={"healing": True})
        ability["timeline"] = [{"at_seconds": attack["_preDelay"], "repeat": {"count": 30, "interval_seconds": attack["_cooldown"]},
            "effect": {"op": "heal", "scale": bb["attack@heal_scale"]}}]
        package["rules"].append(arts_rule())
    elif name == "lisa":
        regen = next(b for b in attack["_buffs"] if b["templateKey"] == "atk_to_hp_recovery")
        if regen["triggerInterval"] != 1 or regen["waitFirstTriggerInterval"] != 1 or attack["_removeBuffWhenTargetLeave"] != 1:
            raise ValueError("native regeneration membership/timer changed")
        parent["control"] = {"attack": False}
        child["interval_seconds"] = regen["triggerInterval"]
        child["effects"] = [{"op": "regenerate", "scale": bb["attack@atk_to_hp_recovery_ratio"]}]
    else:
        selector = components[str(attack["_selector"]["m_PathID"])]["fields"]
        if selector["_maxNum"] != 3 or selector["_limitTargetNum"] != 1 or selector["_postFilter"] != 3 or selector["_excludeOwner"] != 0:
            raise ValueError("native Nightingale heal selector changed")
        parent["modifiers"] = [{"attribute": "atk", "layer": "direct_ratio", "value": bb["atk"]}]
        child["modifiers"] = [{"attribute": "mres", "layer": "direct_ratio", "value": bb["magic_resistance"]}]
    package["buffs"] = [parent, child]
    package["abilities"] = [ability,
        {"id": "ability/aura_leave", "kind": "ability", "activation": {"mode": "manual"}, "timeline": [
            {"at": 0, "effect": {"op": "move", "target": "source", "position": {"row": 0, "col": 0}}}]},
        {"id": "ability/aura_enter", "kind": "ability", "activation": {"mode": "manual"}, "timeline": [
            {"at": 0, "effect": {"op": "move", "target": "source", "position": {"row": 4, "col": 5}}}]}]
    package["entities"].append({"id": "unit/aura_attacker", "kind": "entity", "tags": ["enemy"], "components": {
        "spatial": {}, "attributes": {"base": {"atk": 100, "def": 0, "mres": 0, "max_hp": 1000}},
        "resources": {"hp": {"initial": 1000, "capacity": 1000, "role": "health"}}, "abilities": ["ability/aura_probe"]}})
    damage = {"op": "damage", "damage_type": "arts"}
    if name == "demkni":
        damage["rules"] = {"damage.pipeline": "rule/aura_arts_amplification"}
    package["abilities"].append({"id": "ability/aura_probe", "kind": "ability", "activation": {"mode": "manual"},
        "selector": "selector/aura_probe", "timeline": [{"at": 0, "effect": damage}]})
    package["selectors"].append({"id": "selector/aura_probe", "kind": "selector", "region": {"type": "all"},
        "filters": [{"tag": "probe"}, {"state": "alive"}], "limit": 1})
    package["scenarioDraft"] = {"id": f"scenario/{name}_aura_fixture", "ruleset": "ruleset/ark_standard",
        "metadata": {"not_formal_mainline": True, "status": "partially_implemented"}, "map": {"rows": 9, "cols": 9},
        "initialEntities": [{"definition": actor["id"], "instanceAlias": "caster", "position": {"row": 4, "col": 4}},
                            {"definition": ally["id"], "instanceAlias": "ally", "position": {"row": 4, "col": 5}},
                            {"definition": enemy["id"], "instanceAlias": "enemy", "position": {"row": 4, "col": 6}},
                            {"definition": "unit/aura_attacker", "instanceAlias": "attacker", "position": {"row": 8, "col": 8}}]}
    return package


def arts_rule():
    return {"id": "rule/aura_arts_amplification", "kind": "calculation_rule", "contract": "damage.pipeline",
        "metadata": {"input_bindings": {"attack": {"entity": "source", "attribute_role": "attack"},
            "defense": {"entity": "target", "attribute_role": "defense"}, "resistance": {"entity": "target", "attribute_role": "resistance"},
            "arts_factor": {"entity": "target", "attribute": "arts_factor"}}},
        "implementation": {"type": "graph", "nodes": [
            {"id": "native", "rule": "rule/ark_damage_pipeline", "inputs": {"source": "inputs.source", "target": "inputs.target",
                "effect": "inputs.effect", "samples": "inputs.samples", "states": "inputs.states"}},
            {"id": "result", "expression": "{'accepted': nodes.native.accepted, 'amount': nodes.native.amount * "
                "(inputs.effect.arts_factor if inputs.effect.damage_type == 'arts' else 1), 'allocations': nodes.native.allocations, 'events': nodes.native.events}"}],
            "output": "nodes.result"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name in IDS:
        result = build(name)
        path = ROOT / f"packages/campaign/skills.{name}.json"
        if args.check:
            if read(path) != result:
                raise ValueError("aura recipe source identity changed")
        else:
            path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"name": name, "status": "partially_implemented"}))


if __name__ == "__main__":
    main()
