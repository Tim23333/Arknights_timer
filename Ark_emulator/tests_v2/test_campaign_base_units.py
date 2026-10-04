"""Source conversion witnesses; full-operator integration stays fail-closed."""
from copy import deepcopy
import json

import pytest

from ark_sim import Compiler, Engine
from tools.build_campaign_units import ROOT, OUTPUT, build


def probe(cid, *, count=1):
    data = deepcopy(build())
    source = next(e for e in data["entities"] if e["id"] == "unit/" + cid)
    data["entities"] = [source, {"id": "unit/target", "kind": "entity", "tags": ["enemy", "ground"],
        "components": {"attributes": {"base": {"max_hp": 10000, "def": 10, "mres": 0}},
            "resources": {"hp": {"initial": 10000, "capacity": 10000, "role": "health"}}, "spatial": {}}}]
    data["scenarioDraft"] = {"id": "scenario/base_probe", "ruleset": "ruleset/ark_standard", "map": {"rows": 9, "cols": 9},
        "initialEntities": [{"definition": source["id"], "instanceAlias": "source", "position": {"row": 4, "col": 4}}] + [
            {"definition": "unit/target", "instanceAlias": f"target{i}", "position": {"row": 4, "col": 5}} for i in range(count)]}
    return data


def test_generated_base_content_is_reproducible_and_has_twelve_real_configs():
    data = build()
    assert json.loads(OUTPUT.read_text(encoding="utf-8")) == data
    assert len(data["entities"]) == 12
    assert data["manifest"]["metadata"]["complete_operator_count"] == 0
    for e in data["entities"]:
        assert e["metadata"]["config"]["level"] == 70
        assert e["metadata"]["config"]["trust_percent"] == 100
        assert not e["metadata"]["complete_operator"]
    # Actual alias chains and the exact projectile now close all source gaps.
    unresolved = {r["character_id"] for r in data["manifest"]["metadata"]["conversion"] if r["missing_attack_evidence"]}
    assert not unresolved
    assert len(data["abilities"]) == 12


def test_myrtle_uses_normalized_attack_and_real_attack_event():
    sim = Engine.create(Compiler().compile(probe("char_151_myrtle")))
    sim.session.advance(15)
    assert sim.ctx.resources.current("target0", "hp") == 10000
    sim.session.advance(1)
    assert sim.ctx.resources.current("target0", "hp") == 9490
    assert sim.ctx.attributes.value("source", "max_hp") == 1565


def test_chen_normal_double_hit_has_two_distinct_native_event_ticks():
    sim = Engine.create(Compiler().compile(probe("char_010_chen")))
    sim.session.advance(14)
    assert sim.ctx.resources.current("target0", "hp") == 9382
    sim.session.advance(16)
    assert sim.ctx.resources.current("target0", "hp") == 9382
    sim.session.advance(1)
    assert sim.ctx.resources.current("target0", "hp") == 8764


def test_weedy_normal_target_count_tracks_effective_block_count():
    sim = Engine.create(Compiler().compile(probe("char_400_weedy", count=3)))
    sim.session.advance(17)
    assert sorted(sim.ctx.resources.current(f"target{i}", "hp") for i in range(3)) == [9317, 9317, 10000]


def test_eyja_actual_projectile_is_queued_and_does_not_hit_at_launch():
    sim = Engine.create(Compiler().compile(probe("char_180_amgoat")))
    sim.session.advance(21)
    assert sim.ctx.resources.current("target0", "hp") == 10000
    assert [e for e in sim.session.events if e["type"] == "projectile.launched"]
    sim.session.advance(3)
    assert sim.ctx.resources.current("target0", "hp") == 9290


@pytest.mark.parametrize("cid", ["char_107_liskam", "char_179_cgbird", "char_003_kalts"])
def test_missing_attack_evidence_rejects_compile_instead_of_running_fallback(cid, monkeypatch):
    import tools.build_campaign_units as module
    original = module.load
    def without_restored_evidence(path):
        return {"operators": {}, "projectiles": {}} if path.name == "animation_bindings.reference.json" else original(path)
    monkeypatch.setattr(module, "load", without_restored_evidence)
    with pytest.raises(ValueError, match="Missing reference|source/evidence identity"):
        Compiler().compile(probe(cid))


def test_liskarm_loop_event_uses_exact_alias_and_preserves_first_coroutine_gap():
    data = probe("char_107_liskam")
    ability = next(a for a in data["abilities"] if a["id"] == "ability/char_107_liskam/normal_attack")
    assert ability["metadata"]["native_animation"] == "Attack_Loop"
    assert ability["metadata"]["pending_native_callback_alignment"]
    sim = Engine.create(Compiler().compile(data))
    sim.session.advance(1)
    assert sim.ctx.resources.current("target0", "hp") == 10000
    sim.session.advance(1)
    assert sim.ctx.resources.current("target0", "hp") == 9549


def test_nightingale_attack_a_alias_heals_three_at_frame27():
    data = probe("char_179_cgbird", count=4)
    data["entities"][1]["tags"] = ["player", "ground"]
    data["entities"][1]["components"]["resources"]["hp"]["initial"] = 100
    sim = Engine.create(Compiler().compile(data))
    sim.session.advance(27)
    assert all(sim.ctx.resources.current(f"target{i}", "hp") == 100 for i in range(4))
    sim.session.advance(1)
    assert sorted(sim.ctx.resources.current(f"target{i}", "hp") for i in range(4)) == [100, 504, 504, 504]


def test_kalts_heal_uses_exact_projectile_speed_and_delayed_settlement():
    data = probe("char_003_kalts")
    data["entities"][1]["tags"] = ["player", "ground"]
    data["entities"][1]["components"]["resources"]["hp"]["initial"] = 100
    sim = Engine.create(Compiler().compile(data))
    sim.session.advance(14)
    assert sim.ctx.resources.current("target0", "hp") == 100
    assert [e for e in sim.session.events if e["type"] == "projectile.launched"]
    sim.session.advance(5)
    assert sim.ctx.resources.current("target0", "hp") == 100
    sim.session.advance(1)
    assert sim.ctx.resources.current("target0", "hp") == 568


def test_dynamic_limit_allows_external_modifier_and_rejects_fractional_value():
    data = probe("char_400_weedy", count=3)
    source = data["entities"][0]
    source["components"]["attributes"]["modifiers"] = [{"attribute": "block_count", "layer": "flat", "value": 1}]
    sim = Engine.create(Compiler().compile(data))
    sim.session.advance(17)
    assert all(sim.ctx.resources.current(f"target{i}", "hp") == 9317 for i in range(3))
    bad = deepcopy(data)
    bad["entities"][0]["components"]["attributes"]["modifiers"][0]["value"] = 0.5
    failed = Engine.create(Compiler().compile(bad))
    with pytest.raises(ValueError, match="nonnegative integer"):
        failed.session.advance(1)


@pytest.mark.parametrize("kind", ["magical", "typo", "", 2, None])
def test_unknown_damage_type_cannot_silently_become_physical(kind):
    data = probe("char_151_myrtle")
    next(a for a in data["abilities"] if "char_151_myrtle" in a["id"])["timeline"][0]["effect"]["damage_type"] = kind
    with pytest.raises(ValueError, match="damage type"):
        Compiler().compile(data)


def test_default_unlimited_selector_remains_valid():
    Compiler().compile(ROOT / "packages/custom/custom_guard.json")


def test_plosis_base_heal_uses_actual_attack_on_three_injured_allies():
    data = probe("char_128_plosis", count=4)
    data["entities"][1]["tags"] = ["player", "ground"]
    data["entities"][1]["components"]["resources"]["hp"]["initial"] = 100
    sim = Engine.create(Compiler().compile(data))
    sim.session.advance(16)
    assert sorted(sim.ctx.resources.current(f"target{i}", "hp") for i in range(4)) == [100, 482, 482, 482]
    # Full-health caster is an allowed same-side member but must not consume
    # one of the three injury-target slots.
    assert sim.ctx.resources.current("source", "hp") == 1567
