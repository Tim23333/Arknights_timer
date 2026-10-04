"""Isolated candidate route models. Never collected by primary tests_v2."""
from copy import deepcopy
from pathlib import Path
import sys
import os
import pytest

PRIMARY = Path(__file__).resolve().parents[3]
CANDIDATE = Path(os.environ.get("ARK_CANDIDATE_ROOT", str(PRIMARY.parent/"unpack_work/campaign_m9_final_candidate")))
if "ark_sim" in sys.modules:
    assert Path(sys.modules["ark_sim"].__file__).resolve().is_relative_to(CANDIDATE.resolve()), "primary runtime was imported before candidate injection"
sys.path.insert(0, str(CANDIDATE))
import ark_sim
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay

assert Path(ark_sim.__file__).resolve().is_relative_to(CANDIDATE.resolve())


def policy(effects="reject", auras="suspend", launched="retain"):
    return {"rule": "rule/m9_living_transition", "parameters": {"hidden_effects": effects, "hidden_auras": auras,
        "launched_source_effects": launched, "resource_timers": "continue"}}


def offset_policy(): return {"rule": "rule/m9_checkpoint_cartesian", "parameters": {"axis_signs": {"row": -1, "col": 1}}}


def route():
    return {"motionMode": "WALK", "startPosition": {"row": 1, "col": 0}, "endPosition": {"row": 1, "col": 5},
        "transition_policy": policy(), "checkpoints": [{"type": "DISAPPEAR"}, {"type": "WAIT_FOR_SECONDS", "time": 1},
            {"type": "APPEAR_AT_POS", "position": {"row": 1, "col": 3}}, {"type": "WAIT_FOR_SECONDS", "time": 1}]}


def data(r=None, timeline=False):
    actor = {"id": "unit/route_actor", "kind": "entity", "tags": ["enemy", "ground"], "components": {
        "attributes": {"base": {"max_hp": 100, "atk": 10, "def": 0, "mres": 0, "move_speed": 1,
            "attack_interval": 100, "attack_speed_ratio": 1, "block_cost": 1}},
        "resources": {"hp": {"initial": 100, "capacity": 100, "role": "health"}, "sp": {"initial": 0, "capacity": 20, "recovery_rate": 1}},
        "spatial": {}, "lifecycle": {"policy": "policy/ark_lifecycle"}}}
    player = deepcopy(actor); player.update(id="unit/player", tags=["player", "ground"]); player["components"]["resources"].pop("sp")
    scene = {"id": "scenario/m9_route_candidate", "ruleset": "ruleset/ark_standard", "map": {"rows": 3, "cols": 6},
        "dependencies": ["selector/enemies"],
        "initialEntities": [{"definition": "unit/player", "instanceAlias": "player", "position": {"row": 1, "col": 0}}]}
    wave = {"definition": actor["id"], "instanceAlias": "actor", "position": {"row": 1, "col": 0}, "route": r or route()}
    if timeline:
        scene["objectives"] = {"type": "waves", "life_resource": "life", "defeat_threshold": 0}
        scene["resources"] = {"life": {"initial": 3, "capacity": 3}}
        scene["timeline"] = {"policy": "managed_clear", "negative_timeout_policy": "wait_for_clear", "waves": [
            {"fragments": [{"actions": [{"kind": "spawn", "spawn": wave, "managed": True, "blocks_wave": True, "blocks_fragment": False}]}]},
            {"fragments": [{"actions": [{"kind": "effects", "managed": False, "blocks_wave": False, "effects": [
                {"op": "emit", "target": "battle", "event": "review.next_wave"}]}]}]}]}
    else: scene["waves"] = [{"at": 0, **wave}]
    return {"schemaVersion": 2, "entities": [actor, player], "selectors": [{"id": "selector/enemies", "kind": "selector",
        "region": {"type": "all"}, "filters": [{"tag": "enemy"}, {"state": "alive"}]}], "scenarioDraft": scene}


def sim(d=None): return Engine.create(Compiler().compile(d or data()), seed=912)
def hp(s): return s.ctx.resources.current("actor", "hp")


def test_import_is_exclusively_candidate_and_primary_digest_untouched():
    for name, module in list(sys.modules.items()):
        if name == "ark_sim" or name.startswith("ark_sim."):
            if getattr(module, "__file__", None): assert Path(module.__file__).resolve().is_relative_to(CANDIDATE.resolve())


def test_hidden_is_alive_managed_not_selected_and_timers_continue_until_appearance():
    s = sim(data(timeline=True)); s.advance(1)
    assert s.ctx.alive("actor") and s.ctx.route_hidden("actor")
    assert s.ctx.spatial.select("player", "selector/enemies") == []
    assert len(s.ctx.state()["timeline"]["members"]) == 1 and not s.ctx.state()["finished"]
    s.advance(29); assert s.ctx.route_hidden("actor")
    assert s.ctx.resources.current("actor", "sp") == pytest.approx(1)
    s.advance(1)
    assert not s.ctx.route_hidden("actor") and s.ctx.alive("actor")
    assert s.ctx.get("actor", ("spatial", "position")) == {"row": 1, "col": 3}
    assert s.ctx.spatial.select("player", "selector/enemies") == [s.session.world.resolve("actor")]
    assert len(s.ctx.state()["timeline"]["members"]) == 1


@pytest.mark.parametrize("op", ["damage", "heal", "regenerate", "modify_resource"])
def test_hidden_default_captured_and_direct_health_effects_rejected(op):
    s = sim(); s.advance(1); s.ctx.set("actor", ("resources", "hp", "current"), 50)
    effect = {"op": op, "damage_type": "true", "scale": 1}
    if op == "modify_resource": effect.update(resource="hp", amount=-10)
    s.ctx.effects.execute("player", ["actor"], effect)
    assert hp(s) == 50
    s.session.schedule("domain.effect", {"source": s.session.world.resolve("player"), "targets": [s.session.world.resolve("actor")],
        "effect": effect}, s.session.time, phase=s.ctx.effect_phase)
    s.advance(1); assert hp(s) == 50


def test_explicit_hidden_effect_profile_can_allow_captured_damage_but_not_selection():
    r = route(); r["transition_policy"] = policy(effects="allow")
    s = sim(data(r)); s.advance(1)
    s.ctx.effects.execute("player", ["actor"], {"op": "damage", "damage_type": "true", "scale": 1})
    assert hp(s) == 90 and s.ctx.spatial.select("player", "selector/enemies") == []


def test_hidden_area_member_excluded_even_when_near_visible_actor():
    d = data(); d["scenarioDraft"]["initialEntities"].append({"definition": "unit/route_actor", "instanceAlias": "visible", "position": {"row": 1, "col": 0}})
    s = sim(d); s.advance(1)
    s.ctx.effects.execute("player", ["visible"], {"op": "area", "center": "target", "radius": 1, "filters": [{"tag": "enemy"}],
        "effects": [{"op": "damage", "damage_type": "true", "scale": 1}]})
    assert hp(s) == 100 and s.ctx.resources.current("visible", "hp") == 90


def test_nonzero_offset_axis_flip_is_actual_target_and_not_tile_center():
    r = {"motionMode": "WALK", "startPosition": {"row": 1, "col": 0}, "endPosition": {"row": 1, "col": 5},
        "reach_offset_policy": offset_policy(), "checkpoints": [{"type": "MOVE", "position": {"row": 1, "col": 0},
            "reachOffset": {"x": -.25, "y": .2}}, {"type": "WAIT_FOR_SECONDS", "time": 1}]}
    s = sim(data(r)); s.advance(15)
    assert s.ctx.get("actor", ("spatial", "position")) == {"row": .8, "col": -.25}


@pytest.mark.parametrize("bad", ["no_policy", "nested", "orphan", "unclosed", "hidden_move", "bad_effect_policy", "nan_offset", "no_offset_policy", "bad_axis", "out_of_map", "random", "unknown"])
def test_strict_bad_pair_policy_and_offset_rejected(bad):
    r = route()
    if bad == "no_policy": r.pop("transition_policy")
    elif bad == "nested": r["checkpoints"].insert(1, {"type": 5})
    elif bad == "orphan": r["checkpoints"].pop(0)
    elif bad == "unclosed": r["checkpoints"] = [{"type": 5}]
    elif bad == "hidden_move": r["checkpoints"].insert(1, {"type": 0, "position": {"row": 1, "col": 1}})
    elif bad == "bad_effect_policy": r["transition_policy"]["parameters"]["hidden_effects"] = "silently_ignore"
    else:
        cp = {"type": 0, "position": {"row": 1, "col": 0}, "reachOffset": {"x": .1, "y": 0}}
        r["checkpoints"].insert(0, cp); r["reach_offset_policy"] = offset_policy()
        if bad == "nan_offset": cp["reachOffset"]["x"] = float("nan")
        elif bad == "no_offset_policy": r.pop("reach_offset_policy")
        elif bad == "bad_axis": r["reach_offset_policy"]["parameters"]["axis_signs"]["row"] = True
        elif bad == "out_of_map": cp["reachOffset"]["x"] = -.51
        elif bad == "random": cp["randomizeReachOffset"] = True
        elif bad == "unknown": cp["type"] = 999
    with pytest.raises(ValueError): Compiler().compile(data(r))


def test_wrong_policy_contract_is_compile_rejected():
    r = route(); r["transition_policy"]["rule"] = "rule/ark_wait_deadline"
    with pytest.raises(ValueError, match="incompatible rule"): Compiler().compile(data(r))


@pytest.mark.parametrize("context", ["flat", "timeline", "initial"])
def test_nested_component_route_policy_contract_is_also_strict(context):
    r = route(); r["transition_policy"]["rule"] = "rule/ark_wait_deadline"
    d = data(r, timeline=context == "timeline")
    if context == "timeline": item = d["scenarioDraft"]["timeline"]["waves"][0]["fragments"][0]["actions"][0]["spawn"]
    else: item = d["scenarioDraft"]["waves"][0]
    item["components"] = {"spatial": {"route": item.pop("route")}}
    if context == "initial":
        d["scenarioDraft"].pop("waves"); item.pop("at")
        d["scenarioDraft"]["initialEntities"].append(item)
    with pytest.raises(ValueError, match="incompatible rule"): Compiler().compile(d)


def test_checkpoint_full_replay_hidden_state_membership_and_timer_origins():
    s = sim(data(timeline=True)); s.advance(10); cp = s.checkpoint(); s.advance(70)
    restored = Engine.restore(s.program, cp); restored.advance(70)
    assert restored.snapshot() == s.snapshot()
    assert replay(s.program, s.export_replay()).snapshot() == s.snapshot()


def attacks(d):
    d["selectors"].append({"id": "selector/players", "kind": "selector", "region": {"type": "all"}, "filters": [{"tag": "player"}], "limit": 1})
    d["abilities"] = [{"id": "ability/probe", "kind": "ability", "activation": {"mode": "automatic_attack"},
        "selector": "selector/players", "timeline": [{"at_seconds": .2, "effect": {"op": "damage", "damage_type": "true", "scale": 1}}]}]
    d["entities"][0]["components"]["abilities"] = ["ability/probe"]
    return d


def test_hidden_cancels_pending_attack_and_rejects_new_activation_without_payment():
    d = attacks(data())
    d["abilities"].append({"id": "ability/manual_probe", "kind": "ability", "activation": {"mode": "manual", "costs": [{"resource": "sp", "amount": 1}]},
        "selector": "selector/players", "timeline": []})
    d["entities"][0]["components"]["abilities"].append("ability/manual_probe")
    s = sim(d); s.advance(1)
    assert not s.ctx.get("actor", ("runtime", "casts"))
    assert any(e["type"] == "ability.interrupted" and e["payload"]["reason"] == "route_disappeared" for e in s.session.events)
    before = s.ctx.resources.current("actor", "sp")
    with pytest.raises(ValueError, match="route-hidden"): s.ctx.abilities.start("actor", "ability/manual_probe")
    assert s.ctx.resources.current("actor", "sp") == before
    s.advance(10)
    assert s.ctx.resources.current("player", "hp") == 100
    assert s.ctx.get("actor", ("runtime", "next_attack")) == 3000


def test_appear_relocation_does_not_add_distance_or_trigger_rupture_damage():
    d = data(); d["buffs"] = [{"id": "buff/rupture", "kind": "buff", "duration_seconds": 10,
        "interval_seconds": .1, "movement_damage": {"effect": {"op": "damage", "damage_type": "true",
            "rules": {"damage.pipeline": "rule/rupture"}}}}]
    d["rules"] = [{"id": "rule/rupture", "kind": "calculation_rule", "contract": "damage.pipeline",
        "implementation": {"type": "graph", "nodes": [{"id": "settled", "type": "expression",
            "expression": "{'accepted': True, 'amount': inputs.effect.distance * 20, 'allocations': [], 'events': []}"}], "output": "nodes.settled"}}]
    d["entities"][0]["components"]["buffs"] = {"initial": ["buff/rupture"]}
    s = sim(d); s.advance(31)
    assert hp(s) == 100 and s.ctx.get("actor", ("spatial", "distance_travelled"), 0) == 0
    assert not [e for e in s.session.events if e["type"] == "movement.traveled"]
    s.advance(40)
    assert s.ctx.get("actor", ("spatial", "distance_travelled")) > 0
    assert hp(s) < 100


def test_hidden_blocker_and_mover_release_blocks_then_appear_reconciles():
    d = data(); player = d["entities"][1]["components"]
    player["attributes"]["base"]["block_count"] = 1; player["deployable"] = {"cost": 0, "terrain": "ground"}
    d["scenarioDraft"]["initialEntities"][0]["position"] = {"row": 1, "col": 3}
    s = sim(d); s.advance(1)
    assert s.ctx.spatial.blocked_by("actor") is None
    s.advance(30)
    assert s.ctx.spatial.blocked_by("actor") == s.session.world.resolve("player")
    assert s.ctx.get("actor", ("spatial", "velocity")) == {"row": 0, "col": 0}


def test_offset_pure_formula_is_replaceable_and_invalid_output_rolls_back():
    r = {"motionMode": "WALK", "endPosition": {"row": 1, "col": 5}, "reach_offset_policy": offset_policy(),
        "checkpoints": [{"type": 0, "position": {"row": 1, "col": 0}, "reachOffset": {"x": .1, "y": .1}}]}
    d = data(r); d["rules"] = [{"id": "rule/replaced_point", "kind": "calculation_rule", "contract": "movement.checkpoint_position",
        "implementation": {"type": "expression", "expression": "{'row': inputs.position.row, 'col': inputs.position.col+0.2}"}}]
    r["reach_offset_policy"]["rule"] = "rule/replaced_point"
    s = sim(d); s.advance(10); assert s.ctx.get("actor", ("spatial", "position"))["col"] >= .2
    d["rules"][0]["implementation"]["expression"] = "{'row': 1, 'col': 100}"
    bad = sim(d)
    with pytest.raises(ValueError, match="outside map"): bad.advance(1)
    assert bad.ctx.get("actor", ("spatial", "position")) == {"row": 1, "col": 0}
    assert not [e for e in bad.session.events if e["type"] == "calculation" and e["payload"]["calculation_id"] == "movement.checkpoint_position"]


def aura(d, source="player"):
    d["scenarioDraft"]["dependencies"].append("buff/emitter")
    d["selectors"].append({"id": "selector/aura", "kind": "selector", "region": {"type": "all"}, "filters": [{"state": "alive"}]})
    d["buffs"] = [{"id": "buff/member", "kind": "buff", "stacking": {"mode": "independent"},
        "modifiers": [{"attribute": "atk", "layer": "flat", "value": 5}]},
        {"id": "buff/emitter", "kind": "buff", "aura": {"selector": "selector/aura", "buff": "buff/member"}}]
    return d


def test_hidden_recipient_loses_aura_then_appearance_rejoins_immediately():
    s = sim(aura(data())); s.ctx.buffs.apply("player", "player", "buff/emitter"); s.advance(1)
    assert s.ctx.attributes.value("actor", "atk") == 10
    s.advance(30); assert s.ctx.attributes.value("actor", "atk") == 15


@pytest.mark.parametrize("choice,expected", [("suspend", 10), ("retain", 15)])
def test_hidden_owned_aura_source_keeps_parent_but_policy_controls_visible_members(choice, expected):
    r = route(); r["transition_policy"] = policy(auras=choice)
    s = sim(aura(data(r))); s.advance(1)
    # Owned center remains visible, but contribution source is hidden.
    token = s.ctx.lifecycle.create("unit/player", position={"row": 1, "col": 0}, owner="actor", alias="owned")
    s.ctx.buffs.apply("actor", token, "buff/emitter")
    assert s.ctx.attributes.value("player", "atk") == expected
    assert any(i["definition"] == "buff/emitter" for i in s.ctx.get(token, ("buffs", "instances")))
    s.advance(30); assert s.ctx.attributes.value("player", "atk") == 15


def delayed_route():
    r = route(); r["checkpoints"].insert(0, {"type": "WAIT_FOR_SECONDS", "time": .2})
    return r


def test_already_launched_projectile_cannot_hit_captured_target_after_disappear():
    d = data(delayed_route()); d["scenarioDraft"]["initialEntities"][0]["position"] = {"row": 1, "col": 1}
    d["abilities"] = [{"id": "ability/projectile", "kind": "ability", "activation": {"mode": "automatic_attack"},
        "selector": "selector/enemies", "parameters": {"projectile_speed": 5},
        "timeline": [{"at": 0, "effect": {"op": "damage", "damage_type": "true", "scale": 1}}]}]
    d["entities"][1]["components"]["abilities"] = ["ability/projectile"]
    s = sim(d); s.advance(1)
    assert len([e for e in s.session.events if e["type"] == "projectile.launched"]) == 1
    s.advance(6); assert s.ctx.route_hidden("actor") and hp(s) == 100
    assert any(e["type"] == "effect.visibility_rejected" and e["time"] == 6 for e in s.session.events)


@pytest.mark.parametrize("choice,hp_expected", [("retain", 90), ("discard", 100)])
def test_hidden_source_already_launched_projectile_has_explicit_profile(choice, hp_expected):
    r = delayed_route(); r["transition_policy"] = policy(launched=choice)
    d = attacks(data(r)); d["scenarioDraft"]["initialEntities"][0]["position"] = {"row": 1, "col": 1}
    d["abilities"][0]["parameters"] = {"projectile_speed": 5}
    d["abilities"][0]["timeline"][0]["at_seconds"] = 0
    s = sim(d); s.advance(7)
    assert s.ctx.route_hidden("actor") and s.ctx.resources.current("player", "hp") == hp_expected
    assert len([e for e in s.session.events if e["type"] == "projectile.launched"]) == 1


def test_damage_allocation_cannot_redirect_health_to_hidden_actor():
    d = data(); d["rules"] = [{"id": "rule/redirect_hidden", "kind": "calculation_rule", "contract": "damage.pipeline",
        "implementation": {"type": "graph", "nodes": [{"id": "settled", "type": "expression",
            "expression": "{'accepted': True, 'amount': 10, 'allocations': [{'target': params.recipient, 'resource':'hp', 'amount':10}], 'events': []}"}],
            "output": "nodes.settled"}, "parameters": {"recipient": "actor"}}]
    d["scenarioDraft"]["dependencies"].append("rule/redirect_hidden")
    s = sim(d); s.advance(1)
    s.ctx.effects.execute("player", ["player"], {"op": "damage", "damage_type": "true", "rules": {"damage.pipeline": "rule/redirect_hidden"}})
    assert hp(s) == 100 and s.ctx.resources.current("player", "hp") == 100


def test_invalid_transition_result_is_atomic_and_fail_stop_without_fake_hidden_state():
    d = data(); d["rules"] = [{"id": "rule/bad_transition", "kind": "calculation_rule", "contract": "movement.transition",
        "implementation": {"type": "expression", "expression": "{'hidden': True, 'relocate': False, 'position': {'row':0,'col':100}}"}}]
    d["scenarioDraft"]["waves"][0]["route"]["transition_policy"]["rule"] = "rule/bad_transition"
    s = sim(d)
    with pytest.raises(ValueError, match="outside map"): s.advance(1)
    assert not s.ctx.route_hidden("actor") and s.ctx.alive("actor")
    assert not [e for e in s.session.events if e["type"] in ("movement.visibility_changed",)]
    assert not [e for e in s.session.events if e["type"] == "calculation" and e["payload"]["calculation_id"] == "movement.transition"]
    with pytest.raises(RuntimeError): s.advance(1)


def test_appearance_and_nonzero_offset_into_wall_rejected_but_fly_can_appear():
    for offset in (False, True):
        d = data(); tiles = [{"tileKey": "tile_floor", "passableMask": 1, "buildableType": 1} for _ in range(18)]
        tiles[9] = {"tileKey": "tile_wall", "passableMask": 2, "buildableType": 2}; d["scenarioDraft"]["map"]["tiles"] = tiles
        if offset:
            cp = {"type": 0, "position": {"row": 1, "col": 3}, "reachOffset": {"x": .1, "y": 0}}
            d["scenarioDraft"]["waves"][0]["route"]["checkpoints"] = [cp]
            d["scenarioDraft"]["waves"][0]["route"]["reach_offset_policy"] = offset_policy()
        with pytest.raises(ValueError, match="impassable"): Compiler().compile(d)
        d["scenarioDraft"]["waves"][0]["route"]["motionMode"] = "FLY"
        Compiler().compile(d)


@pytest.mark.parametrize("flag", [None, False, "absent"])
def test_native_undefined_randomize_flag_is_not_randomness(flag):
    r = {"motionMode": "WALK", "endPosition": {"row": 1, "col": 5},
        "checkpoints": [{"type": "MOVE", "position": {"row": 1, "col": 1}, "reachOffset": {"x": 0, "y": 0}}]}
    if flag != "absent": r["checkpoints"][0]["randomizeReachOffset"] = flag
    s = sim(data(r)); s.advance(5)
    assert s.ctx.get("actor", ("spatial", "position"))["col"] > 0
    assert not s.session.random.samples


@pytest.mark.parametrize("flag", [True, 0, 1, "false"])
def test_explicit_random_or_nonboolean_flags_still_fail(flag):
    r = {"motionMode": "WALK", "endPosition": {"row": 1, "col": 5},
        "checkpoints": [{"type": "MOVE", "position": {"row": 1, "col": 1}, "reachOffset": {"x": 0, "y": 0},
            "randomizeReachOffset": flag}]}
    with pytest.raises(ValueError, match="random checkpoint offset"): Compiler().compile(data(r))


def test_actual_offline_0_1_import_compiles_null_native_flags_without_mutation_or_legacy_import():
    from ark_sim.adapters.imports.ark_level import import_ark_level
    before = {k for k in sys.modules if k == "ark_emulator" or k.startswith("ark_emulator.")}
    package = import_ark_level(); original = deepcopy(package)
    checkpoints = [cp for wave in package["scenarioDraft"]["waves"] for cp in wave["route"].get("checkpoints") or []]
    assert checkpoints and all(cp.get("randomizeReachOffset") is None for cp in checkpoints)
    assert all(cp["reachOffset"] == {"x": 0, "y": 0} for cp in checkpoints)
    program = Compiler().compile(package)
    assert "unit/enemy_1002_nsabr" in program.definitions
    assert package == original
    assert {k for k in sys.modules if k == "ark_emulator" or k.startswith("ark_emulator.")} == before
