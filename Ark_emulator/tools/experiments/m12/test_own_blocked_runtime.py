"""Actual runtime relation preserves the explicit own-blocked selector exception."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT.parent / "unpack_work/campaign_m12_projection_candidate"
sys.path.insert(0, str(CANDIDATE))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent == CANDIDATE / "ark_sim"
from ark_sim import Compiler, Engine


def test_actual_own_blocked_outside_projected_range_is_explicit_override():
    for include, expected in ((True, 1), (False, 0)):
        p = json.loads((ROOT / "packages/campaign/mainline_models/level_main_00-10.m12_projection.json").read_bytes())
        selector = next(s for s in p["selectors"] if s["id"] == "selector/char_151_myrtle/normal_attack")
        selector["parameters"]["include_blocked"] = include
        p["scenarioDraft"].update(id="scenario/m12_own_blocked", map={"rows": 9, "cols": 12}, waves=[], scheduledEffects=[], objectives={},
            metadata={"stationary_enemy_override_fixture": True, "not_native_movement": True},
            initialEntities=[{"definition": "unit/char_151_myrtle", "instanceAlias": "myrtle", "position": {"row": 4, "col": 4}},
                {"definition": "unit/enemy_1000_gopro", "instanceAlias": "enemy", "position": {"row": 4.5, "col": 4},
                    "components": {"attributes": {"base": {"move_speed": 0}}},
                    "route": {"motionMode": "WALK", "endPosition": {"row": 4, "col": 6}}}])
        s = Engine.create(Compiler().compile(p)); s.advance(17)
        assert s.ctx.spatial.grid._cell(s.ctx.get("enemy", ("spatial", "position"))) == (5, 4)
        player = s.session.world.resolve("myrtle")
        assert s.ctx.spatial.blocked_by(s.session.world.resolve("enemy")) == player
        attacks = [e for e in s.session.events if e["type"] == "attack.accepted" and e["payload"]["source"] == player]
        assert len(attacks) == expected
