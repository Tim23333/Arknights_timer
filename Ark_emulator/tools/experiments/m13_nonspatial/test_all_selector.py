"""Source-independent selector and real settlement/terminal counterexamples."""
from copy import deepcopy
import pytest
from tools.experiments.m13_nonspatial.test_controls import scene, make, emit
from ark_sim import Compiler, Engine
from ark_sim.presets.providers import selector_grid
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay


def damage_scene():
    p = scene(steps=[{"kind": "effects", "effects": [{"op": "damage", "damage_type": "true", "selector": "selector/all_enemies",
        "rules": {"damage.pipeline": "rule/control_packet"}}]}], ack="immediate", next_fragment=False)
    p["entities"][0]["components"]["resources"]["hp"].update(initial=10, capacity=10)
    p["entities"][0]["components"]["attributes"]["base"]["max_hp"] = 10
    p["scenarioDraft"]["initialEntities"] = [{"definition": "unit/enemy", "instanceAlias": name, "position": {"row": 0, "col": i}}
        for i, name in enumerate(("one", "two"))]
    p["selectors"] = [{"id": "selector/all_enemies", "kind": "selector", "region": {"type": "all"},
        "filters": [{"tag": "enemy"}, {"state": "alive"}], "limit": None}]
    p["rules"] = [{"id": "rule/control_packet", "kind": "calculation_rule", "contract": "damage.pipeline", "implementation": {"type": "graph",
        "nodes": [{"id": "settlement", "expression": "{'accepted': True, 'amount': 10, 'allocations': [{'target': inputs.target.id, 'resource': 'hp', 'delta': -10}, {'target': inputs.source.id, 'resource': 'lives', 'delta': -3}], 'events': []}"}], "output": "nodes.settlement"}}]
    return p


def test_all_provider_has_no_source_or_candidate_position_requirement():
    inputs = {"source": {"id": 1, "components": {}}, "candidates": [{"id": 2, "components": {}}], "region": {"type": "all"}}
    assert selector_grid(inputs, {}, {}) == [2]


def test_actual_first_multi_target_packet_terminal_second_untouched_and_replay():
    s = make(damage_scene()); s.advance(1)
    hits = [e for e in s.session.events if e["type"] == "damage.accepted"]
    assert len(hits) == 1 and hits[0]["payload"]["target"] == s.session.world.resolve("one")
    assert not s.ctx.alive("one") and s.ctx.alive("two") and s.ctx.resources.current("two", "hp") == 10
    assert s.ctx.state()["result"] == "defeat" and s.ctx.controls.instance("story/test")["status"] == "cancelled"
    assert not [t for t in s.session.scheduler.pending if t["kind"].startswith(("domain.control", "domain.timeline"))]
    assert not s.ctx.entity("system/battle")["components"].get("spatial")
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None


@pytest.mark.parametrize("region", [{"type": "radius", "radius": 1}, {"type": "grid_offsets", "offsets": [[0, 0]]}, {"type": "manhattan", "radius": 1}])
def test_control_spatial_selector_without_origin_is_compile_error_not_failstop(region):
    p = damage_scene(); p["selectors"][0]["region"] = region
    with pytest.raises(ValueError, match="spatial origin"): Compiler().compile(p)


def test_default_damage_requires_source_attributes_compile_rejected():
    p = damage_scene(); p["controls"][0]["steps"][0]["effects"][0].pop("rules")
    with pytest.raises(ValueError, match="source attributes"): Compiler().compile(p)


@pytest.mark.parametrize("op", ["heal", "regenerate", "push"])
def test_negative_control_source_contract_requires_actor(op):
    p = damage_scene(); p["controls"][0]["steps"][0]["effects"][0] = {"op": op, "selector": "selector/all_enemies"}
    if op == "push":
        p["controls"][0]["steps"][0]["effects"][0].update(force=3, direction="source_facing", rules={"movement.displacement": "rule/push"})
        p["rules"].append({"id": "rule/push", "kind": "calculation_rule", "contract": "movement.displacement",
            "implementation": {"type": "expression", "expression": "{'distance': 1, 'duration': 1}"}})
    with pytest.raises(ValueError, match="actor source"): Compiler().compile(p)
