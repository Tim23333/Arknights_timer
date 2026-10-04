"""Captured time curves and owned-resource recovery gates are real state."""
from copy import deepcopy

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from test_campaign_acceptance import scene


def curve_model():
    data = scene()
    data["rules"] = [{"id": "rule/temporal", "kind": "calculation_rule", "extends": "rule/ark_attribute_layers",
        "implementation": {"type": "provider", "provider": "ark.attributes.time_layers"}}]
    data["entities"][0]["rules"] = {"attributes.effective": "rule/temporal"}
    data["buffs"] = [{"id": "buff/curve", "kind": "buff", "duration_seconds": 2,
        "modifiers": [{"attribute": "atk", "layer": "direct_ratio", "value": 2.6,
            "parameters": {"time_curve": {"type": "linear_remaining"}}}]}]
    data["scenarioDraft"]["dependencies"] = ["buff/curve"]
    return data


def test_curve_changes_live_stats_but_historical_snapshot_uses_capture_clock():
    sim = Engine.create(Compiler().compile(curve_model()))
    sim.ctx.buffs.apply("source", "source", "buff/curve")
    assert sim.ctx.attributes.value("source", "atk") == 36
    snapshot = sim.ctx.capture_view("source")
    sim.session.advance(30)
    assert sim.ctx.attributes.value("source", "atk") == 23
    assert sim.ctx.attributes.value("source", "atk", snapshot=snapshot) == 36
    sim.session.advance(31)
    assert sim.ctx.attributes.value("source", "atk") == 10
    assert sim.ctx.attributes.value("source", "atk", snapshot=snapshot) == 36


def test_delayed_at_cast_damage_keeps_sampled_curve_value_after_expiry():
    data = curve_model()
    data["abilities"][0]["timeline"][0] = {"at": 65,
        "effect": {"op": "damage", "damage_type": "true", "read_mode": {"source_attributes": "at_cast"}}}
    data["abilities"][0]["activation"]["on_start"] = [{"op": "apply_buff", "target": "source", "buff": "buff/curve"}]
    sim = Engine.create(Compiler().compile(data))
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"})
    sim.session.advance(66)
    assert sim.ctx.resources.current("target1", "hp") == 64
    assert sim.ctx.attributes.value("source", "atk") == 10


def gate_model():
    data = scene()
    source = data["entities"][0]["components"]
    source["resources"]["sp"] = {"initial": 5, "capacity": 20, "recovery_rate": 1,
        "recovery": {"mode": "continuous", "selector": "selector/owned", "empty_value": 0,
            "selector_interval_seconds": .1, "interrupt_when_empty": True}}
    source["abilities"].append("ability/own")
    data["entities"].append({"id": "unit/token", "kind": "entity", "tags": ["player", "token"], "components": {
        "attributes": {"base": {"max_hp": 100}}, "resources": {"hp": {"initial": 100, "capacity": 100, "role": "health"}}, "spatial": {}}})
    data["selectors"].append({"id": "selector/owned", "kind": "selector", "region": {"type": "all"},
        "filters": [{"tag": "token"}, {"owner": "source"}, {"state": "alive"}], "limit": 1})
    data["abilities"].append({"id": "ability/own", "kind": "ability", "activation": {"mode": "manual",
        "on_start": [{"op": "spawn", "definition": "unit/token", "owner": "source", "lifetime_seconds": .5}]}, "timeline": []})
    return data


def test_missing_owned_member_clears_and_stops_recovery_then_resumes_after_spawn():
    sim = Engine.create(Compiler().compile(gate_model()))
    sim.session.advance(1)
    assert sim.ctx.resources.current("source", "sp") == 0
    sim.submit({"action": "skill", "source": "source", "ability": "ability/own"})
    sim.session.advance(14)
    assert sim.ctx.resources.current("source", "sp") == pytest.approx(12/30)
    sim.session.advance(4)
    assert sim.ctx.resources.current("source", "sp") == 0


def test_gate_only_counts_tokens_owned_by_this_instance():
    data = gate_model()
    data["scenarioDraft"]["initialEntities"].append({"definition": "unit/source", "instanceAlias": "foreign", "position": {"row": 0, "col": 0}})
    sim = Engine.create(Compiler().compile(data))
    sim.submit({"action": "skill", "source": "foreign", "ability": "ability/own"})
    sim.session.advance(10)
    assert sim.ctx.resources.current("source", "sp") == 0
    assert sim.ctx.resources.current("foreign", "sp") > 5


def test_gate_and_curve_cache_restore_without_changing_replay():
    data = gate_model()
    program = Compiler().compile(data)
    sim = Engine.create(program)
    sim.submit({"action": "skill", "source": "source", "ability": "ability/own"}, at=1)
    sim.session.advance(8)
    restored = Engine.restore(program, sim.checkpoint())
    sim.session.advance(12)
    restored.session.advance(12)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None
