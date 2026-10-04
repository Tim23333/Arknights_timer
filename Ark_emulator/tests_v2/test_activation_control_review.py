"""Independent review of activation transactions, controls and accounting."""
from copy import deepcopy
import json

import pytest

from ark_sim import Compiler, Engine
from ark_sim.content import CompileError
from test_campaign_acceptance import scene
from test_activation_controls import start_scene, control_scene

from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def records(sim, kind):
    return [r for r in sim.session.events if r["type"] == kind]


@pytest.mark.parametrize("target", ["source", "self"])
def test_missing_source_resource_in_on_start_is_a_compile_error(target):
    data = start_scene()
    data["abilities"][0]["activation"]["on_start"] = [{"op": "modify_resource", "target": target, "resource": "missing", "delta": 1}]
    with pytest.raises(CompileError, match="(?i)undefined|missing|resource"):
        Compiler().compile(data)


def test_missing_buff_in_on_start_is_rejected_by_dependency_preflight():
    data = start_scene()
    data["abilities"][0]["activation"]["on_start"] = [{"op": "apply_buff", "target": "source", "buff": "buff/missing"}]
    with pytest.raises(CompileError):
        Compiler().compile(data)


def test_second_on_start_effect_failure_rolls_back_first_effect_and_payment():
    data = start_scene()
    data["abilities"][0]["activation"]["costs"] = [{"resource": "sp", "amount": 2}]
    data["abilities"][0]["activation"]["parameters"] = {"blocks_attacks": False}
    data["abilities"][0]["activation"]["on_start"].append({"op": "modify_resource", "target": "source", "resource": "ammo", "delta": 2})
    resources = data["entities"][0]["components"]["resources"]
    resources["sp"]["initial"] = 5
    resources["ammo"] = {"initial": 0, "capacity": 1, "parameters": {"mode": "reject"}}
    sim = Engine.create(Compiler().compile(data))
    before = sim.session.checkpoint()
    with pytest.raises(ValueError, match="resource update rejected"):
        sim.ctx.abilities.start("source", "ability/mode")
    assert sim.session.checkpoint() == before


def test_insufficient_payment_does_not_apply_synchronous_buff():
    data = start_scene()
    data["abilities"][0]["activation"]["costs"] = [{"resource": "sp", "amount": 2}]
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = 1
    sim = Engine.create(Compiler().compile(data))
    before = sim.session.checkpoint()
    with pytest.raises(ValueError, match="insufficient resource"):
        sim.ctx.abilities.start("source", "ability/mode")
    assert sim.session.checkpoint() == before


def test_multiple_control_instances_remove_only_the_requested_buff():
    data = control_scene({"move": False, "block": False})
    data["buffs"].append({"id": "buff/second", "kind": "buff", "duration_seconds": 2,
                           "control": {"attack": False, "abilities": False}})
    data["scenarioDraft"]["dependencies"].append("buff/second")
    sim = Engine.create(Compiler().compile(data))
    first = sim.ctx.buffs.apply("source", "source", "buff/control")
    second = sim.ctx.buffs.apply("source", "source", "buff/second")
    assert all(v is False for v in sim.ctx.buffs.controls("source").values())
    sim.ctx.buffs.remove("source", first)
    assert sim.ctx.buffs.controls("source") == {"move": True, "block": True, "attack": False, "abilities": False}
    assert [b["id"] for b in sim.ctx.get("source", ("buffs", "instances"))] == [second]
    sim.advance(60)
    assert all(sim.ctx.buffs.controls("source").values())  # Half-open expiry applies even before expiry callback.


def test_stun_cancels_new_attack_and_movement_but_launched_projectile_still_lands():
    data = control_scene({"move": False, "attack": False, "abilities": False, "block": False, "interrupt": True})
    data["abilities"][0]["parameters"] = {"projectile_speed": 2}
    # One target atdistance2 produces a 1-second flight.
    data["selectors"][0]["limit"] = 1
    sim = Engine.create(Compiler().compile(data))
    sim.advance(1)
    assert len(records(sim, "projectile.launched")) == 1
    sim.ctx.buffs.apply("source", "source", "buff/control")
    position = sim.ctx.get("source", ("spatial", "position"))
    sim.advance(29)
    assert not records(sim, "damage.accepted")
    assert sim.ctx.get("source", ("spatial", "position")) == position
    sim.advance(1)
    assert sim.ctx.resources.current("target1", "hp") == 90
    assert len(records(sim, "projectile.launched")) == 1


def test_block_false_releases_previously_blocked_route_mover():
    data = scene(route={"motionMode": "WALK", "endPosition": {"row": 0, "col": 4}})
    data["entities"][0]["components"]["abilities"] = []
    data["entities"][0]["tags"] = ["enemy"]
    blocker = data["entities"][1]
    blocker["tags"] = ["player"]
    blocker["components"]["attributes"]["base"]["block_count"] = 1
    blocker["components"]["deployable"] = {"base_cost": 0, "cooldown_seconds": 0}
    data["scenarioDraft"]["initialEntities"][0]["position"] = {"row": 0, "col": 2}
    # This case isolates one blocker. The shared target definition otherwise
    # also creates a second legal blocker on the remaining route.
    data["scenarioDraft"]["initialEntities"][2]["position"] = {"row": 0, "col": 0}
    data["buffs"] = [{"id": "buff/release", "kind": "buff", "duration_seconds": 1, "control": {"block": False}}]
    data["scenarioDraft"]["dependencies"] = ["buff/release"]
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.spatial.blocking()
    assert sim.ctx.spatial.blocked_by("source") == sim.session.world.resolve("target1")
    sim.ctx.buffs.apply("target1", "target1", "buff/release")
    sim.advance(1)
    assert sim.ctx.spatial.blocked_by("source") is None
    point = sim.ctx.get("source", ("spatial", "position"))
    sim.advance(1)
    assert sim.ctx.get("source", ("spatial", "position"))["col"] > point["col"]


def test_released_mover_can_transfer_to_another_eligible_blocker_on_remaining_path():
    data = scene(route={"motionMode": "WALK", "endPosition": {"row": 0, "col": 4}})
    data["entities"][0]["components"]["abilities"] = []
    data["entities"][0]["tags"] = ["enemy"]
    blocker = data["entities"][1]
    blocker["tags"] = ["player"]
    blocker["components"]["attributes"]["base"]["block_count"] = 1
    blocker["components"]["deployable"] = {"base_cost": 0, "cooldown_seconds": 0}
    data["scenarioDraft"]["initialEntities"][0]["position"] = {"row": 0, "col": 2}
    data["buffs"] = [{"id": "buff/release", "kind": "buff", "duration_seconds": 1, "control": {"block": False}}]
    data["scenarioDraft"]["dependencies"] = ["buff/release"]
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.spatial.blocking()
    assert sim.ctx.spatial.blocked_by("source") == sim.session.world.resolve("target1")
    sim.ctx.buffs.apply("target1", "target1", "buff/release")
    assert sim.ctx.spatial.blocked_by("source") is None
    sim.advance(1)
    assert sim.ctx.spatial.blocked_by("source") == sim.session.world.resolve("target2")


@pytest.mark.parametrize("hp_loss,charge", [(0, 1), (7, 1), (7, 0)])
def test_mixed_shield_charge_and_health_allocations_count_only_target_health(hp_loss, charge):
    data = scene()
    data["entities"][1]["components"]["resources"]["shield"] = {"initial": 1, "capacity": 1}
    data["rules"] = [{"id": "rule/review_split", "kind": "calculation_rule", "contract": "damage.pipeline",
        "implementation": {"type": "graph", "nodes": [{"id": "settlement", "expression":
            "{'accepted': True, 'amount': 1234, 'allocations': "
            f"[{{'target': 'target', 'resource': 'hp', 'amount': {hp_loss}}}, {{'target': 'target', 'resource': 'shield', 'amount': {charge}}}], 'events': []}}"}],
            "output": "nodes.settlement"}}]
    data["abilities"][0]["timeline"][0]["effect"]["rules"] = {"damage.pipeline": "rule/review_split"}
    sim = Engine.create(Compiler().compile(data))
    sim.submit({"action": "activate_ability", "source": "source", "ability": "ability/probe"})
    sim.advance(1)
    assert [sim.ctx.resources.current(t, "hp") for t in ("target1", "target2")] == [100-hp_loss] * 2
    assert [e["payload"]["amount"] for e in records(sim, "damage.accepted")] == [hp_loss] * 2
    assert sim.ctx.state()["damage_dealt"] == 2 * hp_loss


def test_full_sp_exu_mode_enters_synchronously_before_first_native_burst_tick():
    data = json.loads((ROOT / "packages/campaign/skills.angel.json").read_bytes())
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = 30
    sim = Engine.create(Compiler().compile(data), seed=19)
    sim.advance(10)
    starts = records(sim, "ability.started")
    assert [(e["time"], e["payload"]["ability"]) for e in starts[:2]] == [
        (0, "ability/campaign_angel_s3"), (0, "ability/campaign_angel_burst")]
    assert sim.ctx.resources.current("actor", "mode") == 1
    assert sim.ctx.resources.current("target", "hp") == 100000
    assert [e["time"] for e in records(sim, "projectile.launched")] == [9]
    sim.advance(9)
    assert [e["time"] for e in records(sim, "damage.accepted")] == [10, 12, 14, 16, 18]
    assert [e["payload"]["amount"] for e in records(sim, "damage.accepted")] == [100] * 5
    assert len(records(sim, "attack.accepted")) == 1


def test_full_sp_exu_player_force_is_rejected_before_system_auto_mode_entry():
    data = json.loads((ROOT / "packages/campaign/skills.angel.json").read_bytes())
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = 30
    sim = Engine.create(Compiler().compile(data), seed=19)
    assert sim.ctx.resources.current("actor", "sp") == 30
    sim.submit({"action": "activate_ability", "source": "actor", "ability": "ability/campaign_angel_s3"})
    sim.advance(1)
    assert len(records(sim, "command.rejected")) == 1
    assert sim.ctx.resources.current("actor", "sp") == 0
    started = [r for r in records(sim, "ability.started") if r["payload"]["ability"] == "ability/campaign_angel_s3"]
    assert len(started) == 1
    assert records(sim, "command.rejected")[0]["id"] < started[0]["id"]
    cast = next(c for c in sim.ctx.get("actor", ("runtime", "casts")).values() if c["ability"] == "ability/campaign_angel_s3")
    assert cast["automatic"] is True


def test_full_sp_chen_replacement_owns_first_tick_and_its_source_stun():
    data = json.loads((ROOT / "packages/campaign/skills.chen.json").read_bytes())
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = 4
    sim = Engine.create(Compiler().compile(data), seed=19)
    sim.advance(16)
    assert [(e["time"], e["payload"]["ability"]) for e in records(sim, "ability.started")] == [
        (0, "ability/campaign_chen_s1")]
    assert sim.ctx.resources.current("actor", "sp") == 0
    assert sim.ctx.resources.current("target", "hp") == 100000
    sim.advance(1)
    assert [e["payload"]["amount"] for e in records(sim, "damage.accepted")] == [310]
    assert all(value is False for value in sim.ctx.buffs.controls("target").values())


def test_attack_reference_and_recipes_preserve_partial_native_boundary():
    reference = json.loads((ROOT / "packages/campaign/attacks.reference.json").read_bytes())
    assert len(reference["operators"]) == 12 and reference["runnable"] is False
    assert all(row["status"] == "source_frozen_not_converted" and row["pending"] for row in reference["operators"])
    for name in ("angel", "chen"):
        data = json.loads((ROOT / f"packages/campaign/skills.{name}.json").read_bytes())
        assert data["status"] == "partially_implemented"
        meta = data["manifest"]["metadata"]
        assert meta["official_unit_config_imported"] is False and meta["client_validated"] is False
        assert meta["source_gaps"]
