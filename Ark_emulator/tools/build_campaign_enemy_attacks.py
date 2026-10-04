"""Recover actual default combat nodes and translate first-stage enemy attacks.

Enemy mode._attack is null here: the attack lives in mode._combat. Neither null
nor passive applyWay permits synthesizing an arbitrary attacking ability.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_mainline_dependencies import build as dependency_plan

OUTPUT = ROOT / "packages/campaign/enemies.00_10.attacks.json"


def recover(wanted):
    import UnityPy
    found = {key: [] for key in wanted}
    for path in sorted((ROOT.parent / "data/battle").glob("enm_pfb*.ab_unpacked/CAB-*")):
        if path.suffix == ".resS":
            continue
        env = UnityPy.load(str(path))
        objects = {o.path_id: o for o in env.objects}
        trees = None
        for obj in env.objects:
            if obj.type.name != "GameObject":
                continue
            go = obj.read()
            if go.m_Name not in wanted:
                continue
            if trees is None:
                trees = {o.path_id: o.read_typetree() for o in env.objects if o.type.name == "MonoBehaviour"}
            roots = [trees[c.component.path_id] for c in go.m_Component
                     if c.component.path_id in trees and "_modes" in trees[c.component.path_id]]
            if len(roots) != 1:
                raise ValueError(f"Native mode root ambiguous: {go.m_Name}")
            root = roots[0]
            pointer = root["_modes"][0]
            if pointer["m_FileID"]:
                raise ValueError("External enemy mode requires dependency resolution")
            mode = trees[pointer["m_PathID"]]
            combat = mode["_combat"]
            if combat["m_FileID"] or combat["m_PathID"] not in trees:
                raise ValueError("Native enemy combat node missing or external")
            found[go.m_Name].append({"source": str(path.relative_to(ROOT.parent)).replace("\\", "/"),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "mode_path_id": pointer["m_PathID"],
                "combat_path_id": combat["m_PathID"], "combat_fields": trees[combat["m_PathID"]],
                "raw_mode_attack_pointer": mode["_attack"]})
    if any(len(rows) != 1 for rows in found.values()):
        raise ValueError("Each native enemy needs exactly one source prefab")
    return {key: rows[0] for key, rows in found.items()}


def build():
    plan = dependency_plan("level_main_00-10")
    frames_path = ROOT.parent / "data/tables/effect_frames.json"
    frames = json.loads(frames_path.read_text(encoding="utf-8"))["enemies"]
    sources = recover({r["native_id"] for r in plan["resolved_enemies"]})
    abilities, selectors, records = [], [], []
    for row in plan["resolved_enemies"]:
        identifier = row["native_id"]
        source = sources[identifier]
        fields = source["combat_fields"]
        passive = row["resolved"]["applyWay"] == "NONE"
        records.append({"native_id": identifier, "source": source, "passive": passive,
                        "client_timing_verified": False, "animation_scaling_pending": not passive})
        if passive:
            continue
        if row["resolved"]["applyWay"] != "MELEE" or fields.get("_damageType") not in (1, 2, 3):
            raise ValueError("Unsupported enemy attack variant")
        if fields.get("_projectileKey") or fields.get("_activeBuffs"):
            raise ValueError("Enemy projectile or on-hit Buff needs conversion")
        animation = fields["_animKey"]
        events = [e for e in frames[identifier]["anims"][animation]["ev"] if e["n"] == "OnAttack"]
        if not events or any(e["f"] < 0 for e in events):
            raise ValueError("Valid enemy animation events are required")
        selector_id = f"selector/{identifier}/blocked_target"
        selectors.append({"id": selector_id, "kind": "selector", "region": {"type": "all", "blocked_only": True},
            "filters": [{"tag": "player"}, {"state": "alive"}], "limit": 1})
        abilities.append({"id": f"ability/{identifier}/normal_attack", "kind": "ability",
            "activation": {"mode": "automatic_attack"}, "selector": selector_id,
            "timeline": [{"at_seconds": e["f"] / 30, "effect": {"op": "damage", "scale": fields["_atkScale"],
                "damage_type": {1: "physical", 2: "arts", 3: "true"}[fields["_damageType"]]}} for e in events],
            "metadata": {"native_id": identifier, "source_combat_path_id": source["combat_path_id"],
                         "timing_policy": "unscaled_native_event_model", "client_fsm_timing_verified": False}})
    return {"schemaVersion": 2, "status": "source_backed_attack_models", "manifest": {
        "id": "package/campaign/enemy_attacks/00_10", "version": "0.1.0", "requires": ["preset/ark_standard"],
        "metadata": {"dependency_plan_source": plan["source"], "native_enemy_records": records,
                     "frames_sha256": hashlib.sha256(frames_path.read_bytes()).hexdigest(),
                     "formal_stage_approved": False}}, "abilities": abilities, "selectors": selectors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
            raise SystemExit("Enemy attack source/artifact mismatch")
    else:
        OUTPUT.write_text(text, encoding="utf-8")
    print("Four native combat attacks converted; passive flying enemy preserved.")
