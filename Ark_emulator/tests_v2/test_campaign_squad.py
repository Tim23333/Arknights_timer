"""Actual fixed unit stats joined to selected-skill closures, not fixture stats."""
from copy import deepcopy
import json

import pytest

from ark_sim import Compiler, Engine
from tools.build_campaign_squad import BINDINGS, OUTPUT, build


def exercise():
    data = deepcopy(build())
    data["entities"].append({"id": "unit/squad_enemy", "kind": "entity", "tags": ["enemy", "ground"], "components": {
        "attributes": {"base": {"max_hp": 100000, "def": 0, "mres": 0, "mass_level": 0, "move_speed": 0, "arts_factor": 1}},
        "resources": {"hp": {"initial": 100000, "capacity": 100000, "role": "health"}},
        "lifecycle": {"policy": "policy/ark_lifecycle"}, "spatial": {}}})
    data["scenarioDraft"] = {"id": "scenario/squad_exercise", "ruleset": "ruleset/ark_standard",
        "map": {"rows": 9, "cols": 14}, "resources": {"dp": {"initial": 50, "capacity": 99}},
        "roster": ["unit/"+cid for cid in BINDINGS], "initialEntities": []}
    return data


def test_squad_has_twelve_actual_configs_skills_and_no_synthetic_unit_leaks():
    data = build()
    assert json.loads(OUTPUT.read_text(encoding="utf-8")) == data
    actors = [e for e in data["entities"] if "campaign_roster" in e.get("tags", [])]
    assert len(actors) == 12
    assert {e["metadata"]["native_id"] for e in actors} == set(BINDINGS)
    assert all(e["metadata"]["selected_skill_ability"] in e["components"]["abilities"] for e in actors)
    assert all(e["metadata"]["talent_models_integrated"] for e in actors)
    assert all(e["metadata"]["config"]["level"] == 70 and not e["metadata"]["complete_operator"] for e in actors)
    assert all("fixture" not in e["id"] and "probe" not in e["id"] for e in data["entities"])
    assert not {"ability/token_leave", "ability/token_enter", "ability/aura_leave", "ability/aura_enter"} & {a["id"] for a in data["abilities"]}
    assert data["manifest"]["metadata"]["complete_operator_count"] == 0
    Compiler().compile(exercise())


def test_fixed_base_stats_survive_all_selected_fixture_merges():
    actors = {e["metadata"]["native_id"]: e for e in build()["entities"] if "campaign_roster" in e.get("tags", [])}
    assert actors["char_151_myrtle"]["components"]["attributes"]["base"]["atk"] == 520
    assert actors["char_103_angel"]["components"]["attributes"]["base"]["atk"] == 607
    assert actors["char_003_kalts"]["components"]["attributes"]["base"]["max_hp"] == 1996
    assert actors["char_400_weedy"]["components"]["attributes"]["base"]["max_hp"] == 2027
    assert actors["char_010_chen"]["components"]["attributes"]["base"]["attack_interval"] == 1.3


def test_myrtle_selected_skill_heals_using_real_attack_and_restores_real_block():
    data = exercise()
    data["scenarioDraft"]["initialEntities"] = [
        {"definition": "unit/char_151_myrtle", "instanceAlias": "myrtle", "position": {"row": 4, "col": 4},
            "components": {"resources": {"sp": {"initial": 24}}}},
        {"definition": "unit/char_222_bpipe", "instanceAlias": "ally", "position": {"row": 4, "col": 5},
            "components": {"resources": {"hp": {"initial": 100}}}},
    ]
    sim = Engine.create(Compiler().compile(data))
    sim.submit({"action": "skill", "source": "myrtle", "ability": "ability/campaign_myrtle_s2"})
    sim.session.advance(17)
    # Skill packet is still real ATK*.5; the now-integrated live talent also
    # contributes 25 HP/s at t=1..16, rather than silently being omitted.
    assert sim.ctx.resources.current("ally", "hp") == pytest.approx(100+260+16*25/30)
    assert [e["payload"]["amount"] for e in sim.session.events if e["type"] == "healing.accepted"
            and e["payload"]["target"] == sim.session.world.resolve("ally")] == [260]
    assert sim.ctx.attributes.value("myrtle", "block_count") == 0
    assert sim.ctx.resources.current("system/battle", "dp") == 50


def test_integrated_weedy_uses_real_stats_and_owned_cannon_definition():
    data = exercise()
    data["scenarioDraft"]["initialEntities"] = [{"definition": "unit/char_400_weedy", "instanceAlias": "weedy", "position": {"row": 3, "col": 2}}]
    sim = Engine.create(Compiler().compile(data))
    sim.submit({"action": "skill", "source": "weedy", "ability": "ability/campaign_weedy_deploy_cannon",
        "payload": {"position": {"row": 3, "col": 3}, "facing": "right"}})
    sim.session.advance(1)
    owned = [e for e in sim.session.world.entities() if e["components"].get("ownership", {}).get("owner") == sim.session.world.resolve("weedy")]
    assert len(owned) == 1
    assert sim.ctx.attributes.value(owned[0]["id"], "atk") == 561
    assert sim.ctx.resources.current("system/battle", "dp") == 45


def test_support_time_aura_accelerates_attack_side_time_sp_and_preserves_event_sp():
    data = exercise()
    data["scenarioDraft"]["initialEntities"] = [
        {"definition": "unit/char_128_plosis", "instanceAlias": "plosis", "position": {"row": 3, "col": 2}},
        {"definition": "unit/char_151_myrtle", "instanceAlias": "myrtle", "position": {"row": 4, "col": 2}},
        {"definition": "unit/char_010_chen", "instanceAlias": "chen", "position": {"row": 4, "col": 3}}]
    sim = Engine.create(Compiler().compile(data))
    assert sim.ctx.resources.current("myrtle", "sp") == 16  # Bagpipe stays in the deck.
    sim.session.advance(31)
    assert sim.ctx.resources.current("myrtle", "sp") == pytest.approx(17.3)
    assert sim.ctx.resources.current("chen", "sp") == 0  # attack SP isn't converted to time SP.


def test_owned_payload_deployment_payment_is_actual_and_refundable_once():
    data = exercise()
    data["scenarioDraft"]["initialEntities"] = [
        {"definition": "unit/char_400_weedy", "instanceAlias": "weedy", "position": {"row": 3, "col": 2}}]
    sim = Engine.create(Compiler().compile(data))
    sim.submit({"action": "skill", "source": "weedy", "ability": "ability/campaign_weedy_deploy_cannon",
        "payload": {"position": {"row": 3, "col": 3}, "facing": "right"}})
    sim.session.advance(1)
    child = next(e for e in sim.session.world.entities() if e["components"].get("ownership", {}).get("owner") == sim.session.world.resolve("weedy"))
    assert child["components"]["deployable"]["paid_cost"] == 5
    assert sim.ctx.resources.current("system/battle", "dp") == 45
    assert len([e for e in sim.session.events if e["type"] == "deployment.payment_allocated"]) == 1
