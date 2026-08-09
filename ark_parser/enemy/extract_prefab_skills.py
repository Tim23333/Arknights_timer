#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract enemy skill prefab components (enm_pfb) to JSON (research artifact).

Prefab source: data/battle/enm_pfb_*.ab_unpacked/CAB-* (Unity serialized
files, extracted by AssetStudio-Arknights). UnityPy reads the MonoBehaviour
type trees directly (Arknights bundles carry type trees), giving the runtime
field values used by EnemySkill / Ability / TargetTrigger / Buff components.

Class names are NOT stored locally (no MonoScript objects in the CABs), so
each component is labelled by field-signature heuristics and the script
pathID is kept for future mapping.

Outputs (relative to this file):
  data/skill_prefab_catalog.json           full component dump grouped by
                                           GameObject (prefab) name
  data/skill_prefab_catalog_summary.json   compact per-prefab key params

Usage:
    python extract_prefab_skills.py [--src DIR] [--out DIR]
"""

import argparse
import json
import os
from collections import Counter, defaultdict

import UnityPy

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.join(SCRIPT_DIR, "..", "..", "data", "battle")
DEFAULT_OUT = os.path.join(SCRIPT_DIR, "data")


def classify(fields):
    """Best-effort class label from serialized field signature."""
    if "_familyMask" in fields:
        return "EnemySkill"
    if "_castEffects" in fields or "_preDelayFactor" in fields:
        return "AbilityStandard"
    if "_projectileActions" in fields:
        return "ProjectileAbility"
    if "_attackBlackboardModeIndex" in fields or "_defaultModeIndex" in fields:
        return "AttackAbility"
    if "_abilities" in fields:
        return "CompositeAbility"
    if "_extraCondition" in fields and "_maxTarget" in fields:
        return "BuffAbility"
    if "_selector" in fields and (
            "_waitForAttackEvent" in fields or "_interuptIfTargetDead" in fields):
        return "Ability"
    if "_triggerType" in fields or "_targetRange" in fields:
        return "TargetTrigger"
    if "_buffs" in fields and "_timeMode" in fields:
        return "BuffHolder"
    if "_blackboard" in fields and "_key" in fields:
        return "Talent"
    if "_behaviours" in fields:
        return "Behaviour"
    return "Other"


ENEMY_SKILL_KEYS = [
    "_familyMask", "_maxTriggerTime", "_overwriteInitCooldown",
    "_resetMainAbilityCdWhenCastEnd", "_resetCdWaitFirstPeriod",
    "_checkParentActive", "_ignoreSilence", "_immuneStunWhenAffecting",
    "_addEnemyIdToSignalId", "_castLikeAttack", "_spCost",
]


def collect_buff_keys(fields):
    keys = []
    def walk(v):
        if isinstance(v, dict):
            if isinstance(v.get("buffKey"), str) and v["buffKey"]:
                keys.append(v["buffKey"])
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(fields)
    return keys


def compact_params(cls, fields):
    """Extract the parameters most relevant to behavior simulation."""
    out = {}
    if cls == "EnemySkill":
        for k in ENEMY_SKILL_KEYS:
            if k in fields:
                out[k] = fields[k]
        trig = fields.get("_trigger")
        if isinstance(trig, dict) and trig.get("m_PathID"):
            out["_triggerRef"] = trig["m_PathID"]
    elif cls in ("Ability", "AbilityStandard", "AttackAbility",
                 "ProjectileAbility", "CompositeAbility", "BuffAbility"):
        for k in ("_selector", "_waitForAttackEvent", "_interuptIfTargetDead",
                  "_interruptAbilityOnDetach", "_attachPassiveBuffsOnDummy",
                  "_ignoreIfOwnerDead", "_forceAsDmgOrHealAbility",
                  "_preDelay", "_preDelayFactor", "_selectTargetTiming",
                  "_selectTargetSource", "_allowNoTarget", "_alwaysIncludeTarget",
                  "_animKey", "_endAnimKey", "_resetCdStrategy", "_purposeMask",
                  "_timeMode", "_atkScale", "_attackBlackboardModeIndex",
                  "_defaultModeIndex", "_extraCondition", "_maxTarget",
                  "_onlyRunOnce", "_extraConditionTiming"):
            if k in fields:
                out[k] = fields[k]
        if "_castEffects" in fields:
            out["_castEffects"] = fields["_castEffects"]
        if "_projectileActions" in fields:
            out["_projectileActions"] = fields["_projectileActions"]
        if "_abilities" in fields:
            out["_abilities"] = fields["_abilities"]
    bkeys = collect_buff_keys(fields)
    if bkeys:
        out["buffKeys"] = sorted(set(bkeys))
    return out


def process_cab(path, go_names, out_prefabs, script_clusters):
    env = UnityPy.load(path)
    names = {}
    for obj in env.objects:
        if obj.type.name == "GameObject":
            try:
                names[obj.path_id] = obj.read().m_Name
            except Exception:
                names[obj.path_id] = "?"
    go_names.update(names)
    mono_count = 0
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tt = obj.read_typetree()
        except Exception:
            continue
        mono_count += 1
        go = tt.get("m_GameObject", {}).get("m_PathID")
        script = tt.get("m_Script", {}).get("m_PathID")
        fields = {k: v for k, v in tt.items() if not k.startswith("m_")}
        cls = classify(fields)
        name = names.get(go, "?")
        entry = {"cabin": os.path.basename(path), "pathID": obj.path_id,
                 "scriptPathID": script, "class": cls, "fields": fields}
        out_prefabs[name].append(entry)
        cluster = script_clusters.setdefault(script, {"class": cls, "count": 0,
                                                       "fields": set()})
        cluster["count"] += 1
        cluster["fields"].update(fields.keys())
        if cluster["class"] == "Other" and cls != "Other":
            cluster["class"] = cls
    return mono_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    cabs = []
    for d in sorted(os.listdir(args.src)):
        if not d.startswith("enm_pfb"):
            continue
        pkg = os.path.join(args.src, d)
        for f in sorted(os.listdir(pkg)):
            if f.startswith("CAB-"):
                cabs.append(os.path.join(pkg, f))
    print(f"cabs: {len(cabs)}")

    go_names = {}
    prefabs = defaultdict(list)
    script_clusters = {}
    total = 0
    for i, cab in enumerate(cabs, 1):
        try:
            n = process_cab(cab, go_names, prefabs, script_clusters)
        except Exception as e:
            print(f"[ERR] {os.path.basename(cab)}: {e}")
            continue
        total += n
        if i % 6 == 0:
            print(f"[{i}/{len(cabs)}] monos={total} prefabs={len(prefabs)}")

    catalog = {
        "meta": {
            "generatedBy": "extract_prefab_skills.py",
            "cabs": len(cabs),
            "monoBehaviours": total,
            "note": "class labels are field-signature heuristics; "
                    "scriptPathID kept for exact mapping",
        },
        "prefabs": {k: {"components": v} for k, v in sorted(prefabs.items())},
        "scriptClusters": {
            str(k): {"class": v["class"], "count": v["count"],
                     "fields": sorted(v["fields"])}
            for k, v in sorted(script_clusters.items())
        },
    }
    path = os.path.join(args.out, "skill_prefab_catalog.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, separators=(",", ":"))

    summary = {}
    for name, comps_raw in prefabs.items():
        comps = []
        for c in comps_raw:
            p = compact_params(c["class"], c["fields"])
            comps.append({"class": c["class"], "scriptPathID": c["scriptPathID"],
                          **p})
        summary[name] = comps
    spath = os.path.join(args.out, "skill_prefab_catalog_summary.json")
    with open(spath, "w", encoding="utf-8") as f:
        json.dump({"prefabs": summary}, f, ensure_ascii=False,
                  separators=(",", ":"))

    cls_counter = Counter(c["class"] for v in prefabs.values() for c in v)
    print(f"monos={total} prefabKeys={len(prefabs)}")
    print("class distribution:", dict(cls_counter))
    print(f"catalog -> {path}")
    print(f"summary -> {spath}")


if __name__ == "__main__":
    main()
