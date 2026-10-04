"""Real V2 composition tests; synthetic attributes do not validate a native unit."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from ark_sim.tools.compare import first_difference
from tools.build_campaign_skills import OUTPUT, SKILL, build


@pytest.fixture(scope="module")
def package():
    return json.loads(OUTPUT.read_bytes())


def simulation(package):
    return Engine.create(Compiler().compile(package), seed=123)


def charged(package):
    sim = simulation(package)
    assert sim.ctx.resources.current("myrtle", "sp") == 10
    sim.advance(420)  # Fourteen native SP periods, independent expected count.
    assert sim.ctx.resources.current("myrtle", "sp") == 24
    sim.submit({"action": "activate_ability", "source": "myrtle", "ability": SKILL})
    return sim


def events(sim, kind):
    return [e for e in sim.session.events if e["type"] == kind]


def test_builder_matches_frozen_prefab_charpack_and_compiled_prototype(package):
    assert build() == package
    assert package["status"] == "partially_implemented"
    assert package["manifest"]["metadata"]["official_unit_config_imported"] is False
    assert package["scenarioDraft"]["metadata"]["not_formal_mainline"] is True
    Compiler().compile(package)


def test_unimplemented_selected_skill_is_rejected_without_damage_substitution():
    with pytest.raises(ValueError, match="skchr_kalts_3.*not implemented|not implemented.*skchr_kalts_3"):
        build("char_003_kalts")


def test_initial_sp_insufficient_cast_is_rejected_without_payment(package):
    sim = simulation(package)
    sim.submit({"action": "activate_ability", "source": "myrtle", "ability": SKILL})
    sim.advance(1)
    assert sim.ctx.resources.current("myrtle", "sp") == 10
    assert events(sim, "command.rejected")
    assert sim.ctx.resources.current("system/battle", "dp") == 0


def test_native_dp_first_wait_and_sixteen_period_endpoint(package):
    sim = charged(package)
    sim.advance(30)  # Executes [420,450); first DP task is at450.
    assert sim.ctx.resources.current("system/battle", "dp") == 0
    assert sim.ctx.resources.current("myrtle", "sp") == 0
    sim.advance(1)
    assert sim.ctx.resources.current("system/battle", "dp") == 1
    sim.advance(449)  # End time900 excludes the t900 endpoint.
    assert sim.ctx.resources.current("system/battle", "dp") == 15
    sim.advance(1)
    assert sim.ctx.resources.current("system/battle", "dp") == 16
    changes = [e for e in events(sim, "resource.changed") if e["payload"]["resource"] == "dp"]
    assert [e["time"] for e in changes] == list(range(450, 901, 30))
    assert [e["payload"]["delta"] for e in changes] == [1] * 16


def test_mode2_heal_predelay_single_target_and_half_open_duration(package):
    sim = charged(package)
    sim.advance(16)  # [420,436) excludes first hit, ceil(.533/(1/30))=16.
    assert sim.ctx.resources.current("ally", "hp") == 100
    sim.advance(1)
    assert sim.ctx.resources.current("ally", "hp") == 150
    sim.advance(463)  # t900: all16 healing tasks, no endpoint heal.
    healing = events(sim, "healing.accepted")
    assert [e["time"] for e in healing] == list(range(436, 900, 30))
    assert [e["payload"]["amount"] for e in healing] == [50] * 16
    assert sim.ctx.resources.current("ally", "hp") == 900
    assert {e["payload"]["target"] for e in healing} == {sim.session.world.resolve("ally")}


def test_each_heal_reselects_lowest_hp_ratio_and_ignores_outside_range(package):
    data = deepcopy(package)
    data["scenarioDraft"]["initialEntities"].extend([
        {"definition": "unit/campaign_myrtle_ally", "instanceAlias": "second", "position": {"row": 1, "col": 2}},
        {"definition": "unit/campaign_myrtle_ally", "instanceAlias": "outside", "position": {"row": 0, "col": 0}},
    ])
    sim = charged(data)
    sim.advance(47)  # First two heal hits select injured ties by stable entity ID.
    assert sim.ctx.resources.current("ally", "hp") == 150
    assert sim.ctx.resources.current("second", "hp") == 150
    assert sim.ctx.resources.current("outside", "hp") == 100
    assert len(events(sim, "healing.accepted")) == 2


def test_injured_caster_can_heal_self_and_dead_friend_cannot_be_selected(package):
    data = deepcopy(package)
    data["entities"][0]["components"]["resources"]["hp"]["initial"] = 100
    data["entities"][1]["components"]["lifecycle"] = {"policy": "policy/ark_lifecycle"}
    sim = charged(data)
    sim.ctx.resources.adjust("ally", "hp", -100)
    assert not sim.ctx.alive("ally")
    sim.advance(17)
    assert sim.ctx.resources.current("myrtle", "hp") == 150
    assert sim.ctx.resources.current("ally", "hp") == 0
    assert [e["payload"]["target"] for e in events(sim, "healing.accepted")] == [sim.session.world.resolve("myrtle")]


def test_stop_attack_zero_block_and_restore_with_sp_freeze(package):
    sim = charged(package)
    sim.advance(1)
    assert sim.ctx.attributes.value("myrtle", "block_count") == 0
    sim.advance(479)
    assert sim.ctx.resources.current("myrtle", "sp") == 0
    assert not [e for e in events(sim, "damage.accepted") if 420 <= e["time"] < 900]
    sim.advance(2)
    assert sim.ctx.attributes.value("myrtle", "block_count") == 1
    assert [e for e in events(sim, "damage.accepted") if e["time"] >= 900]
    assert sim.ctx.resources.current("myrtle", "sp") == 0
    sim.advance(29)
    assert sim.ctx.resources.current("myrtle", "sp") == 1


def test_no_injured_ally_does_not_cancel_dp_or_pay_again(package):
    data = deepcopy(package)
    data["entities"][1]["components"]["resources"]["hp"]["initial"] = 2000
    sim = charged(data)
    sim.advance(481)
    assert sim.ctx.resources.current("system/battle", "dp") == 16
    assert sim.ctx.resources.current("myrtle", "sp") == 0
    assert not events(sim, "healing.accepted")


def test_checkpoint_continuation_and_input_replay_preserve_exact_model(package):
    program = Compiler().compile(package)
    sim = Engine.create(program, seed=123)
    sim.submit({"action": "activate_ability", "source": "myrtle", "ability": SKILL}, at=420)
    sim.advance(600)
    checkpoint = sim.checkpoint()
    sim.advance(450)
    expected = sim.snapshot()
    resumed = Engine.restore(program, checkpoint)
    resumed.advance(450)
    assert first_difference(expected, resumed.snapshot()) is None
    assert first_difference(expected, replay(program, sim.export_replay()).snapshot()) is None
