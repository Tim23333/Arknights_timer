"""Per-packet pure hooks, explicit random streams and complete rollback."""
from copy import deepcopy

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from test_campaign_acceptance import scene


def hook_model():
    data = scene()
    data["selectors"][0]["limit"] = 1
    data["selectors"].append({"id": "selector/extra", "kind": "selector", "region": {"type": "all"},
        "filters": [{"tag": "enemy"}, {"state": "alive"}], "limit": 1, "parameters": {"exclude_primary": True}})
    data["buffs"] = [{"id": "buff/crit", "kind": "buff", "damage_hooks": [
        {"phase": "before", "rule": "rule/crit", "samples": {"stream": "imp", "count": 1}}]}]
    data["entities"][0]["components"]["buffs"] = {"initial": ["buff/crit"]}
    data["rules"] = [{"id": "rule/crit", "kind": "calculation_rule", "contract": "damage.request",
        "dependencies": ["selector/extra"], "implementation": {"type": "graph", "nodes": [
            {"id": "request", "expression": "{'accepted':True,'effect':{'attack':inputs.effect.attack,'scale':1.3,'additions':0,'defense':0,'resistance':0,'damage_type':'true'},'effects':[{'op':'damage','damage_type':'true','scale':1.3,'selector':'selector/extra'}]}"}], "output": "nodes.request"}}]
    return data


def test_source_hook_scales_primary_and_excludes_primary_from_nonrecursive_extra():
    sim = Engine.create(Compiler().compile(hook_model()), seed=42)
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"})
    sim.session.advance(1)
    assert [sim.ctx.resources.current(t, "hp") for t in ("target1", "target2")] == [87, 87]
    assert len(sim.session.random.samples) == 1
    assert len([e for e in sim.session.events if e["type"] == "damage.accepted"]) == 2


def test_receiver_hook_cancels_packet_without_binding_incoming_effect():
    data = scene()
    data["buffs"] = [{"id": "buff/dodge", "kind": "buff", "damage_hooks": [{"phase": "after", "rule": "rule/dodge",
        "condition": "inputs.effect.damage_type == 'true'", "samples": {"stream": "imp", "count": 1}}]}]
    data["entities"][1]["components"]["buffs"] = {"initial": ["buff/dodge"]}
    data["rules"] = [{"id": "rule/dodge", "kind": "calculation_rule", "contract": "damage.pipeline", "implementation": {
        "type": "graph", "nodes": [{"id": "result", "expression": "{'accepted':False,'amount':0,'allocations':[],'events':[]}"}], "output": "nodes.result"}}]
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.effects.execute("source", [sim.session.world.resolve("target1")], {"op": "damage", "damage_type": "true"})
    assert sim.ctx.resources.current("target1", "hp") == 100
    assert len(sim.session.random.samples) == 1
    assert not [e for e in sim.session.events if e["type"] == "damage.accepted"]


def test_failed_deferred_effect_rolls_back_health_random_stream_queue_and_events():
    data = hook_model()
    expression = data["rules"][0]["implementation"]["nodes"][0]["expression"]
    data["rules"][0]["implementation"]["nodes"][0]["expression"] = expression.replace("'selector':'selector/extra'", "'selector':'selector/extra','on_success':[{'op':'modify_resource','resource':'absent','delta':1}]")
    sim = Engine.create(Compiler().compile(data))
    before = sim.checkpoint()
    with pytest.raises(ValueError):
        sim.ctx.effects.execute("source", [sim.session.world.resolve("target1")], {"op": "damage", "damage_type": "true"})
    assert sim.checkpoint() == before


def test_random_resource_uses_float_sample_and_not_an_untraced_second_draw():
    data = scene()
    data["rules"] = [{"id": "rule/random_sp", "kind": "calculation_rule", "contract": "resource.recovery",
        "implementation": {"type": "expression", "expression": "inputs.current + 7 + 9*inputs.parameters.random_sample"}}]
    data["abilities"][0].pop("selector")
    data["abilities"][0]["timeline"] = [{"at": 0, "effect": {"op": "random", "stream": "imp", "probability": 1,
        "on_success": [{"op": "modify_resource", "target": "source", "resource": "sp", "amount_rule": "rule/random_sp"}]}}]
    sim = Engine.create(Compiler().compile(data), seed=55)
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"})
    sim.session.advance(1)
    samples = sim.session.random.samples
    assert len(samples) == 1
    assert sim.ctx.resources.current("source", "sp") == pytest.approx(7+9*samples[0]["value"])


def test_random_target_selection_empty_consumes_none_and_samples_without_replacement():
    data = scene()
    data["selectors"][0]["ordering"] = "random"
    data["selectors"][0]["parameters"] = {"random_stream": "imp"}
    sim = Engine.create(Compiler().compile(data))
    targets = sim.ctx.spatial.select("source", "selector/probe")
    assert len(targets) == 2 and len(set(targets)) == 2 and len(sim.session.random.samples) == 2
    sim.ctx.lifecycle.retire("target1", "dead")
    sim.ctx.lifecycle.retire("target2", "dead")
    assert sim.ctx.spatial.select("source", "selector/probe") == []
    assert len(sim.session.random.samples) == 2


def test_random_hooks_restore_and_replay_identical_consumption():
    program = Compiler().compile(hook_model())
    sim = Engine.create(program, seed=99)
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"})
    sim.session.advance(1)
    restored = Engine.restore(program, sim.checkpoint())
    sim.session.advance(2)
    restored.session.advance(2)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None
