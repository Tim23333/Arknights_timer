"""Independent source/semantics checks for the non-executable 0-10 plan."""
from copy import deepcopy
import json

import pytest

from tools import build_mainline_dependencies as planner


@pytest.fixture(scope="module")
def plan():
    return planner.read(planner.ROOT / "packages/campaign/mainline_dependencies/level_main_00-10.json")


def test_defined_false_inherits_but_defined_zero_and_false_override():
    base = {"attributes": {"maxHp": 900, "atk": 50, "stunImmune": True}, "motion": "WALK"}
    layer = {"attributes": {"maxHp": {"m_defined": False, "m_value": 0},
                            "atk": {"m_defined": True, "m_value": 0},
                            "stunImmune": {"m_defined": True, "m_value": False}}}
    assert planner.merge_defined(base, layer) == {
        "attributes": {"maxHp": 900, "atk": 0, "stunImmune": False}, "motion": "WALK"}
    assert base["attributes"]["atk"] == 50


def test_requested_db_level_inherits_then_applies_stage_override():
    database = {"enemy/review": [
        {"level": 1, "enemyData": {"attributes": {"maxHp": {"m_defined": False, "m_value": 0},
                                                   "atk": {"m_defined": True, "m_value": 20}}}},
        {"level": 0, "enemyData": {"attributes": {"maxHp": {"m_defined": True, "m_value": 100},
                                                   "atk": {"m_defined": True, "m_value": 10}}}},
        {"level": 2, "enemyData": {"attributes": {"maxHp": {"m_defined": True, "m_value": 999}}}},
    ]}
    result = planner.resolve_enemy(database, {"useDb": True, "id": "enemy/review", "level": 1,
        "overwrittenData": {"attributes": {"atk": {"m_defined": True, "m_value": 0}}}})
    assert result["native_level"] == 1
    assert result["resolved"]["attributes"] == {"maxHp": 100, "atk": 0}
    assert [r["level"] for r in result["raw_rows"]] == [0, 1]
    with pytest.raises(ValueError, match="level is missing"):
        planner.resolve_enemy(database, {"useDb": True, "id": "enemy/review", "level": 3})


def test_first_normal_stage_has_exact_enemy_population_and_unbuffed_stats(plan):
    assert plan["difficulty"] == 1
    assert plan["spawn_count"] == 35
    assert plan["spawn_counts_by_key"] == {"enemy_1000_gopro": 14, "enemy_1027_mob": 5,
        "enemy_1030_wteeth": 2, "enemy_1007_slime": 12, "enemy_1005_yokai": 2}
    enemies = {e["native_id"]: e for e in plan["resolved_enemies"]}
    expected = {"enemy_1007_slime": (550, 130), "enemy_1027_mob": (1700, 250),
                "enemy_1030_wteeth": (5000, 500), "enemy_1000_gopro": (820, 190), "enemy_1005_yokai": (800, 0)}
    assert {key: (row["resolved"]["attributes"]["maxHp"], row["resolved"]["attributes"]["atk"])
            for key, row in enemies.items()} == expected
    assert all(row["native_level"] == 0 for row in enemies.values())
    assert enemies["enemy_1005_yokai"]["resolved"]["motion"] == "FLY"
    assert "flying" in plan["required_mechanics"]
    assert {r["difficultyMask"] for r in plan["native_runes"]} == {"FOUR_STAR"}
    assert plan["applicable_runes"] == []
    assert plan["inactive_runes"] == plan["native_runes"]
    # Challenge multipliers have not been applied to normal enemy values.
    assert enemies["enemy_1007_slime"]["resolved"]["attributes"]["maxHp"] != 660


def test_raw_control_predefine_rune_and_route_inputs_are_preserved_without_execution(plan):
    native = planner.read(planner.ROOT / "packages/campaign/native_reference/level_main_00-10.json")
    assert plan["control_counts"] == {"STORY": 1, "DISPLAY_ENEMY_INFO": 1}
    assert plan["native_wave_script"] == native["waves"]
    assert plan["native_predefines"] == native["predefines"]
    assert plan["native_runes"] == native["runes"]
    assert plan["native_options"] == native["options"]
    assert all(route == native["routes"][int(index)] for index, route in plan["used_routes"].items())
    assert plan["runnable"] is plan["model_validated"] is False


def test_map_palette_uses_index_matrix_and_route_conversion_remains_a_plan():
    native = {"mapData": {"map": [[1, 0], [0, 1]], "tiles": [
        {"tileKey": "tile_road", "buildableType": "MELEE", "passableMask": "WALK_ONLY", "heightType": "LOWLAND"},
        {"tileKey": "tile_wall", "buildableType": "RANGED", "passableMask": "FLY_ONLY", "heightType": "HIGHLAND"}]}}
    mapped = planner.map_plan(native)
    assert (mapped["rows"], mapped["cols"]) == (2, 2)
    assert [t["tileKey"] for t in mapped["tiles"]] == ["tile_wall", "tile_road", "tile_road", "tile_wall"]
    assert [t["passableMask"] for t in mapped["tiles"]] == [2, 1, 1, 2]
    assert "rows-1-row" in mapped["coordinate_conversion"]
    assert native["mapData"]["map"] == [[1, 0], [0, 1]]


def test_all_selected_skills_and_talents_remain_pending_without_placeholder_abilities(plan):
    expected = ["skchr_myrtle_2", "skchr_bpipe_3", "skchr_chen_1", "skchr_liskam_1", "skchr_demkni_3",
                "skchr_plosis_2", "skchr_angel_3", "skchr_amgoat_3", "skchr_kalts_3", "skchr_lisa_3",
                "skchr_weedy_3", "skchr_cgbird_3"]
    assert [r["selected_skill"]["skill_id"] for r in plan["roster"]] == expected
    assert all("selected_skill:" + skill in plan["required_mechanics"] for skill in expected)
    assert all(r["talents"] and r["gaps"] for r in plan["roster"])
    assert "abilities" not in plan
    assert "selected_skill_models_partial_not_native_complete" in plan["pending_conversion"]
    assert len(plan["available_selected_skill_models"]) == 12
    assert all(r["native_complete"] is False for r in plan["available_selected_skill_models"])
    assert "fixed_roster_talents_and_native_attack_clocks_not_fully_converted" in plan["pending_conversion"]
    assert plan["first_skill_prototype_status"] == "partially_implemented"
    assert plan["status"] == "dependencies_resolved_not_executable"


def test_changed_database_cannot_keep_pinned_provenance_claim(tmp_path):
    database = planner.read(planner.DEFAULT_DB)
    database["enemy_1007_slime"][0]["enemyData"]["attributes"]["maxHp"]["m_value"] = 999999
    path = tmp_path / "modified_enemy_database.json"
    path.write_text(json.dumps(database), encoding="utf-8")
    with pytest.raises(ValueError, match="(?i)identity|pin|source|provenance"):
        planner.build(database_path=path)


def test_first_plan_matches_frozen_source_and_pinned_database_lock(plan):
    lock_path = planner.ROOT / "packages/campaign/enemy_sources.lock.json"
    lock = planner.read(lock_path)
    assert lock["commit"] == plan["source"]["commit"] == "56aee3d6c5a29c3a0d192456d70d14252cbb0804"
    assert lock["sha256"] == plan["source"]["enemy_database_sha256"] == planner.sha(planner.DEFAULT_DB)
    assert planner.sha(lock_path) == plan["source"]["enemy_source_lock_sha256"]
    assert plan == planner.build()
