"""Author explicit, replaceable W HP-mode/C4 profiles; native callbacks remain gaps."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = ROOT / "packages/campaign/chapter01_sources/native.reference.json"
OUT = ROOT / "packages/campaign/chapter01_models/w"
MODE = "buff/chapter01_w_mode1"
UNIT = "unit/chapter01_w"
C4 = "ability/chapter01_w_c4_"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    source = json.loads(SOURCE.read_bytes())
    w = source["enemies"]["enemy_1504_cqbw"]
    attrs = w["native_enemy"]["resolved"]["attributes"]
    skills = w["native_enemy"]["resolved"]["skills"]
    if len(skills) != 1 or skills[0]["prefabKey"] != "C4":
        raise ValueError("W C4 DB identity changed")
    skill = skills[0]
    bb = {r["key"]: r["value"] for r in skill["blackboard"]}
    components = w["prefab"]["components"]
    checkers = [r for r in components.values() if "_minHpRatio" in r["raw"]]
    if len(checkers) != 1:
        raise ValueError("W HP checker identity ambiguous")
    checker = checkers[0]["raw"]
    if (checker["_minHpRatio"], checker["_maxHpRatio"], checker["_useLTForMax"], checker["_toggleOnce"]) != (0, .5, 0, 0):
        raise ValueError("W reversible half-HP source changed")
    drivers = [r for r in components.values() if "_overwriteInitCooldown" in r["raw"]]
    attacks = [r for r in components.values() if r["raw"].get("_projectileKey") == "projectile_enemy_cqbw_s1"]
    if sorted(r["raw"]["_overwriteInitCooldown"] for r in drivers) != [-1, 0] or len(attacks) != 2:
        raise ValueError("W C4 mode source changed")
    predelays = {r["raw"]["_preDelay"] for r in attacks}
    projectiles = source["projectiles"]["projectile_enemy_cqbw_s1"]["components"]
    lives = {r["raw"]["_lifeTime"] for r in projectiles.values() if "_lifeTime" in r["raw"]}
    if len(predelays) != 1 or len(lives) != 1:
        raise ValueError("W C4 timing source ambiguous")
    # Authored 1x profile: round source float32 animation durations to 30Hz frames.
    windup = round(next(iter(predelays))*30)/30
    lifetime = round(next(iter(lives))*30)/30
    period = skill["cooldown"]
    initial = skill["initCooldown"]
    if (period, initial, windup, lifetime, bb["atk_scale"], bb["range_radius"]) != (20, 9, .6, 3.2, 1.8, 2.5):
        raise ValueError("W source values differ from independently reviewed profile")
    selectors, abilities = [], []
    for mode, count in ((0, 1), (1, 3)):
        sid = f"selector/chapter01_w_c4_{mode}"
        selectors.append({"id": sid, "kind": "selector", "region": {"type": "radius", "radius": 2.5},
            "filters": [{"tag": "player"}, {"state": "alive"}], "ordering": "stable", "limit": count})
        abilities.append({"id": C4+str(mode), "kind": "ability", "metadata": {"native_enemy_id": "enemy_1504_cqbw",
            "native_skill_key": "C4", "mode": mode, "client_verified": False},
            "activation": {"mode": "manual", "condition": f"inputs.resources.mode.current == {mode}",
                "costs": [{"resource": f"c4_clock_{mode}", "amount": period}],
                "parameters": {"auto_when_ready": True, "auto_only": True, "requires_targets": True}},
            "selector": sid, "target_capture": "at_cast", "parameters": {"blocks_attacks": True},
            "timeline": [{"at_seconds": windup+lifetime, "effect": {"op": "area", "center": "target",
                "radius": bb["range_radius"], "filters": [{"tag": "player"}],
                "effects": [{"op": "damage", "damage_type": "physical", "scale": bb["atk_scale"],
                    "read_mode": {"source_attributes": "at_cast"}}]}}]})
    enter = "ability/chapter01_w_enter_mode1"
    leave = "ability/chapter01_w_leave_mode1"
    guard = "inputs.payload.target == inputs.source.id and inputs.payload.resource == 'hp'"
    abilities += [{"id": enter, "kind": "ability", "activation": {"mode": "passive", "event": "resource.changed",
        "condition": guard+" and 0 < inputs.resources.hp.current <= 5000 and inputs.resources.mode.current == 0",
        "parameters": {"cancel_pending_attacks": True, "reset_attack_clock": True},
        "on_start": [{"op": "modify_resource", "target": "source", "resource": "mode", "value": 1},
            {"op": "modify_resource", "target": "source", "resource": "c4_clock_1", "value": period},
            {"op": "apply_buff", "target": "source", "buff": MODE}]},
        "parameters": {"blocks_attacks": False}, "timeline": []},
        {"id": leave, "kind": "ability", "activation": {"mode": "passive", "event": "resource.changed",
            "condition": guard+" and inputs.resources.hp.current > 5000 and inputs.resources.mode.current == 1",
            "parameters": {"cancel_pending_attacks": True, "reset_attack_clock": True},
            "on_start": [{"op": "remove_buff", "target": "source", "buff": MODE},
                {"op": "modify_resource", "target": "source", "resource": "c4_clock_0", "value": period-initial}]},
            "parameters": {"blocks_attacks": False}, "timeline": []}]
    resources = {"hp": {"initial": attrs["maxHp"], "capacity": attrs["maxHp"], "role": "health"},
        "mode": {"initial": 0, "capacity": 1}}
    for mode in (0, 1):
        resources[f"c4_clock_{mode}"] = {"initial": period-initial if mode == 0 else 0, "capacity": period,
            "recovery_rate": 1, "parameters": {"pause_at_full": True}}
    entity = {"id": UNIT, "kind": "entity", "tags": ["enemy", "ground", "boss"],
        "components": {"attributes": {"base": {"max_hp": attrs["maxHp"], "atk": attrs["atk"], "def": attrs["def"],
            "mres": attrs["magicResistance"], "attack_interval": attrs["baseAttackTime"], "attack_speed_ratio": 1}},
            "resources": resources, "spatial": {}, "lifecycle": {"policy": "policy/ark_lifecycle"},
            "abilities": [a["id"] for a in abilities]}}
    profiles = {"hp_mode": "resource-change event; 0 < hp/max_hp <= .5 activates reversible mode1; no ATK modifier",
        "FSM_restart": "cancel pending automatic attacks and reset next_attack; active C4 survives mode change",
        "C4_clock": "named timer, not native SP; recovery includes tick0: Default first readiness tick269/period600ticks; T1 ready on entry; reset Default9s on restore",
        "C4_target": "Default stable one in radius2.5; T1 stable three; cast captures actor identity",
        "C4_bomb": "fixed 1x launch .6s plus attached lifetime3.2s; target current position at explosion; overlapping bombs settle separately",
        "sampling": "source ATK at cast, target DEF at explosion; no target-death cancellation; dead source cancels remaining cast"}
    gaps = ["native_C4_projectile_attach_callbacks_and_expiry_not_recovered", "native_Default_C4_null_selector_inheritance",
        "native_C4_cooldown_restart_and_mode_transition_driver_semantics", "native_HP_checker_event_order_and_comparison_algorithm",
        "native_normal_attack_two_event_packets_and_parabolic_motion_not_authored", "native_target_sorting_and_projectile_invalid_FSM"]
    return {"schemaVersion": 2, "manifest": {"id": "package/campaign/chapter01_w_model", "version": "0.1.0",
        "requires": ["preset/ark_standard"], "metadata": {"source": SOURCE.relative_to(ROOT).as_posix(),
            "source_sha256": digest(SOURCE), "builder_sha256": digest(Path(__file__)), "profiles": profiles,
            "status": "partial_source_backed_replaceable_model", "client_pending": gaps,
            "model_gaps": ["normal_attack_not_authored", "native_C4_projectile_lifetime_and_invalid_callback_adapter"],
            "full_enemy_implemented": False, "formal_stage_approved": False}},
        "entities": [entity], "abilities": abilities, "selectors": selectors,
        "buffs": [{"id": MODE, "kind": "buff", "on_remove": [
            {"op": "modify_resource", "target": "source", "resource": "mode", "value": 0}]}]}


def fixture(package, positions=((3, 4),), automatic=True):
    data = deepcopy(package)
    data["entities"].append({"id": "unit/chapter01_w_target", "kind": "entity", "tags": ["player", "ground"],
        "components": {"attributes": {"base": {"max_hp": 5000, "def": 100, "mres": 0}}, "spatial": {},
            "lifecycle": {"policy": "policy/ark_lifecycle"},
            "resources": {"hp": {"initial": 5000, "capacity": 5000, "role": "health"}}}})
    if not automatic:
        for a in data["abilities"]:
            if a["id"].startswith(C4):
                a["activation"]["parameters"].update(auto_when_ready=False, auto_only=False)
    data["scenarioDraft"] = {"id": "scenario/chapter01_w_probe", "ruleset": "ruleset/ark_standard",
        "map": {"rows": 9, "cols": 9}, "initialEntities": [
            {"definition": UNIT, "instanceAlias": "w", "position": {"row": 3, "col": 3}}]+[
            {"definition": "unit/chapter01_w_target", "instanceAlias": f"target{i}", "position": {"row": row, "col": col}}
            for i, (row, col) in enumerate(positions)]}
    return data


def verify(package):
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.compare import first_difference
    from ark_sim.tools.replay import replay
    # Independent arithmetic: 470*1.8 - DEF100 = 746. Fixed 30Hz .6+3.2 =>114 ticks.
    manual_data = fixture(package, automatic=False)
    manual_data["entities"][0]["components"]["resources"]["c4_clock_0"]["initial"] = 20
    sim = Engine.create(Compiler().compile(manual_data))
    sim.submit({"action": "skill", "source": "w", "ability": C4+"0"})
    sim.advance(100)
    assert sim.ctx.resources.current("target0", "hp") == 5000
    restored = Engine.restore(sim.program, sim.checkpoint())
    sim.advance(15); restored.advance(15)
    assert sim.ctx.resources.current("target0", "hp") == 4254
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(sim.program, sim.export_replay()).snapshot()) is None
    single = {"damage": 746, "impact_tick": 114, "checkpoint_equal": True, "replay_equal": True,
        "program_fingerprint": sim.program.fingerprint, "runtime_fingerprint": sim.runtime_fingerprint}
    # HP equality enters, healing above boundary restores. No inferred ATK increase.
    mode = Engine.create(Compiler().compile(fixture(package, positions=(), automatic=False)))
    mode.ctx.resources.adjust(mode.session.world.resolve("w"), "hp", value=5000)
    mode.advance(2)
    assert mode.ctx.resources.current("w", "mode") == 1
    assert mode.ctx.attributes.values("w")["atk"] == 470
    mode.ctx.resources.adjust(mode.session.world.resolve("w"), "hp", value=5001)
    mode.advance(2)
    assert mode.ctx.resources.current("w", "mode") == 0
    assert mode.ctx.attributes.values("w")["atk"] == 470
    # Independent clock arithmetic: 270 recovery steps including tick0 =>269;
    # fixed .6+3.2 delay adds114, so first impact is383 (model, not native timing).
    auto = Engine.create(Compiler().compile(fixture(package)))
    auto.advance(383)
    assert auto.ctx.resources.current("target0", "hp") == 5000
    auto.advance(1)
    assert auto.ctx.resources.current("target0", "hp") == 4254
    auto.advance(599)
    assert auto.ctx.resources.current("target0", "hp") == 4254
    auto.advance(1)
    assert auto.ctx.resources.current("target0", "hp") == 3508
    # Three bombs: separated centers hit only themselves, fourth legal target is
    # not captured. A separate clustered probe checks overlap without deduping.
    def mode1_fixture(positions):
        data = fixture(package, positions=positions, automatic=False)
        resources = data["entities"][0]["components"]["resources"]
        resources["mode"]["initial"] = 1
        resources["c4_clock_1"]["initial"] = 20
        return data
    spread = Engine.create(Compiler().compile(mode1_fixture(((3, 5), (5, 3), (3, 1), (1, 3)))))
    spread.submit({"action": "skill", "source": "w", "ability": C4+"1"})
    spread.advance(115)
    assert [spread.ctx.resources.current(f"target{i}", "hp") for i in range(4)] == [4254, 4254, 4254, 5000]
    cluster = Engine.create(Compiler().compile(mode1_fixture(((3, 4),)*4)))
    cluster.submit({"action": "skill", "source": "w", "ability": C4+"1"})
    cluster.advance(115)
    assert [cluster.ctx.resources.current(f"target{i}", "hp") for i in range(4)] == [2762]*4
    dead_source = Engine.create(Compiler().compile(manual_data))
    dead_source.submit({"action": "skill", "source": "w", "ability": C4+"0"})
    dead_source.advance(50)
    dead_source.ctx.lifecycle.retire("w", "dead")
    dead_source.advance(65)
    assert dead_source.ctx.resources.current("target0", "hp") == 5000
    return {"passed": True, "implementation_digest": implementation_digest(), "single_c4": single,
        "hp_mode_boundary": {"hp5000_mode": 1, "hp5001_mode": 0, "atk_both_modes": 470},
        "default_automatic_impact_ticks": [383, 983], "mode1_separated_hp": [4254, 4254, 4254, 5000],
        "mode1_cluster_hp": [2762]*4, "source_death_cancels_remaining_cast": True,
        "client_verified": False, "full_enemy_implemented": False,
        "formal_stage_approved": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    package = build(); evidence = verify(package)
    values = {"model.json": package, "probe.json": fixture(package), "assertions.json": evidence}
    OUT.mkdir(parents=True, exist_ok=True)
    for name, value in values.items():
        path = OUT/name
        if args.check:
            if not path.exists() or json.loads(path.read_bytes()) != value:
                raise SystemExit("W model drift: "+name)
        else:
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps({"passed": evidence["passed"], "output": OUT.as_posix(),
        "implementation_digest": evidence["implementation_digest"], "full_enemy_implemented": False}))


if __name__ == "__main__":
    main()
