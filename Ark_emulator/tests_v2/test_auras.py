"""Generic aura ownership and regeneration, with independent state witnesses."""
from copy import deepcopy

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from test_campaign_acceptance import scene


def aura_scene():
    data = scene()
    for unit in data["entities"]:
        unit["components"]["attributes"]["base"]["atk"] = 10
    data["selectors"].append({"id": "selector/aura", "kind": "selector",
        "region": {"type": "radius", "radius": 2}, "filters": [{"state": "alive"}]})
    data["buffs"] = [
        {"id": "buff/emitter", "kind": "buff", "duration_seconds": 1,
         "aura": {"selector": "selector/aura", "buff": "buff/member"}},
        {"id": "buff/member", "kind": "buff", "stacking": {"mode": "independent"},
         "modifiers": [{"attribute": "atk", "layer": "flat", "value": 5}]},
    ]
    data["scenarioDraft"]["dependencies"] = ["buff/emitter"]
    return data


def members(sim, ref):
    return [i for i in sim.ctx.get(ref, ("buffs", "instances")) if i["definition"] == "buff/member"]


def test_apply_selects_synchronously_and_only_changes_in_range_members():
    sim = Engine.create(Compiler().compile(aura_scene()))
    sim.ctx.buffs.apply("source", "source", "buff/emitter")
    assert [sim.ctx.attributes.value(t, "atk") for t in ("source", "target1", "target2")] == [15, 15, 10]
    before = members(sim, "target1")[0]["id"]
    sim.ctx.buffs.reconcile()
    assert members(sim, "target1")[0]["id"] == before
    assert len(members(sim, "target1")) == 1


def test_new_actor_joins_existing_live_aura_before_first_tick():
    sim = Engine.create(Compiler().compile(aura_scene()))
    sim.ctx.buffs.apply("source", "source", "buff/emitter")
    ref = sim.ctx.lifecycle.create("unit/target", {"row": 0, "col": 1})
    assert sim.ctx.attributes.value(ref, "atk") == 15
    assert len(members(sim, ref)) == 1


def test_leave_and_reenter_create_new_owned_instance_and_restore_attributes():
    sim = Engine.create(Compiler().compile(aura_scene()))
    sim.ctx.buffs.apply("source", "source", "buff/emitter")
    original = members(sim, "target1")[0]["id"]
    sim.ctx.set("target1", ("spatial", "position"), {"row": 0, "col": 4})
    sim.session.advance(1)
    assert sim.ctx.attributes.value("target1", "atk") == 10
    sim.ctx.set("target1", ("spatial", "position"), {"row": 0, "col": 1})
    sim.session.advance(1)
    assert sim.ctx.attributes.value("target1", "atk") == 15
    assert members(sim, "target1")[0]["id"] != original


def test_effect_phase_displacement_updates_aura_in_same_atomic_effect():
    sim = Engine.create(Compiler().compile(aura_scene()))
    sim.ctx.buffs.apply("source", "source", "buff/emitter")
    sim.ctx.effects.execute("source", ["target1"], {"op": "move", "position": {"row": 0, "col": 4}})
    assert sim.ctx.attributes.value("target1", "atk") == 10
    assert not members(sim, "target1")
    sim.ctx.effects.execute("source", ["target1"], {"op": "move", "position": {"row": 0, "col": 1}})
    assert sim.ctx.attributes.value("target1", "atk") == 15


def test_overlap_removes_only_one_parent_including_center_self_members():
    sim = Engine.create(Compiler().compile(aura_scene()))
    first = sim.ctx.buffs.apply("source", "source", "buff/emitter")
    sim.ctx.buffs.apply("target1", "target1", "buff/emitter")
    assert sim.ctx.attributes.value("source", "atk") == 20
    sim.ctx.buffs.remove("source", first)
    assert sim.ctx.attributes.value("source", "atk") == 15
    assert len(members(sim, "source")) == 1
    assert len(members(sim, "target1")) == 1
    assert len(members(sim, "target2")) == 1


@pytest.mark.parametrize("reason", ["dead", "withdrawn"])
def test_source_retirement_cleans_members_synchronously(reason):
    sim = Engine.create(Compiler().compile(aura_scene()))
    sim.ctx.buffs.apply("source", "source", "buff/emitter")
    sim.ctx.lifecycle.retire("source", reason)
    assert all(not members(sim, t) for t in ("source", "target1", "target2"))
    assert sim.ctx.attributes.value("target1", "atk") == 10


def test_half_open_expiry_cleans_before_other_tick_consumers():
    sim = Engine.create(Compiler().compile(aura_scene()))
    sim.ctx.buffs.apply("source", "source", "buff/emitter")
    sim.session.advance(30)
    assert sim.ctx.attributes.value("target1", "atk") == 15
    sim.session.advance(1)
    assert sim.ctx.attributes.value("target1", "atk") == 10
    assert not sim.ctx.get("source", ("buffs", "instances"))


@pytest.mark.parametrize("aura", [True, False])
def test_expiry_precedes_phase_zero_command_at_cast_snapshot(aura):
    data = aura_scene()
    if not aura:
        data["buffs"][0].pop("aura")
        data["buffs"][0]["modifiers"] = [{"attribute": "atk", "layer": "flat", "value": 5}]
    data["abilities"][0]["timeline"][0]["effect"]["read_mode"] = {"source_attributes": "at_cast"}
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.buffs.apply("source", "source", "buff/emitter")
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"}, at=30)
    sim.session.advance(31)
    assert sim.ctx.resources.current("target1", "hp") == 90
    assert sim.ctx.attributes.value("source", "atk") == 10


def test_pre_expiry_historical_at_cast_snapshot_keeps_its_buff_after_expiry():
    data = aura_scene()
    data["abilities"][0]["timeline"][0]["at"] = 2
    data["abilities"][0]["timeline"][0]["effect"]["read_mode"] = {"source_attributes": "at_cast"}
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.buffs.apply("source", "source", "buff/emitter")
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"}, at=29)
    sim.session.advance(32)
    assert sim.ctx.resources.current("target1", "hp") == 85
    assert sim.ctx.attributes.value("source", "atk") == 10


def test_refresh_keeps_child_instances_and_extends_parent_lifetime():
    sim = Engine.create(Compiler().compile(aura_scene()))
    parent = sim.ctx.buffs.apply("source", "source", "buff/emitter")
    child = members(sim, "target1")[0]["id"]
    sim.session.advance(10)
    assert sim.ctx.buffs.apply("source", "source", "buff/emitter") == parent
    assert members(sim, "target1")[0]["id"] == child
    sim.session.advance(21)
    assert sim.ctx.attributes.value("target1", "atk") == 15


def test_member_failure_rolls_back_parent_members_tasks_and_events():
    data = aura_scene()
    data["buffs"][1]["effects"] = [{"op": "modify_resource", "resource": "absent", "delta": 1}]
    sim = Engine.create(Compiler().compile(data))
    before = sim.checkpoint()
    with pytest.raises(ValueError):
        sim.ctx.buffs.apply("source", "source", "buff/emitter")
    assert sim.checkpoint() == before


def test_membership_survives_checkpoint_and_command_replay_exactly():
    data = aura_scene()
    data["abilities"][0]["activation"]["on_start"] = [{"op": "apply_buff", "target": "self", "buff": "buff/emitter"}]
    program = Compiler().compile(data)
    sim = Engine.create(program)
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"})
    sim.session.advance(10)
    restored = Engine.restore(program, sim.checkpoint())
    sim.session.advance(25)
    restored.session.advance(25)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None


@pytest.mark.parametrize("change", [
    {"stacking": {"mode": "refresh"}}, {"duration_seconds": 1},
    {"aura": {"selector": "selector/aura", "buff": "buff/member"}},
])
def test_invalid_member_contract_is_rejected_before_execution(change):
    data = aura_scene()
    data["buffs"][1].update(deepcopy(change))
    with pytest.raises(ValueError):
        Compiler().compile(data)


def test_regeneration_uses_effective_source_attack_without_healing_event():
    sim = Engine.create(Compiler().compile(aura_scene()))
    sim.ctx.resources.adjust("target1", "hp", -50)
    sim.ctx.buffs.apply("source", "source", "buff/emitter")
    sim.ctx.effects.execute("source", ["target1"], {"op": "regenerate", "scale": 2})
    assert sim.ctx.resources.current("target1", "hp") == 80
    records = list(sim.session.events)
    assert len([e for e in records if e["type"] == "regeneration.accepted"]) == 1
    assert not [e for e in records if e["type"] == "healing.accepted"]
