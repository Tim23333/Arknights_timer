"""Translate a native level into V2 IR while retaining unresolved dependencies.

This draft deliberately fails compilation until the complete squad, attacks
and native controls have real implementations; it is not a playable fallback.
"""
from copy import deepcopy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_mainline_dependencies import ROOT, build


def top_position(position, rows):
    return {"row": rows-1-position["row"], "col": position["col"]}


def route_ir(route, rows):
    result = deepcopy(route)
    result["startPosition"] = top_position(route["startPosition"], rows)
    result["endPosition"] = top_position(route["endPosition"], rows)
    for checkpoint in result.get("checkpoints") or []:
        if checkpoint.get("position") is not None:
            checkpoint["position"] = top_position(checkpoint["position"], rows)
    return result


def translate(level_id="level_main_00-10"):
    plan = build(level_id)
    rows, cols = plan["map_plan"]["rows"], plan["map_plan"]["cols"]
    enemy_rows = {row["native_id"]: row for row in plan["resolved_enemies"]}
    entities, pending = [], ["policy/campaign_native_controls"]
    for identifier, row in enemy_rows.items():
        data = row["resolved"]
        attrs = data["attributes"]
        native_to_v2 = {"maxHp": "max_hp", "atk": "atk", "def": "def", "magicResistance": "mres",
                        "moveSpeed": "move_speed", "baseAttackTime": "attack_interval", "massLevel": "mass_level"}
        base = {target: attrs[source] for source, target in native_to_v2.items()}
        base.update(attack_speed_ratio=attrs["attackSpeed"]/100, block_cost=1, block_count=0)
        normal = []
        if data["applyWay"] != "NONE":
            normal = [f"ability/{identifier}/normal_attack"]
            pending.extend(normal)
        motion = data["motion"]
        components = {"attributes": {"base": base},
                      "resources": {"hp": {"initial": base["max_hp"], "capacity_attribute": "max_hp", "role": "health"}},
                      "abilities": normal,
                      "behavior": {"machine": "behavior/campaign_passive" if not normal else "behavior/ground_melee"},
                      "lifecycle": {"policy": "policy/ark_lifecycle", "leak_loss": data["lifePointReduce"]}, "spatial": {}}
        entities.append({"id": "unit/"+identifier, "kind": "entity", "tags": ["enemy", "flying" if motion == "FLY" else "ground"],
                         "components": components, "metadata": {"native_id": identifier, "native_spawn_key": identifier,
                         "native_level": row["native_level"], "source_normal_attack_pending": bool(normal)}})
    cursor, waves = 0, []
    for wave_index, wave in enumerate(plan["native_wave_script"]):
        cursor += wave["preDelay"]
        for fragment_index, fragment in enumerate(wave["fragments"]):
            start, end = cursor+fragment["preDelay"], cursor+fragment["preDelay"]
            for action in fragment["actions"]:
                count = action["count"]
                if count:
                    end = max(end, start+action["preDelay"]+(count-1)*action["interval"])
                if action["actionType"] != "SPAWN":
                    continue
                identifier = action["key"]
                route = route_ir(plan["used_routes"][str(action["routeIndex"])], rows)
                motion = enemy_rows[identifier]["resolved"]["motion"]
                if route["motionMode"] == "E_NUM":
                    route["motionMode"] = motion
                for repeat in range(count):
                    waves.append({"at_seconds": start+action["preDelay"]+repeat*action["interval"],
                        "definition": "unit/"+identifier, "route": deepcopy(route), "position": route["startPosition"],
                        "instanceAlias": f"wave/{len(waves)+1}", "parameters": {"native_wave": wave_index,
                        "native_fragment": fragment_index, "native_route_index": action["routeIndex"]}})
            cursor = end
        cursor += wave["postDelay"]
    roster = ["unit/"+row["character_id"] for row in plan["roster"]]
    pending.extend(roster)
    options = plan["native_options"]
    package = {"schemaVersion": 2, "status": "draft_unresolved_dependencies", "manifest": {
        "id": "package/campaign_draft/"+level_id, "version": "0.1.0", "requires": ["preset/ark_standard"],
        "metadata": {"runnable": False, "dependency_plan_source": plan["source"], "pending": pending,
                     "native_controls": plan["control_counts"], "native_runes": plan["native_runes"],
                     "native_predefines": plan["native_predefines"], "native_branches": plan["native_branches"]}},
        "entities": entities, "behaviors": [{"id": "behavior/campaign_passive", "kind": "behavior",
             "initial": "active", "states": {"active": {}}, "transitions": []}],
        "rules": [{"id": "rule/campaign_draft_move_speed", "kind": "calculation_rule", "contract": "movement.speed",
            "implementation": {"type": "expression", "expression": "inputs.movement_parameters.base_speed * params.multiplier"},
            "parameters": {"multiplier": options["moveMultiplier"]}}],
        "scenarioDraft": {"id": "scenario/campaign_draft/"+level_id, "ruleset": "ruleset/ark_standard",
            "roster": roster, "dependencies": ["policy/campaign_native_controls"],
            "map": {"rows": rows, "cols": cols, "tiles": plan["map_plan"]["tiles"]}, "waves": waves,
            "rules": {"movement.speed": "rule/campaign_draft_move_speed"},
            "resources": {"dp": {"initial": options["initialCost"], "capacity": options["maxCost"],
                "recovery_rate": 1/options["costIncreaseTime"], "recovery": {"mode": "periodic", "interval_seconds": options["costIncreaseTime"]}},
                "life": {"initial": options["maxLifePoint"], "capacity": options["maxLifePoint"]}},
            "parameters": {"deploy_capacity": options["characterLimit"]},
            "objectives": {"type": "waves", "life_resource": "life"},
            "metadata": {"runnable": False, "native_level_id": level_id, "pending_conversion": plan["pending_conversion"]}}}
    return package


if __name__ == "__main__":
    output = ROOT/"packages/campaign/mainline_drafts/level_main_00-10.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(translate(), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("Wrote unresolved V2 IR draft; native controls and squad implementation are required before execution.")
