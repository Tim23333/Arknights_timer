"""Independent expectations for campaign selection; no battle execution claims."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mainline_catalog", ROOT / "tools/mainline_catalog.py")
catalog_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog_tool)

# Manually reviewed from local stages and levels_index, not computed by selector.
EXPECTED = {
    0: ("0-10", "0-11"), 1: ("1-11", "1-12"), 2: ("2-9", "2-10"),
    3: ("3-7", "3-8"), 4: ("4-9", "4-10"), 5: ("5-9", "5-10"),
    6: ("6-16", "6-17"), 7: ("7-17", "7-18"), 8: ("JT8-2", "JT8-3"),
    9: ("9-18", "9-19"), 10: ("10-16", "10-17"), 11: ("11-19", "11-20"),
    12: ("12-19", "12-20"), 13: ("13-20", "13-21"), 14: ("14-21", "14-22"),
    15: ("15-19", "15-20"), 16: ("16-17", "16-18"), 17: ("17-17", "17-18"),
}


@pytest.fixture(scope="module")
def catalog():
    return json.loads((ROOT / "packages/campaign/mainline_catalog.json").read_text(encoding="utf8"))


def test_independent_chapter_tail_codes(catalog):
    assert {c["chapter"]: tuple(c["selected_codes"]) for c in catalog["chapters"]} == EXPECTED
    assert sum(r["selected"] for r in catalog["stages"]) == 36


def test_order_is_native_numeric_not_lexical_or_display_code():
    stages = {
        "main_08-9": {"difficulty": 1, "code": "Z8-999"},
        "main_08-10": {"difficulty": 1, "code": "R8-1"},
        "main_08-11": {"difficulty": 1, "code": "M8-0"},
        "main_08-11#f#": {"difficulty": 2}, "main_08-11#s": {"difficulty": 8},
        "easy_08-99": {"difficulty": 1}, "tough_08-99": {"difficulty": 1},
        "tr_08": {"difficulty": 1}, "st_08-99": {"difficulty": 1},
        "spst_08-99": {"difficulty": 1}, "sub_08-99": {"difficulty": 1},
        "hard_08-99": {"difficulty": 1}, "act08side_99": {"difficulty": 1},
        "main_08-12": {"difficulty": 2},
    }
    assert catalog_tool.select_tail_pairs(stages) == {8: ["main_08-10", "main_08-11"]}


def test_variants_are_preserved_without_standard_duplicate(catalog):
    rows = {r["code"]: r for r in catalog["stages"]}
    assert {v["variant"] for v in rows["10-17"]["variants"]} == {"main", "easy", "tough"}
    assert any(v["suffix"] == "#s" and v["difficulty"] == 8 for v in rows["17-17"]["variants"])
    assert all(r["native_id"].startswith("main_") and "#" not in r["native_id"] for r in rows.values())
    assert rows["6-17"]["native_id"] == "main_06-15"
    assert rows["JT8-3"]["native_id"] == "main_08-17"


def test_every_selected_source_is_traceable_and_not_runtime_validated(catalog):
    for row in catalog["stages"]:
        if not row["selected"]:
            continue
        assert row["v2_status"] == "not_validated"
        assert row["dependency_status"] == "not_imported"
        for field in ("parsed_level_source", "dependency_summary_source"):
            src = row[field]
            assert hashlib.sha256((ROOT / src["path"]).read_bytes()).hexdigest() == src["sha256"]
        assert row["status"] == "source_available_with_geometry_gaps"
        assert row["dependency_summary"]["invalid_motion_route_count"] > 0


def test_missing_required_sources_fail_explicitly(tmp_path):
    with pytest.raises(FileNotFoundError, match="Required campaign source missing"):
        catalog_tool.build_catalog(tmp_path / "Ark_emulator")


def test_control_actions_and_spawn_counts_are_separate():
    result = catalog_tool.dependency_summary({"waves": [{"fragments": [{"actions": [
        {"actionType": "SPAWN", "count": 3, "routeIndex": 1},
        {"actionType": {"name": "STORY", "value": 2}, "count": 9},
    ]}]}], "routes": []})
    assert result["declared_spawn_count"] == 3
    assert result["spawn_action_count"] == 1
    assert result["control_action_counts"] == {"STORY": 1}
    assert result["used_spawn_route_indices"] == [1]
