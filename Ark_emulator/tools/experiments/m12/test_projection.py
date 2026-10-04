"""M12 cell-projection counterexamples in a new explicit candidate root."""
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT.parent / "unpack_work/campaign_m12_projection_candidate"
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(CANDIDATE))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent == CANDIDATE / "ark_sim"
from ark_sim import Compiler, Engine
from ark_sim.domains.spatial import GridTopology, project_cell
from ark_sim.presets.providers import selector_grid
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay


def selector_input(source=(4, 4), target=(4.5, 5), facing="right", region=None, blocked=None):
    return {"source": {"id": 2, "components": {"spatial": {"position": {"row": source[0], "col": source[1]}, "facing": facing}}},
        "candidates": [{"id": 3, "components": {"spatial": {"position": {"row": target[0], "col": target[1]}},
            "runtime": {"blocked_by": blocked}}}], "region": region or {"type": "grid_offsets", "offsets": [[0, 0], [0, 1]]}}


def scene():
    p = json.loads((ROOT / "packages/campaign/mainline_models/level_main_00-10.m11_block_sync.json").read_bytes())
    p["scenarioDraft"].update(id="scenario/m12_projection", map={"rows": 9, "cols": 12}, waves=[], scheduledEffects=[], objectives={},
        initialEntities=[{"definition": "unit/char_151_myrtle", "instanceAlias": "myrtle", "position": {"row": 4, "col": 4}},
            {"definition": "unit/enemy_1000_gopro", "instanceAlias": "enemy", "position": {"row": 4.5, "col": 5}}])
    return p


def make(p): return Engine.create(Compiler().compile(p), seed=1201)


@pytest.mark.parametrize("row,expected", [(4.5, 5), (5.5, 6), (-.5, 0), (-1.5, -1), (.5, 1), (3.5, 4)])
def test_exact_half_up_projection_not_bankers_round(row, expected):
    assert project_cell({"row": row, "col": row}) == (expected, expected)


def test_source_half_ties_and_candidate_half_ties_share_same_cell():
    for source, target, hit in [((4, 4), (4.5, 5), False), ((4, 4), (5.5, 5), False),
            ((4.5, 4), (5, 5), True), ((5.5, 4), (6, 5), True), ((4.5, 4), (4, 5), False)]:
        assert selector_grid(selector_input(source, target), {}, {}) == ([3] if hit else [])


@pytest.mark.parametrize("facing,target", [("right", (5, 5)), ("up", (4, 4)), ("left", (5, 3)), ("down", (6, 4))])
def test_rotated_footprint_uses_source_half_up_anchor(facing, target):
    region = {"type": "grid_offsets", "offsets": [[0, 1]]}
    assert selector_grid(selector_input((4.5, 4), target, facing, region), {}, {}) == [3]
    assert selector_grid(selector_input((4.5, 4), (4, 5), facing, region), {}, {}) == []


def test_negative_margin_and_positive_border_match_compiler_and_runtime():
    grid = GridTopology({"rows": 3, "cols": 4})
    assert grid._cell({"row": -.5, "col": -.5}) == (0, 0)
    assert grid._cell({"row": 2.499, "col": 3.499}) == (2, 3)
    for pos in ({"row": -.50001, "col": 0}, {"row": 2.5, "col": 0}, {"row": 0, "col": 3.5}):
        with pytest.raises(ValueError, match="outside map"): grid._cell(pos)
    assert selector_grid(selector_input((0, 0), (-.5, -.5), region={"type": "grid_offsets", "offsets": [[0, 0]]}), {}, {}) == [3]
    for bad in (True, float("inf"), float("nan")):
        with pytest.raises(ValueError, match="finite"): project_cell({"row": bad, "col": 0})


def test_circle_radius_and_manhattan_preserve_continuous_distance():
    inputs = selector_input((4, 4), (4.5, 4))
    for kind in ("circle", "radius", "manhattan"):
        inputs["region"] = {"type": kind, "radius": .5}
        assert selector_grid(inputs, {}, {}) == [3] # cell distance1 would wrongly reject
        inputs["region"]["radius"] = .499
        assert selector_grid(inputs, {}, {}) == []


def test_own_blocked_exception_is_explicit_and_not_foreign_blocker():
    inputs = selector_input((4, 4), (5.5, 4), blocked=2)
    assert selector_grid(inputs, {}, {}) == []
    assert selector_grid(inputs, {"include_blocked": True}, {}) == [3]
    inputs["candidates"][0]["components"]["runtime"]["blocked_by"] = 4
    assert selector_grid(inputs, {"include_blocked": True}, {}) == []


def test_canonical_Myrtle_original_half_tie_counterexample():
    for row in (4.5, 5.5):
        p = scene(); p["scenarioDraft"]["initialEntities"][1]["position"]["row"] = row
        s = make(p); assert s.ctx.spatial.grid._cell({"row": row, "col": 5}) == (math.floor(row+.5), 5)
        s.advance(16)
        assert not [e for e in s.session.events if e["type"] == "attack.accepted"]


def test_recorded_move_commands_cross_tie_complete_checkpoint_and_replay():
    p = scene(); aid = "ability/m12_probe_move"
    p["abilities"].append({"id": aid, "kind": "ability", "activation": {"mode": "manual", "on_start": [
        {"op": "move", "target": "source", "position": {"row": 4.4, "col": 5}}]}, "parameters": {"blocks_attacks": False}, "timeline": []})
    enemy = next(e for e in p["entities"] if e["id"] == "unit/enemy_1000_gopro")
    enemy["components"].setdefault("abilities", []).append(aid)
    s = make(p); s.advance(1)
    assert not [e for e in s.session.events if e["type"] == "ability.started"]
    s.submit({"action": "skill", "source": "enemy", "ability": aid}); s.advance(10)
    restored = Engine.restore(s.program, s.checkpoint()); s.advance(10); restored.advance(10)
    attacks = [e for e in s.session.events if e["type"] == "attack.accepted"]
    assert len(attacks) == 1 and attacks[0]["time"] == 16
    assert first_difference(s.snapshot(), restored.snapshot()) is None
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None


def test_block_footprint_and_route_start_share_half_up_cell():
    p = json.loads((ROOT / "tools/experiments/m11/capacity.fixture.json").read_bytes())
    p["scenarioDraft"]["initialEntities"] = p["scenarioDraft"]["initialEntities"][:2]
    player, enemy = p["scenarioDraft"]["initialEntities"]
    player["position"] = {"row": 2, "col": 2}
    enemy["position"] = {"row": 2.5, "col": 2}; enemy["route"]["endPosition"] = {"row": 3, "col": 6}
    s = make(p); s.advance(1)
    assert s.ctx.spatial.grid._cell(enemy["position"]) == (3, 2)
    assert s.ctx.spatial.blocked_by(s.session.world.resolve("enemy0")) is None
    player["position"] = {"row": 2.5, "col": 2}
    enemy["position"] = {"row": 3, "col": 2}
    s = make(p); s.advance(1)
    assert s.ctx.spatial.blocked_by(s.session.world.resolve("enemy0")) == s.session.world.resolve("blocker")


def test_runtime_displacement_rejects_same_upper_border_as_compiler():
    p = scene(); aid = "ability/m12_probe_outside"
    p["abilities"].append({"id": aid, "kind": "ability", "activation": {"mode": "manual", "on_start": [
        {"op": "move", "target": "source", "position": {"row": 8.5, "col": 5}}]}, "timeline": []})
    next(e for e in p["entities"] if e["id"] == "unit/enemy_1000_gopro")["components"]["abilities"].append(aid)
    s = make(p); before = s.checkpoint()
    with pytest.raises(ValueError, match="outside map"): s.ctx.abilities.start("enemy", aid)
    assert first_difference(before, s.checkpoint()) is None
    p["scenarioDraft"]["initialEntities"][1]["position"] = {"row": 8.5, "col": 5}
    with pytest.raises(ValueError, match="outside declared map"): Compiler().compile(p)


def alternate_selector(inputs, params, context):
    return [e["id"] for e in inputs["candidates"]]


def test_entire_selector_provider_remains_user_replaceable():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    providers = dict(BUILTIN_PROVIDERS); providers["test/m12_selector"] = alternate_selector
    p = scene(); selector = next(s for s in p["selectors"] if s["id"] == "selector/char_151_myrtle/normal_attack")
    selector["provider"] = "test/m12_selector"
    s = Engine.create(Compiler(providers=providers).compile(p), providers=providers); s.advance(16)
    assert len([e for e in s.session.events if e["type"] == "attack.accepted"]) == 1


def test_half_cell_route_reaches_portal_and_leaks_in_same_projected_map():
    p = json.loads((ROOT / "tools/experiments/m11/capacity.fixture.json").read_bytes())
    p["scenarioDraft"].update(map={"rows": 4, "cols": 8, "tiles": [
        {"tileKey": "tile_end" if i == 25 else "tile_floor", "passableMask": 0 if i == 25 else 1} for i in range(32)]},
        resources={"lives": {"initial": 3, "capacity": 3}}, objectives={"life_resource": "lives"})
    p["scenarioDraft"]["initialEntities"] = [{"definition": "unit/mover", "instanceAlias": "enemy0",
        "position": {"row": 2.5, "col": 0}, "route": {"motionMode": "WALK", "endPosition": {"row": 3.49, "col": 1}}}]
    p["entities"][1]["components"]["attributes"]["base"]["move_speed"] = 60
    s = make(p)
    assert s.ctx.spatial.grid._cell({"row": 2.5, "col": 0}) == (3, 0)
    assert s.ctx.spatial.grid._cell({"row": 3.49, "col": 1}) == (3, 1)
    s.advance(1); restored = Engine.restore(s.program, s.checkpoint()); s.advance(2); restored.advance(2)
    assert s.ctx.state()["leaks"] == 1 and s.ctx.resources.current("system/battle", "lives") == 2
    assert not s.ctx.alive("enemy0")
    assert first_difference(s.snapshot(), restored.snapshot()) is None
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None
