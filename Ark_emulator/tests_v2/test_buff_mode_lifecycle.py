"""Synchronous Buff removal keeps mode state and half-open lifetime aligned."""
from copy import deepcopy

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from test_campaign_acceptance import scene


def model():
    data = scene()
    actor = data["entities"][0]["components"]
    actor["resources"]["mode"] = {"initial": 0, "capacity": 1}
    data["buffs"] = [{"id": "buff/mode", "kind": "buff", "duration_seconds": 1,
        "on_remove": [{"op": "modify_resource", "target": "source", "resource": "mode", "value": 0}],
        "modifiers": [{"attribute": "atk", "layer": "flat", "value": 5}]}]
    data["abilities"][0]["activation"]["condition"] = "inputs.resources.mode.current == 0"
    data["abilities"].append({"id": "ability/start_mode", "kind": "ability",
        "activation": {"mode": "manual", "on_start": [
            {"op": "modify_resource", "target": "source", "resource": "mode", "value": 1},
            {"op": "apply_buff", "target": "source", "buff": "buff/mode"}]},
        "parameters": {"blocks_attacks": False}, "duration_seconds": 1, "timeline": []})
    actor["abilities"].append("ability/start_mode")
    return data


def test_expiry_resets_mode_before_command_without_losing_duration_end_effect():
    data = model()
    actor = data["entities"][0]["components"]
    actor["resources"]["dp_test"] = {"initial": 0, "capacity": 1}
    data["abilities"][1]["timeline"] = [{"at_seconds": 1,
        "effect": {"op": "modify_resource", "target": "source", "resource": "dp_test", "delta": 1}}]
    sim = Engine.create(Compiler().compile(data))
    sim.submit({"action": "skill", "source": "source", "ability": "ability/start_mode"})
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"}, at=30)
    sim.session.advance(31)
    assert sim.ctx.resources.current("target1", "hp") == 90
    assert sim.ctx.resources.current("source", "mode") == 0
    assert sim.ctx.resources.current("source", "dp_test") == 1


def test_explicit_remove_is_synchronous_and_repeat_remove_is_idempotent():
    sim = Engine.create(Compiler().compile(model()))
    sim.ctx.abilities.start("source", "ability/start_mode")
    assert sim.ctx.resources.current("source", "mode") == 1
    assert sim.ctx.buffs.remove("source", "buff/mode") == 1
    assert sim.ctx.resources.current("source", "mode") == 0
    assert sim.ctx.buffs.remove("source", "buff/mode") == 0


def test_removal_failure_rolls_back_buff_attributes_state_jobs_and_events():
    data = model()
    # A runtime fault reached through another target's resource is allowed to
    # demonstrate rollback without bypassing source-resource compile checks.
    data["buffs"][0]["on_remove"].append({"op": "modify_resource", "resource": "absent", "delta": 1})
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.abilities.start("source", "ability/start_mode")
    before = sim.checkpoint()
    with pytest.raises(ValueError):
        sim.ctx.buffs.remove("source", "buff/mode")
    assert sim.checkpoint() == before


def test_source_resource_missing_in_reachable_on_remove_rejects_compile():
    data = model()
    data["buffs"][0]["on_remove"][0]["resource"] = "absent"
    with pytest.raises(ValueError, match="undefined resource"):
        Compiler().compile(data)


@pytest.mark.parametrize("effect", [
    {"op": "modify_resource", "resource": "mode", "value": 0, "delta": 1},
    {"op": "modify_resource", "resource": "mode"},
])
def test_resource_assignment_cannot_mix_or_omit_write_modes(effect):
    data = model()
    data["buffs"][0]["on_remove"] = [effect]
    with pytest.raises(ValueError, match="exactly one"):
        Compiler().compile(data)


def test_mode_cleanup_preserves_checkpoint_and_replay():
    program = Compiler().compile(model())
    sim = Engine.create(program)
    sim.submit({"action": "skill", "source": "source", "ability": "ability/start_mode"})
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"}, at=30)
    sim.session.advance(15)
    restored = Engine.restore(program, sim.checkpoint())
    sim.session.advance(20)
    restored.session.advance(20)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None
