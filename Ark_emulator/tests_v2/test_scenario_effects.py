"""Scheduled scenario effects are observable, validated and replayable."""
from copy import deepcopy
import pytest
from ark_sim import Compiler, Engine
from ark_sim.content.repository import ContentError
from ark_sim.tools.replay import replay
from test_campaign_acceptance import scene


def test_input_lock_rejects_command_and_unlock_restores_execution():
    data = scene()
    data["scenarioDraft"]["scheduledEffects"] = [
        {"at": 0, "effect": {"op": "input_lock", "target": "battle", "parameters": {"key": "story", "enabled": True}}},
        {"at": 2, "effect": {"op": "input_lock", "target": "battle", "parameters": {"key": "story", "enabled": False}}}]
    sim = Engine.create(Compiler().compile(data))
    for tick in (0, 2):
        sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"}, at=tick)
    sim.session.advance(3)
    assert [e["type"] for e in sim.session.events if e["type"].startswith("command.")] == ["command.rejected", "command.accepted"]
    assert sim.ctx.resources.current("target1", "hp") == 90
    assert sim.ctx.state()["input_locks"] == []
    restored = replay(sim.program, sim.export_replay())
    assert restored.session.checkpoint() == sim.session.checkpoint()


def test_scheduled_effect_dependency_and_timing_validate_before_execution():
    data = scene()
    data["scenarioDraft"]["scheduledEffects"] = [{"at": 0, "effect": {
        "op": "apply_buff", "target": "battle", "buff": "buff/missing"}}]
    with pytest.raises(ContentError, match="Missing reference"):
        Compiler().compile(data)
    data["scenarioDraft"]["scheduledEffects"][0].update(at_seconds=0)
    with pytest.raises(ContentError, match="mutually exclusive"):
        Compiler().compile(data)
