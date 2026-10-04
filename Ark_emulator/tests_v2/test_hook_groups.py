"""Receiver hook arbitration and health-only allocation scaling."""
import pytest

from ark_sim import Compiler, Engine
from test_campaign_acceptance import scene


def model():
    data = scene()
    target = data["entities"][1]["components"]
    target["attributes"]["base"]["factor"] = 1.2
    target["resources"]["shield"] = {"initial": 2, "capacity": 2}
    target["buffs"] = {"initial": ["buff/one", "buff/two"]}
    data["buffs"] = [{"id": "buff/"+name, "kind": "buff", "damage_hooks": [{"phase": "after", "rule": "rule/scale",
        "group": "incoming_scale", "priority": index}]} for index, name in enumerate(["one", "two"])]
    data["rules"] = [{"id": "rule/scale", "kind": "calculation_rule", "contract": "damage.pipeline",
        "metadata": {"input_bindings": {"multiplier": {"entity": "target", "attribute": "factor"}}},
        "implementation": {"type": "provider", "provider": "ark.damage.settlement_scale"}},
        {"id": "rule/base", "kind": "calculation_rule", "contract": "damage.pipeline", "implementation": {"type": "graph",
         "nodes": [{"id": "value", "expression": "{'accepted':True,'amount':10,'allocations':[{'target':'target','resource':'shield','delta':-1},{'target':'target','resource':'hp','delta':-10}],'events':[]}"}], "output": "nodes.value"}}]
    data["abilities"][0]["timeline"][0]["effect"]["rules"] = {"damage.pipeline": "rule/base"}
    return data


def test_same_hook_group_scales_only_once_and_keeps_shield_charge_cost():
    sim = Engine.create(Compiler().compile(model()))
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"})
    sim.session.advance(1)
    assert sim.ctx.resources.current("target1", "hp") == 88
    assert sim.ctx.resources.current("target1", "shield") == 1
    assert sim.ctx.state()["damage_dealt"] == 24


def test_ineligible_higher_priority_does_not_occupy_group_or_sample():
    data = model()
    data["buffs"][1]["damage_hooks"][0].update(condition="'buff/slow' in context.target_buff_ids", samples={"stream": "imp", "count": 1})
    sim = Engine.create(Compiler().compile(data))
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"})
    sim.session.advance(1)
    assert sim.ctx.resources.current("target1", "hp") == 88
    assert not sim.session.random.samples


def test_invalid_multiplier_rolls_back_health_and_shield_allocations():
    data = model()
    data["entities"][1]["components"]["attributes"]["base"]["factor"] = -1
    sim = Engine.create(Compiler().compile(data))
    before = sim.checkpoint()
    with pytest.raises(ValueError, match="nonnegative"):
        sim.ctx.effects.execute("source", [sim.session.world.resolve("target1")], {"op": "damage", "rules": {"damage.pipeline": "rule/base"}})
    assert sim.checkpoint() == before
