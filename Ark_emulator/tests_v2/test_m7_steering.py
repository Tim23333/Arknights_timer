"""Explicit acceleration/collision profile and scene seed behavior."""
import pytest
from ark_sim import Compiler, Engine
from test_campaign_acceptance import scene


def model():
    data = scene(behavior="behavior/ground_melee", route={
        "startPosition": {"row": 0, "col": 0}, "endPosition": {"row": 0, "col": 4}, "checkpoints": []})
    data["entities"][0]["components"]["spatial"]["steering"] = {
        "rule": "rule/steer", "parameters": {"response_factor": 8, "max_acceleration": 10}}
    data["rules"] = [{"id": "rule/steer", "kind": "calculation_rule", "contract": "movement.steering",
        "implementation": {"type": "provider", "provider": "ark.movement.steering_velocity"}}]
    return data


def test_acceleration_is_bounded_and_current_velocity_persists():
    sim = Engine.create(Compiler().compile(model()))
    inputs = {"origin": {"row": 0, "col": 0}, "destination": {"row": 0, "col": 2},
        "velocity": {"row": 0, "col": 0}, "speed": 2, "delta_seconds": .1,
        "parameters": {"response_factor": 8, "max_acceleration": 10}}
    first = sim.ctx.calc("movement.steering", inputs, source="source", rule_id="rule/steer")
    assert first["velocity"]["col"] == 1
    assert first["position"]["col"] == pytest.approx(.1)
    inputs.update(origin=first["position"], velocity=first["velocity"])
    second = sim.ctx.calc("movement.steering", inputs, source="source", rule_id="rule/steer")
    assert second["velocity"]["col"] == pytest.approx(1.8)
    assert second["position"]["col"] == pytest.approx(.28)


def test_live_steering_is_used_and_control_stop_clears_velocity():
    data = model()
    data["buffs"] = [{"id": "buff/stop", "kind": "buff", "control": {"move": False}}]
    data["entities"][0]["dependencies"] = ["buff/stop"]
    sim = Engine.create(Compiler().compile(data))
    sim.session.advance(1)
    assert sim.ctx.get("source", ("spatial", "position", "col")) == pytest.approx(8/900)
    sim.ctx.buffs.apply("source", "source", "buff/stop")
    before = sim.ctx.get("source", ("spatial", "position"))
    sim.session.advance(2)
    assert sim.ctx.get("source", ("spatial", "position")) == before
    assert sim.ctx.get("source", ("spatial", "velocity")) == {"row": 0, "col": 0}


def test_scene_seed_is_default_and_explicit_zero_overrides_it():
    data = model()
    data["scenarioDraft"]["seed"] = 953816614
    program = Compiler().compile(data)
    assert Engine.create(program).seed == 953816614
    assert Engine.create(program, seed=0).seed == 0


def test_steering_rule_can_be_replaced_without_native_provider():
    data = model()
    data["rules"][0]["implementation"] = {"type": "expression", "expression":
        "{'position':inputs.destination,'velocity':{'row':0,'col':0}}"}
    sim = Engine.create(Compiler().compile(data))
    sim.session.advance(1)
    # The steering destination is the current path waypoint, not a shortcut
    # over later checkpoints or the full route endpoint.
    assert sim.ctx.get("source", ("spatial", "position")) == {"row": 0, "col": 1}
