"""Synchronous mode entry and control Buffs affect the actual executor."""
from copy import deepcopy

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from ark_sim.tools.compare import first_difference
from test_campaign_acceptance import scene


def start_scene():
    data = scene(mode="automatic_attack")
    data["buffs"] = [{"id": "buff/mode", "kind": "buff", "duration_seconds": 1,
        "modifiers": [{"attribute": "atk", "layer": "flat", "value": 10}]}]
    data["abilities"].insert(0, {"id": "ability/mode", "kind": "ability",
        "activation": {"mode": "manual", "parameters": {"auto_when_ready": True, "blocks_attacks": False},
            "on_start": [{"op": "apply_buff", "target": "self", "buff": "buff/mode"}]},
        "duration_seconds": 1, "timeline": []})
    data["entities"][0]["components"]["abilities"].insert(0, "ability/mode")
    return data


def test_same_tick_automatic_attack_samples_synchronous_mode_entry():
    sim = Engine.create(Compiler().compile(start_scene()))
    sim.advance(1)
    assert sim.ctx.resources.current("target1", "hp") == 80
    assert sim.ctx.resources.current("target2", "hp") == 80
    assert len([e for e in sim.session.events if e["type"] == "buff.applied"]) == 1


def test_on_start_failure_rolls_back_payment_buff_tasks_and_events():
    data = start_scene()
    data["rules"] = [{"id": "rule/negative_duration", "kind": "calculation_rule", "contract": "buff.duration",
                     "implementation": {"type": "expression", "expression": "-1"}}]
    data["buffs"][0]["duration_rule"] = "rule/negative_duration"
    skill = data["abilities"][0]
    skill["activation"]["costs"] = [{"resource": "sp", "amount": 2}]
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = 5
    sim = Engine.create(Compiler().compile(data))
    before = sim.session.checkpoint()
    with pytest.raises(ValueError, match="duration"):
        sim.ctx.abilities.start("source", "ability/mode")
    assert sim.session.checkpoint() == before


def control_scene(flags):
    data = scene(mode="automatic_attack", route={"startPosition": {"row": 0, "col": 0},
        "endPosition": {"row": 0, "col": 4}, "checkpoints": []})
    data["buffs"] = [{"id": "buff/control", "kind": "buff", "duration_seconds": 1, "control": flags}]
    data["scenarioDraft"]["dependencies"] = ["buff/control"]
    return data


def test_control_stops_movement_and_attack_and_expires_on_half_open_boundary():
    sim = Engine.create(Compiler().compile(control_scene({"move": False, "attack": False, "abilities": False})))
    sim.ctx.buffs.apply("source", "source", "buff/control")
    sim.advance(30)
    assert sim.ctx.get("source", ("spatial", "position")) == {"row": 0, "col": 0}
    assert sim.ctx.resources.current("target1", "hp") == 100
    sim.advance(1)
    assert sim.ctx.get("source", ("spatial", "position"))["col"] > 0
    assert sim.ctx.resources.current("target1", "hp") == 90


def test_control_rejects_manual_start_and_interrupts_existing_cast():
    data = control_scene({"abilities": False, "interrupt": True})
    data["abilities"][0]["activation"]["mode"] = "manual"
    data["abilities"][0]["timeline"][0]["at"] = 15
    second = deepcopy(data["abilities"][0])
    second["id"] = "ability/other"
    data["abilities"].append(second)
    data["entities"][0]["components"]["abilities"].append(second["id"])
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.abilities.start("source", "ability/probe")
    sim.ctx.buffs.apply("source", "source", "buff/control")
    assert not sim.ctx.get("source", ("runtime", "casts"))
    with pytest.raises(ValueError, match="controlled"):
        sim.ctx.abilities.start("source", "ability/other")
    sim.advance(16)
    assert sim.ctx.resources.current("target1", "hp") == 100


def test_new_mode_and_control_state_restore_and_replay_exactly():
    program = Compiler().compile(start_scene())
    sim = Engine.create(program, seed=123)
    sim.advance(1)
    restored = Engine.restore(program, sim.checkpoint())
    sim.advance(2)
    restored.advance(2)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None


def test_control_flags_require_booleans():
    with pytest.raises(ValueError, match="booleans"):
        Compiler().compile(control_scene({"move": 0}))
