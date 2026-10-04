"""Source-bound 1-11 NPC configuration and explicitly partial normal attack model.

Offline Unity/Spine readers are used only to author immutable JSON. No V1
battle code is imported by the V2 model or its short Engine assertions.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "packages/campaign/chapter01_predefines"
SOURCE = ROOT / "packages/campaign/chapter01_sources/native.reference.json"
CID = "char_211_adnach"
UNIT = "unit/ch1_predefined_adnach_e0_l20"
AID = "ability/ch1_predefined_adnach_normal"
SID = "selector/ch1_predefined_adnach_normal"


def read(p): return json.loads(p.read_text(encoding="utf8"))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def encoded(v): return (json.dumps(v, ensure_ascii=False, indent=2) + "\n").encode("utf8")


def build():
    from tools.normalize_campaign_operators import load_sources, interpolate, half_away_integer, ROUNDING_PROFILE, rational_json
    from tools.extract_campaign_animation_bindings import character_bindings, library_identity
    from tools.build_chapter01_enemy_sources import NativeAssets
    tables, skills, lock = load_sources()
    stage = read(SOURCE)["stages"]["level_main_01-11"]
    predefines = stage["native_level_document"]["predefines"]
    if len(predefines["characterInsts"]) != 1 or len(predefines["characterCards"]) != 12:
        raise ValueError("native predefined instance/card count changed")
    inst = predefines["characterInsts"][0]
    cfg = inst["inst"]
    if cfg != {"characterKey": CID, "level": 20, "phase": "PHASE_0", "favorPoint": 0, "potentialRank": 0}:
        raise ValueError("source NPC config changed; no fixed-roster substitution permitted")
    rawchar = tables[CID]
    if rawchar != stage["predefined_character_sources"][CID]:
        raise ValueError("pinned table and source audit character disagree")
    if inst["overrideTalents"] is not None or inst["overrideSkillBlackboard"] is not None:
        raise ValueError("unconverted native overrides")
    phase = rawchar["phases"][0]
    base, interpolation = interpolate(phase["attributesKeyFrames"], cfg["level"])
    favor, favor_interpolation = interpolate(rawchar["favorKeyFrames"], cfg["favorPoint"])
    combined = {}
    for key, value in base.items():
        if isinstance(value, bool):
            if favor[key] is not False: raise ValueError("unconverted favor immunity")
            combined[key] = value
        else:
            value += favor[key]
            combined[key] = half_away_integer(value) if key in ROUNDING_PROFILE["integer_attributes"] else float(value)
    assert {k: combined[k] for k in ("maxHp", "atk", "def", "cost", "blockCnt")} == {"maxHp": 677, "atk": 199, "def": 74, "cost": 9, "blockCnt": 1}
    talent_rows = []
    for talent in rawchar["talents"]:
        for candidate in talent["candidates"]:
            condition = candidate["unlockCondition"]
            unlocked = condition["phase"] == "PHASE_0" and condition["level"] <= 20 and candidate["requiredPotentialRank"] <= 0
            talent_rows.append({"raw": candidate, "unlocked": unlocked})
    if any(t["unlocked"] for t in talent_rows): raise ValueError("new E0 talent requires explicit conversion")
    prefab = stage["predefined_prefab_sources"][CID]
    components = prefab["components"]
    assets = {}; before = library_identity(); binding = character_bindings(CID, assets)
    if library_identity() != before: raise ValueError("offline Spine reader changed during extraction")
    if binding["charpack_source"]["sha256"] != prefab["source"]["sha256"]:
        raise ValueError("fresh character binding and frozen native prefab refer to different CAB sources")
    mode = binding["modes"][0]
    attack = components[str(mode["attack_path_id"])]
    fields = attack["raw"]
    if attack["native_class"] != "RangedAttack" or (fields["_damageType"], fields["_atkScale"], fields["_timeMode"], fields["_waitForAttackEvent"]) != (1, 1, 0, 1):
        raise ValueError("native normal attack contract changed")
    for face in ("front", "back"):
        events = mode["bindings_by_face"][face]["events"]
        if [(e["name"], e["frame"], e["exact_authored_frame"]) for e in events] != [("OnAttack", 9, True)]:
            raise ValueError("native face timing differs or is unproven")
    paths = [p for p in (ROOT.parent / "data/battle/prefabs/[uc]projectiles.ab_unpacked").glob("CAB-*") if not p.name.endswith(".resS")]
    if len(paths) != 1: raise ValueError("projectile source CAB ambiguous")
    native_assets = NativeAssets(); projectile = native_assets.closure(paths[0], fields["_projectileKey"])
    movers = [c for c in projectile["components"].values() if c["native_class"] == "AdvancedMovement"]
    if len(movers) != 1 or movers[0]["raw"]["_speed"] != 10: raise ValueError("native crossbow movement changed")
    range_path = ROOT / "ark_emulator/data_range_table.json"
    native_range = read(range_path)[phase["rangeId"]]
    offsets = [[-cell["row"], cell["col"]] for cell in native_range["grids"]]
    skillid = rawchar["skills"][inst["skillIndex"]]["skillId"]
    selected_skill = skills[skillid]["levels"][inst["mainSkillLvl"]-1]
    if skills[skillid] != stage["predefined_skill_sources"][skillid]: raise ValueError("selected skill table source mismatch")
    pending = ["native_ACTIVATE_PREDEFINED_hidden_activation_and_routeIndex_semantics", "native_selected_skill_not_converted",
        "native_implicit_selector_priority_air_filter_and_immunity", "native_GetTimeScale_and_attack_FSM_callback_order",
        "native_projectile_tracking_collision_lifetime_and_hit_callback", "source_snapshot_vs_public_pin_alignment",
        "fixed12_deck_override_and_native_card_semantics_require_stage_composition"]
    identities = {"chapter01_audit": sha(SOURCE), "builder": sha(Path(__file__)),
        "offline_range_json": sha(range_path), "table_lock": sha(ROOT / "packages/campaign/operator_sources.lock.json"),
        "normalization_helper": sha(ROOT / "tools/normalize_campaign_operators.py"),
        "animation_binding_helper": sha(ROOT / "tools/extract_campaign_animation_bindings.py"),
        "native_asset_helper": sha(ROOT / "tools/build_chapter01_enemy_sources.py")}
    source = {"schema": "ark-sim/chapter01-predefines-source/v1", "source_identities": identities,
        "table_sources": lock, "predefines": deepcopy(predefines), "native_controls": stage["controls"],
        "native_stories": stage["stories"], "native_stage_document": stage["native_level_document"],
        "raw_character": rawchar, "selected_skill_id": skillid, "selected_skill_level": selected_skill,
        "prefab": prefab, "selected_skill_prefab_sources": stage["predefined_skill_prefabs"],
        "animation_binding": binding, "skeleton_assets": assets, "reader_identity": before,
        "projectile": projectile, "projectile_scripts": native_assets.scripts, "native_range": native_range,
        "talent_candidates": talent_rows, "stats": {"model_stats": combined,
            "base_exact": {k: rational_json(v) if not isinstance(v, bool) else v for k, v in base.items()},
            "favor_exact": {k: rational_json(v) if not isinstance(v, bool) else v for k, v in favor.items()},
            "interpolation": interpolation, "favor_interpolation": favor_interpolation,
            "profile": {"id": "native_predefine_linear_frames_half_away_v1", "rounding": ROUNDING_PROFILE["rounding"],
                "favor_mapping": "native favorPoint=0 directly uses exact frame level0; no trust-percent remapping",
                "client_formula_verified": False}}, "pending": pending, "formal_stage_approved": False}
    baseattrs = {dest: combined[src] for src, dest in {"maxHp": "max_hp", "atk": "atk", "def": "def", "magicResistance": "mres",
        "cost": "deploy_cost", "blockCnt": "block_count", "baseAttackTime": "attack_interval", "moveSpeed": "move_speed",
        "massLevel": "mass_level", "respawnTime": "redeploy_time"}.items()}
    baseattrs.update(attack_speed_ratio=combined["attackSpeed"]/100, block_cost=1)
    model = {"schemaVersion": 2, "manifest": {"id": "package/campaign/chapter01/predefined_adnach", "version": "0.1.0",
        "requires": ["preset/ark_standard"], "metadata": {"status": "partial_NPC_create_and_normal_attack_model",
            "source_identities": identities, "native_inst": deepcopy(inst), "pending": pending, "formal_stage_approved": False,
            "activation": "definition only; no automatic source-hidden conversion or timeline activation",
            "selector_profile": "one alive enemy in rotated exact range; implicit native priority and motion mask unproven",
            "clock_profile": "unscaled authored OnAttack frame9, base interval1/ASPD100; client GetTimeScale pending",
            "flight_profile": "launch planar distance / serialized speed10; live target HP/DEF at impact; captured target ID, no native homing proof"}},
        "entities": [{"id": UNIT, "kind": "entity", "tags": ["player", "ground", "predefined"],
            "components": {"attributes": {"base": baseattrs}, "resources": {"hp": {"initial": 677, "capacity_attribute": "max_hp", "role": "health"}},
                "abilities": [AID], "lifecycle": {"policy": "policy/ark_lifecycle"}, "spatial": {}}}],
        "selectors": [{"id": SID, "kind": "selector", "region": {"type": "grid_offsets", "offsets": offsets},
            "filters": [{"tag": "enemy"}, {"state": "alive"}], "limit": 1}],
        "abilities": [{"id": AID, "kind": "ability", "activation": {"mode": "automatic_attack"}, "target_capture": "at_cast",
            "selector": SID, "parameters": {"projectile_speed": 10}, "timeline": [{"at_seconds": .3,
                "effect": {"op": "damage", "damage_type": "physical", "scale": 1,
                    "condition": "inputs.targets[0].components.runtime.alive", "read_mode": {"source_attributes": "at_hit", "target_attributes": "at_hit"}}}]}]}
    return source, model


def assertions(source, model):
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    digest = implementation_digest(); results = []
    def fixture(position, facing="right"):
        p = deepcopy(model)
        p["entities"].append({"id": "unit/predefined_probe_enemy", "kind": "entity", "tags": ["enemy", "ground"],
            "components": {"attributes": {"base": {"max_hp": 1000, "atk": 100, "def": 30, "mres": 0}},
                "resources": {"hp": {"initial": 1000, "capacity": 1000, "role": "health"}},
                "lifecycle": {"policy": "policy/ark_lifecycle"}, "spatial": {}}})
        p["scenarioDraft"] = {"id": "scenario/predefined_probe", "ruleset": "ruleset/ark_standard", "map": {"rows": 8, "cols": 12},
            "initialEntities": [{"definition": UNIT, "instanceAlias": "npc", "position": {"row": 3, "col": 6}, "facing": facing},
                {"definition": "unit/predefined_probe_enemy", "instanceAlias": "enemy", "position": position}]}
        return p
    s = Engine.create(Compiler().compile(fixture({"row": 3, "col": 7})))
    assert s.ctx.resources.current("npc", "hp") == 677
    s.advance(9); assert s.ctx.resources.current("enemy", "hp") == 1000
    s.advance(1); launched = [e for e in s.session.events if e["type"] == "projectile.launched"]
    assert len(launched) == 1 and launched[0]["time"] == 9 and launched[0]["payload"]["flight_seconds"] == .1
    s.advance(2); assert s.ctx.resources.current("enemy", "hp") == 1000
    cp = s.checkpoint(); s.advance(1); assert s.ctx.resources.current("enemy", "hp") == 831
    restored = Engine.restore(s.program, cp); restored.advance(1)
    assert restored.checkpoint() == s.checkpoint()
    s.ctx.effects.execute("enemy", ["npc"], {"op": "damage", "damage_type": "physical", "scale": 1})
    assert s.ctx.resources.current("npc", "hp") == 651
    results.append({"probe": "normal_packet_and_HP_defense", "launch_tick": 9, "impact_tick": 12,
        "expected_attack_damage": 199-30, "expected_received_damage": 100-74, "target_hp": 831, "NPC_hp_after_damage": 651,
        "program_fingerprint": s.program.fingerprint, "runtime_fingerprint": s.runtime_fingerprint, "checkpoint_equal": True})
    for position, facing, hit in [({"row": 3, "col": 9}, "right", True), ({"row": 2, "col": 9}, "right", False),
            ({"row": 3, "col": 5}, "right", False), ({"row": 3, "col": 5}, "left", True)]:
        s = Engine.create(Compiler().compile(fixture(position, facing))); s.advance(22)
        assert s.ctx.resources.current("enemy", "hp") == (831 if hit else 1000)
        results.append({"probe": "range_facing", "position": position, "facing": facing, "expected_hit": hit, "passed": True})
    s = Engine.create(Compiler().compile(fixture({"row": 3, "col": 7}))); s.advance(10)
    s.ctx.lifecycle.retire("enemy", "withdraw"); s.advance(4)
    assert not [e for e in s.session.events if e["type"] == "damage.accepted"]
    results.append({"probe": "captured_target_retired_before_impact", "damage_packets": 0, "passed": True})
    assert len(source["predefines"]["characterCards"]) == 12 and not any(t["unlocked"] for t in source["talent_candidates"])
    if implementation_digest() != digest: raise RuntimeError("primary implementation changed during probes; refuse mixed identity evidence")
    return {"schema": "ark-sim/chapter01-predefines-assertions/v1", "implementation_digest": digest,
        "builder_sha256": sha(Path(__file__)), "model_sha256": hashlib.sha256(encoded(model)).hexdigest(),
        "source_sha256": hashlib.sha256(encoded(source)).hexdigest(), "probes": results, "passed": True,
        "scope": "synthetic stationary enemy short Engine probes; manual fixture damage/retirement are not command replay",
        "client_verified": False, "full_stage_executed": False, "formal_stage_approved": False}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--check", action="store_true"); args = p.parse_args()
    source, model = build(); evidence = assertions(source, model)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, value in (("native.reference.json", source), ("npc.model.json", model), ("assertions.json", evidence)):
        path = OUT/name
        if args.check:
            if not path.exists() or path.read_bytes() != encoded(value): raise ValueError("predefined source/model/assertion drift: " + name)
        else: path.write_bytes(encoded(value))
    print(json.dumps({"passed": True, "probes": len(evidence["probes"]), "native_cards": 12,
        "NPC_config": source["predefines"]["characterInsts"][0]["inst"], "implementation_digest": evidence["implementation_digest"], "full_stage_executed": False}))


if __name__ == "__main__": main()
