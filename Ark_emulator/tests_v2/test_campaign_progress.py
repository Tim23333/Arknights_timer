"""A source-only campaign cannot be reported as executed or accepted."""
from copy import deepcopy
from pathlib import Path

import pytest

from tools.campaign_progress import ROOT, load, fixed_roster, build_progress, audit_recovery, execution_gate
from ark_sim import Compiler


def inputs():
    return (load(ROOT/"packages/campaign/mainline_catalog.json"),
            load(ROOT/"packages/campaign/roster.reference.json"),
            load(ROOT/"validation/campaign/data_recovery.json"))


def test_complete_source_inventory_is_not_complete_campaign_execution():
    report = build_progress(*inputs())
    assert report["counts"]["targets"] == 36
    assert report["counts"]["decoded"] == 36
    assert report["counts"]["core_reference_verified"] >= 4
    assert report["counts"]["accepted"] == report["counts"]["client_verified"] == 0
    assert {c["model_status"] for c in report["cases"]} == {"not_run"}
    assert [(c["code"], c["expected_native_spawns"]) for c in report["cases"][:4]] == [
        ("0-10", 35), ("0-11", 37), ("1-11", 45), ("1-12", 30)]


def test_modified_recovery_file_cannot_keep_verified_source_status(tmp_path):
    output = tmp_path/"level.json"
    output.write_text("{}", encoding="utf-8")
    status, gaps = audit_recovery({"output_path": str(output), "output_sha256": "0"*64}, tmp_path)
    assert status == "stale"
    assert gaps == ["recovered_content_identity_mismatch"]


def test_fixed_roster_cannot_silently_drop_an_operator():
    reference = deepcopy(inputs()[1])
    reference["roster"].pop()
    with pytest.raises(ValueError, match="exactly twelve"):
        fixed_roster(reference)


def test_changed_frozen_skill_data_invalidates_roster_identity():
    reference = deepcopy(inputs()[1])
    reference["frozen"]["skills"].clear()
    with pytest.raises(ValueError, match="dependency bytes"):
        fixed_roster(reference)


def test_known_zero_one_program_cannot_substitute_for_a_campaign_stage():
    program = Compiler().compile(ROOT/"packages/ark_content/level_main_00_01.json")
    case = {"level_id": "level_main_00-10"}
    with pytest.raises(ValueError, match="different native level"):
        execution_gate(program, case, inputs()[1])
