"""Independent edge cases for the real V2 event resource driver."""
from copy import deepcopy

import pytest

from ark_sim import Compiler, Engine
from ark_sim.content import CompileError
from ark_sim.kernel.session import ReactionBudgetExceeded
from test_event_resources import event_scene


def records(sim, event):
    return [e for e in sim.session.events if e["type"] == event]


def test_legacy_and_event_recovery_for_same_resource_cannot_charge_twice():
    data = event_scene(repeats=2)
    data["abilities"][0]["activation"]["parameters"] = {"sp_resource": "sp", "recovery_per_attack": 1}
    with pytest.raises(CompileError, match="(?i)legacy|event|recovery"):
        Compiler().compile(data)


@pytest.mark.parametrize("repeats", [1, 3])
def test_attack_witness_is_once_while_damage_witness_is_per_accepted_hit(repeats):
    data = event_scene(repeats=repeats, amount=7)
    sim = Engine.create(Compiler().compile(data))
    sim.advance(1)
    assert sim.ctx.resources.current("source", "sp") == 7
    assert len(records(sim, "attack.accepted")) == 1
    assert len(records(sim, "damage.accepted")) == 2 * repeats
    taken = Engine.create(Compiler().compile(event_scene("damage.accepted", "target", repeats=repeats, amount=3)))
    taken.advance(1)
    assert [taken.ctx.resources.current(t, "sp") for t in ("source", "target1", "target2")] == [0, 3 * repeats, 3 * repeats]


def test_any_event_driver_handles_unknown_external_alias_without_fabricating_entities():
    data = event_scene("external.signal", "any", amount=3)
    data["entities"][0]["components"]["abilities"] = []
    for unit in data["entities"]:
        unit["components"]["resources"]["sp"]["recovery"]["condition"] = "inputs.event.source == 'external/unknown'"
    sim = Engine.create(Compiler().compile(data))
    count = len(sim.session.world.entities())
    sim.ctx.emit("external.signal", {"source": "external/unknown", "target": "external/missing"})
    sim.advance(1)
    assert len(sim.session.world.entities()) == count
    assert [sim.ctx.resources.current(t, "sp") for t in ("source", "target1", "target2")] == [3, 3, 3]
    assert len(records(sim, "resource.event_recovered")) == 3


def test_rejected_event_resource_settlement_rolls_back_gain_and_recovery_witness():
    data = event_scene("external.signal", "source", amount=2)
    data["entities"][0]["components"]["abilities"] = []
    spec = data["entities"][0]["components"]["resources"]["sp"]
    spec.update(capacity=1, parameters={"mode": "reject"})
    sim = Engine.create(Compiler().compile(data))
    before = len(sim.session.events)
    sim.ctx.emit("external.signal", {"source": sim.session.world.resolve("source")})
    with pytest.raises(ValueError, match="resource update rejected"):
        sim.advance(1)
    assert sim.ctx.resources.current("source", "sp") == 0
    assert not records(sim, "resource.event_recovered")
    assert not [e for e in sim.session.events[before:] if e["type"] == "resource.changed" and e["payload"]["resource"] == "sp"]


def self_driven(pause):
    data = event_scene("resource.event_recovered", "source", amount=1)
    data["entities"][0]["components"]["abilities"] = []
    data["rulesets"] = [{"id": "ruleset/review_budget", "kind": "ruleset", "extends": "ruleset/ark_standard", "reaction_budget": 200}]
    data["scenarioDraft"]["ruleset"] = "ruleset/review_budget"
    spec = data["entities"][0]["components"]["resources"]["sp"]
    spec.update(capacity=2, parameters={"pause_at_full": pause})
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.emit("resource.event_recovered", {"source": sim.session.world.resolve("source")})
    return sim


def test_self_event_chain_stops_at_full_when_explicitly_paused():
    sim = self_driven(True)
    sim.advance(1)
    assert sim.ctx.resources.current("source", "sp") == 2
    actual = [e for e in records(sim, "resource.event_recovered") if e["payload"].get("trigger")]
    assert [e["payload"]["delta"] for e in actual] == [1, 1]


def test_unbounded_self_event_chain_fails_with_reaction_budget_instead_of_hanging():
    sim = self_driven(False)
    with pytest.raises(ReactionBudgetExceeded, match="budget.*exhausted"):
        sim.advance(1)
    assert sim.ctx.resources.current("source", "sp") == 2


def test_kill_event_credits_attacker_once_for_each_dead_enemy_not_each_damage_repeat():
    data = event_scene("combat.kill", "source", repeats=3, amount=4)
    enemy = data["entities"][1]["components"]
    enemy["resources"]["hp"]["initial"] = 10
    enemy["lifecycle"] = {"policy": "policy/ark_lifecycle"}
    sim = Engine.create(Compiler().compile(data))
    sim.advance(1)
    kills = records(sim, "combat.kill")
    assert len(kills) == 2  # Two targets share this definition; each dies once.
    assert {e["payload"]["source"] for e in kills} == {sim.session.world.resolve("source")}
    assert {e["payload"]["target"] for e in kills} == {sim.session.world.resolve("target1"), sim.session.world.resolve("target2")}
    assert sim.ctx.resources.current("source", "sp") == 8
    assert [sim.ctx.resources.current(t, "sp") for t in ("target1", "target2")] == [0, 0]


@pytest.mark.parametrize("reason", ["withdrawn", "exited"])
def test_noncombat_retirement_does_not_emit_kill_or_credit_attacker(reason):
    data = event_scene("combat.kill", "source", repeats=1)
    data["entities"][0]["components"]["abilities"] = []
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.lifecycle.retire("target1", reason)
    sim.advance(1)
    assert not records(sim, "combat.kill")
    assert sim.ctx.resources.current("source", "sp") == 0


@pytest.mark.parametrize("event", ["attack.accepted", "damage.accepted", "combat.kill"])
def test_manual_zero_duration_finish_does_not_unfreeze_emit_time_recipients(event):
    data = event_scene(event, "source", repeats=2)
    data["abilities"][0]["activation"] = {"mode": "manual", "parameters": {"counts_as_attack": True}}
    data["entities"][0]["components"]["resources"]["sp"]["parameters"] = {
        "freeze_while_cast": True, "freeze_cast_modes": ["manual"]}
    if event == "combat.kill":
        data["entities"][1]["components"]["resources"]["hp"]["initial"] = 10
        data["entities"][1]["components"]["lifecycle"] = {"policy": "policy/ark_lifecycle"}
    sim = Engine.create(Compiler().compile(data))
    sim.submit({"action": "activate_ability", "source": "source", "ability": "ability/probe"})
    sim.advance(1)
    assert records(sim, event)
    assert not sim.ctx.get("source", ("runtime", "casts"))
    assert sim.ctx.resources.current("source", "sp") == 0
