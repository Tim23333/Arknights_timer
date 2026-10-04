"""Support prototypes exercise real resource allocations and target selection."""
from copy import deepcopy
import json

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from ark_sim.tools.compare import first_difference
from tools.build_support_skill_recipes import ROOT, build_liskam, build_plosis


@pytest.fixture(scope="module")
def packages():
    return {key: json.loads((ROOT / f"packages/campaign/skills.{key}.json").read_bytes()) for key in ("liskam", "plosis")}


def events(sim, kind):
    return [e for e in sim.session.events if e["type"] == kind]


def hit(sim):
    sim.submit({"action": "activate_ability", "source": "attacker", "ability": "ability/support_hit"})
    sim.advance(1)


def ready_liskam(data):
    copied = deepcopy(data)
    copied["entities"][0]["components"]["resources"]["sp"]["initial"] = 18
    sim = Engine.create(Compiler().compile(copied), seed=123)
    sim.advance(1)
    assert sim.ctx.resources.current("liskam", "sp") == 0
    assert sim.ctx.resources.current("liskam", "shield_charge") == 1
    return sim


def test_builds_match_raw_dependency_freezes_and_refuse_complete_claim(packages):
    assert build_liskam() == packages["liskam"]
    assert build_plosis() == packages["plosis"]
    for builder in (build_liskam, build_plosis):
        with pytest.raises(ValueError, match="complete.*unsupported"):
            builder(require_complete=True)
    for package in packages.values():
        assert package["status"] == "partially_implemented"
        assert package["manifest"]["metadata"]["official_unit_complete"] is False
        Compiler().compile(package)


def test_liskam_event_sp_reaches_eighteen_then_automatically_pays_and_activates(packages):
    sim = Engine.create(Compiler().compile(packages["liskam"]), seed=123)
    for _ in range(17):
        hit(sim)
    assert sim.ctx.resources.current("liskam", "sp") == 17
    assert not events(sim, "buff.applied")
    hit(sim)
    assert sim.ctx.resources.current("liskam", "sp") == 18
    sim.advance(1)
    assert sim.ctx.resources.current("liskam", "sp") == 0
    assert sim.ctx.attributes.value("liskam", "def") == 200
    assert sim.ctx.resources.current("liskam", "shield_charge") == 1


def test_one_shield_charge_is_not_health_damage_or_damage_counter(packages):
    sim = ready_liskam(packages["liskam"])
    before_hp = sim.ctx.resources.current("liskam", "hp")
    before_damage = sim.ctx.state()["damage_dealt"]
    hit(sim)
    assert sim.ctx.resources.current("liskam", "shield_charge") == 0
    assert sim.ctx.resources.current("liskam", "hp") == before_hp
    assert events(sim, "damage.accepted")[-1]["payload"]["amount"] == 0
    assert sim.ctx.state()["damage_dealt"] == before_damage
    hit(sim)
    assert sim.ctx.resources.current("liskam", "hp") == before_hp - 7.5  # 150*5% physical minimum against DEF200.
    assert events(sim, "damage.accepted")[-1]["payload"]["amount"] == 7.5
    assert sim.ctx.resources.current("liskam", "sp") == 0  # Active cast freezes target-driven recovery.


def test_ready_shield_starts_before_incoming_hit_in_same_tick(packages):
    data = deepcopy(packages["liskam"])
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = 18
    sim = Engine.create(Compiler().compile(data))
    before = sim.ctx.resources.current("liskam", "hp")
    hit(sim)
    assert sim.ctx.resources.current("liskam", "hp") == before
    assert sim.ctx.resources.current("liskam", "shield_charge") == 0
    assert events(sim, "damage.accepted")[-1]["payload"]["amount"] == 0


def test_full_eighteen_sp_player_command_is_rejected_then_system_auto_starts(packages):
    data = deepcopy(packages["liskam"])
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = 18
    sim = Engine.create(Compiler().compile(data))
    assert sim.ctx.resources.current("liskam", "sp") == 18
    sim.submit({"action": "activate_ability", "source": "liskam", "ability": "ability/liskam_s1"})
    sim.advance(1)
    rejected = events(sim, "command.rejected")
    started = events(sim, "ability.started")
    assert len(rejected) == len(started) == 1
    assert started[0]["payload"]["ability"] == "ability/liskam_s1"
    assert rejected[0]["id"] < started[0]["id"]
    assert sim.ctx.resources.current("liskam", "sp") == 0
    assert all(cast["automatic"] for cast in sim.ctx.get("liskam", ("runtime", "casts")).values())
    costs = [e for e in events(sim, "resource.changed") if e["payload"].get("reason") == "ability_cost"]
    assert [e["payload"]["delta"] for e in costs] == [-18]


def test_liskam_defense_and_unused_shield_expire_at_eight_seconds(packages):
    sim = ready_liskam(packages["liskam"])
    sim.advance(239)  # End time240 excludes expiry at240.
    assert sim.ctx.attributes.value("liskam", "def") == 200
    assert sim.ctx.resources.current("liskam", "shield_charge") == 1
    sim.advance(1)
    assert sim.ctx.attributes.value("liskam", "def") == 100
    assert sim.ctx.resources.current("liskam", "shield_charge") == 0
    hit(sim)
    assert events(sim, "damage.accepted")[-1]["payload"]["amount"] == 50
    assert sim.ctx.resources.current("liskam", "sp") == 1


def plosis_cast(package):
    sim = Engine.create(Compiler().compile(package), seed=123)
    assert sim.ctx.resources.current("plosis", "sp") == 85
    sim.advance(450)
    assert sim.ctx.resources.current("plosis", "sp") == 100
    sim.submit({"action": "activate_ability", "source": "plosis", "ability": "ability/plosis_s2_first_packet"})
    return sim


def test_plosis_first_packet_has_three_targets_and_source_predelay(packages):
    sim = plosis_cast(packages["plosis"])
    sim.advance(7)  # float0.20000000298 is native; ceil ratio gives7tick, not6.
    assert not events(sim, "healing.accepted")
    sim.advance(1)
    assert [sim.ctx.resources.current(f"ally{i}", "hp") for i in range(1, 4)] == [200, 200, 200]
    assert len(events(sim, "healing.accepted")) == 3
    assert sim.ctx.resources.current("plosis", "sp") == 0


def test_plosis_no_constant_cadence_is_falsely_substituted_for_unimplemented_ramp(packages):
    sim = plosis_cast(packages["plosis"])
    sim.advance(90)
    assert len(events(sim, "healing.accepted")) == 3
    assert "skill_cadence_ramp_not_reconstructed_from_native_FSM" in packages["plosis"]["manifest"]["metadata"]["pending_mechanics"]
    assert packages["plosis"]["abilities"][0]["metadata"]["first_packet_only"] is True


def test_plosis_fourth_friend_does_not_create_fourth_heal_and_dead_filter_applies(packages):
    data = deepcopy(packages["plosis"])
    data["scenarioDraft"]["initialEntities"].append({"definition": "unit/support_ally", "instanceAlias": "fourth", "position": {"row": 3, "col": 5}})
    sim = plosis_cast(data)
    sim.ctx.lifecycle.retire("ally1", "dead")
    sim.advance(8)
    assert {e["payload"]["target"] for e in events(sim, "healing.accepted")} == {
        sim.session.world.resolve("ally2"), sim.session.world.resolve("ally3"), sim.session.world.resolve("fourth")}


def test_liskam_shield_model_checkpoint_and_replay_are_exact(packages):
    data = deepcopy(packages["liskam"])
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = 18
    program = Compiler().compile(data)
    sim = Engine.create(program, seed=123)
    sim.submit({"action": "activate_ability", "source": "attacker", "ability": "ability/support_hit"}, at=1)
    sim.advance(1)
    checkpoint = sim.checkpoint()
    sim.advance(2)
    restored = Engine.restore(program, checkpoint)
    restored.advance(2)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None
