"""Table-backed Adnach level-1 skill profile; missing prefab/body remain gaps."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE = ROOT / "packages/campaign/chapter01_predefines"
OUT = BASE / "skill_model"
RUNTIME = ROOT.parent / "unpack_work/campaign_m10_cast_freeze_candidate"
EXPECTED = "f6bb448edc40641f55550f7188b412f57e68a56fa083ac4f4c1c24e30502328e"
SOURCE_SHA = "15eb6edf057af42e1c03acf441cc44852f1a3b4aefd511dd23428fcead1413e6"
MODEL_SHA = "4eb40df9ef979f54f289c099b78723da61fc49d00fc88fcdafb1ace3c77b779e"
SKILL = "ability/chapter01_adnach_atk_up_level1"
BUFF = "buff/chapter01_adnach_atk_up_level1"
UNIT = "unit/ch1_predefined_adnach_e0_l20"


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_bytes())
def encoded(v): return (json.dumps(v, ensure_ascii=False, indent=2)+"\n").encode("utf8")


def build():
    if sha(BASE / "native.reference.json") != SOURCE_SHA or sha(BASE / "npc.model.json") != MODEL_SHA:
        raise ValueError("frozen predefined input checksum changed")
    source = read(BASE / "native.reference.json"); package = read(BASE / "npc.model.json")
    level = source["selected_skill_level"]; sp = level["spData"]
    bb = {r["key"]: r["value"] for r in level["blackboard"]}
    if source["selected_skill_id"] != "skcom_atk_up[1]" or level["prefabId"] != "skcom_atk_up":
        raise ValueError("selected level1 skill identity changed")
    if (level["skillType"], sp["spType"], sp["spCost"], sp["initSp"], sp["maxChargeTime"], sp["increment"], level["duration"]) != (
            "MANUAL", "INCREASE_WITH_TIME", 50, 0, 1, 1, 20):
        raise ValueError("unsupported native skill/SP/duration parameters")
    if len(bb) != len(level["blackboard"]) or bb != {"atk": .1}: raise ValueError("selected BB missing/ambiguous")
    profile = {"id": "adnach_level1_additive_ATK_ratio_periodic_SP_cast_window_v1",
        "attribute": "effective ATK = base199 * (1 + native BB atk0.1); no intermediate integer rounding",
        "SP": "periodic +increment1 each elapsed1s, initial0/cap50/payment50; explicitly freeze only selected ability while active",
        "duration": "20 seconds; Buff half-open expiry independent of cast finish task; native ordering pending",
        "attack": "existing NPC normal ability/range/frame/projectile preserved; no mode switch, attack clock reset, or extra packets",
        "manual": "native skillType MANUAL; no auto_when_ready",
        "client_verified": False}
    gaps = ["native_skcom_atk_up_prefab_BSON_template_not_recovered", "native_attribute_formula_rounding_and_modifier_application_pending",
        "native_SP_recovery_freeze_and_cast_duration_FSM_body_pending", "native_skill_activation_animation_and_attack_clock_reset_unknown",
        "native_ACTIVATE_PREDEFINED_hidden_activation_and_sourceCards_composition_pending"]
    unit = package["entities"][0]
    unit["components"]["resources"]["sp"] = {"initial": sp["initSp"], "capacity": sp["spCost"], "recovery_rate": sp["increment"],
        "recovery": {"mode": "periodic", "interval_seconds": 1}, "parameters": {"pause_at_full": True},
        "recovery_freeze_abilities": [SKILL]}
    unit["components"]["abilities"].append(SKILL)
    package["abilities"].append({"id": SKILL, "kind": "ability", "activation": {"mode": "manual",
        "costs": [{"resource": "sp", "amount": sp["spCost"]}], "on_start": [{"op": "apply_buff", "target": "source", "buff": BUFF}]},
        "parameters": {"blocks_attacks": False}, "duration_seconds": level["duration"], "timeline": [],
        "metadata": {"native_skill_id": source["selected_skill_id"], "native_level_index": 0, "profile": profile, "client_verified": False}})
    package["buffs"] = [{"id": BUFF, "kind": "buff", "duration_seconds": level["duration"],
        "modifiers": [{"attribute": "atk", "layer": "direct_ratio", "value": bb["atk"]}],
        "metadata": {"source_BB": level["blackboard"], "attribute_formula_is_model": True}}]
    identities = {"native_predefined_source": SOURCE_SHA, "NPC_model": MODEL_SHA, "builder": sha(Path(__file__))}
    metadata = package["manifest"]["metadata"]
    metadata.update(status="partial_predefined_NPC_normal_and_selected_skill_profile", source_identities=identities,
        selected_skill_profile=profile, skill_source_gaps=gaps, complete_NPC=False, formal_stage_approved=False)
    metadata["pending"] = [p for p in metadata["pending"] if p != "native_selected_skill_not_converted"] + gaps
    package["manifest"]["id"] = "package/campaign/chapter01_adnach_selected_skill"
    reference = {"schema": "ark-sim/chapter01-predefined-skill-source/v1", "source_identities": identities,
        "native_config": source["predefines"]["characterInsts"][0], "native_cards": source["predefines"]["characterCards"],
        "native_controls": source["native_controls"], "native_skill_id": source["selected_skill_id"], "selected_level": level,
        "table_sources": source["table_sources"], "selected_skill_prefab_sources": source["selected_skill_prefab_sources"],
        "reader_identity": source["reader_identity"], "profile": profile, "gaps": gaps,
        "scope": "table-driven replaceable model; no native prefab/body claim", "full_NPC_implemented": False}
    return reference, package


def runtime(root, expected):
    root = root.resolve(); sys.path.insert(0, str(root))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    actual = Path(ark_sim.__file__).resolve()
    if actual.parent != root / "ark_sim" or implementation_digest() != expected: raise RuntimeError("runtime actual path/identity mismatch")
    return {"root": root.as_posix(), "actual_import": actual.as_posix(), "implementation_digest": expected}


def fixture(package, initial_sp=50, enemy=True):
    p = deepcopy(package)
    p["entities"][0]["components"]["resources"]["sp"]["initial"] = initial_sp
    p["entities"].append({"id": "unit/adnach_skill_probe_enemy", "kind": "entity", "tags": ["enemy", "ground"],
        "components": {"attributes": {"base": {"max_hp": 100000, "atk": 100, "def": 30, "mres": 0}},
            "resources": {"hp": {"initial": 100000, "capacity": 100000, "role": "health"}},
            "lifecycle": {"policy": "policy/ark_lifecycle"}, "spatial": {}}})
    p["scenarioDraft"] = {"id": "scenario/adnach_selected_skill_probe", "ruleset": "ruleset/ark_standard",
        "metadata": {"synthetic_enemy": True, "initial_SP_override_fixture_only": initial_sp, "not_native_activation": True},
        "map": {"rows": 8, "cols": 12}, "initialEntities": [{"definition": UNIT, "instanceAlias": "npc",
            "position": {"row": 3, "col": 6}, "facing": "right"}]+([{"definition": "unit/adnach_skill_probe_enemy",
                "instanceAlias": "enemy", "position": {"row": 3, "col": 7}}] if enemy else [])}
    return p


def verify(package, identity):
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.compare import first_difference
    from ark_sim.tools.replay import replay
    def make(p): return Engine.create(Compiler().compile(p), seed=111)
    s = make(fixture(package)); s.submit({"action": "skill", "source": "npc", "ability": SKILL}); s.advance(1)
    assert s.ctx.resources.current("npc", "sp") == 0
    s.advance(11); assert s.ctx.resources.current("enemy", "hp") == 100000
    s.advance(1); assert abs(s.ctx.resources.current("enemy", "hp") - 99811.1) < 1e-8
    s.advance(287); assert s.ctx.resources.current("npc", "sp") == 0
    cp = s.checkpoint(); r = Engine.restore(s.program, cp)
    s.advance(301); r.advance(301)
    assert first_difference(s.snapshot(), r.snapshot()) is None
    damage = [e for e in s.session.events if e["type"] == "damage.accepted"]
    assert len(damage) == 20 and all(abs(e["payload"]["amount"]-188.9) < 1e-8 for e in damage)
    s.advance(12)
    damage = [e for e in s.session.events if e["type"] == "damage.accepted"]
    assert len(damage) == 21 and damage[-1]["time"] == 612 and abs(damage[-1]["payload"]["amount"]-169) < 1e-8
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None
    s.advance(18); assert s.ctx.resources.current("npc", "sp") == 1
    negative = make(fixture(package, initial_sp=0)); negative.submit({"action": "skill", "source": "npc", "ability": SKILL}); negative.advance(13)
    assert any(e["type"] == "command.rejected" for e in negative.session.events)
    assert negative.ctx.resources.current("npc", "sp") == 0
    assert negative.ctx.resources.current("enemy", "hp") == 99831
    assert first_difference(negative.snapshot(), replay(negative.program, negative.export_replay()).snapshot()) is None
    # Full SP alone does not auto-start a native MANUAL skill.
    idle = make(fixture(package)); idle.advance(13)
    assert idle.ctx.resources.current("npc", "sp") == 50 and idle.ctx.resources.current("enemy", "hp") == 99831
    assert not [e for e in idle.session.events if e["type"] == "ability.started" and e["payload"]["ability"] == SKILL]
    if implementation_digest() != identity["implementation_digest"]: raise RuntimeError("runtime changed during probes")
    return {"schema": "ark-sim/chapter01-predefined-skill-assertions/v1", "passed": True, "runtime": identity,
        "payment": 50, "selected_skill_initial_SP": 0, "synthetic_probe_initial_SP": 50,
        "ordinary_damage": 169, "skill_damage": 188.9, "skill_gain": 19.9, "model_effective_ATK": 218.9,
        "last_buff_packet_tick": 582, "first_restored_packet_tick": 612, "buff_packet_count": 20,
        "SP_during_skill": 0, "SP_after_next_periodic_tick630": 1, "checkpoint_equal": True, "commands_replay_equal": True,
        "insufficient_SP_command_rejected": True, "full_SP_no_manual_autostart": True,
        "program_fingerprint": s.program.fingerprint, "runtime_fingerprint": s.runtime_fingerprint,
        "builder_sha256": sha(Path(__file__)), "model_sha256": hashlib.sha256(encoded(package)).hexdigest(),
        "native_template_body_recovered": False, "full_NPC_implemented": False, "formal_stage_approved": False}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--check", action="store_true")
    p.add_argument("--runtime-root", type=Path, default=RUNTIME); p.add_argument("--expected-digest", default=EXPECTED)
    args = p.parse_args(); identity = runtime(args.runtime_root, args.expected_digest)
    source, model = build(); evidence = verify(model, identity)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, value in (("native.reference.json", source), ("model.json", model), ("probe.json", fixture(model)), ("assertions.json", evidence)):
        path = OUT/name
        if args.check:
            if not path.exists() or path.read_bytes() != encoded(value): raise ValueError("predefined skill source/model/assertions drift: "+name)
        else: path.write_bytes(encoded(value))
    print(json.dumps({"passed": True, "runtime": identity, "template_body_recovered": False, "full_NPC_implemented": False}))


if __name__ == "__main__": main()
