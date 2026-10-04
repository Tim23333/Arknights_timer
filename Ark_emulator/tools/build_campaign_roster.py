"""Freeze campaign inputs; this tool never imports a battle runtime.

The resulting reference is deliberately not an executable V2 content package.
Raw table rows and prefab links are evidence, not implemented abilities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "ark_parser" / "character" / "data"
OUTPUT = ROOT / "packages" / "campaign" / "roster.reference.json"
FILES = ("characters.json", "skills.json", "battle_equip.json", "uniequip.json",
         "operator_skill_prefab_summary.json", "skill_prefab_catalog_operator.json")
# Stable squad order is independent of extraction-table dictionary insertion order.
SELECTION = (
    ("char_151_myrtle", "skchr_myrtle_2", ["dp_periodic", "heal_periodic", "attack_stop"]),
    ("char_222_bpipe", "skchr_bpipe_3", ["physical", "multihit", "dp_on_kill", "initial_sp", "random_proc"]),
    ("char_010_chen", "skchr_chen_1", ["sp_on_attack", "next_attack", "stun", "sp_grant"]),
    ("char_107_liskam", "skchr_liskam_1", ["sp_on_hit", "damage_block_once", "random_ally_sp"]),
    ("char_202_demkni", "skchr_demkni_3", ["heal_aoe_periodic", "arts_amplification", "slow", "sp_on_heal"]),
    ("char_128_plosis", "skchr_plosis_2", ["heal_multitarget", "sp_rate", "range_change", "attack_interval"]),
    ("char_103_angel", "skchr_angel_3", ["physical", "multihit", "automatic_activation", "air_target"]),
    ("char_180_amgoat", "skchr_amgoat_3", ["arts", "random_targets", "multitarget", "range_change"]),
    ("char_003_kalts", "skchr_kalts_3", ["summon", "bound_skill", "true_damage", "time_decay", "conditional_hp_loss"]),
    ("char_358_lisa", "skchr_lisa_3", ["sluggish", "fragile", "hp_regeneration", "attack_stop", "aura"]),
    ("char_400_weedy", "skchr_weedy_3", ["displace", "distance_true_damage", "projectile", "token_skill_link"]),
    ("char_179_cgbird", "skchr_cgbird_3", ["heal_multitarget", "arts_dodge", "resistance_buff", "decoy_summon"]),
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def walk(value, path=""):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, f"{path}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}/{index}")


def unlocked(condition, config):
    phase, level = condition.get("phase", 0), condition.get("level", 1)
    return config["elite_phase"] > phase or (
        config["elite_phase"] == phase and config["level"] >= level)


def validate_config(character, skill, levels, config):
    phase, level = config["elite_phase"], config["level"]
    if not 0 <= phase < len(character["phases"]):
        raise ValueError("elite phase unavailable")
    if not 1 <= level <= character["phases"][phase]["maxLevel"]:
        raise ValueError("level unavailable")
    if phase != 2 or level != 70:
        raise ValueError("campaign fixes elite phase 2 and level 70")
    if config["skill_id"] != skill["skillId"]:
        raise ValueError("configured skill does not belong to selected skill slot")
    if not unlocked(skill.get("initialUnlockCond", {}), config):
        raise ValueError("skill locked")
    index = config["skill_level_index"]
    if config["skill_rank"] != 7 or config["mastery"] != 3 or index != 9:
        raise ValueError("campaign fixes skill rank 7 plus mastery 3 (zero-based index 9)")
    if config["potential"] != 1:
        raise ValueError("campaign fixes potential 1")
    if not 0 <= index < len(levels):
        raise ValueError("skill level unavailable")
    if index >= 7:
        mastery = index - 7
        upgrades = skill.get("specializeLevelUpData", [])
        if mastery >= len(upgrades) or not unlocked(upgrades[mastery]["unlockCond"], config):
            raise ValueError("mastery locked")
    if config["potential_rank"] != 0 or config["trust_percent"] != 100:
        raise ValueError("campaign fixes potential rank 0 (potential 1) and trust 100%")
    if config["equipment_id"] is not None or config["equipment_level"] != 0:
        raise ValueError("equipment unlock/formula normalization pending; fixed roster has no module")


def build(source=SOURCE):
    tables, sources = {}, {}
    for name in FILES:
        path = source / name
        raw = path.read_bytes()
        tables[name] = json.loads(raw)
        sources[name] = {"path": f"../ark_parser/character/data/{name}",
                         "sha256": digest(raw), "bytes": len(raw)}
    chars, skills = tables["characters.json"], tables["skills.json"]
    summary = tables["operator_skill_prefab_summary.json"]["prefabs"]
    catalog = tables["skill_prefab_catalog_operator.json"]["prefabs"]
    frozen = {"characters": {}, "skills": {}, "uniequip": {}, "battle_equip": {},
              "prefab_summary": {}, "prefab_catalog": {}, "linked_components": []}
    roster, token_ids, prefab_ids, gaps = [], set(), set(), []
    trait_character_ids = set()
    for order, (cid, sid, mechanisms) in enumerate(SELECTION, 1):
        character = chars[cid]
        skill = next(s for s in character["skills"] if s.get("skillId") == sid)
        config = {"elite_phase": 2, "level": 70, "skill_id": sid,
                  "skill_level_index": 9, "skill_rank": 7, "mastery": 3,
                  "potential_rank": 0, "potential": 1, "trust_percent": 100,
                  "equipment_id": None, "equipment_level": 0}
        validate_config(character, skill, skills[sid]["levels"], config)
        selected_level = skills[sid]["levels"][9]
        prefab = selected_level.get("prefabId")
        if prefab:
            prefab_ids.add(prefab)
        active_talents = []
        for talent in character.get("talents", []):
            eligible = [c for c in talent.get("candidates", [])
                        if unlocked(c.get("unlockCondition", {}), config)
                        and c.get("requiredPotentialRank", 0) <= config["potential_rank"]]
            if eligible:
                chosen = max(eligible, key=lambda c: (c.get("unlockCondition", {}).get("phase", 0),
                             c.get("unlockCondition", {}).get("level", 1), c.get("requiredPotentialRank", 0)))
                active_talents.append(chosen)
                if chosen.get("tokenKey"):
                    token_ids.add(chosen["tokenKey"])
        equip_candidates = sorted(k for k, v in tables["uniequip.json"].items()
                                  if v.get("charId", v.get("10")) == cid)
        for key in equip_candidates:
            frozen["uniequip"][key] = tables["uniequip.json"][key]
            if key in tables["battle_equip.json"]:
                frozen["battle_equip"][key] = tables["battle_equip.json"][key]
        frozen["characters"][cid] = character
        frozen["skills"][sid] = skills[sid]
        for _, value in walk(character.get("trait", {})):
            if isinstance(value, dict) and value.get("key") == "char_id" and value.get("valueStr"):
                trait_character_ids.add(value["valueStr"])
                gaps.append({"character_id": cid, "kind": "trait_character_reference_semantics_pending",
                             "referenced_character_id": value["valueStr"],
                             "detail": "Freeze explicit trait char_id, but do not substitute it for talent tokenKey."})
        roster.append({"order": order, "character_id": cid, "name": character["name"],
                       "config": config, "skill_level": selected_level, "active_talents": active_talents,
                       "candidate_mechanisms": mechanisms, "equipment_candidates": equip_candidates,
                       "range_ids": sorted({v.get("rangeId") for v in character["phases"]
                                             if v.get("rangeId")} | ({selected_level["rangeId"]}
                                             if selected_level.get("rangeId") else set())),
                       "status": "source_frozen_only", "v2_imported": False,
                       "model_validated": False, "client_validated": False, "runnable": False})
        for path, value in walk({"skill": selected_level, "talents": active_talents}):
            if isinstance(value, dict) and "key" in value and "value" not in value and "valueStr" not in value:
                gaps.append({"character_id": cid, "kind": "missing_blackboard_value", "path": path,
                             "key": value["key"]})
        for talent in active_talents:
            if talent.get("prefabKey"):
                gaps.append({"character_id": cid, "kind": "character_talent_prefab_scope_pending",
                             "prefab_key": talent["prefabKey"],
                             "detail": "Talent prefabKey is character-scoped; generic skill catalog names 1/2 cannot resolve it safely."})
        if character.get("displayTokenDict"):
            gaps.append({"character_id": cid, "kind": "display_token_dictionary_unreliable",
                         "detail": "Raw extraction contains malformed/foreign rows; use talent.tokenKey, then validate prefab linkage."})
    for token in sorted(token_ids | trait_character_ids):
        if token not in chars:
            gaps.append({"kind": "missing_token", "token_id": token})
            continue
        frozen["characters"][token] = chars[token]
        for skill in chars[token].get("skills", []):
            sid = skill.get("skillId")
            if sid in skills:
                frozen["skills"][sid] = skills[sid]
                prefab_ids.update(l.get("prefabId", sid) for l in skills[sid].get("levels", []))
            elif sid:
                gaps.append({"kind": "missing_token_skill", "token_id": token, "skill_id": sid})
    # Preserve exact CAB-local component references rather than trusting heuristic class names.
    index = {}
    for record in catalog.values():
        for component in record.get("components", []):
            index[(component.get("cabin"), component.get("pathID"))] = component
    pending = []
    for prefab in sorted(prefab_ids):
        if prefab in summary:
            frozen["prefab_summary"][prefab] = summary[prefab]
        if prefab in catalog:
            frozen["prefab_catalog"][prefab] = catalog[prefab]
            pending.extend(catalog[prefab].get("components", []))
        else:
            gaps.append({"kind": "missing_skill_prefab", "prefab_id": prefab})
    visited, unresolved = set(), set()
    while pending:
        component = pending.pop()
        identity = (component.get("cabin"), component.get("pathID"))
        if identity in visited:
            continue
        visited.add(identity)
        frozen["linked_components"].append(component)
        for _, value in walk(component.get("fields", {})):
            if not isinstance(value, dict) or not value.get("m_PathID"):
                continue
            target = (identity[0], value["m_PathID"])
            if value.get("m_FileID", 0) == 0 and target in index:
                pending.append(index[target])
            else:
                unresolved.add((identity[0], value.get("m_FileID", 0), value["m_PathID"]))
    frozen["linked_components"].sort(key=lambda c: (c.get("cabin", ""), c.get("pathID", 0)))
    return {"schema": "ark_sim_campaign_roster_reference_v1", "purpose": "offline source freeze; not V2 executable content",
            "status": "source_frozen_only", "sources": sources, "roster": roster,
            "token_ids": sorted(token_ids), "trait_character_ids": sorted(trait_character_ids),
            "frozen": frozen, "data_gaps": gaps,
            "unresolved_prefab_object_references": [{"cabin": c, "file_id": f, "path_id": p}
                                                     for c, f, p in sorted(unresolved)],
            "validation_gates": ["normalize raw equipment/trait/token fields", "convert to V2 primitives",
                                 "compile actual dependencies", "independent mechanism model assertions",
                                 "fixed-squad chapter regression", "client frame comparison"],
            "coverage_limits": ["candidate_mechanisms are source-backed requirements, not passing coverage",
                                "fixed no-module squad does not exercise actual equipment",
                                "freeze/sleep/fear/elemental damage/revival and chapter-specific enemy mechanics require separate cases",
                                "provider replacement/transaction/rollback/checkpoint/replay are technical synthetic validations",
                                "prefab class labels are heuristic; unresolved paths may be assets, objects, or missing behaviours",
                                "normal attacks/character prefab/animation/projectile/range coordinates still require additional sources"],
            "frozen_sha256": digest(canonical(frozen))}


def check_reference(reference, source=SOURCE):
    expected = build(source)
    if reference != expected:
        raise ValueError("roster/reference/source identity differs; rebuild and revalidate downstream evidence")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check_reference(json.loads(args.output.read_bytes()), args.source)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical(build(args.source)))
    print(json.dumps({"output": str(args.output), "checked": args.check, "operators": 12,
                      "status": "source_frozen_only"}))


if __name__ == "__main__":
    main()
