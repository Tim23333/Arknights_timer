"""Root independent terrain tests; no author fixture/helper dependency."""
from copy import deepcopy
import json

import pytest
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_chapter01_stage_models import ROOT


def base():
    def unit(identifier, tags):
        return {"id": identifier, "kind": "entity", "tags": tags, "components": {
            "attributes": {"base": {"max_hp": 100, "atk": 0, "def": 0, "mres": 0, "move_speed": 3, "block_count": 0}},
            "resources": {"hp": {"initial": 100, "capacity": 100, "role": "health"}},
            "lifecycle": {"policy": "policy/ark_lifecycle"}, "spatial": {}, "abilities": []}}
    return {"schemaVersion": 2, "manifest": {"id": "package/root_terrain_peer", "version": "1", "requires": ["preset/ark_standard"]},
        "entities": [unit("unit/a", ["ally"]), unit("unit/b", ["ally"]), unit("unit/walker", ["enemy", "ground"])],
        "abilities": [], "scenarioDraft": {"id": "scenario/root_terrain_peer", "ruleset": "ruleset/ark_standard",
            "map": {"rows": 1, "cols": 6}, "objectives": {}, "initialEntities": [
                {"definition": "unit/a", "instanceAlias": "a", "position": {"row": 0, "col": 5}},
                {"definition": "unit/b", "instanceAlias": "b", "position": {"row": 0, "col": 5}},
                {"definition": "unit/walker", "instanceAlias": "walker", "position": {"row": 0, "col": 0},
                    "route": {"motionMode": "WALK", "startPosition": {"row": 0, "col": 0}, "endPosition": {"row": 0, "col": 4}, "checkpoints": []}}]}}


def ability(p, owner, name, effect):
    identifier = "ability/peer/"+name
    next(e for e in p["entities"] if e["id"] == "unit/"+owner)["components"]["abilities"].append(identifier)
    p["abilities"].append({"id": identifier, "kind": "ability", "activation": {"mode": "manual", "on_start": [effect]}, "timeline": []})
    return identifier


def overlay(key, values):
    return {"op": "apply_terrain_overlay", "parameters": {"key": key, "priority": 0, "values": values, "position": {"row": 0, "col": 2}}}


def test_blocking_owner_retire_preserves_second_layer_and_restored_live_grid():
    p = base(); wall = ability(p, "a", "wall", overlay("shared", {"passableMask": 0}))
    upper = ability(p, "b", "upper", overlay("shared", {"buildableType": 2, "physicalHeight": 2}))
    end = ability(p, "a", "end", {"op": "retire", "parameters": {"reason": "dead"}})
    sim = Engine.create(Compiler().compile(p), seed=1630)
    for tick, actor, aid in ((1, "a", wall), (2, "b", upper), (3, "a", end)):
        sim.submit({"action": "skill", "source": actor, "ability": aid}, at=tick)
    sim.advance(2); held = sim.ctx.get("walker", ("spatial", "position")); checkpoint = sim.checkpoint()
    assert not sim.ctx.spatial.grid.passable(0, 2)
    sim.advance(2)
    tile = sim.ctx.spatial.grid.tile(0, 2)
    assert sim.ctx.spatial.grid.passable(0, 2)
    assert tile["buildableType"] == 2 and tile["physicalHeight"] == 2
    layers = list(sim.ctx.get("system/battle", ("state", "terrain", "layers")).values())
    assert len(layers) == 1 and layers[0]["owner"] == sim.session.world.resolve("b")
    assert sim.ctx.get("walker", ("spatial", "position"))["col"] > held["col"]
    assert sim.ctx.resources.current("a", "hp") == 100 and not sim.ctx.alive("a")
    restored = Engine.restore(sim.program, checkpoint); restored.advance(2)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(tuple(sim.session.events), tuple(restored.session.events)) is None
    replayed = replay(sim.program, sim.export_replay())
    assert first_difference(sim.snapshot(), replayed.snapshot()) is None
    assert first_difference(tuple(sim.session.events), tuple(replayed.session.events)) is None


def test_rule_only_in_overlay_loads_and_invalid_numeric_output_rolls_back():
    p = base(); fx = overlay("bad", {"passableMask": 0}); fx["parameters"]["rule"] = "rule/peer_bad_tile"
    p["rules"] = [{"id": "rule/peer_bad_tile", "kind": "calculation_rule", "contract": "terrain.tile_options",
        "implementation": {"type": "expression", "expression": "{'passableMask':0,'groundPassable':False,'movementCost':0}"}}]
    ability(p, "a", "bad", fx)
    sim = Engine.create(Compiler().compile(p), seed=1631)
    assert "rule/peer_bad_tile" in sim.program.definitions
    checkpoint = sim.checkpoint()
    with pytest.raises(ValueError, match="positive finite movementCost"):
        sim.ctx.effects.execute("a", ["a"], fx)
    assert first_difference(checkpoint, sim.checkpoint()) is None
    assert sim.ctx.spatial.grid.passable(0, 2)


def test_actual_emp_preserves_native_pass_and_advanced_then_restores_after_withdraw():
    p = json.loads((ROOT/"packages/campaign/chapter01_devices/emp.terrain.json").read_bytes())
    p["scenarioDraft"] = {"id": "scenario/root_emp_preservation", "ruleset": "ruleset/ark_standard",
        "resources": {"dp": {"initial": 10, "capacity": 99}},
        "map": {"rows": 1, "cols": 1, "tiles": [{"tileKey": "tile_floor", "passableMask": 3,
            "buildableType": 3, "heightType": "HIGHLAND", "physicalHeight": 7, "advancedBuildMask": 0}]},
        "initialEntities": [{"definition": "unit/chapter01_emp", "instanceAlias": "device", "position": {"row": 0, "col": 0}}], "objectives": {}}
    sim = Engine.create(Compiler().compile(p), seed=1632)
    expected = deepcopy(sim.ctx.spatial._base_map_definition["tiles"][0])
    checkpoint = sim.checkpoint()
    for _ in range(4):
        tile = sim.ctx.spatial.grid.tile(0, 0)
        assert tile["passableMask"] == 3 and tile["advancedBuildMask"] == 0
        assert tile["heightType"] == "HIGHLAND" and tile["buildableType"] == 0
        assert abs(tile["physicalHeight"]-.4000000059604645) < 1e-12
    assert first_difference(checkpoint, sim.checkpoint()) is None
    sim.submit({"action": "withdraw", "source": "device"}, at=0); sim.advance(1)
    assert sim.ctx.spatial.grid.tile(0, 0) == expected
    assert sim.ctx.get("system/battle", ("state", "terrain", "layers")) == {}
    assert first_difference(sim.snapshot(), replay(sim.program, sim.export_replay()).snapshot()) is None
