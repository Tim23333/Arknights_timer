"""Owned spawn uses normal deploy decisions without charging a second cost."""
from copy import deepcopy
import pytest
from ark_sim import Compiler, Engine
from test_impacts_and_owned import owned_model, tokens


def model(capacity=1, slots=2):
    data = owned_model()
    data["entities"][0]["components"]["deployable"] = {"terrain": "ground", "capacity": 1, "cooldown_seconds": 0}
    token = next(e for e in data["entities"] if e["id"] == "unit/token")
    token["components"]["deployable"] = {"terrain": "ground", "cost": 5,
        "cooldown_seconds": 2, "capacity": capacity}
    token["components"]["abilities"] = []
    ability = next(a for a in data["abilities"] if a["id"] == "ability/spawn")
    effect = ability["activation"]["on_start"][0]
    effect.pop("position")
    effect["parameters"]["position_from_payload"] = True
    data["scenarioDraft"]["parameters"] = {"deploy_capacity": slots}
    return data


def start(sim, position):
    return sim.ctx.abilities.start("source", "ability/spawn", event_payload={"position": position, "facing": "right"})


@pytest.mark.parametrize("failure", ["capacity", "occupied", "terrain"])
def test_invalid_owned_deployment_rolls_back_payment_and_world(failure):
    data = model(slots=1 if failure == "capacity" else 2)
    position = {"row": 0, "col": 0 if failure == "occupied" else 1}
    if failure == "terrain":
        rows, cols = data["scenarioDraft"]["map"]["rows"], data["scenarioDraft"]["map"]["cols"]
        data["scenarioDraft"]["map"]["tiles"] = [{"buildableType": 2} for _ in range(rows*cols)]
    sim = Engine.create(Compiler().compile(data))
    before = sim.session.checkpoint()
    with pytest.raises(ValueError, match={"terrain": "not_buildable"}.get(failure, failure)):
        start(sim, position)
    assert sim.session.checkpoint() == before


def test_zero_capacity_owned_token_works_at_full_slots_and_cools_down_on_expiry():
    sim = Engine.create(Compiler().compile(model(capacity=0, slots=1)))
    start(sim, {"row": 0, "col": 1})
    assert sim.ctx.resources.current("system/battle", "dp") == 5
    child = tokens(sim)[0]
    key = sim.ctx.get(child, ("deployable", "parameters", "history_key"))
    assert sim.ctx.state()["deployments"][key]["count"] == 1
    sim.session.advance(31)
    assert not sim.ctx.alive(child)
    before = sim.session.checkpoint()
    with pytest.raises(ValueError, match="on_cooldown"):
        start(sim, {"row": 0, "col": 1})
    assert sim.session.checkpoint() == before
