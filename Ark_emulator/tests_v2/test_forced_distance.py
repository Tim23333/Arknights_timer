"""Actual accepted motion, collision, DoT tails and merge accounting."""
from copy import deepcopy

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from test_campaign_acceptance import scene


def model(distance=1, duration=.1, buff_duration=.2, interval=2/30):
    data = scene()
    target = data["entities"][1]["components"]
    target["attributes"]["base"].update(max_hp=20000, mass_level=0)
    target["resources"]["hp"].update(initial=20000, capacity=20000)
    data["selectors"][0]["limit"] = 1
    data["abilities"][0]["timeline"] = [{"at": 0, "effects": [
        {"op": "push", "force": 3, "direction": "source_facing", "rules": {"movement.displacement": "rule/push"}},
        {"op": "apply_buff", "buff": "buff/distance"}]}]
    data["rules"] = [
        {"id": "rule/push", "kind": "calculation_rule", "contract": "movement.displacement",
         "parameters": {"distance": distance, "duration": duration}, "implementation": {"type": "expression",
         "expression": "{'distance':params.distance if inputs.force > inputs.mass else 0,'duration':params.duration if inputs.force > inputs.mass else 0}"}},
        {"id": "rule/distance_damage", "kind": "calculation_rule", "contract": "damage.pipeline", "implementation": {"type": "graph", "nodes": [
         {"id": "settlement", "expression": "{'accepted':True,'amount':inputs.effect.distance * inputs.effect.parameters.value / inputs.effect.parameters.per_distance,'allocations':[],'events':[]}"}], "output": "nodes.settlement"}},
    ]
    data["buffs"] = [{"id": "buff/distance", "kind": "buff", "duration_seconds": buff_duration, "interval_seconds": interval,
        "stacking": {"mode": "extend", "identity": ["definition", "target"], "max_stacks": 1},
        "movement_damage": {"effect": {"op": "damage", "damage_type": "true", "parameters": {"value": 1200, "per_distance": 1},
            "rules": {"damage.pipeline": "rule/distance_damage"}}}}]
    data["scenarioDraft"]["dependencies"] = ["buff/distance"]
    return data


def start(data):
    sim = Engine.create(Compiler().compile(data))
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"})
    return sim


def test_force_is_timed_and_distance_damage_uses_accepted_positions():
    sim = start(model())
    sim.session.advance(1)
    assert sim.ctx.get("target1", ("spatial", "position"))["col"] == 2
    sim.session.advance(6)
    assert sim.ctx.get("target1", ("spatial", "position"))["col"] == pytest.approx(3)
    assert sim.ctx.get("target1", ("spatial", "distance_travelled")) == pytest.approx(1)
    assert sim.ctx.resources.current("target1", "hp") == pytest.approx(18800)
    assert sim.ctx.resources.current("target2", "hp") == 20000
    assert not sim.ctx.get("target1", ("spatial", "forced_motion"))


def test_wall_clips_actual_path_and_only_clipped_length_deals_damage():
    data = model(distance=2)
    tiles = [{"tileKey": "tile_floor", "passableMask": 1} for _ in range(5)]
    tiles[3] = {"tileKey": "tile_wall", "passableMask": 0}
    data["scenarioDraft"]["map"]["tiles"] = tiles
    sim = start(data)
    sim.session.advance(7)
    position = sim.ctx.get("target1", ("spatial", "position"))
    assert position["col"] < 2.5 and position["col"] == pytest.approx(2.5)
    assert sim.ctx.get("target1", ("spatial", "distance_travelled")) == pytest.approx(.5)
    assert sim.ctx.resources.current("target1", "hp") == pytest.approx(19400)


def test_heavy_zero_force_is_no_motion_and_no_distance_damage():
    data = model()
    data["entities"][1]["components"]["attributes"]["base"]["mass_level"] = 4
    sim = start(data)
    sim.session.advance(7)
    assert sim.ctx.get("target1", ("spatial", "position"))["col"] == 2
    assert sim.ctx.resources.current("target1", "hp") == 20000
    assert not [e for e in sim.session.events if e["type"] == "damage.accepted"]


def test_expiry_flushes_tail_when_no_periodic_task_fits_lifetime():
    sim = start(model(distance=1, duration=1, buff_duration=.1, interval=.2))
    sim.session.advance(4)
    # Only forced steps at t1/t2 lie in the half-open [0,3) Buff lifetime.
    assert sim.ctx.resources.current("target1", "hp") == pytest.approx(19920)
    assert not sim.ctx.get("target1", ("buffs", "instances"))
    assert sim.ctx.get("target1", ("spatial", "forced_motion"))


def test_reapply_extend_flushes_old_source_tail_without_double_damage():
    data = model()
    data["scenarioDraft"]["initialEntities"].append({"definition": "unit/source", "instanceAlias": "second", "position": {"row": 0, "col": 0}})
    sim = Engine.create(Compiler().compile(data))
    target = sim.session.world.resolve("target1")
    sim.ctx.buffs.apply("source", target, "buff/distance")
    sim.ctx.movement.displace("source", target, {"position": {"row": 0, "col": 2.25}}, {})
    uid = sim.ctx.buffs.apply("second", target, "buff/distance")
    assert sim.ctx.resources.current(target, "hp") == 19700
    instances = sim.ctx.get(target, ("buffs", "instances"))
    assert len(instances) == 1 and instances[0]["stacks"] == 1 and instances[0]["expires_at"] == 12
    sim.ctx.movement.displace("source", target, {"position": {"row": 0, "col": 2.5}}, {})
    sim.ctx.buffs.remove(target, uid)
    assert sim.ctx.resources.current(target, "hp") == 19400
    accepted = [e for e in sim.session.events if e["type"] == "damage.accepted"]
    assert [e["payload"]["source"] for e in accepted] == [sim.session.world.resolve("source"), sim.session.world.resolve("second")]


def test_failed_step_rolls_back_actual_ledger_cursor_health_and_jobs():
    data = model()
    data["rules"][1]["implementation"]["nodes"][0]["expression"] = "{'accepted':True,'amount':1 / 0,'allocations':[],'events':[]}"
    sim = Engine.create(Compiler().compile(data))
    target = sim.session.world.resolve("target1")
    sim.ctx.buffs.apply("source", target, "buff/distance")
    sim.ctx.movement.displace("source", target, {"position": {"row": 0, "col": 2.25}}, {})
    before = sim.checkpoint()
    with pytest.raises(ValueError):
        sim.ctx.buffs.remove(target, "buff/distance")
    assert sim.checkpoint() == before


def test_forced_jobs_and_distance_cursor_restore_and_replay():
    program = Compiler().compile(model(duration=1, buff_duration=2))
    sim = Engine.create(program)
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"})
    sim.session.advance(10)
    restored = Engine.restore(program, sim.checkpoint())
    sim.session.advance(55)
    restored.session.advance(55)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None
