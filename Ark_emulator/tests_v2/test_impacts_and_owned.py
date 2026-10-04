"""Real packets, ownership lifetimes, and atomic multi-owner resource payment."""
from copy import deepcopy

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from test_campaign_acceptance import scene


def impact_model():
    data = scene()
    actor = data["entities"][0]["components"]
    actor["resources"]["sp"].update(initial=5, recovery_rate=1,
        parameters={"freeze_while_cast": True, "freeze_cast_modes": ["manual"]})
    ability = data["abilities"][0]
    ability["parameters"] = {"projectile_speed": 2, "wait_for_projectiles": True}
    ability["activation"]["costs"] = [{"resource": "sp", "amount": 1}]
    ability["timeline"][0]["effect"] = {"op": "area", "center": "target", "radius": 1.2,
        "filters": [{"tag": "enemy"}], "effects": [{"op": "damage", "damage_type": "true", "additions": 90}]}
    data["selectors"][0]["limit"] = 1
    return data


def test_one_projectile_explodes_at_primary_target_and_waits_until_impact():
    sim = Engine.create(Compiler().compile(impact_model()))
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"})
    sim.session.advance(30)
    assert len([e for e in sim.session.events if e["type"] == "projectile.launched"]) == 1
    assert sim.ctx.resources.current("target1", "hp") == 100
    assert sim.ctx.resources.current("source", "sp") == 4
    assert sim.ctx.get("source", ("runtime", "casts"))
    sim.session.advance(1)
    assert [sim.ctx.resources.current(t, "hp") for t in ("target1", "target2")] == [0, 0]
    assert not sim.ctx.get("source", ("runtime", "casts"))
    assert sim.ctx.resources.current("source", "sp") == 4
    sim.session.advance(30)
    assert sim.ctx.resources.current("source", "sp") == pytest.approx(5)


def test_positive_recovery_effect_respects_waiting_cast_but_cost_still_works():
    sim = Engine.create(Compiler().compile(impact_model()))
    sim.ctx.abilities.start("source", "ability/probe")
    sim.ctx.effects.execute("source", [sim.session.world.resolve("source")], {
        "op": "modify_resource", "resource": "sp", "delta": 1, "parameters": {"respect_recovery_freeze": True}})
    assert sim.ctx.resources.current("source", "sp") == 4
    sim.ctx.effects.execute("source", [sim.session.world.resolve("source")], {
        "op": "modify_resource", "resource": "sp", "delta": -1, "parameters": {"respect_recovery_freeze": True}})
    assert sim.ctx.resources.current("source", "sp") == 3


def owned_model():
    data = scene()
    actor = data["entities"][0]["components"]
    actor["resources"]["sp"]["initial"] = 5
    token = deepcopy(data["entities"][0])
    token["id"] = "unit/token"
    token["tags"] = ["player", "token"]
    token["components"]["abilities"] = ["ability/token_pulse"]
    data["entities"].append(token)
    data["abilities"] += [
        {"id": "ability/spawn", "kind": "ability", "activation": {"mode": "manual", "costs": [
            {"owner": "battle", "resource": "dp", "amount": 5}, {"resource": "sp", "amount": 1}],
            "on_start": [{"op": "spawn", "definition": "unit/token", "owner": "source", "lifetime_seconds": 1,
                "position": {"row": 0, "col": 1}, "parameters": {"max_owned": 1, "on_owner_retire": "remove"}}]}, "timeline": []},
        {"id": "ability/token_pulse", "kind": "ability", "activation": {"mode": "manual", "parameters": {"auto_only": True}},
            "timeline": [{"at": 0, "effect": {"op": "modify_resource", "target": "source", "resource": "sp", "delta": 1}}]},
        {"id": "ability/trigger", "kind": "ability", "activation": {"mode": "manual"}, "timeline": [{"at": 0,
            "effect": {"op": "trigger_ability", "ability": "ability/token_pulse", "selector": "selector/owned"}}]},
    ]
    actor["abilities"] += ["ability/spawn", "ability/trigger"]
    data["selectors"].append({"id": "selector/owned", "kind": "selector", "region": {"type": "manhattan", "radius": 4},
        "filters": [{"tag": "token"}, {"owner": "source"}, {"state": "alive"}]})
    data["scenarioDraft"]["resources"] = {"dp": {"initial": 10, "capacity": 99}}
    return data


def tokens(sim):
    return [e["id"] for e in sim.session.world.entities() if "token" in e["tags"] and sim.ctx.alive(e["id"])]


def test_battle_dp_and_source_sp_are_paid_atomically_with_owned_spawn():
    sim = Engine.create(Compiler().compile(owned_model()))
    sim.ctx.abilities.start("source", "ability/spawn")
    assert sim.ctx.resources.current("system/battle", "dp") == 5
    assert sim.ctx.resources.current("source", "sp") == 4
    child = tokens(sim)[0]
    assert sim.ctx.get(child, ("ownership", "owner")) == sim.session.world.resolve("source")
    sim.session.advance(1)
    before = sim.checkpoint()
    with pytest.raises(ValueError, match="capacity"):
        sim.ctx.abilities.start("source", "ability/spawn")
    assert sim.checkpoint() == before


def test_insufficient_dp_does_not_spend_source_sp_or_spawn():
    data = owned_model()
    data["scenarioDraft"]["resources"]["dp"]["initial"] = 4
    sim = Engine.create(Compiler().compile(data))
    before = sim.checkpoint()
    with pytest.raises(ValueError, match="insufficient"):
        sim.ctx.abilities.start("source", "ability/spawn")
    assert sim.checkpoint() == before
    assert not tokens(sim)


def test_owner_selector_does_not_trigger_foreign_token_and_expires_before_input():
    data = owned_model()
    data["scenarioDraft"]["initialEntities"].append({"definition": "unit/source", "instanceAlias": "foreign", "position": {"row": 0, "col": 0}})
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.abilities.start("source", "ability/spawn")
    sim.ctx.abilities.start("foreign", "ability/spawn")
    children = tokens(sim)
    own = next(c for c in children if sim.ctx.get(c, ("ownership", "owner")) == sim.session.world.resolve("source"))
    other = next(c for c in children if c != own)
    sim.submit({"action": "skill", "source": "source", "ability": "ability/trigger"}, at=1)
    sim.submit({"action": "skill", "source": "source", "ability": "ability/trigger"}, at=30)
    sim.session.advance(31)
    assert sim.ctx.resources.current(own, "sp") == 6
    assert sim.ctx.resources.current(other, "sp") == 5
    assert not tokens(sim)


def test_parent_retirement_synchronously_removes_configured_owned_child():
    sim = Engine.create(Compiler().compile(owned_model()))
    sim.ctx.abilities.start("source", "ability/spawn")
    child = tokens(sim)[0]
    sim.ctx.lifecycle.retire("source", "withdrawn")
    assert not sim.ctx.alive(child)
    assert not tokens(sim)


@pytest.mark.parametrize("factory,ability", [(impact_model, "ability/probe"), (owned_model, "ability/spawn")])
def test_waiting_packets_and_owned_lifetimes_restore_and_replay(factory, ability):
    program = Compiler().compile(factory())
    sim = Engine.create(program)
    sim.submit({"action": "skill", "source": "source", "ability": ability})
    sim.session.advance(10)
    restored = Engine.restore(program, sim.checkpoint())
    sim.session.advance(25)
    restored.session.advance(25)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None
