"""V2 draft preserves the real first-stage script and refuses incomplete execution."""
import pytest

from ark_sim import Compiler, CompileError
from tools.build_mainline_draft import top_position, route_ir, translate


def test_native_bottom_up_route_coordinates_become_top_down_without_mutation():
    route = {"startPosition": {"row": 0, "col": 1}, "endPosition": {"row": 8, "col": 12},
        "checkpoints": [{"type": "MOVE", "position": {"row": 2, "col": 3}}, {"type": "WAIT_FOR_SECONDS", "time": 1}],
        "motionMode": "WALK"}
    result = route_ir(route, 9)
    assert result["startPosition"] == {"row": 8, "col": 1}
    assert result["endPosition"] == {"row": 0, "col": 12}
    assert result["checkpoints"][0]["position"] == {"row": 6, "col": 3}
    assert route["startPosition"]["row"] == 0


def test_zero_ten_draft_preserves_five_enemies_and_35_births():
    data = translate()
    assert len(data["entities"]) == 5
    assert len(data["scenarioDraft"]["waves"]) == 35
    assert len(data["scenarioDraft"]["roster"]) == 12
    assert data["scenarioDraft"]["resources"]["life"]["initial"] == 10
    assert data["scenarioDraft"]["parameters"]["deploy_capacity"] == 8
    flyer = next(row for row in data["entities"] if row["metadata"]["native_id"] == "enemy_1005_yokai")
    assert "flying" in flyer["tags"]
    assert flyer["components"]["abilities"] == []
    assert flyer["components"]["attributes"]["base"]["max_hp"] == 800


def test_unresolved_roster_attacks_and_control_are_real_compile_dependencies():
    data = translate()
    assert data["manifest"]["metadata"]["runnable"] is False
    assert "policy/campaign_native_controls" in data["manifest"]["metadata"]["pending"]
    with pytest.raises(CompileError, match="Missing"):
        Compiler().compile(data)
