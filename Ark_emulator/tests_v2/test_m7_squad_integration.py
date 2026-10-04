"""Real selected melee recipes include their own blocked corner target."""
from copy import deepcopy
from ark_sim import Compiler, Engine
from tools.build_m7_mainline_model import build


def run(include_blocked):
    data = build()
    actor = next(e for e in data["entities"] if e["id"] == "unit/char_222_bpipe")
    ability = next(a for a in data["abilities"] if a["id"] == "ability/campaign_bpipe_normal")
    selector = next(s for s in data["selectors"] if s["id"] == ability["selector"])
    selector["parameters"]["include_blocked"] = include_blocked
    scene = data["scenarioDraft"]
    scene.update(waves=[], scheduledEffects=[], objectives={}, commands=[], initialEntities=[
        {"definition": actor["id"], "instanceAlias": "bagpipe", "position": {"row": 4, "col": 10}, "facing": "left"},
        {"definition": "unit/enemy_1000_gopro", "instanceAlias": "enemy", "position": {"row": 5, "col": 10},
         "route": {"startPosition": {"row": 5, "col": 10}, "endPosition": {"row": 4, "col": 12},
                   "checkpoints": [], "motionMode": "WALK", "allowDiagonalMove": True}}])
    sim = Engine.create(Compiler().compile(data), seed=123)
    sim.session.advance(25)
    return sim


def test_real_corner_block_is_attacked_only_with_own_blocked_inclusion():
    old = run(False)
    assert old.ctx.spatial.blocked_by("enemy") == old.session.world.resolve("bagpipe")
    assert old.ctx.resources.current("enemy", "hp") == 820
    current = run(True)
    assert current.ctx.resources.current("enemy", "hp") < 820
    assert any(e["type"] == "damage.accepted" and e["payload"]["source"] == current.session.world.resolve("bagpipe")
               for e in current.session.events)
