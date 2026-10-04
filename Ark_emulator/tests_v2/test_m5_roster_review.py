"""Independent payer scope and real-stat/source-boundary review for M5."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from test_campaign_acceptance import scene
from test_temporal_and_recovery_gate import curve_model, gate_model
from test_buff_mode_lifecycle import model as mode_model
from tools import build_campaign_units as units
from tools import build_campaign_squad as squad

ROOT = Path(__file__).resolve().parents[1]


def payer_model(owner_sp=5):
    data = scene()
    data["entities"][0]["components"]["resources"]["sp"]["initial"] = owner_sp
    child = deepcopy(data["entities"][0])
    child["id"] = "unit/review_child"
    child["components"]["abilities"] = ["ability/review_payers"]
    child["components"]["resources"]["ammo"] = {"initial": 4, "capacity": 4}
    child["components"]["ownership"] = {"owner": "source", "on_owner_retire": "retain"}
    data["entities"].append(child)
    data["abilities"].append({"id": "ability/review_payers", "kind": "ability", "activation": {"mode": "manual",
        "costs": [{"owner": "source", "resource": "ammo", "amount": 1},
                  {"owner": "owner", "resource": "sp", "amount": 2},
                  {"owner": "battle", "resource": "dp", "amount": 3}]}, "timeline": []})
    data["scenarioDraft"]["resources"] = {"dp": {"initial": 10, "capacity": 10}}
    data["scenarioDraft"]["initialEntities"].append({"definition": child["id"], "instanceAlias": "child", "position": {"row": 0, "col": 0}})
    return data


def test_three_cost_owners_debit_the_correct_resources():
    sim = Engine.create(Compiler().compile(payer_model()))
    sim.ctx.abilities.start("child", "ability/review_payers")
    assert sim.ctx.resources.current("child", "ammo") == 3
    assert sim.ctx.resources.current("source", "sp") == 3
    assert sim.ctx.resources.current("system/battle", "dp") == 7
    assert sim.ctx.resources.current("child", "sp") == 5


def test_insufficient_owner_resource_rolls_back_other_payers_and_cast():
    sim = Engine.create(Compiler().compile(payer_model(owner_sp=1)))
    before = sim.checkpoint()
    with pytest.raises(ValueError, match="insufficient resource"):
        sim.ctx.abilities.start("child", "ability/review_payers")
    assert sim.checkpoint() == before


def test_automatic_replacement_readiness_honors_battle_cost_owner():
    data = scene(mode="automatic_attack")
    replacement = deepcopy(data["abilities"][0])
    replacement["id"] = "ability/review_battle_replace"
    replacement["activation"] = {"mode": "manual", "parameters": {"auto_when_ready": True, "replace_attack": True},
                                 "costs": [{"owner": "battle", "resource": "dp", "amount": 1}]}
    replacement["timeline"][0]["effect"]["scale"] = 2
    data["abilities"].insert(0, replacement)
    data["entities"][0]["components"]["abilities"].insert(0, replacement["id"])
    data["scenarioDraft"]["resources"] = {"dp": {"initial": 2, "capacity": 2}}
    sim = Engine.create(Compiler().compile(data))
    sim.advance(1)
    assert sim.ctx.resources.current("system/battle", "dp") == 1
    assert [sim.ctx.resources.current(t, "hp") for t in ("target1", "target2")] == [80, 80]


def test_integrated_roster_stats_are_native_model_values_not_fixture_values():
    package = squad.build()
    native = json.loads((ROOT / "packages/campaign/operators.normalized.json").read_bytes())
    models = {r["character_id"]: r for r in native["operators"]}
    actors = [r for r in package["entities"] if "campaign_roster" in r.get("tags", [])]
    assert len(actors) == 12
    definitions = {r["id"]: r for section in squad.SECTIONS for r in package.get(section, [])}
    for actor in actors:
        row = models[actor["metadata"]["native_id"]]
        assert actor["metadata"]["config"] == row["config"]
        stats = row["stats"]["model_stats"]
        base = actor["components"]["attributes"]["base"]
        for source, target in (("atk", "atk"), ("def", "def"), ("maxHp", "max_hp"), ("magicResistance", "mres")):
            assert base[target] == stats[source]
        aid = actor["metadata"]["selected_skill_ability"]
        assert aid in actor["components"]["abilities"] and definitions[aid]["kind"] == "ability"
        assert actor["metadata"]["selected_skill_native_id"] == row["selected_skill"]["skill_id"]
        assert actor["metadata"]["complete_operator"] is False
    assert package["manifest"]["metadata"]["complete_operator_count"] == 0
    assert package["manifest"]["metadata"]["formal_mainline_approved"] is False
    assert all(r["pending"] and r["complete_operator"] is False for r in package["manifest"]["metadata"]["integration"])


def test_twelve_base_frame_entries_keep_native_callback_pending():
    package = units.build()
    assert len(package["abilities"]) == 12
    assert all(r["normal_attack_converted"] for r in package["manifest"]["metadata"]["conversion"])
    assert all(r["complete_operator"] is False and r["pending"] for r in package["manifest"]["metadata"]["conversion"])
    night = next(a for a in package["abilities"] if a["id"] == "ability/char_179_cgbird/normal_attack")
    assert night["timeline"][0]["at_seconds"] == .9
    assert night["metadata"]["exact_animation_binding"]["resolved_animation_key"] == "Attack_A"


def test_forged_frame_binding_cannot_override_its_own_raw_payload_evidence(tmp_path, monkeypatch):
    target = tmp_path / "packages/campaign"
    target.mkdir(parents=True)
    for name in ("operators.normalized.json", "attacks.reference.json", "animation_bindings.reference.json"):
        (target / name).write_bytes((ROOT / "packages/campaign" / name).read_bytes())
    range_dir = tmp_path / "ark_emulator"
    range_dir.mkdir()
    (range_dir / "data_range_table.json").write_bytes((ROOT / "ark_emulator/data_range_table.json").read_bytes())
    path = target / "animation_bindings.reference.json"
    binding = json.loads(path.read_bytes())
    for face in ("front", "back"):
        binding["operators"]["char_179_cgbird"]["modes"][0]["bindings_by_face"][face]["events"][0]["frame"] = 0
    # Raw source bytes, payload hash and parsed skeleton still prove frame27.
    path.write_text(json.dumps(binding), encoding="utf-8")
    monkeypatch.setattr(units, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="(?i)source|binding|identity|frame|evidence"):
        units.build()


@pytest.mark.parametrize("read_mode, expected_hp", [("at_cast", 64), ("at_hit", 90)])
def test_captured_and_live_curve_damage_diverge_after_expiry_with_replay(read_mode, expected_hp):
    data = curve_model()
    data["abilities"][0]["activation"]["on_start"] = [{"op": "apply_buff", "target": "source", "buff": "buff/curve"}]
    data["abilities"][0]["timeline"] = [{"at": 65, "effect": {"op": "damage", "damage_type": "true",
        "read_mode": {"source_attributes": read_mode}}}]
    program = Compiler().compile(data)
    sim = Engine.create(program)
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"})
    sim.advance(30)
    restored = Engine.restore(program, sim.checkpoint())
    sim.advance(36)
    restored.advance(36)
    assert sim.ctx.resources.current("target1", "hp") == expected_hp
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None


def test_owned_member_expiry_interrupts_active_cast_before_delayed_hit():
    data = gate_model()
    data["abilities"][0]["duration_seconds"] = 2
    data["abilities"][0]["timeline"][0]["at"] = 40
    program = Compiler().compile(data)
    sim = Engine.create(program)
    sim.submit({"action": "skill", "source": "source", "ability": "ability/own"})
    sim.submit({"action": "skill", "source": "source", "ability": "ability/probe"}, at=4)
    sim.advance(12)
    assert sim.ctx.get("source", ("runtime", "casts"))
    restored = Engine.restore(program, sim.checkpoint())
    sim.advance(35)
    restored.advance(35)
    assert sim.ctx.get("source", ("runtime", "casts")) == {}
    assert sim.ctx.resources.current("source", "sp") == 0
    assert sim.ctx.resources.current("target1", "hp") == 100
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None


def test_removing_target_buff_writes_to_caster_synchronously():
    data = mode_model()
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.resources.adjust("source", "mode", value=1)
    sim.ctx.buffs.apply("source", "target1", "buff/mode")
    assert sim.ctx.buffs.remove("target1", "buff/mode") == 1
    # 'source' is the retained buff caster, not its target or remover.
    assert sim.ctx.resources.current("source", "mode") == 0
    assert sim.ctx.resources.current("target1", "hp") == 100
