"""Explicit MultiMelee split and fixed-flight ranged model profiles.

Native declarations/fields support the input shape; unknown client bodies remain
pending. This builder never imports V1 or mutates the frozen kernel/source audit.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = ROOT/"packages/campaign/chapter01_sources/native.reference.json"
SOURCE_SHA = "a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd"
OUT = ROOT/"packages/campaign/chapter01_models"
IDS = ("enemy_1014_rogue", "enemy_1028_mocock", "enemy_1028_mocock_2")


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding="utf8"))


def build():
    if sha(SOURCE) != SOURCE_SHA: raise ValueError("frozen chapter01 source audit changed")
    source = read(SOURCE)
    records = {key: source["enemies"][key] for key in IDS}
    identities = {}
    for record in [*source["sources"].values(), *(r["prefab"]["source"] for r in records.values()),
                   *(r["animation"]["source"] for r in records.values()), source["projectiles"]["projectile_mocock"]["source"]]:
        path = ROOT.parent/record["path"]
        if not path.exists() or sha(path) != record["sha256"]: raise ValueError("frozen native input drift: "+record["path"])
        identities[record["path"]] = record["sha256"]
    entities = []; abilities = []; selectors = []
    rules = [{"id": "rule/ch1_launch_distance_flight", "kind": "calculation_rule", "contract": "projectile.flight_time",
         "implementation": {"type": "expression", "expression": "min(inputs.distance / inputs.speed, params.lifetime_seconds)"},
         "parameters": {"lifetime_seconds": 10},
         "metadata": {"profile": "launch_planar_distance_capped_at_lifetime_v1", "client_verified": False}},
        {"id": "rule/ch1_recent_target", "kind": "calculation_rule", "contract": "targeting.score",
         "implementation": {"type": "expression", "expression": "-inputs.candidate.id"},
         "metadata": {"profile": "newest_runtime_id_priority_v1", "client_verified": False}}]
    # The split multiplier is explicit content scale, independently replaceable;
    # standard physical mitigation still runs separately for each actual packet.
    profiles = {}
    for key, record in records.items():
        row = record["native_enemy"]["resolved"]; attrs = row["attributes"]
        mode = record["modes"][0]; fields = mode["combat"]
        component = record["prefab"]["components"][str(mode["combat_path_id"])]
        hits = [e for e in mode["attack_animation"]["events"] if e["name"] == "OnAttack"]
        if len(record["modes"]) != 1 or fields["_damageType"] != 1 or fields["_atkScale"] != 1 or fields["_activeBuffs"]:
            raise ValueError("selected attack source shape changed")
        if fields["_timeMode"] != 0 or fields["_waitForAttackEvent"] != 1:
            raise ValueError("explicit source attack-signal windup required")
        sid = f"selector/{key}/ch1_model"; aid = f"ability/{key}/ch1_model_normal"
        profile = {"native_combat_path_id": mode["combat_path_id"], "native_class": component["native_class"],
            "native_combat_fields": fields, "source_binding": mode["attack_animation"],
            "client_pending": ["native_get_time_scale_and_coroutine_clock", "source_versions_alignment"], "model_gap": []}
        if key == IDS[0]:
            if component["native_class"] != "MultiMeleeAttack" or fields["_additionalTimes"] != 1 or fields["_splitDamage"] != 1:
                raise ValueError("native MultiMelee split flags changed")
            if fields["_waitAttackEventForAllAttacks"] != 1 or fields["_triggerDelta"] != 0 or fields["_refreshInputTargetOnCheckSpell"] != 0:
                raise ValueError("native multi attack signal/target refresh contract changed")
            if [h["frame"] for h in hits] != [12, 23]: raise ValueError("exact multi attack source frames changed")
            selector = {"id": sid, "kind": "selector", "region": {"type": "all", "blocked_only": True},
                "filters": [{"tag": "player"}, {"state": "alive"}], "limit": 1}
            scale = fields["_atkScale"]/(fields["_additionalTimes"]+1)
            profile.update(split_profile={"id": "equal_total_attack_split_before_defense_v1", "total_scale": fields["_atkScale"],
                "packet_count": 2, "packet_scale": scale, "native_formula_body_recovered": False},
                target_profile="capture_current_blocker_for_both_packets", windup_profile="unscaled_source_events_v1")
            profile["client_pending"] += ["native_split_damage_order_formula", "native_multi_melee_interrupt_and_fsm"]
            ability = {"id": aid, "kind": "ability", "activation": {"mode": "automatic_attack"},
                "selector": sid, "target_capture": "at_cast", "timeline": [{"at_seconds": h["seconds"],
                    "effect": {"op": "damage", "damage_type": "physical", "scale": scale,
                        "condition": "inputs.targets[0].components.runtime.alive"}} for h in hits]}
        else:
            if component["native_class"] != "RangedAttack" or fields["_projectileKey"] != "projectile_mocock" or fields["_waitForProjectileInvalid"] != 0:
                raise ValueError("exact ranged projectile/source finish contract changed")
            if [h["frame"] for h in hits] != [22] or row["rangeRadius"] != 1.75:
                raise ValueError("ranged frame/range changed")
            native_selectors = [c for c in record["prefab"]["components"].values() if c["native_class"] == "AdvancedSelector"]
            if len(native_selectors) != 1: raise ValueError("native ranged selector ambiguous")
            ns = native_selectors[0]["raw"]
            if (ns["_targetSide"], ns["_targetMotion"], ns["_postFilter"], ns["_maxNum"]) != (2, 1, 4, 1):
                raise ValueError("native ranged motion/count/priority changed")
            projectile = source["projectiles"]["projectile_mocock"]
            movers = [c for c in projectile["components"].values() if c["native_class"] == "ParacurveMovement"]
            simples = [c for c in projectile["components"].values() if c["native_class"] == "SimpleProjectile"]
            if len(movers) != 1 or len(simples) != 1: raise ValueError("native projectile closure ambiguous")
            speed = movers[0]["raw"]["_speed"]; p = simples[0]["raw"]
            if speed != 5 or p["_maxHitNum"] != 1 or p["_stopAfterMaxHit"] != 1 or p["_stopWhenSourceInvalid"] != 0 or p["_lifeTime"] != 10 or p["_alwaysHitTraceTargetInTheEnd"] != 1:
                raise ValueError("native projectile speed/hit/lifetime/source-retirement flags changed")
            if fields["_useCachedAtkOnly"] != 0:
                raise ValueError("native live attack attribute flag changed")
            selector = {"id": sid, "kind": "selector", "region": {"type": "circle", "radius": row["rangeRadius"]},
                "filters": [{"tag": "player"}, {"tag": "ground"}, {"state": "alive"}], "limit": 1}
            profile.update(native_selector=native_selectors[0], native_projectile=projectile,
                target_profile="newest_runtime_id_priority_v1", windup_profile="unscaled_source_event22_v1",
                flight_profile={"id": "launch_planar_distance_capped_at_lifetime_v1", "speed": speed,
                    "distance_sample": "launch", "duration": "min(distance/speed, native_lifetime) then ceil logical ticks",
                    "target_motion_after_launch": "captured_target_id; no rescheduled flight",
                    "source_retire_after_launch": "launched_effect_survives", "target_retire_before_impact": "reject damage; no retarget",
                    "native_lifetime": 10, "selection_radius_at_cast": 1.75,
                    "stationary_in_range_max_flight": .35, "model_expiry_policy": "attempt_alive_captured_target_hit_at_lifetime",
                    "expiry_supporting_field": "_alwaysHitTraceTargetInTheEnd=1; native callback unverified"})
            profile["client_pending"] += ["native_paracurve_tracking_and_impact_callback", "native_hatred_desc_priority_formula"]
            profile["model_gap"] += ["native_target_free_camouflage_and_abnormal_filter_semantics", "native_paracurve_collision_and_curved_path",
                "native_projectile_expiry_after_dynamic_chase", "native_ranged_move_attack_fsm_and_stop_move_clock"]
            profile["behavior_profile"] = {"id": "declarative_move_and_attack_allowed_v1", "move": True, "attack": True,
                "native_fsm_body_recovered": False}
            ability = {"id": aid, "kind": "ability", "activation": {"mode": "automatic_attack"},
                "selector": sid, "target_capture": "at_cast", "parameters": {"projectile_speed": speed},
                "rules": {"projectile.flight_time": "rule/ch1_launch_distance_flight", "targeting.score": "rule/ch1_recent_target"},
                "timeline": [{"at_seconds": hits[0]["seconds"], "effect": {"op": "damage", "damage_type": "physical", "scale": 1,
                    "condition": "inputs.targets[0].components.runtime.alive",
                    "read_mode": {"source_attributes": "at_hit", "target_attributes": "at_hit"}}}]}
        ability["metadata"] = {"native_id": key, "profile": profile, "status": "executable_model_client_pending", "formal_approved": False}
        abilities.append(ability); selectors.append(selector); profiles[key] = profile
        entities.append({"id": "unit/"+key, "kind": "entity", "tags": ["enemy", "ground"],
            "components": {"attributes": {"base": {"max_hp": attrs["maxHp"], "atk": attrs["atk"], "def": attrs["def"],
                "mres": attrs["magicResistance"], "move_speed": attrs["moveSpeed"], "mass_level": attrs["massLevel"],
                "attack_interval": attrs["baseAttackTime"], "attack_speed_ratio": attrs["attackSpeed"]/100, "block_cost": 1}},
                "resources": {"hp": {"initial": attrs["maxHp"], "capacity": attrs["maxHp"], "role": "health"}},
                "lifecycle": {"policy": "policy/ark_lifecycle"}, "spatial": {}, "abilities": [aid]},
            "metadata": {"native_id": key, "source_configuration": record["native_enemy"], "client_pending": True}})
        if key != IDS[0]:
            entities[-1]["components"]["behavior"] = {"machine": "behavior/ch1_ranged_model"}
    return {"schemaVersion": 2, "manifest": {"id": "package/campaign/chapter01/advanced_attack_models", "version": "0.1.0",
        "requires": ["preset/ark_standard"], "metadata": {"status": "executable_profiles_client_pending", "formal_stage_approved": False,
            "source_audit_sha256": SOURCE_SHA, "builder_sha256": sha(Path(__file__)), "native_source_identities": identities,
            "integration": {"normal_attack_overrides": {e["id"]: e["components"]["abilities"][0] for e in entities},
                "behavior_overrides": {"unit/"+key: {"machine": "behavior/ch1_ranged_model"} for key in IDS[1:]},
                "do_not_append_second_normal_attack": True, "preserve_stage_spatial_and_instance_rules": True,
                "preserve_stage_melee_behavior": True},
            "profiles": profiles, "test_scope": "new_after_M8_full_suite_no_full_stage"}},
        "entities": entities, "abilities": abilities, "selectors": selectors, "rules": rules,
        "behaviors": [{"id": "behavior/ch1_ranged_model", "kind": "behavior", "initial": "active",
            "states": {"active": {}}, "transitions": [], "metadata": {"profile": "move_and_attack_allowed_v1", "client_verified": False}}]}


def fixture(key, positions=None, defender_hp=2000, defender_def=30):
    value = build()
    player = {"id": "unit/ch1_fixture_player", "kind": "entity", "tags": ["player", "ground"],
        "components": {"attributes": {"base": {"max_hp": defender_hp, "atk": 10000, "def": defender_def, "mres": 0}},
            "resources": {"hp": {"initial": defender_hp, "capacity": defender_hp, "role": "health"}},
            "lifecycle": {"policy": "policy/ark_lifecycle"}, "spatial": {}}}
    value["entities"].append(player)
    positions = positions or {"first": {"row": 2, "col": 3}}
    value["scenarioDraft"] = {"id": "scenario/ch1_advanced_attack_fixture", "ruleset": "ruleset/ark_standard", "map": {"rows": 5, "cols": 6},
        "initialEntities": [{"definition": "unit/"+key, "instanceAlias": "enemy", "position": {"row": 2, "col": 2}},
            *[{"definition": player["id"], "instanceAlias": name, "position": pos} for name, pos in positions.items()]]}
    return value


def assertions():
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    result = {}; key = IDS[0]
    s = Engine.create(Compiler().compile(fixture(key)))
    s.ctx.set("enemy", ("runtime", "blocked_by"), s.session.world.resolve("first"))
    s.advance(12); assert s.ctx.resources.current("first", "hp") == 2000
    s.advance(1); assert s.ctx.resources.current("first", "hp") == 1855
    s.advance(10); assert s.ctx.resources.current("first", "hp") == 1855
    s.advance(1); assert s.ctx.resources.current("first", "hp") == 1710
    result[key] = {"packet_ticks": [12, 23], "packet_amount": 145, "final_hp": 1710,
        "program_fingerprint": s.program.fingerprint, "runtime_fingerprint": s.runtime_fingerprint}
    assert len([e for e in s.session.events if e["type"] == "attack.accepted"]) == 1
    for key, expected in zip(IDS[1:], (1850, 1780)):
        s = Engine.create(Compiler().compile(fixture(key))); s.advance(22)
        assert s.ctx.resources.current("first", "hp") == 2000
        s.advance(1); launches = [e for e in s.session.events if e["type"] == "projectile.launched"]
        assert len(launches) == 1 and launches[0]["time"] == 22 and launches[0]["payload"]["flight_seconds"] == .2
        s.advance(5); assert s.ctx.resources.current("first", "hp") == 2000
        s.advance(1); assert s.ctx.resources.current("first", "hp") == expected
        result[key] = {"launch_tick": 22, "launch_distance": 1, "native_speed": 5, "model_flight_seconds": .2,
            "impact_tick": 28, "final_hp": expected, "runtime_fingerprint": s.runtime_fingerprint}
        result[key]["program_fingerprint"] = s.program.fingerprint
    return {"schema": "ark-sim/chapter01-advanced-attack-assertions/v1", "actual_probes_passed": True,
        "profiles": result, "implementation_digest": implementation_digest(), "client_verified": False, "full_stage_executed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    value = build(); evidence = assertions()
    from ark_sim import Compiler
    probe = deepcopy(value)
    probe["scenarioDraft"] = {"id": "scenario/ch1_all_profiles_validation", "ruleset": "ruleset/ark_standard",
        "map": {"rows": 5, "cols": 6}, "roster": [e["id"] for e in value["entities"]]}
    program = Compiler().compile(probe)
    evidence["all_profile_compiler_definitions"] = len(program.definitions)
    evidence["all_profile_compiler_rules"] = len(program.rules)
    evidence["model_sha256"] = hashlib.sha256((json.dumps(value, ensure_ascii=False, indent=2)+"\n").encode()).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in (("attacks.model.json", value), ("assertions.json", evidence)):
        path = OUT/name
        if args.check:
            if not path.exists() or read(path) != data: raise SystemExit("chapter01 attack model drift: "+name)
        else: path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf8", newline="\n")
    print(f"3 executable profiles; actual damage/frame/flight probes passed; {len(program.definitions)} definitions; client pending")
