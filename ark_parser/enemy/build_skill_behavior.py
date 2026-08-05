#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Join enemy_database skills with enm_pfb prefab components (research
artifact). For every (enemy, skill) the output carries:
  - ESkillData blackboard (priority/cooldown/initCooldown/bb params)
  - EnemySkill component params (familyMask/maxTriggerTime/...)
  - resolved TargetTrigger params (via pathID ref inside the same prefab)
  - Ability/AbilityStandard params (waitForAttackEvent/timeMode/preDelay/...)
  - buffKeys referenced by the prefab (actual effect templates)

Outputs:
  data/skill_behavior_catalog.json
  data/skill_prefab_coverage.json

Usage:
    python build_skill_behavior.py [--out DIR]
"""

import argparse
import json
import os
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(SCRIPT_DIR, "data")

TRIGGER_FIELDS = [
    "_triggerType", "_targetRange", "_time", "_hpRatio", "_damageTakenRatio",
    "_condition", "_extraCondition", "_event", "_forcePredict",
    "_normalSkillOnly", "_maxTriggerTime", "_interval", "_radius",
    "_target", "_buffKeys", "_minHpRatio",
]


def find_components(comps, cls=None):
    return [c for c in comps
            if cls is None or c["class"] == cls or
            (isinstance(cls, tuple) and c["class"] in cls)]


def resolve_ref(components, ref):
    """Resolve a PPtr {m_PathID} to a component in the same prefab."""
    if not isinstance(ref, dict):
        return None
    pid = ref.get("m_PathID")
    if not pid:
        return None
    for c in components:
        if c.get("pathID") == pid:
            return c
    return None


def summarize_trigger(comp):
    if comp is None:
        return None
    f = comp["fields"]
    return {k: f[k] for k in TRIGGER_FIELDS if k in f} or {"_classHint": comp["class"]}


def summarize_ability(comp):
    f = comp["fields"]
    return {k: f[k] for k in (
        "_waitForAttackEvent", "_timeMode", "_preDelay", "_atkScale",
        "_interuptIfTargetDead", "_selectTargetTiming", "_selectTargetSource",
        "_allowNoTarget", "_alwaysIncludeTarget", "_attackBlackboardModeIndex",
        "_defaultModeIndex", "_extraCondition", "_maxTarget", "_onlyRunOnce",
        "_preDelayFactor", "_purposeMask", "_resetCdStrategy") if k in f}


def collect_buff_keys(fields):
    keys = []
    def walk(v):
        if isinstance(v, dict):
            if isinstance(v.get("buffKey"), str) and v["buffKey"]:
                keys.append(v["buffKey"])
            if isinstance(v.get("templateKey"), str) and v["templateKey"]:
                keys.append(v["templateKey"])
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(fields)
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    cat = json.load(open(os.path.join(args.out, "skill_prefab_catalog.json"),
                         encoding="utf-8"))
    db = json.load(open(os.path.join(args.out, "enemy_database.json"),
                        encoding="utf-8"))
    prefabs = {k.lower(): v for k, v in cat["prefabs"].items()}

    out = {}
    usage = Counter()
    resolved = Counter()
    for eid, levels in db.items():
        for lv in levels:
            d = lv.get("data") or {}
            for si, sk in enumerate(d.get("skills") or []):
                pk = sk.get("prefabKey")
                if not pk:
                    continue
                usage[pk] += 1
                prefab = prefabs.get(pk.lower())
                if prefab is None:
                    resolved[pk] = 0
                    continue
                comps = prefab["components"]
                eskill = find_components(comps, "EnemySkill")
                abilities = find_components(comps, (
                    "Ability", "AbilityStandard", "AttackAbility",
                    "ProjectileAbility", "CompositeAbility", "BuffAbility"))
                trig_ref = None
                if eskill:
                    trig_ref = eskill[0]["fields"].get("_trigger")
                trigger_comp = resolve_ref(comps, trig_ref)
                entry = {
                    "prefabKey": pk,
                    "enemyId": eid,
                    "skillIndex": si,
                    "blackboard": sk.get("blackboard"),
                    "priority": sk.get("priority"),
                    "cooldown": sk.get("cooldown"),
                    "initCooldown": sk.get("initCooldown"),
                    "spCost": sk.get("spCost"),
                    "enemySkill": {
                        k: eskill[0]["fields"][k]
                        for k in ("_familyMask", "_maxTriggerTime",
                                  "_overwriteInitCooldown", "_ignoreSilence",
                                  "_castLikeAttack", "_resetMainAbilityCdWhenCastEnd",
                                  "_resetCdWaitFirstPeriod", "_checkParentActive",
                                  "_spCost") if eskill and k in eskill[0]["fields"]
                    },
                    "trigger": summarize_trigger(trigger_comp),
                    "abilities": [summarize_ability(a) for a in abilities],
                    "buffKeys": sorted(set(
                        bk for c in comps for bk in collect_buff_keys(c["fields"])
                    )),
                }
                out.setdefault(pk, []).append(entry)
                resolved[pk] = 1

    path = os.path.join(args.out, "skill_behavior_catalog.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    total_usage = sum(usage.values())
    total_resolved = sum(1 for k in usage if resolved.get(k))
    cov = {
        "uniquePrefabKeys": len(usage),
        "uniqueResolved": total_resolved,
        "resolveRatio": round(total_resolved / max(1, len(usage)), 4),
        "skillInstances": total_usage,
        "missingPrefabKeys": sorted(k for k in usage if not resolved.get(k)),
        "topUsedPrefabKeys": [k for k, _ in usage.most_common(30)],
    }
    cpath = os.path.join(args.out, "skill_prefab_coverage.json")
    with open(cpath, "w", encoding="utf-8") as f:
        json.dump(cov, f, ensure_ascii=False, indent=1)

    print(f"unique prefabKeys={len(usage)} resolved={total_resolved} "
          f"({cov['resolveRatio']*100:.1f}%) skillInstances={total_usage}")
    print(f"missing ({len(cov['missingPrefabKeys'])}): "
          f"{cov['missingPrefabKeys'][:15]}")
    print(f"catalog -> {path}")


if __name__ == "__main__":
    main()
