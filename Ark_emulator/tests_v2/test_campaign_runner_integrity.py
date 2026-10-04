"""Independent negative gates for campaign evidence and persistence.

The deceptive package is executable through the real V2 compiler/engine. No
runtime is stubbed; it must be rejected because external approval is absent.
"""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from tools import campaign_progress as runner
from ark_sim import Compiler


@pytest.fixture(scope="module")
def inputs():
    return (runner.load(runner.ROOT / "packages/campaign/mainline_catalog.json"),
            runner.load(runner.ROOT / "packages/campaign/roster.reference.json"),
            runner.load(runner.ROOT / "validation/campaign/data_recovery.json"))


@pytest.mark.parametrize("change", [
    {"level": 1}, {"elite_phase": 0}, {"mastery": 0, "skill_level_index": 6},
    {"trust_percent": 0}, {"potential": 6, "potential_rank": 5},
    {"equipment_id": "uniequip_002_kalts", "equipment_level": 3},
])
def test_fixed_configuration_cannot_change_without_changing_frozen_dependencies(inputs, change):
    reference = deepcopy(inputs[1])
    reference["roster"][0]["config"].update(change)
    with pytest.raises(ValueError):
        runner.fixed_roster(reference)


@pytest.mark.parametrize("field", ["source_path", "source_sha256", "helper_sha256", "fb_helper_sha256", "extractor_sha256"])
def test_source_or_decoder_identity_failure_cannot_remain_verified(inputs, field):
    record = deepcopy(next(r for r in inputs[2]["levels"] if r.get("core_status") == "reference_verified"))
    record[field] = "missing_campaign_binary.dat" if field == "source_path" else "0" * 64
    status, gaps = runner.audit_recovery(record)
    assert status == "stale"
    assert gaps


def deceptive_package(reference, native_level_id, count):
    """Keep native labels, falsify all actual unit/skill/enemy semantics."""
    units, abilities, declarations = [], [], {}
    for index, row in enumerate(reference["roster"]):
        uid, aid = f"unit/fake_{index}", f"ability/fake_{index}"
        declarations[row["character_id"]] = aid
        units.append({"id": uid, "kind": "entity", "metadata": {"native_id": row["character_id"]},
            "components": {"attributes": {"base": {"atk": 999999, "def": 0, "magic_resistance": 0, "max_hp": 1}},
                           "resources": {"hp": {"initial": 1, "capacity": 1, "role": "health"}},
                           "spatial": {}, "abilities": [aid]}})
        abilities.append({"id": aid, "kind": "ability", "metadata": {"native_skill_id": row["config"]["skill_id"]},
            "activation": {"mode": "manual"}, "selector": "selector/all",
            "timeline": [{"at": 0, "effect": {"op": "damage", "damage_type": "true"}}]})
    roster = [u["id"] for u in units]
    units.append({"id": "unit/fake_enemy", "kind": "entity", "tags": ["enemy"], "components": {
        "attributes": {"base": {"def": 0, "magic_resistance": 0, "max_hp": 1}},
        "resources": {"hp": {"initial": 1, "capacity": 1, "role": "health"}}, "spatial": {},
        "lifecycle": {"policy": "policy/ark_lifecycle"}}})
    campaign = {"native_level_id": native_level_id, "roster_frozen_sha256": reference["frozen_sha256"],
        "pending_mechanics": [], "native_fields_verified": True, "selected_skill_definitions": declarations,
        "required_mechanics": ["fictional"], "mechanic_tests": {"fictional": "this_test_does_not_exist"},
        "native_spawn_count": count}
    return {"schemaVersion": 2, "entities": units, "abilities": abilities,
        "selectors": [{"id": "selector/all", "kind": "selector", "region": {"type": "all"},
                       "filters": [{"tag": "enemy"}, {"state": "alive"}]}],
        "scenarioDraft": {"id": "scenario/fake", "ruleset": "ruleset/ark_standard",
            "metadata": {"campaign": campaign}, "roster": roster, "map": {"rows": 1, "cols": 2},
            "resources": {"life": {"initial": 3, "capacity": 3}}, "objectives": {"type": "waves"},
            "initialEntities": [{"definition": roster[0], "instanceAlias": "source", "position": {"row": 0, "col": 0}}],
            "waves": [{"at": 0, "definition": "unit/fake_enemy", "position": {"row": 0, "col": 1}} for _ in range(count)]}}


def test_executable_fake_native_metadata_cannot_run_without_external_review(inputs, tmp_path):
    row = next(r for r in inputs[0]["stages"] if r["selected"])
    case = {"native_id": row["native_id"], "level_id": row["level_id"], "planned_content": "fake.json",
            "planned_commands": "commands.json", "expected_native_spawns": 35}
    data = deceptive_package(inputs[1], case["level_id"], 35)
    # Compilable fake data is precisely what metadata-only checks must reject.
    Compiler().compile(data)
    (tmp_path / "fake.json").write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "commands.json").write_text(json.dumps([
        {"at": 0, "action": "activate_ability", "source": "source", "ability": "ability/fake_0"}]), encoding="utf-8")
    assert not (tmp_path / "validation/campaign/reviews" / f"{case['native_id']}.json").exists()
    with pytest.raises(ValueError, match="(?i)review|receipt|approval"):
        runner.run_case(case, inputs[1], root=tmp_path, max_ticks=300)


def result_record(native_id):
    return {"native_id": native_id, "status": "model_passed_pending_review", "model_status": "passed_pending_review",
            "program_fingerprint": "obsolete-program", "runtime_fingerprint": "obsolete-runtime",
            "input_identity": {"content_sha256": "0" * 64, "commands_sha256": "0" * 64},
            "checkpoint_equal": True, "replay_equal": True, "client_status": "pending",
            "replay": {"historical_marker": "keep-this-replay"}}


def test_case_result_save_is_independent_and_atomic(inputs, tmp_path, monkeypatch):
    native_id = next(r["native_id"] for r in inputs[0]["stages"] if r["selected"])
    first = result_record(native_id)
    path = Path(runner.save_case_result(native_id, first, root=tmp_path))
    assert path.is_file()
    before = path.read_bytes()
    assert json.loads(before)["replay"]["historical_marker"] == "keep-this-replay"
    assert path != tmp_path / "validation/campaign/progress.json"

    def interrupted_replace(*args, **kwargs):
        raise OSError("simulated atomic commit interruption")

    monkeypatch.setattr(os, "replace", interrupted_replace)
    with pytest.raises(OSError, match="interruption"):
        runner.save_case_result(native_id, {**first, "replay": {"historical_marker": "new"}}, root=tmp_path)
    assert path.read_bytes() == before


def test_dry_refresh_preserves_history_but_rejects_old_result_as_current_pass(inputs, tmp_path):
    row = next(r for r in inputs[0]["stages"] if r["selected"])
    path = Path(runner.save_case_result(row["native_id"], result_record(row["native_id"]), root=tmp_path))
    before = path.read_bytes()
    report = runner.build_progress(*inputs, root=tmp_path, run_ready=False)
    assert path.read_bytes() == before
    case = next(c for c in report["cases"] if c["native_id"] == row["native_id"])
    assert case["model_status"] != "passed_pending_review"
    assert report["counts"]["model_passed_pending_review"] == 0
    assert case.get("history") or case.get("evidence_history")
    assert "keep-this-replay" in path.read_text(encoding="utf-8")
