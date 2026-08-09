#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract operator/token skill prefab components ([uc]skills CAB) to JSON.

Prefab source: data/battle/prefabs/[uc]skills.ab_unpacked/CAB-* (Unity
serialized files). UnityPy reads the GameObject names and MonoBehaviour
type trees directly, giving the runtime fields used by Ability / Buff /
Selector / Effect components for OPERATOR skills (the enemy side has its
own catalog from enm_pfb).

Outputs (relative to this file, ark_parser/character/):
  data/skill_prefab_catalog_operator.json  full component dump grouped by
                                           GameObject (prefab) name
  data/operator_skill_prefab_summary.json  compact per-prefab params incl.
                                           _buffs (emulator input)
  data/operator_skill_prefab_coverage.json prefabId coverage vs skills.json

Usage:
    python extract_operator_skill_prefabs.py [--src DIR] [--out DIR]
"""

import argparse
import json
import os
from collections import Counter, defaultdict

import UnityPy

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.join(SCRIPT_DIR, "..", "..", "data", "battle",
                           "prefabs", "[uc]skills.ab_unpacked")
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


def walk_buffs(v, out):
    """Collect every BuffData dict (has buffKey/templateKey) from a value."""
    if isinstance(v, dict):
        if isinstance(v.get("buffKey"), str) and v["buffKey"]:
            out.append(v)
        for x in v.values():
            walk_buffs(x, out)
    elif isinstance(v, list):
        for x in v:
            walk_buffs(x, out)


def compact_params(cls, fields):
    """Parameters most relevant to operator-skill behaviour simulation."""
    out = {}
    meta = fields.get("_metadata")
    if isinstance(meta, dict):
        alias = meta.get("namedAsAlias")
        if isinstance(alias, str) and alias:
            out["namedAsAlias"] = alias
        if meta.get("blackboardPrefix"):
            out["blackboardPrefix"] = meta["blackboardPrefix"]
    for k in ("_selector", "_waitForAttackEvent", "_interuptIfTargetDead",
              "_interruptAbilityOnDetach", "_attachPassiveBuffsOnDummy",
              "_ignoreIfOwnerDead", "_forceAsDmgOrHealAbility",
              "_preDelay", "_preDelayFactor", "_selectTargetTiming",
              "_selectTargetSource", "_allowNoTarget", "_alwaysIncludeTarget",
              "_animKey", "_endAnimKey", "_resetCdStrategy", "_purposeMask",
              "_timeMode", "_atkScale", "_attackBlackboardModeIndex",
              "_defaultModeIndex", "_extraCondition", "_maxTarget",
              "_onlyRunOnce", "_extraConditionTiming", "_lifeTimeKey",
              "_maxChargeTime", "_chargeTimeKey",
              "_damageType", "_elementDamageType", "_epDamageRatio",
              "_projectileKey", "_additionalProjectile", "_extraDamageType",
              "_additionalTimes", "_preDelay"):
        if k in fields:
            out[k] = fields[k]
    # keep buff containers by field name; semantics depend on the
    # component class (Ability._buffs = owner self-buffs; BuffAbility._buffs
    # / Ability._activeBuffs = target buffs; _passiveBuffs = passive)
    for _fk in ("_buffs", "_activeBuffs", "_passiveBuffs"):
        _v = fields.get(_fk)
        if isinstance(_v, list) and _v:
            out[_fk] = _v
    if "_castEffects" in fields:
        out["_castEffects"] = fields["_castEffects"]
    if "_projectileActions" in fields:
        out["_projectileActions"] = fields["_projectileActions"]
    for _rk in ("_abilities", "_extraAbilities", "_wrappedAbilities"):
        if fields.get(_rk):
            out[_rk] = fields[_rk]
    return out


def process_cab(path, out_prefabs, out_names, out_go_map):
    env = UnityPy.load(path)
    names = {}
    for obj in env.objects:
        if obj.type.name == "GameObject":
            try:
                names[obj.path_id] = obj.read().m_Name
            except Exception:
                names[obj.path_id] = "?"
    out_names.update(names)
    out_go_map.update(names)     # GameObject pathID -> name (per CAB)
    mono = 0
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tt = obj.read_typetree()
        except Exception:
            continue
        mono += 1
        go = tt.get("m_GameObject", {}).get("m_PathID")
        script = tt.get("m_Script", {}).get("m_PathID")
        fields = {k: v for k, v in tt.items() if not k.startswith("m_")}
        cls = classify(fields)
        out_prefabs[names.get(go, "?")].append({
            "cabin": os.path.basename(path), "pathID": obj.path_id,
            "gameObjectPathID": go, "scriptPathID": script,
            "class": cls, "fields": fields})
    return mono


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    cabs = []
    for f in sorted(os.listdir(args.src)):
        if f.startswith("CAB-") and not f.endswith(".resS"):
            cabs.append(os.path.join(args.src, f))
    print(f"cabs: {len(cabs)}")

    prefabs = defaultdict(list)
    names = {}
    go_map = {}
    total = 0
    for cab in cabs:
        try:
            n = process_cab(cab, prefabs, names, go_map)
        except Exception as e:
            print(f"[ERR] {os.path.basename(cab)}: {e}")
            continue
        total += n
    print(f"monos={total} prefabKeys={len(prefabs)}")

    catalog = {
        "meta": {
            "generatedBy": "extract_operator_skill_prefabs.py",
            "cabs": len(cabs), "monoBehaviours": total,
            "note": "class labels are field-signature heuristics; "
                    "scriptPathID kept for exact mapping",
            "gameObjectPathIDToName": go_map,
        },
        "prefabs": {k: {"components": v} for k, v in sorted(prefabs.items())},
    }
    cpath = os.path.join(args.out, "skill_prefab_catalog_operator.json")
    with open(cpath, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, separators=(",", ":"))

    summary = {}
    for name, comps_raw in prefabs.items():
        comps = []
        for c in comps_raw:
            p = compact_params(c["class"], c["fields"])
            comps.append({"class": c["class"],
                          "scriptPathID": c["scriptPathID"],
                          "gameObjectPathID": c.get("gameObjectPathID"),
                          **p})
        summary[name] = comps
    spath = os.path.join(args.out, "operator_skill_prefab_summary.json")
    with open(spath, "w", encoding="utf-8") as f:
        json.dump({"prefabs": summary}, f, ensure_ascii=False,
                  separators=(",", ":"))

    # coverage vs skills.json prefabIds; a MainSkill.overridePrefabKey
    # (characters.json) replaces the LevelData.prefabId at runtime (e.g.
    # token summons like sktok_phatm2_mndclv_3 -> sktok_empty), so the
    # effective prefab is the override when present.
    sk_path = os.path.join(args.out, "skills.json")
    ch_path = os.path.join(args.out, "characters.json")
    override = {}
    if os.path.exists(ch_path):
        try:
            chars = json.load(open(ch_path, encoding="utf-8"))
            for c in chars.values():
                for ms in (c.get("skills") or []):
                    sid = ms.get("skillId")
                    ov = ms.get("overridePrefabKey")
                    if sid and ov:
                        override[sid] = ov
        except Exception:
            override = {}
    prefab_ids = set()
    if os.path.exists(sk_path):
        sk = json.load(open(sk_path, encoding="utf-8"))
        for v in sk.values():
            for lv in (v.get("levels") or [])[:1]:
                pid = lv.get("prefabId")
                if pid:
                    prefab_ids.add(override.get(v.get("skillId"), pid))
    keys = set(prefabs)
    cov = {
        "skillPrefabIds": len(prefab_ids),
        "matched": len(prefab_ids & keys),
        "missing": sorted(prefab_ids - keys),
        "extraGameObjects": len(keys - prefab_ids),
    }
    cov_path = os.path.join(args.out, "operator_skill_prefab_coverage.json")
    with open(cov_path, "w", encoding="utf-8") as f:
        json.dump(cov, f, ensure_ascii=False, indent=1)

    cls_counter = Counter(c["class"] for v in prefabs.values() for c in v)
    print("class distribution:", dict(cls_counter))
    print(f"coverage: {cov['matched']}/{cov['skillPrefabIds']} prefabIds")
    print(f"catalog -> {cpath}")
    print(f"summary -> {spath}")
    print(f"coverage -> {cov_path}")


if __name__ == "__main__":
    main()
