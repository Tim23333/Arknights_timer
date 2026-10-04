"""Real live-member aura prototypes, with independent values and boundaries."""
from copy import deepcopy

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from ark_sim.tools.compare import first_difference
from tools.build_aura_skill_recipes import ROOT, IDS, build, read


@pytest.fixture(scope="module")
def packages():
    return {name: read(ROOT / f"packages/campaign/skills.{name}.json") for name in IDS}


def start(package, name):
    data = deepcopy(package)
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = data["entities"][0]["components"]["resources"]["sp"]["capacity"]
    sim = Engine.create(Compiler().compile(data), seed=73)
    sim.submit({"action": "activate_ability", "source": "caster", "ability": f"ability/{name}_s3"})
    sim.advance(1)
    assert sim.ctx.resources.current("caster", "sp") == 0
    return sim


def move(sim, alias, entering):
    sim.submit({"action": "activate_ability", "source": alias, "ability": "ability/aura_enter" if entering else "ability/aura_leave"})
    sim.advance(1)


def events(sim, kind):
    return [e for e in sim.session.events if e["type"] == kind]


@pytest.mark.parametrize("name", list(IDS))
def test_source_builds_match_and_complete_claim_is_rejected(packages, name):
    assert build(name) == packages[name]
    assert packages[name]["status"] == "partially_implemented"
    with pytest.raises(ValueError, match="complete.*unsupported"):
        build(name, require_complete=True)
    Compiler().compile(packages[name])


def test_demkni_each_pulse_queries_current_injured_allies_and_effective_source_attack(packages):
    sim = start(packages["demkni"], "demkni")
    assert sim.ctx.attributes.value("enemy", "move_speed") == pytest.approx(0.4)
    assert sim.ctx.attributes.value("enemy", "arts_factor") == pytest.approx(1.55)
    sim.advance(16)
    assert sim.ctx.resources.current("ally", "hp") == 135
    assert [(e["time"], e["payload"]["amount"]) for e in events(sim, "healing.accepted")] == [(16, 35)]
    move(sim, "ally", False)
    sim.advance(30)
    assert sim.ctx.resources.current("ally", "hp") == 135
    move(sim, "ally", True)
    sim.advance(30)
    assert sim.ctx.resources.current("ally", "hp") == 170
    assert all(e["payload"]["target"] == sim.session.world.resolve("ally") for e in events(sim, "healing.accepted"))


@pytest.mark.parametrize("kind,expected", [("arts", 155), ("physical", 100), ("true", 100)])
def test_demkni_amplification_applies_only_to_arts_with_live_exit_cleanup(packages, kind, expected):
    data = deepcopy(packages["demkni"])
    next(a for a in data["abilities"] if a["id"] == "ability/aura_probe")["timeline"][0]["effect"]["damage_type"] = kind
    sim = start(data, "demkni")
    sim.submit({"action": "activate_ability", "source": "attacker", "ability": "ability/aura_probe"})
    sim.advance(1)
    assert events(sim, "damage.accepted")[-1]["payload"]["amount"] == pytest.approx(expected)
    move(sim, "enemy", False)
    assert sim.ctx.attributes.value("enemy", "move_speed") == 1
    assert sim.ctx.attributes.value("enemy", "arts_factor") == 1
    sim.submit({"action": "activate_ability", "source": "attacker", "ability": "ability/aura_probe"})
    sim.advance(1)
    assert events(sim, "damage.accepted")[-1]["payload"]["amount"] == 100


def test_lisa_regeneration_distinct_from_healing_and_rejoining_restarts_member_timer(packages):
    sim = start(packages["lisa"], "lisa")
    assert sim.ctx.buffs.controls("caster")["attack"] is False
    sim.advance(29)
    assert sim.ctx.resources.current("ally", "hp") == 100
    sim.advance(1)
    assert sim.ctx.resources.current("ally", "hp") == 120
    assert not events(sim, "healing.accepted")
    assert any(e["payload"]["target"] == sim.session.world.resolve("ally") for e in events(sim, "regeneration.accepted"))
    move(sim, "ally", False)
    sim.advance(30)
    assert sim.ctx.resources.current("ally", "hp") == 120
    move(sim, "ally", True)
    sim.advance(30)
    assert sim.ctx.resources.current("ally", "hp") == 140


def test_lisa_member_regeneration_uses_effective_source_attack_after_modification(packages):
    data = deepcopy(packages["lisa"])
    data["buffs"].append({"id": "buff/review_attack", "kind": "buff", "duration_seconds": 2,
        "modifiers": [{"attribute": "atk", "layer": "flat", "value": 50}]})
    data["scenarioDraft"]["dependencies"] = ["buff/review_attack"]
    sim = start(data, "lisa")
    sim.ctx.buffs.apply("caster", "caster", "buff/review_attack")
    sim.advance(30)
    assert sim.ctx.resources.current("ally", "hp") == 130


def test_cgbird_res_and_self_attack_enter_leave_and_restore_dynamically(packages):
    sim = start(packages["cgbird"], "cgbird")
    assert sim.ctx.attributes.value("caster", "atk") == 180
    assert sim.ctx.attributes.value("ally", "mres") == 25
    sim.submit({"action": "activate_ability", "source": "attacker", "ability": "ability/aura_probe"})
    sim.advance(1)
    assert events(sim, "damage.accepted")[-1]["payload"]["amount"] == 75
    move(sim, "ally", False)
    assert sim.ctx.attributes.value("ally", "mres") == 10
    move(sim, "ally", True)
    assert sim.ctx.attributes.value("ally", "mres") == 25
    sim.ctx.lifecycle.retire("caster", "withdrawn")
    sim.advance(1)
    assert sim.ctx.attributes.value("ally", "mres") == 10
    assert not sim.ctx.get("ally", ("buffs", "instances"))


@pytest.mark.parametrize("name", list(IDS))
def test_aura_source_death_detaches_members_and_future_periodic_effects(packages, name):
    sim = start(packages[name], name)
    before = sim.ctx.resources.current("ally", "hp")
    sim.ctx.resources.adjust("caster", "hp", -5000)
    sim.advance(35)
    assert sim.ctx.resources.current("ally", "hp") == before
    assert not sim.ctx.get("ally", ("buffs", "instances"))
    assert not sim.ctx.get("enemy", ("buffs", "instances"))


def test_lisa_overlapping_casters_keep_independent_members_and_remove_only_one_parent(packages):
    data = deepcopy(packages["lisa"])
    data["scenarioDraft"]["initialEntities"].append({"definition": data["entities"][0]["id"], "instanceAlias": "second", "position": {"row": 5, "col": 4},
        "components": {"resources": {"sp": {"initial": 70}}}})
    sim = start(data, "lisa")
    sim.submit({"action": "activate_ability", "source": "second", "ability": "ability/lisa_s3"})
    sim.advance(1)
    children = [b for b in sim.ctx.get("ally", ("buffs", "instances")) if b["definition"] == "buff/lisa_member"]
    assert len(children) == 2 and len({b["aura_parent"] for b in children}) == 2
    sim.ctx.buffs.remove("caster", "buff/lisa_emitter")
    children = [b for b in sim.ctx.get("ally", ("buffs", "instances")) if b["definition"] == "buff/lisa_member"]
    assert len(children) == 1 and children[0]["source"] == sim.session.world.resolve("second")


def test_lisa_half_open_expiry_cleans_member_before_terminal_periodic_tick(packages):
    sim = start(packages["lisa"], "lisa")
    sim.advance(1049)
    assert sim.ctx.resources.current("ally", "hp") == 780  # 34*20 in the documented half-open prototype.
    assert sim.ctx.buffs.controls("caster")["attack"] is True
    sim.advance(1)
    assert not sim.ctx.get("ally", ("buffs", "instances"))
    assert sim.ctx.resources.current("ally", "hp") == 780
    assert sim.ctx.resources.current("caster", "sp") == 0


@pytest.mark.parametrize("name", list(IDS))
def test_live_aura_membership_and_pending_jobs_restore_and_replay_exactly(packages, name):
    data = deepcopy(packages[name])
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = data["entities"][0]["components"]["resources"]["sp"]["capacity"]
    program = Compiler().compile(data)
    sim = Engine.create(program, seed=73)
    sim.submit({"action": "activate_ability", "source": "caster", "ability": f"ability/{name}_s3"}, at=0)
    sim.submit({"action": "activate_ability", "source": "ally", "ability": "ability/aura_leave"}, at=35)
    sim.submit({"action": "activate_ability", "source": "ally", "ability": "ability/aura_enter"}, at=65)
    sim.advance(50)
    checkpoint = sim.checkpoint()
    sim.advance(45)
    restored = Engine.restore(program, checkpoint)
    restored.advance(45)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None
