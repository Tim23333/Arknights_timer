"""Native sparse inheritance and the first actual campaign dependency closure."""
import pytest

from tools.build_mainline_dependencies import build, merge_defined, resolve_enemy


def test_defined_zero_and_false_override_but_undefined_values_inherit():
    result = merge_defined({"atk": 10, "flag": True, "def": 20}, {
        "atk": {"m_defined": True, "m_value": 0},
        "flag": {"m_defined": True, "m_value": False},
        "def": {"m_defined": False, "m_value": 0}})
    assert result == {"atk": 0, "flag": False, "def": 20}


def test_native_enemy_level_inherits_base_and_applies_stage_override_last():
    database = {"enemy/probe": [
        {"level": 0, "enemyData": {"attributes": {"maxHp": {"m_defined": True, "m_value": 100},
            "atk": {"m_defined": True, "m_value": 10}}}},
        {"level": 1, "enemyData": {"attributes": {"atk": {"m_defined": True, "m_value": 0}}}}]}
    result = resolve_enemy(database, {"id": "enemy/probe", "useDb": True, "level": 1,
        "overwrittenData": {"attributes": {"maxHp": {"m_defined": True, "m_value": 200}}}})
    assert result["resolved"]["attributes"] == {"maxHp": 200, "atk": 0}


def test_absent_enemy_level_is_not_filled_with_another_level():
    with pytest.raises(ValueError, match="level is missing"):
        resolve_enemy({"enemy/probe": [{"level": 0, "enemyData": {}}]},
                      {"id": "enemy/probe", "useDb": True, "level": 5})


def test_zero_ten_has_real_ground_and_air_dependencies_without_fake_execution():
    plan = build()
    assert plan["spawn_count"] == 35
    assert len(plan["resolved_enemies"]) == 5
    drone = next(row for row in plan["resolved_enemies"] if row["native_id"] == "enemy_1005_yokai")
    assert drone["resolved"]["motion"] == "FLY"
    assert drone["resolved"]["attributes"]["maxHp"] == 800
    assert drone["resolved"]["attributes"]["atk"] == 0
    assert plan["map_plan"]["rows"] == 9 and plan["map_plan"]["cols"] == 13
    assert len(plan["map_plan"]["tiles"]) == 117
    assert len(plan["roster"]) == 12
    assert plan["runnable"] is False and plan["model_validated"] is False
    assert "selected_skill_models_partial_not_native_complete" in plan["pending_conversion"]
    assert len(plan["available_selected_skill_models"]) == 12
    assert plan["control_counts"]["STORY"] > 0
