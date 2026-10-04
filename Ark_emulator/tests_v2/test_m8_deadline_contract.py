"""Clock basis and replaceable quantization for actual checkpoint waits."""
import pytest
from ark_sim import Compiler, Engine
from ark_sim.content.repository import ContentError
from test_campaign_acceptance import scene


def model(kind=3, origins=None, seconds=1):
    data = scene(behavior="behavior/ground_melee", route={"motionMode": "WALK",
        "startPosition": {"row": 0, "col": 0}, "endPosition": {"row": 0, "col": 4},
        "checkpoints": [{"type": kind, "time": seconds, "position": {"row": 0, "col": 0}}]})
    if origins is not None:
        data["scenarioDraft"]["initialEntities"][0]["parameters"] = {"timing_origins": origins}
    return data


@pytest.mark.parametrize("kind,key", [(3, "fragment_start"), (4, "wave_start")])
def test_origin_wait_requires_real_captured_input_before_run(kind, key):
    with pytest.raises(ContentError, match=key):
        Compiler().compile(model(kind))


def test_wave_origin_is_preserved_and_wait_does_not_move_to_placeholder():
    sim = Engine.create(Compiler().compile(model(4, {"wave_start": 30})))
    sim.session.advance(60)
    assert sim.ctx.get("source", ("spatial", "position")) == {"row": 0, "col": 0}
    assert sim.ctx.get("source", ("spatial", "movement", "wait_until")) == 60
    sim.session.advance(1)
    assert sim.ctx.get("source", ("spatial", "position", "col")) > 0


def test_default_deadline_uses_replaced_time_quantizer():
    data = model(2, seconds=.05)
    data["rules"] = [{"id": "rule/floor_time", "kind": "calculation_rule", "contract": "time.quantize",
        "implementation": {"type": "expression", "expression": "floor(inputs.seconds/inputs.quantum)"}}]
    data["scenarioDraft"]["rules"] = {"time.quantize": "rule/floor_time"}
    sim = Engine.create(Compiler().compile(data))
    sim.session.advance(1)
    assert sim.ctx.get("source", ("spatial", "movement", "wait_until")) == 1
    sim.session.advance(1)
    assert sim.ctx.get("source", ("spatial", "position", "col")) > 0
