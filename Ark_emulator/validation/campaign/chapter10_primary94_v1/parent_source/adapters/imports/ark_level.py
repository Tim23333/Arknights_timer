"""Offline 0-1 data conversion; reads a JSON artifact, never legacy Python."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path


DEFAULT_PACK = Path(__file__).resolve().parents[3] / "ark_emulator" / "levels" / "packs" / "level_main_00-01.json"


class ArkImportError(ValueError):
    pass


def _delay(value):
    return 0 if value is None else value


def _action_name(action):
    value = action.get("actionType")
    if isinstance(value, dict):
        return value.get("name")
    return {0: "SPAWN", 2: "STORY", 5: "DISPLAY_ENEMY_INFO"}.get(value)


def _waves(level):
    """Parallel actions within sequential fragments, with repeat intervals."""
    cursor, spawns, controls = 0, [], []
    routes = level["routes"]
    for wave_index, wave in enumerate(level["waves"]):
        cursor += _delay(wave.get("preDelay"))
        for fragment_index, fragment in enumerate(wave.get("fragments", [])):
            start = cursor + _delay(fragment.get("preDelay"))
            end = start
            for action_index, action in enumerate(fragment.get("actions", [])):
                count = action.get("count", 1)
                if type(count) is not int or count < 0:
                    raise ArkImportError("Action repeat count must be a nonnegative integer")
                first = start + _delay(action.get("preDelay"))
                interval = _delay(action.get("interval"))
                if interval < 0:
                    raise ArkImportError("Action interval cannot be negative")
                if count:
                    end = max(end, first + (count - 1) * interval)
                action_type = _action_name(action)
                if action_type not in {"SPAWN", "STORY", "DISPLAY_ENEMY_INFO"}:
                    raise ArkImportError(f"Unsupported native action type: {action.get('actionType')}")
                if action_type != "SPAWN":
                    controls.append({"at_seconds": first, "type": action_type, "native": deepcopy(action),
                                     "wave": wave_index, "fragment": fragment_index})
                    continue
                route_index = action.get("routeIndex")
                if type(route_index) is not int or not 0 <= route_index < len(routes):
                    raise ArkImportError(f"Invalid spawn route index: {route_index}")
                route = routes[route_index]
                for repeat in range(count):
                    spawns.append({"at_seconds": round(first + repeat * interval, 10),
                        "definition": f"unit/{action['key']}", "position": deepcopy(route["startPosition"]),
                        "facing": "left", "route": deepcopy(route),
                        "instanceAlias": f"spawn/{len(spawns)+1}",
                        "parameters": {"native_wave": wave_index, "native_fragment": fragment_index,
                                       "native_action": action_index, "route_index": route_index,
                                       "spawn_random_range": deepcopy(route.get("spawnRandomRange", {})),
                                       "spawn_offset": deepcopy(route.get("spawnOffset", {}))}})
            cursor = end
        cursor += _delay(wave.get("postDelay"))
    return sorted(spawns, key=lambda value: value["at_seconds"]), controls


def _attributes(native, *, operator=False):
    aliases = {"maxHp": "max_hp", "atk": "atk", "def": "def", "magicResistance": "mres",
               "baseAttackTime": "attack_interval", "moveSpeed": "move_speed", "blockCnt": "block_count",
               "cost": "deploy_cost", "respawnTime": "redeploy_time"}
    base = {"max_hp": 1, "atk": 0, "def": 0, "mres": 0, "attack_interval": 1,
            "attack_speed_ratio": 1, "move_speed": 1, "block_count": 0,
            "block_cost": 1, "deploy_cost": 0, "redeploy_time": 0}
    for original, renamed in aliases.items():
        if native.get(original) is not None:
            base[renamed] = native[original]
    speed = native.get("attackSpeed")
    base["attack_speed_ratio"] = (100 if speed is None else speed) / 100
    return base


def _actor(identifier, native, package, *, operator=False):
    metadata = {"native_id": identifier, "name": native.get("name"), "verification": "model_unverified"}
    if operator:
        frames = native["attributeFrames"]
        frame = max(frames, key=lambda item: item["level"])
        attrs = _attributes(frame["data"], operator=True)
        metadata.update({"elite": 0, "level": frame["level"], "skill_level": 1,
                         "native_attribute_frames": deepcopy(frames), "native_skills": deepcopy(native.get("skillLevels", []))})
        for talent in native.get("talents", []):
            if talent.get("level", 0) <= frame["level"] and talent.get("stat") == "respawnTime":
                attrs["redeploy_time"] += talent["value"]
        offsets = deepcopy(native.get("range", [[0, 0], [0, 1]]))
        healing = native.get("ability", {}).get("healing", False)
        region = {"type": "grid_offsets", "offsets": offsets, "rotate_with_facing": True}
        target_tag = "operator" if healing else "enemy"
    else:
        attrs = _attributes(native["attributes"])
        region = {"type": "all", "blocked_only": True}
        target_tag, healing = "operator", False
    selector = {"id": f"selector/{identifier}_attack", "kind": "selector", "provider": "ark.selector.grid",
                "region": region, "filters": [{"tag": target_tag}, {"state": "alive"}],
                "ordering": "lowest_health_ratio" if healing else "nearest_then_entity_id", "limit": 1,
                "parameters": {"include_blocked": bool(operator and native.get("position") == 1 and not healing)}}
    package["selectors"].append(selector)
    timing = native.get("ability", {})
    windup = attrs["attack_interval"] * timing.get("hit_ratio", 0.5)
    ability = {"id": f"ability/{identifier}_attack", "kind": "ability",
               "activation": {"mode": "automatic_attack", "interval_rule": "rule/ark_attack_interval",
                              "parameters": {"windup_ratio": timing.get("hit_ratio", 0.5)}},
               "selector": selector["id"], "timeline": [{"at_seconds": windup,
                 "effect": {"op": "heal" if healing else "damage", "target": "selected", "scale": 1,
                            **({} if healing else {"damage_type": "physical"}),
                            "read_mode": {"source_attributes": "at_hit", "target_attributes": "at_hit"}}}],
               "parameters": {"windup_seconds": windup, "healing": healing,
                              "projectile_speed": timing.get("projectile_speed", 0),
                              "projectile_key": timing.get("projectile_key", "")},
               "metadata": {"native": deepcopy(timing), "verification": "model_unverified"}}
    package["abilities"].append(ability)
    components = {"attributes": {"base": attrs},
                  "resources": {"hp": {"initial": attrs["max_hp"], "capacity_attribute": "max_hp", "role": "health"}},
                  "abilities": [ability["id"]], "buffs": {"initial": []},
                  "behavior": {"machine": "behavior/player_combat" if operator else "behavior/ground_melee"},
                  "lifecycle": {"policy": "policy/ark_lifecycle", "leak_loss": native.get("lifePointReduce", 1)},
                  "spatial": {"facing": "right" if operator else "left", "block_capacity": attrs["block_count"],
                              "block_cost": attrs["block_cost"]}}
    if operator:
        high = native.get("position") == 2
        components["deployable"] = {"policy": "policy/ark_ground_deploy", "base_cost": attrs["deploy_cost"],
            "cooldown_seconds": attrs["redeploy_time"], "refund_ratio": 0.5, "terrain": "high" if high else "ground"}
        skills = native.get("skillLevels", [])
        if skills:
            skill = skills[0]
            components["resources"]["sp"] = {"initial": skill.get("initSp", 0), "capacity": skill["spCost"],
                "recovery_rate": skill.get("increment", 1) if skill["spType"] == 1 else 0,
                "recovery_rule": "rule/ark_import_resource_recovery", "role": "skill_energy",
                "recovery": {"mode": "periodic", "interval_seconds": 1},
                "parameters": {"freeze_while_cast": True, "freeze_cast_modes": ["manual"]}}
            skill_id = f"ability/{identifier}_skill_1"
            activation = {"mode": "manual", "costs": [{"resource": "sp", "amount": skill["spCost"]}],
                          "parameters": {"automatic": skill.get("automatic", False), "auto_when_ready": skill.get("automatic", False),
                                         "sp_resource": "sp", "replace_attack": skill["spType"] == 2}}
            if skill["spType"] == 2:
                ability["activation"]["parameters"].update({"sp_resource": "sp", "recovery_per_attack": 1})
                scale, count = skill["blackboard"].get("atk_scale", 1), int(skill["blackboard"].get("times", 1))
                timeline = [{"at_seconds": windup, "repeat": {"count": count, "interval_seconds": 0},
                             "effect": {"op": "damage", "target": "selected", "damage_type": "physical", "scale": scale}}]
                parameters = {"windup_seconds": windup, "projectile_speed": timing.get("projectile_speed", 0),
                              "automatic": True, "replace_attack": True}
            elif skill["handler"] == "cost_skill_v1":
                timeline = [{"at_seconds": 0, "effect": {"op": "modify_resource", "target": "scenario",
                            "resource": "dp", "delta": skill["blackboard"]["cost"]}}]
                parameters = {"automatic": True}
            elif skill["handler"] == "healing_skill_v1":
                buff_id = f"buff/{identifier}_skill_1"
                package["buffs"].append({"id": buff_id, "kind": "buff", "duration_seconds": skill["duration"],
                    "stacking": {"mode": "refresh"}, "modifiers": [{"attribute": "atk", "layer": "direct_ratio",
                    "value": skill["blackboard"]["atk"]}]})
                timeline = [{"at_seconds": 0, "effect": {"op": "apply_buff", "target": "self", "buff": buff_id}}]
                parameters = {"automatic": False, "blocks_attacks": False}
            else:
                raise ArkImportError(f"No explicit effect conversion for native skill: {skill['handler']}")
            package["abilities"].append({"id": skill_id, "kind": "ability", "activation": activation,
                "selector": selector["id"], "timeline": timeline, "duration_seconds": skill.get("duration", 0),
                "parameters": parameters, "metadata": {"native": deepcopy(skill), "verification": "model_unverified"}})
            components["abilities"].append(skill_id)
    entity = {"id": f"unit/{identifier}", "kind": "entity",
              "tags": ["operator" if operator else "enemy", "high" if operator and native.get("position") == 2 else "ground"],
              "components": components, "metadata": metadata}
    package["entities"].append(entity)


def import_ark_level(pack_path=None):
    """Convert the fixed E0 0-1 evidence pack into a standalone V2 package."""
    path = Path(pack_path) if pack_path is not None else DEFAULT_PACK
    raw = path.read_bytes()
    try:
        pack = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise ArkImportError(f"Invalid source JSON: {path}") from exc
    if pack.get("schemaVersion") != 1 or pack.get("levelId") != "level_main_00-01":
        raise ArkImportError("This importer requires the explicit level_main_00-01 schema-1 artifact")
    level = pack["level"]
    waves, controls = _waves(level)
    options = level["options"]
    package = {"schemaVersion": 2, "status": "model_unverified",
        "manifest": {"id": "package/ark_00_01", "version": "2.0.0", "requires": ["preset/ark_standard"],
            "metadata": {"source_hash": hashlib.sha256(raw).hexdigest(), "source": deepcopy(pack.get("source", {}))}},
        "entities": [], "abilities": [], "selectors": [], "buffs": [],
        "rules": [{"id": "rule/ark_import_resource_recovery", "kind": "calculation_rule", "contract": "resource.recovery",
            "implementation": {"type": "expression", "expression": "inputs.current + inputs.parameters.rate * inputs.delta_seconds"}},
            {"id": "rule/ark_00_01_movement_speed", "kind": "calculation_rule", "contract": "movement.speed",
            "implementation": {"type": "expression", "expression": "inputs.movement_parameters.base_speed * params.multiplier"},
            "parameters": {"multiplier": options["moveMultiplier"]}}],
        "rulesets": [{"id": "ruleset/ark_00_01", "kind": "ruleset", "extends": "ruleset/ark_standard",
            "bindings": {"movement.speed": "rule/ark_00_01_movement_speed"},
            "parameters": {"deploy_capacity": options["characterLimit"]}}]}
    for identifier, native in pack["enemies"].items():
        _actor(identifier, native, package)
    for identifier, native in pack["operators"].items():
        _actor(identifier, native, package, operator=True)
    known = {entity["id"] for entity in package["entities"]}
    if any(wave["definition"] not in known for wave in waves):
        raise ArkImportError("Wave refers to an enemy absent from the source evidence pack")
    package["scenarioDraft"] = {"id": "scenario/ark_00_01", "kind": "scenario", "ruleset": "ruleset/ark_00_01",
        "description": "0-1 E0 fixed configurations; native frame calibration pending",
        "map": deepcopy(level["map"]), "routes": deepcopy(level["routes"]), "initialEntities": [],
        "roster": [entity["id"] for entity in package["entities"] if "operator" in entity["tags"]],
        "dependencies": [entity["id"] for entity in package["entities"] if "operator" in entity["tags"]],
        "waves": waves, "seed": level.get("randomSeed", 0),
        "resources": {"dp": {"initial": options["initialCost"], "capacity": options["maxCost"],
            "recovery_rate": 1 / options["costIncreaseTime"], "recovery_rule": "rule/ark_import_resource_recovery",
            "recovery": {"mode": "periodic", "interval_seconds": options["costIncreaseTime"]}},
            "life": {"initial": options["maxLifePoint"], "capacity": options["maxLifePoint"]}},
        "objectives": {"type": "waves", "life_resource": "life", "defeat_threshold": 0},
        "parameters": {"deploy_capacity": options["characterLimit"]},
        "metadata": {"verification": "model_unverified", "source_hash": hashlib.sha256(raw).hexdigest(),
            "pendingCalibration": deepcopy(pack.get("calibrationNotes", [])) + [
                "Four-neighbour shortest path preserves walls; native diagonal steering is unverified",
                "Tutorial STORY controls retained as source evidence; native tutorial pacing awaits traces"],
            "native_controls": controls, "native_options": deepcopy(options)}}
    return package
