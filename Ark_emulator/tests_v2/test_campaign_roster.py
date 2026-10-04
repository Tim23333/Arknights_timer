"""Source identity/configuration tests; these do not claim battle coverage."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("campaign_roster_builder", ROOT / "tools/build_campaign_roster.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture(scope="module")
def reference():
    return json.loads(builder.OUTPUT.read_bytes())


def test_committed_reference_matches_current_raw_sources(reference):
    builder.check_reference(reference)


def test_fixed_twelve_unique_real_characters_and_skills(reference):
    assert len(reference["roster"]) == 12
    assert len({r["character_id"] for r in reference["roster"]}) == 12
    assert [r["order"] for r in reference["roster"]] == list(range(1, 13))
    for row in reference["roster"]:
        char = reference["frozen"]["characters"][row["character_id"]]
        skill = next(s for s in char["skills"] if s.get("skillId") == row["config"]["skill_id"])
        levels = reference["frozen"]["skills"][row["config"]["skill_id"]]["levels"]
        builder.validate_config(char, skill, levels, row["config"])
        assert row["skill_level"] == levels[9]
        assert row["skill_level"]["prefabId"] in reference["frozen"]["prefab_catalog"]


def test_snapshot_hash_covers_every_frozen_raw_dependency(reference):
    assert reference["frozen_sha256"] == builder.digest(builder.canonical(reference["frozen"]))
    changed = copy.deepcopy(reference)
    changed["frozen"]["characters"]["char_003_kalts"]["name"] = "changed"
    with pytest.raises(ValueError, match="identity differs"):
        builder.check_reference(changed)


def test_source_identity_change_is_rejected_even_if_parsed_data_equal(reference, tmp_path):
    for name in builder.FILES:
        raw = (builder.SOURCE / name).read_bytes()
        (tmp_path / name).write_bytes(raw + (b"\n" if name == "skills.json" else b""))
    with pytest.raises(ValueError, match="identity differs"):
        builder.check_reference(reference, tmp_path)


def test_roster_and_frozen_order_do_not_depend_on_raw_table_order(reference, tmp_path):
    for name in builder.FILES:
        data = json.loads((builder.SOURCE / name).read_bytes())
        (tmp_path / name).write_text(json.dumps(dict(reversed(list(data.items())))), encoding="utf-8")
    reversed_reference = builder.build(tmp_path)
    assert reversed_reference["roster"] == reference["roster"]
    assert reversed_reference["frozen_sha256"] == reference["frozen_sha256"]


@pytest.mark.parametrize("field,value", [
    ("level", 71), ("level", 69), ("level", 0), ("elite_phase", 3), ("elite_phase", 0),
    ("skill_level_index", 10), ("mastery", 2), ("potential", 2),
    ("potential_rank", 1), ("trust_percent", 200),
    ("equipment_id", "uniequip_002_kalts"), ("equipment_level", 3),
])
def test_unavailable_or_drifting_configuration_is_rejected(reference, field, value):
    row = reference["roster"][0]  # Myrtle E2 maximum 70, skill S2 requires promotion.
    char = reference["frozen"]["characters"][row["character_id"]]
    skill = next(s for s in char["skills"] if s.get("skillId") == row["config"]["skill_id"])
    config = dict(row["config"], **{field: value})
    with pytest.raises(ValueError):
        builder.validate_config(char, skill, reference["frozen"]["skills"][config["skill_id"]]["levels"], config)


def test_base_potential_talents_never_include_locked_potential_bonus(reference):
    for row in reference["roster"]:
        assert all(t.get("requiredPotentialRank", 0) == 0 for t in row["active_talents"])
        assert all(builder.unlocked(t.get("unlockCondition", {}), row["config"])
                   for t in row["active_talents"])


def test_summons_use_talent_token_keys_and_real_frozen_rows(reference):
    assert reference["token_ids"] == ["token_10002_kalts_mon3tr", "token_10003_cgbird_bird", "token_10009_weedy_cannon"]
    assert all(t in reference["frozen"]["characters"] for t in reference["token_ids"])
    assert "sktok_weedy_token" in reference["frozen"]["skills"]
    assert reference["trait_character_ids"] == ["char_4179_monstr"]
    assert "char_4179_monstr" in reference["frozen"]["characters"]
    assert any(g["kind"] == "display_token_dictionary_unreliable" for g in reference["data_gaps"])


def test_source_presence_does_not_claim_runtime_or_model_pass(reference):
    assert reference["status"] == "source_frozen_only"
    for row in reference["roster"]:
        assert not any(row[k] for k in ("runnable", "v2_imported", "model_validated", "client_validated"))
        assert row["config"]["equipment_id"] is None
    assert any("equipment" in limit for limit in reference["coverage_limits"])
    assert any(g["kind"] == "character_talent_prefab_scope_pending" for g in reference["data_gaps"])
