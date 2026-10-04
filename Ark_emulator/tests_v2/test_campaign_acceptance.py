"""Independent campaign gates using the real V2 compiler and engine.

Failing expectations deliberately expose blockers; no fake domain handlers.
"""
import json
from pathlib import Path

import pytest

from ark_sim import Compiler, Engine
from ark_sim.content.repository import ContentError

ROOT = Path(__file__).resolve().parents[1]


def scene(*, behavior=None, route=None, sp=False, mode="manual", repeats=1):
    components = {
        "attributes": {"base": {"atk": 10, "def": 0, "magic_resistance": 0, "max_hp": 100, "attack_interval": 10,
                                    "attack_speed_ratio": 1, "move_speed": 1}},
        "resources": {"hp": {"initial": 100, "capacity": 100, "role": "health"},
                      "sp": {"initial": 0, "capacity": 100}},
        "spatial": {}, "abilities": ["ability/probe"],
    }
    if behavior:
        components["behavior"] = {"machine": behavior}
    ability = {"id": "ability/probe", "kind": "ability", "activation": {"mode": mode},
               "selector": "selector/probe", "timeline": [{"at": 0,
               "repeat": {"count": repeats, "interval_seconds": 0},
               "effect": {"op": "damage", "damage_type": "true", "scale": 1}}]}
    if sp:
        ability["activation"]["parameters"] = {"sp_resource": "sp", "recovery_per_attack": 1}
    first = {"definition": "unit/source", "instanceAlias": "source", "position": {"row": 0, "col": 0}}
    if route:
        first["route"] = route
    return {"schemaVersion": 2,
            "entities": [{"id": "unit/source", "kind": "entity", "tags": ["player"], "components": components},
                         {"id": "unit/target", "kind": "entity", "tags": ["enemy"], "components": {
                             "attributes": {"base": {"max_hp": 100, "def": 0, "magic_resistance": 0}}, "spatial": {},
                             "resources": {"hp": {"initial": 100, "capacity": 100, "role": "health"}}}}],
            "abilities": [ability], "selectors": [{"id": "selector/probe", "kind": "selector",
                 "region": {"type": "all"}, "filters": [{"tag": "enemy"}, {"state": "alive"}], "limit": 2}],
            "scenarioDraft": {"id": "scenario/probe", "ruleset": "ruleset/ark_standard",
                 "map": {"rows": 1, "cols": 5}, "initialEntities": [first,
                     {"definition": "unit/target", "instanceAlias": "target1", "position": {"row": 0, "col": 2}},
                     {"definition": "unit/target", "instanceAlias": "target2", "position": {"row": 0, "col": 3}}]}}


def cast(data):
    sim = Engine.create(Compiler().compile(data), seed=123)
    sim.submit({"action": "activate_ability", "source": "source", "ability": "ability/probe"})
    sim.advance(1)
    return sim


def test_multitarget_damage_has_two_independent_settlement_witnesses():
    sim = cast(scene())
    assert [sim.ctx.resources.current(t, "hp") for t in ("target1", "target2")] == [90, 90]
    accepted = [e for e in sim.session.events if e["type"] == "damage.accepted"]
    assert len(accepted) == 2
    assert {e["payload"]["target"] for e in accepted} == {
        sim.session.world.resolve("target1"), sim.session.world.resolve("target2")}


@pytest.mark.parametrize("repeats", [1, 2])
def test_attack_recovery_occurs_once_per_attack_not_per_target_or_hit(repeats):
    sim = cast(scene(sp=True, repeats=repeats))
    assert sim.ctx.resources.current("source", "sp") == 1


def test_behavior_move_false_prevents_route_progress():
    route = {"startPosition": {"row": 0, "col": 0}, "endPosition": {"row": 0, "col": 4}, "checkpoints": []}
    sim = Engine.create(Compiler().compile(scene(behavior="behavior/player_combat", route=route)))
    assert sim.ctx.behavior.plan("source")["move"] is False
    sim.advance(30)
    assert sim.ctx.get("source", ("spatial", "position")) == {"row": 0, "col": 0}


def test_behavior_attack_false_prevents_automatic_attack():
    sim = Engine.create(Compiler().compile(scene(behavior="behavior/ground_melee", mode="automatic_attack")))
    assert sim.ctx.behavior.plan("source")["attack"] is False
    sim.advance(1)
    assert sim.ctx.resources.current("target1", "hp") == 100
    assert not [e for e in sim.session.events if e["type"] == "damage.accepted"]


@pytest.mark.parametrize("route", [
    {"motionMode": {"name": "E_NUM", "value": 999}, "checkpoints": []},
    {"checkpoints": [{"type": {"name": "UNKNOWN", "value": 999},
                      "position": {"row": 0, "col": 2}, "time": 10}]},
    {"checkpoints": [{"type": {"name": "WAIT_CURRENT_FRAGMENT_TIME", "value": 3},
                      "position": {"row": 0, "col": 2}, "time": 10}]},
    {"checkpoints": [{"type": {"name": "DISAPPEAR", "value": 5},
                      "position": {"row": 0, "col": 2}}]},
    {"checkpoints": [{"type": {"name": "APPEAR_AT_POS", "value": 6},
                      "position": {"row": 0, "col": 2}}]},
])
def test_unimplemented_native_route_semantics_fail_before_execution(route):
    route = {"startPosition": {"row": 0, "col": 0}, "endPosition": {"row": 0, "col": 4}, **route}
    with pytest.raises(ContentError):
        Compiler().compile(scene(route=route))


@pytest.mark.parametrize("tile_key", ["tile_campaign_unknown", "tile_healing", "tile_defup", "tile_volcano", "tile_telin"])
def test_unknown_or_unimplemented_tile_mechanic_is_rejected_instead_of_becoming_floor(tile_key):
    data = scene()
    data["scenarioDraft"]["map"]["tiles"] = [{"tileKey": tile_key,
         "passableMask": 1, "buildableType": 1} for _ in range(5)]
    with pytest.raises(ContentError):
        Compiler().compile(data)


def test_selected_catalog_does_not_claim_execution_or_client_evidence():
    data = json.loads((ROOT / "packages/campaign/mainline_catalog.json").read_bytes())
    selected = [r for r in data["stages"] if r["selected"]]
    assert len(selected) == 36
    assert {r["chapter"] for r in selected} == set(range(18))
    for row in selected:
        assert row["v2_status"] == "not_validated"
        assert row["dependency_status"] == "not_imported"
        assert row["dependency_summary"]["invalid_motion_route_count"] > 0


@pytest.mark.parametrize("location", ["entity", "initial", "wave", "initial_override", "wave_override"])
def test_executable_route_paths_are_validated_but_unreferenced_inventory_is_preserved(location):
    data = scene()
    route = {"motionMode": "E_NUM", "endPosition": {"row": 0, "col": 4}}
    if location == "entity":
        data["entities"][0]["components"]["spatial"]["route"] = route
    elif location == "initial":
        data["scenarioDraft"]["initialEntities"][0]["route"] = route
    elif location == "initial_override":
        data["scenarioDraft"]["initialEntities"][0]["components"] = {"spatial": {"route": route}}
    else:
        wave = {"at": 10, "definition": "unit/target"}
        wave["route" if location == "wave" else "components"] = route if location == "wave" else {"spatial": {"route": route}}
        data["scenarioDraft"]["waves"] = [wave]
    with pytest.raises(ContentError, match=r"route.motionMode: unsupported"):
        Compiler().compile(data)
    plain = scene()
    plain["scenarioDraft"]["routes"] = [{"motionMode": {"name": "E_NUM", "value": 0}}]
    Compiler().compile(plain)


@pytest.mark.parametrize("value", ["WAIT_FOR_SECONDS", {"name": "WAIT_FOR_SECONDS"}, {"name": "WAIT_FOR_SECONDS", "value": 1}, 1])
def test_legal_wait_enum_forms_execute_the_same_wait(value):
    route = {"motionMode": "WALK", "startPosition": {"row": 0, "col": 0},
             "endPosition": {"row": 0, "col": 4}, "checkpoints": [{"type": value, "time": 1}]}
    sim = Engine.create(Compiler().compile(scene(route=route)))
    sim.advance(15)
    assert sim.ctx.get("source", ("spatial", "position")) == {"row": 0, "col": 0}
    assert [e["payload"]["until"] for e in sim.session.events if e["type"] == "movement.wait"] == [30]


@pytest.mark.parametrize("update,error", [
    ({"motionMode": {"name": "WALK", "value": 1}}, "motionMode"),
    ({"checkpoints": [{"type": {"name": "MOVE", "value": 1}, "position": {"row": 0, "col": 1}}]}, "type"),
    ({"endPosition": {"row": True, "col": 1}}, "endPosition.row"),
    ({"endPosition": {"row": 0, "col": 99}}, "outside declared map"),
    ({"checkpoints": [{"type": "MOVE"}]}, "position"),
    ({"checkpoints": [{"type": "WAIT_FOR_SECONDS", "time": -1}]}, "time"),
    ({"checkpoints": [{"type": "WAIT_FOR_SECONDS", "time": False}]}, "time"),
])
def test_route_positions_and_enum_name_value_mismatch_are_rejected(update, error):
    route = {"endPosition": {"row": 0, "col": 4}, **update}
    with pytest.raises(ContentError, match=error):
        Compiler().compile(scene(route=route))
