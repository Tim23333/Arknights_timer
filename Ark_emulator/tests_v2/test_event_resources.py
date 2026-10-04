"""Event-driven resource recovery distinguishes attacks from each damage hit."""
from copy import deepcopy

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from ark_sim.tools.compare import first_difference
from test_campaign_acceptance import scene


def event_scene(event="attack.accepted", owner_role="source", repeats=2, amount=1):
    data = scene(mode="automatic_attack", repeats=repeats)
    rule = {"id": "rule/event_gain", "kind": "calculation_rule", "contract": "resource.recovery",
        "implementation": {"type": "expression", "expression": "inputs.current + inputs.parameters.amount"}}
    data["rules"] = [rule]
    for entity in data["entities"]:
        entity["components"]["resources"]["sp"] = {"initial": 0, "capacity": 100,
            "recovery_rule": rule["id"], "recovery": {"mode": "event", "event": event,
                "owner_role": owner_role, "amount": amount}}
    return data


def test_two_targets_two_hits_charge_source_once_per_attack():
    sim = Engine.create(Compiler().compile(event_scene()))
    sim.advance(1)
    assert sim.ctx.resources.current("source", "sp") == 1
    assert sim.ctx.resources.current("target1", "sp") == 0
    assert len([e for e in sim.session.events if e["type"] == "damage.accepted"]) == 4
    assert len([e for e in sim.session.events if e["type"] == "attack.accepted"]) == 1


def test_taken_damage_charges_each_target_for_each_accepted_hit():
    sim = Engine.create(Compiler().compile(event_scene("damage.accepted", "target")))
    sim.advance(1)
    assert [sim.ctx.resources.current(alias, "sp") for alias in ("source", "target1", "target2")] == [0, 2, 2]


def test_skill_freeze_is_sampled_before_same_tick_cast_finish():
    data = event_scene()
    ability = data["abilities"][0]
    ability["activation"].update(mode="manual", parameters={"counts_as_attack": True})
    spec = data["entities"][0]["components"]["resources"]["sp"]
    spec["parameters"] = {"freeze_while_cast": True, "freeze_cast_modes": ["manual"]}
    sim = Engine.create(Compiler().compile(data))
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"})
    sim.advance(1)
    assert not sim.ctx.get("source", ("runtime", "casts"))
    assert sim.ctx.resources.current("source", "sp") == 0


def test_event_rule_can_cool_instead_of_assuming_positive_sp():
    data = event_scene(amount=3)
    data["rules"][0]["implementation"]["expression"] = "inputs.current - inputs.parameters.amount"
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = 10
    sim = Engine.create(Compiler().compile(data))
    sim.advance(1)
    assert sim.ctx.resources.current("source", "sp") == 7


def test_event_recovery_with_checkpoint_and_replay_has_identical_results():
    program = Compiler().compile(event_scene())
    sim = Engine.create(program, seed=123)
    sim.advance(1)
    checkpoint = sim.checkpoint()
    restored = Engine.restore(program, checkpoint)
    sim.advance(2)
    restored.advance(2)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None


def test_event_resource_does_not_recover_on_clock_ticks_alone():
    data = event_scene()
    data["entities"][0]["components"]["abilities"] = []
    sim = Engine.create(Compiler().compile(data))
    sim.advance(30)
    assert sim.ctx.resources.current("source", "sp") == 0


@pytest.mark.parametrize("change", [{"event": ""}, {"owner_role": "unknown"}, {"amount": True}, {"interval_seconds": 1}])
def test_invalid_event_driver_is_rejected_before_runtime(change):
    data = event_scene()
    data["entities"][0]["components"]["resources"]["sp"]["recovery"].update(change)
    with pytest.raises(ValueError):
        Compiler().compile(data)


def test_event_driver_requires_an_explicit_formula():
    data = event_scene()
    del data["entities"][0]["components"]["resources"]["sp"]["recovery_rule"]
    with pytest.raises(ValueError, match="explicit"):
        Compiler().compile(data)
