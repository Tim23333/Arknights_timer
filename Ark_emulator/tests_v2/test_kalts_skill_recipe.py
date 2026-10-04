"""Native source recovery and actual owned-token/curve/damage model checks."""
from copy import deepcopy
import base64
import hashlib
import json
import struct

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from ark_sim.tools.compare import first_difference
from tools.build_kalts_skill_recipe import ROOT, OUTPUT, HOST_SKILL, TOKEN_SKILL, build, decode_bson_document


@pytest.fixture(scope="module")
def package():
    return json.loads(OUTPUT.read_bytes())


def events(sim, kind):
    return [e for e in sim.session.events if e["type"] == kind]


def pet(sim, host="host"):
    owner = sim.session.world.resolve(host)
    owned = [e["id"] for e in sim.session.world.entities() if e["definition_id"] == "unit/kalts_mon3tr_model"
             and e["components"].get("ownership", {}).get("owner") == owner and sim.ctx.alive(e["id"])]
    assert len(owned) == 1
    return owned[0]


def initialized(package, active=False):
    data = deepcopy(package)
    if active:
        data["entities"][0]["components"]["resources"]["sp"]["initial"] = 15
    sim = Engine.create(Compiler().compile(data), seed=23)
    sim.submit({"action": "activate_ability", "source": "host", "ability": "ability/kalts_summon"}, at=0)
    if active:
        sim.submit({"action": "activate_ability", "source": "host", "ability": HOST_SKILL}, at=0)
    sim.advance(1)
    return sim


def test_build_matches_sources_and_no_official_token_skill_id_is_invented(package):
    assert build() == package
    native = package["manifest"]["metadata"]["native_source"]
    assert native["token_skill_id_slots"] == [None, None, None]
    assert native["token_stats"]["model"]["maxHp"] == 5177
    assert native["token_stats"]["model"]["atk"] == 1345
    assert native["token_stats"]["model"]["def"] == 389
    assert native["token_stats"]["model"]["cost"] == 10
    assert native["token_stats"]["model"]["respawnTime"] == 25
    assert native["token_asset_audit"]["textasset_count"] == 0
    assert package["status"] == "partially_implemented"
    with pytest.raises(ValueError, match="complete.*unsupported"):
        build(require_complete=True)


def test_native_bson_subset_bytes_and_remaining_ratio_kill_marker_nodes(package):
    selected = package["manifest"]["metadata"]["native_source"]["templates"]["templates"]
    for data in selected.values():
        raw = base64.b64decode(data["bson_document_base64"], validate=True)
        assert hashlib.sha256(raw).hexdigest() == data["bson_document_sha256"]
        assert decode_bson_document(raw)[0] == data["parsed"]
    ratio = selected["kalts_s_3[ratio_atk]"]["parsed"]
    node = ratio["eventToActions"]["ON_BUFF_TRIGGER"][0]
    assert node["$type"].endswith("RemainingRatioToAttributeModifier, Assembly-CSharp")
    assert (node["_attributeType"], node["_formulaType"], node["_isInversed"], node["_endTime"]) == ("ATK", "MULTIPLIER", False, 0)
    assert "ON_TARGET_KILLED" in selected["kalts_token[finish_kill_mark]"]["parsed"]["eventToActions"]


@pytest.mark.parametrize("raw", [b"", struct.pack("<i", 4), b"\x05\x00\x00\x00x", b"\x05\x00\x00\x00\x00x"])
def test_bson_rejects_truncation_bad_terminator_and_trailing_data(raw):
    with pytest.raises(ValueError):
        decode_bson_document(raw)


def test_owned_spawn_cost_capacity_and_failed_second_spawn_are_atomic(package):
    sim = initialized(package)
    token = pet(sim)
    assert sim.ctx.get(token, ("ownership", "owner")) == sim.session.world.resolve("host")
    assert sim.ctx.resources.current("system/battle", "dp") == 10
    sim.submit({"action": "activate_ability", "source": "host", "ability": "ability/kalts_summon"})
    sim.advance(1)
    assert len(sim.ctx.spatial.select("host", "selector/owned_mon3tr")) == 1
    assert sim.ctx.resources.current("system/battle", "dp") == 10
    assert events(sim, "command.rejected")


def test_host_sp_stops_without_token_and_clears_when_token_dies(package):
    sim = Engine.create(Compiler().compile(package), seed=23)
    sim.advance(60)
    assert sim.ctx.resources.current("host", "sp") == 0
    sim.submit({"action": "activate_ability", "source": "host", "ability": "ability/kalts_summon"})
    sim.advance(451)
    assert sim.ctx.resources.current("host", "sp") == 15
    sim.ctx.resources.adjust(pet(sim), "hp", -5177)
    sim.advance(4)
    assert sim.ctx.resources.current("host", "sp") == 0


def test_host_requires_its_own_live_token_before_payment(package):
    data = deepcopy(package)
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = 15
    data["scenarioDraft"]["initialEntities"].append({"definition": data["entities"][0]["id"], "instanceAlias": "other", "position": {"row": 3, "col": 4}})
    sim = initialized(data)
    token = pet(sim)
    sim.submit({"action": "activate_ability", "source": "other", "ability": HOST_SKILL})
    sim.advance(1)
    assert sim.ctx.spatial.select("other", "selector/owned_mon3tr") == []
    assert sim.ctx.resources.current(token, "mode") == 0
    assert not [e for e in events(sim, "ability.started") if e["payload"]["ability"] == HOST_SKILL]


def test_s3_host_token_linkage_and_remaining_ratio_is_not_constant(package):
    sim = initialized(package, True)
    token = pet(sim)
    assert sim.ctx.resources.current("host", "sp") == 0
    assert sim.ctx.resources.current(token, "mode") == 1
    assert sim.ctx.attributes.value(token, "def") == 1167
    starts = [e["payload"]["ability"] for e in events(sim, "ability.started")]
    assert HOST_SKILL in starts and TOKEN_SKILL in starts
    sim.advance(299)
    assert sim.ctx.attributes.value(token, "atk") == pytest.approx(3093.5)  # 1345*(1+2.6*.5), t10.
    sim.advance(270)
    assert sim.ctx.attributes.value(token, "atk") == pytest.approx(1519.85)  # t19.


def test_true_attack_probe_ignores_armor_and_host_sp_does_not_charge_during_skill(package):
    sim = initialized(package, True)
    token = pet(sim)
    sim.submit({"action": "activate_ability", "source": token, "ability": "ability/mon3tr_true_probe"})
    sim.advance(1)
    amount = events(sim, "damage.accepted")[-1]["payload"]["amount"]
    assert amount == pytest.approx(1345 * (1 + 2.6 * (599/600)))
    sim.advance(30)
    assert sim.ctx.resources.current("host", "sp") == 0


def test_def_zero_outside_host_range_overrides_even_s3_bonus(package):
    sim = initialized(package, True)
    token = pet(sim)
    sim.submit({"action": "activate_ability", "source": token, "ability": "ability/token_leave"})
    sim.advance(1)
    assert sim.ctx.attributes.value(token, "def") == 0
    sim.submit({"action": "activate_ability", "source": token, "ability": "ability/token_enter"})
    sim.advance(1)
    assert sim.ctx.attributes.value(token, "def") == 1167


def test_no_kill_penalty_is_half_max_hp_at_expiry_and_normal_mode_restores(package):
    sim = initialized(package, True)
    token = pet(sim)
    sim.advance(599)
    assert sim.ctx.resources.current(token, "hp") == 5177
    sim.advance(1)
    assert sim.ctx.resources.current(token, "hp") == 2588.5
    assert sim.ctx.resources.current(token, "mode") == 0
    assert sim.ctx.attributes.value(token, "atk") == 1345
    assert sim.ctx.attributes.value(token, "def") == 389
    injured = initialized(package, True)
    other_token = pet(injured)
    injured.ctx.resources.adjust(other_token, "hp", -1177)
    injured.advance(600)
    assert injured.ctx.resources.current(other_token, "hp") == 1411.5  # 4000 - .5*5177, not .5*currentHP.


def test_own_token_kill_clears_marker_and_skips_penalty(package):
    data = deepcopy(package)
    data["entities"][2]["components"]["resources"]["hp"]["initial"] = 100
    sim = initialized(data, True)
    token = pet(sim)
    sim.submit({"action": "activate_ability", "source": token, "ability": "ability/mon3tr_true_probe"})
    sim.advance(1)
    assert sim.ctx.resources.current(token, "no_kill") == 0
    sim.advance(599)
    assert sim.ctx.resources.current(token, "hp") == 5177


def test_historical_attribute_snapshot_uses_captured_curve_clock(package):
    sim = initialized(package, True)
    token = pet(sim)
    snapshot = sim.ctx.capture_view(token)
    captured = sim.ctx.attributes.value(token, "atk", snapshot=snapshot)
    sim.advance(300)
    assert sim.ctx.attributes.value(token, "atk") < captured
    assert sim.ctx.attributes.value(token, "atk", snapshot=snapshot) == captured


def test_delayed_at_cast_hit_does_not_recompute_decay_at_hit_clock(package):
    data = deepcopy(package)
    ability = deepcopy(next(a for a in data["abilities"] if a["id"] == "ability/mon3tr_true_probe"))
    ability["id"] = "ability/review_delayed_at_cast"
    ability["timeline"][0]["at"] = 300
    ability["timeline"][0]["effect"]["read_mode"]["source_attributes"] = "at_cast"
    data["abilities"].append(ability)
    data["entities"][1]["components"]["abilities"].append(ability["id"])
    sim = initialized(data, True)
    token = pet(sim)
    expected = 1345 * (1 + 2.6 * (599/600))  # Cast at tick1, not the later hit tick301.
    sim.submit({"action": "activate_ability", "source": token, "ability": ability["id"]})
    sim.advance(301)
    damage = [e for e in events(sim, "damage.accepted") if e["payload"]["ability"] == ability["id"]]
    assert [e["time"] for e in damage] == [301]
    assert damage[0]["payload"]["amount"] == pytest.approx(expected)
    assert sim.ctx.attributes.value(token, "atk") < expected


def test_another_unit_kill_does_not_clear_mon3tr_no_kill_marker(package):
    data = deepcopy(package)
    data["entities"][2]["components"]["resources"]["hp"]["initial"] = 50
    helper = deepcopy(data["entities"][2])
    helper.update(id="unit/review_helper", tags=["player"])
    helper["components"]["attributes"]["base"]["atk"] = 1000
    helper["components"]["abilities"] = ["ability/review_helper_kill"]
    data["entities"].append(helper)
    data["abilities"].append({"id": "ability/review_helper_kill", "kind": "ability", "activation": {"mode": "manual"},
        "selector": "selector/token_melee", "timeline": [{"at": 0, "effect": {"op": "damage", "damage_type": "true"}}]})
    data["scenarioDraft"]["initialEntities"].append({"definition": helper["id"], "instanceAlias": "helper", "position": {"row": 4, "col": 5}})
    sim = initialized(data, True)
    token = pet(sim)
    sim.submit({"action": "activate_ability", "source": "helper", "ability": "ability/review_helper_kill"})
    sim.advance(1)
    assert not sim.ctx.alive("enemy")
    assert sim.ctx.resources.current(token, "no_kill") == 1
    sim.advance(599)
    assert sim.ctx.resources.current(token, "hp") == 2588.5


def test_host_retire_retires_owned_token_and_disables_host_skill(package):
    sim = initialized(package, True)
    token = pet(sim)
    sim.ctx.lifecycle.retire("host", "withdrawn")
    assert not sim.ctx.alive(token)
    assert not sim.ctx.alive("host")
    assert sim.ctx.spatial.select("host", "selector/owned_mon3tr") == []


def test_model_checkpoint_and_input_replay_are_exact(package):
    data = deepcopy(package)
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = 15
    program = Compiler().compile(data)
    sim = Engine.create(program, seed=23)
    sim.submit({"action": "activate_ability", "source": "host", "ability": "ability/kalts_summon"}, at=0)
    sim.submit({"action": "activate_ability", "source": "host", "ability": HOST_SKILL}, at=0)
    sim.advance(20)
    token = pet(sim)
    sim.submit({"action": "activate_ability", "source": token, "ability": "ability/mon3tr_true_probe"}, at=100)
    checkpoint = sim.checkpoint()
    sim.advance(620)
    restored = Engine.restore(program, checkpoint)
    restored.advance(620)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None
