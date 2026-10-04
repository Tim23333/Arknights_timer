"""Compose source-preserving chapter 1 scenarios under explicit partial profiles.

This is an integration input, not a complete-stage acceptance receipt. Historical
source packages and the primary implementation are never edited by this builder.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_mainline_draft import route_ir, top_position

INPUTS = {
    "source": ("packages/campaign/chapter01_sources/native.reference.json", "a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd"),
    "squad": ("packages/campaign/mainline_models/level_main_00-10.m14_timeline.json", "83bfa1829958f80a4f1da95740466326db3f5a8c7143737d728887b3670116d2"),
    "simple_attacks": ("packages/campaign/chapter01_sources/attacks.model.json", "6ad098d3f5c5b3bb160ad7b2a1341e6bbb3ff3de4a25261de765c26cebf5b723"),
    "controls": ("packages/campaign/chapter01_controls/m13_nonspatial_profiles/model.immediate.json", "40752fbefedc9d52f5b0f36115b9c583907736e0379f2d083ad056a3cc16dd00"),
    "emp": ("packages/campaign/chapter01_devices/emp.category.json", "79ed4124a4dec23f199fd9edf83e6c473a166a803dd973fb02f4560a9841b24d"),
    "advanced": ("packages/campaign/chapter01_models/attacks.model.json", "0d099238a72afb7279a6dc46bab5f9cc28e2bf1f791d4ac11d78b44300215fb8"),
    "w": ("packages/campaign/chapter01_models/w_combat/model.json", "4b647811d8808130970ac85b8a068b4623feb2e1e4fa68dca61d87cccea0df9a"),
    "control_source": ("packages/campaign/chapter01_controls/m13_nonspatial_profiles/source.immediate.json", "8173ea0e92334cb685e1b9e6fe632a2d7b54b500ff6265fd630b8ff3fc5c915a"),
}
OUT = ROOT / "packages/campaign/chapter01_stage_models"
RUNTIME = ROOT.parent / "unpack_work/campaign_m15_category_candidate"
CORE = "f98a638812a18a01d10505dadd48b01de410ac27e992230881bc01c4f9a993b9"
SECTIONS = ("entities", "abilities", "buffs", "selectors", "rules", "behaviors", "policies", "controls")
LEVELS = ("level_main_01-11", "level_main_01-12")


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def encoded(value): return (json.dumps(value, ensure_ascii=False, indent=2)+"\n").encode("utf8")
def read(path): return json.loads((ROOT/path).read_bytes())


def native_locks(value):
    """Read each recorded native file; source metadata alone is insufficient."""
    found = {}
    def visit(node):
        if isinstance(node, dict):
            if isinstance(node.get("path"), str) and isinstance(node.get("sha256"), str):
                local_package = node["path"].startswith("packages/")
                file = ((ROOT if local_package else ROOT.parent)/node["path"]).resolve()
                if not file.is_file() or sha(file) != node["sha256"]:
                    raise ValueError("native file drift: "+node["path"])
                found[("" if local_package else "../")+node["path"]] = node["sha256"]
            for child in node.values(): visit(child)
        elif isinstance(node, list):
            for child in node: visit(child)
    visit(value)
    return found


class StageModelGap(ValueError): pass


def require_complete(package):
    gaps = package["manifest"]["metadata"]["pending_model_gaps"]
    if gaps:
        raise StageModelGap("chapter 1 complete acceptance requires: "+", ".join(gaps))


def merge(target, package):
    for section in SECTIONS:
        rows = target.setdefault(section, {})
        for row in package.get(section, []):
            old = rows.get(row["id"])
            if old is not None and old != row:
                raise ValueError("conflicting imported definition: "+row["id"])
            rows[row["id"]] = deepcopy(row)


def build(level):
    if level not in LEVELS: raise ValueError("unsupported chapter 1 stage")
    packages = {}; locks = {}
    for key, (path, pin) in INPUTS.items():
        if sha(ROOT/path) != pin: raise ValueError("frozen source drift: "+path)
        packages[key] = read(path); locks[path] = pin
    # These inputs already carry source locks; also bind every actual native file.
    native = packages["source"]; stage = native["stages"][level]
    doc, plan = stage["native_level_document"], stage["dependency_plan"]
    locks.update(native_locks({"sources": native["sources"], "stage": stage,
        "enemies": {r["native_id"]: native["enemies"][r["native_id"]] for r in plan["resolved_enemies"]},
        "projectiles": native["projectiles"]}))
    if plan["applicable_runes"] or plan["native_global_buffs"] or plan["native_branches"]:
        raise StageModelGap("native runes/global buffs/branches require explicit integration")
    rows, cols = plan["map_plan"]["rows"], plan["map_plan"]["cols"]
    team = deepcopy(packages["squad"])
    team["entities"] = [e for e in team["entities"] if "enemy" not in e.get("tags", [])]
    for section, prefix in (("abilities", "ability/enemy_"), ("selectors", "selector/enemy_")):
        team[section] = [row for row in team[section] if not row["id"].startswith(prefix)]
    definitions = {}; merge(definitions, team)
    for key in ("simple_attacks", "advanced", "w", "emp"):
        p = deepcopy(packages[key])
        if key == "advanced": p.pop("entities", None)
        merge(definitions, p)
    controls = deepcopy(packages["controls"])
    # Never let the synthetic command probe become a production stage actor.
    controls["entities"] = [e for e in controls["entities"] if e["id"] != "unit/chapter01_control_probe_driver"]
    controls["abilities"] = [a for a in controls["abilities"] if a["id"] != "ability/chapter01_control_probe_ping"]
    merge(definitions, controls)
    enemy_rows = {r["native_id"]: r for r in plan["resolved_enemies"]}
    overrides = packages["advanced"]["manifest"]["metadata"]["integration"]
    enemy_defs = {}
    for key, row in enemy_rows.items():
        record = native["enemies"][key]; data = row["resolved"]; attrs = data["attributes"]
        converters = {"maxHp": "max_hp", "atk": "atk", "def": "def", "magicResistance": "mres",
            "moveSpeed": "move_speed", "baseAttackTime": "attack_interval", "massLevel": "mass_level"}
        base = {dst: attrs[src] for src, dst in converters.items()}
        base.update(attack_speed_ratio=attrs["attackSpeed"]/100, block_cost=1, block_count=0)
        unit = "unit/chapter01_w" if key == "enemy_1504_cqbw" else "unit/"+key
        if key == "enemy_1504_cqbw":
            entity = deepcopy(definitions["entities"][unit])
            # Stage attributes, including movement/leak values, come from this stage.
            entity["components"]["attributes"]["base"].update(base)
        else:
            ability = overrides["normal_attack_overrides"].get(unit, "ability/"+key+"/normal_attack")
            if ability not in definitions["abilities"]: raise StageModelGap("missing normal attack: "+key)
            entity = {"id": unit, "kind": "entity", "tags": ["enemy", "ground"], "components": {
                "attributes": {"base": base}, "abilities": [ability],
                "resources": {"hp": {"initial": base["max_hp"], "capacity_attribute": "max_hp", "role": "health"}},
                "lifecycle": {"policy": "policy/ark_lifecycle"}, "spatial": {}}}
            entity["components"]["behavior"] = deepcopy(overrides["behavior_overrides"].get(unit, {"machine": "behavior/ground_melee"}))
        if data["motion"] != "WALK": raise StageModelGap("unhandled source motion: "+str(data["motion"]))
        movers = [(pid, c) for pid, c in record["prefab"]["components"].items() if c["native_class"] == "MoveController"]
        if len(movers) != 1: raise StageModelGap("ambiguous source mover: "+key)
        mover_id, mover = movers[0]; fields = mover["raw"]
        entity["components"]["spatial"] = {"steering": {"rule": "rule/m7_steering_velocity", "parameters": {
            "response_factor": fields["_steeringFactor"], "max_acceleration": fields["_maxSteeringForce"], "arrival_radius": .05}}}
        entity["components"]["lifecycle"]["leak_loss"] = data["lifePointReduce"]
        entity["components"]["attributes"]["layers"] = ["flat", "direct_ratio", "final_ratio", "sluggish", "fragility"]
        entity.setdefault("rules", {}).update({"attributes.effective": "rule/support_temporal", "targeting.score": "rule/m8_enemy_taunt_score"})
        entity.setdefault("metadata", {}).update(native_id=key, native_category=1, native_level=row["native_level"],
            source_configuration=deepcopy(row), source_mover={"path_id": mover_id, "fields": deepcopy(fields)},
            source_motion=data["motion"], client_verified=False)
        definitions["entities"][unit] = entity; enemy_defs[key] = unit
    # Exact source action template carries a real control member and barrier flags.
    templates = {(t["source_origin"]["wave"], t["source_origin"]["fragment"], t["source_origin"]["action_index"]): t
        for t in packages["control_source"]["action_templates"] if t["source_origin"]["level"] == level}
    timeline = []
    for wi, wave in enumerate(doc["waves"]):
        outwave = {"pre_delay_seconds": wave["preDelay"], "post_delay_seconds": wave["postDelay"],
            "max_wait_seconds": wave["maxTimeWaitingForNextWave"], "fragments": [], "metadata": {"native_wave": deepcopy(wave)}}
        for fi, fragment in enumerate(wave["fragments"]):
            outfrag = {"pre_delay_seconds": fragment["preDelay"], "actions": [], "metadata": {"native_fragment_index": fi}}
            for ai, action in enumerate(fragment["actions"]):
                provenance = {"native_action": deepcopy(action), "native_wave": wi, "native_fragment": fi, "native_action_index": ai}
                if action["actionType"] != "SPAWN":
                    t = templates[(wi, fi, ai)]
                    if t["native_action"] != action: raise ValueError("control source action drift")
                    converted = deepcopy(t["template"]); converted["metadata"].update(provenance)
                else:
                    if any(action[k] for k in ("hiddenGroup", "randomSpawnGroupKey", "randomSpawnGroupPackKey", "isUnharmfulAndAlwaysCountAsKilled", "forceBlockWaveInBranch")):
                        raise StageModelGap("native grouped/special spawn requires explicit conversion")
                    if action["randomType"] != "ALWAYS" or action["refreshType"] != "ALWAYS": raise StageModelGap("native conditional spawn")
                    route = route_ir(doc["routes"][action["routeIndex"]], rows)
                    if route["motionMode"] == "E_NUM": route["motionMode"] = enemy_rows[action["key"]]["resolved"]["motion"]
                    if any(any((c.get("reachOffset") or {}).values()) for c in route.get("checkpoints") or []):
                        route["reach_offset_policy"] = {"rule": "rule/m9_checkpoint_cartesian", "parameters": {"axis_signs": {"row": -1, "col": 1}}}
                    if any(c["type"] in ("DISAPPEAR", "APPEAR_AT_POS") for c in route.get("checkpoints") or []):
                        route["transition_policy"] = {"rule": "rule/m9_living_transition", "parameters": {
                            "hidden_effects": "reject", "hidden_auras": "suspend", "launched_source_effects": "retain", "resource_timers": "continue"}}
                    offset, extent = route["spawnOffset"], route["spawnRandomRange"]
                    spawn = {"definition": enemy_defs[action["key"]], "route": route, "position": deepcopy(route["startPosition"]),
                        "instanceAlias": f"chapter01/{level}/w{wi}/f{fi}/a{ai}", "parameters": {"native_wave": wi,
                        "native_fragment": fi, "native_action_index": ai, "native_route_index": action["routeIndex"]},
                        "placement": {"rule": "rule/m7_spawn_rectangle", "stream": "spawn", "sample_axes": ["col", "row"],
                            "sample_zero_range": False, "offset": {"row": -offset["y"], "col": offset["x"]},
                            "random_range": {"row": extent["y"], "col": extent["x"]}}}
                    converted = {"kind": "spawn", "count": action["count"], "spawn": spawn,
                        "delay_seconds": action["preDelay"], "interval_seconds": action["interval"],
                        "managed": action["managedByScheduler"], "blocks_wave": not action["dontBlockWave"],
                        "blocks_fragment": action["blockFragment"], "metadata": provenance}
                outfrag["actions"].append(converted)
            outwave["fragments"].append(outfrag)
        timeline.append(outwave)
    initial = []
    for inst in doc["predefines"]["tokenInsts"] or []:
        if inst["inst"]["characterKey"] != "trap_002_emp" or inst["hidden"]: raise StageModelGap("unconverted predefined token")
        initial.append({"definition": "unit/chapter01_emp", "instanceAlias": "chapter01/predefined/emp",
            "position": top_position(inst["position"], rows), "facing": inst["direction"].lower()})
    # The old isolated NPC profile used source coordinates directly. Translate the
    # actual activation effect to the map convention; preserve the frozen original.
    for template in templates.values():
        if template["native_action"]["actionType"] == "ACTIVATE_PREDEFINED":
            control = definitions["controls"][template["template"]["definition"]]
            for step in control["steps"]:
                for effect in step.get("effects", []):
                    if effect.get("op") == "spawn": effect["position"] = top_position(effect["position"], rows)
            control["metadata"]["coordinate_translation"] = "native_bottom_origin_to_top_origin"
    options = doc["options"]
    definitions["rules"]["rule/campaign_draft_move_speed"]["parameters"]["multiplier"] = options["moveMultiplier"]
    gaps = ["full_stage_commands_and_checkpoint_replay_not_executed", "W_persistent_projectile_attachment_lifecycle",
        "ranged_enemy_persistent_tracking_and_collision", "native_enemy_target_free_abnormal_filters_and_move_attack_FSM"]
    if level.endswith("01-11"):
        gaps += ["predefined_hidden_dormant_registry_activation_and_SP_clock", "native_training_cards_and_fixed12_explicit_composition"]
    else: gaps += ["EMP_owned_terrain_layers_not_in_this_runtime", "native_tile_telin_telout_requires_explicit_mechanics_profile"]
    result = {"schemaVersion": 2, "status": "partial_source_preserving_stage_integration", "manifest": {
        "id": "package/campaign/chapter01_stage/"+level, "version": "0.1.0", "requires": ["preset/ark_standard"], "metadata": {
            "source_locks": locks, "builder_sha256": sha(Path(__file__)), "required_runtime": CORE,
            "pending_model_gaps": gaps, "formal_stage_approved": False, "client_verified": False,
            "native_predefines": deepcopy(doc["predefines"]), "native_options": deepcopy(options),
            "fixed12_profile": {"id": "fixed_campaign_12_stage_test_overlay_v1", "native_cards_retained": True,
                "native_training_deck_legal": not options["isTrainingLevel"], "test_roster_substitution": options["isTrainingLevel"]},
            "model_profiles": {"control": "logical_immediate_ack_with_real_owned_control_lifecycle",
                "negative_timeout": "wait_for_managed_clear", "source_random_seed": "explicit_root_seed_profile",
                "steering": "bounded_velocity_with_native_constants_point_body", "arrival_radius": .05,
                "native_body_width_consumed": False, "NPC": "create_on_activation_partial", "EMP": "category_filtered_retire_partial"}}},
        **{key: [rows[k] for k in sorted(rows)] for key, rows in definitions.items() if rows},
        "scenarioDraft": {"id": "scenario/campaign/chapter01/"+level, "ruleset": "ruleset/ark_standard",
            "roster": deepcopy(team["scenarioDraft"]["roster"]), "seed": doc["randomSeed"],
            "map": {"rows": rows, "cols": cols, "tiles": deepcopy(plan["map_plan"]["tiles"])},
            "initialEntities": initial, "rules": deepcopy(team["scenarioDraft"]["rules"]),
            "timeline": {"policy": "managed_clear", "negative_timeout_policy": "wait_for_clear", "waves": timeline},
            "resources": {"dp": {"initial": options["initialCost"], "capacity": options["maxCost"],
                "recovery_rate": 1/options["costIncreaseTime"], "recovery": {"mode": "periodic", "interval_seconds": options["costIncreaseTime"]}},
                "life": {"initial": options["maxLifePoint"], "capacity": options["maxLifePoint"]}},
            "parameters": {"deploy_capacity": options["characterLimit"]}, "objectives": {"type": "waves", "life_resource": "life"},
            "metadata": {"native_level_id": level, "model_validated": False, "formal_mainline_approved": False,
                "native_spawn_count": plan["spawn_count"], "native_control_counts": deepcopy(stage["control_counts"])}}}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); parser.add_argument("--require-compilable", action="store_true"); args = parser.parse_args()
    sys.path.insert(0, str(RUNTIME))
    import ark_sim
    from ark_sim import Compiler
    from ark_sim.content.compiler import CompileError
    from ark_sim.adapters.api import implementation_digest
    if Path(ark_sim.__file__).resolve().parent != RUNTIME/"ark_sim" or implementation_digest() != CORE: raise RuntimeError("wrong integration runtime")
    OUT.mkdir(parents=True, exist_ok=True); results = []
    for level in LEVELS:
        package = build(level); output = OUT/(level+".partial.json")
        try:
            program = Compiler().compile(package); compiled = True; diagnostic = None
        except CompileError as error:
            if args.require_compilable: raise
            program = None; compiled = False; diagnostic = str(error)
        if args.check:
            if not output.exists() or output.read_bytes() != encoded(package): raise ValueError("stage composition drift: "+level)
        else: output.write_bytes(encoded(package))
        results.append({"level": level, "package_sha256": sha(output), "compiled": compiled, "compile_diagnostic": diagnostic,
            "definitions": len(program.definitions) if program else None,
            "native_spawn_count": package["scenarioDraft"]["metadata"]["native_spawn_count"], "complete": False})
    print(json.dumps({"runtime": CORE, "stages": results}))
