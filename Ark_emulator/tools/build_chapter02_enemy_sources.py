"""Offline chapter02 exact variants; classify actual component fields, not prose."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import argparse
import hashlib
import json
import sys
import struct
import base64

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT/"packages/campaign/chapter02_sources"
LEVELS = ("level_main_02-09", "level_main_02-10")


def read(path): return json.loads(path.read_bytes())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
def identity(path): return {"path": path.relative_to(ROOT.parent).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size}


def geometry_source(assets, closure):
    objects, trees, _ = assets.load(ROOT.parent/closure["source"]["path"])
    rows = []
    for go in closure["hierarchy"]:
        raw_go = objects[go["path_id"]].read()
        for component in raw_go.m_Component:
            obj = objects[component.component.path_id]
            if obj.type.name == "Transform" or "Collider" in obj.type.name or obj.type.name.startswith("Rigidbody"):
                rows.append({"path_id": obj.path_id, "gameobject_path_id": go["path_id"], "gameobject_name": go["name"],
                    "unity_type": obj.type.name, "raw": trees[obj.path_id] if obj.path_id in trees else obj.read_typetree()})
    return rows


def exact_shared_skeleton(key, path, assets):
    """A variant may explicitly point at a base skeleton; never infer by name."""
    from tools.extract_campaign_animation_bindings import unity_payload, parse_spine
    art_paths = [p for p in (ROOT.parent/"data/refs/arts").glob("enm_art_*.ab_unpacked/CAB-*") if not p.name.endswith(".resS")]
    def pointer(ref, current):
        if not ref["m_PathID"]: raise ValueError("required animation pointer null")
        if ref["m_FileID"]:
            file = assets.load(current)[2]; name = file.externals[ref["m_FileID"]-1].path.rsplit("/", 1)[-1]
            matches = [p for p in art_paths if p.name == name]
            if len(matches) != 1: raise ValueError("exact external animation CAB unavailable")
            current = matches[0]
        objects, trees, _ = assets.load(current)
        obj = objects[ref["m_PathID"]]
        return current, obj, trees.get(ref["m_PathID"])
    p = assets.closure(path, key)
    root = next(c["raw"] for c in p["components"].values() if "_modes" in c["raw"])
    ap, ao, animator = pointer(root["_animator"], path)
    rp, ro, renderer = pointer(animator["_skeleton"], ap)
    dp, do, data = pointer(renderer["skeletonDataAsset"], rp)
    tp, to, _ = pointer(data["skeletonJSON"], dp)
    if to.type.name != "TextAsset": raise ValueError("native skeleton pointer is not TextAsset")
    wrapper = to.get_raw_data(); size = struct.unpack_from("<I", wrapper)[0]; name = wrapper[4:4+size].decode("utf8")
    payload = unity_payload(wrapper)
    return {"status": "exact_serialized_pointer_shared_skeleton", "prefab_key": key, "name": name,
        "name_alias_is_explicit_pointer_not_fallback": True, "source": identity(tp), "textasset_path_id": to.path_id,
        "payload_sha256": hashlib.sha256(payload).hexdigest(), "payload_base64": base64.b64encode(payload).decode(), "parsed": parse_spine(payload),
        "animator": {"source": identity(ap), "path_id": ao.path_id, "fields": animator},
        "renderer": {"source": identity(rp), "path_id": ro.path_id, "fields": renderer},
        "data_asset": {"source": identity(dp), "path_id": do.path_id, "fields": data}}


def build():
    import UnityPy
    from tools.build_chapter01_enemy_sources import NativeAssets, find_templates, bson_source, story_source
    from tools.build_mainline_dependencies import resolve_enemy, DEFAULT_DB, PIN
    from tools.fetch_campaign_reference import load_manifest, validate_lock, entry_for
    from tools.build_mainline_00_11_sources import animation_sources
    from tools.extract_campaign_animation_bindings import library_identity, resolve_animation
    db = read(DEFAULT_DB); lock_path = ROOT/"packages/campaign/enemy_sources.lock.json"; lock = read(lock_path)
    if lock["commit"] != PIN or lock["sha256"] != sha(DEFAULT_DB): raise ValueError("pinned enemy DB lock drift")
    manifest_path = ROOT/"packages/campaign/native_reference/reference.manifest.json"; manifest = load_manifest(manifest_path)
    stages = {}; variants = {}; all_prefabs = set()
    for level in LEVELS:
        path = ROOT/"packages/campaign/native_reference"/(level+".json"); raw = path.read_bytes()
        validate_lock(manifest["files"][level], level)
        if entry_for(raw, level) != manifest["files"][level]: raise ValueError("native stage cache drift")
        native = read(path); plan_path = ROOT/"packages/campaign/chapter02_plans"/(level+".json"); plan = read(plan_path)
        rows = []
        for reference in native["enemyDbRefs"]:
            row = resolve_enemy(db, reference)
            vid = row["native_id"]+"@"+str(row["native_level"])+"/"+digest({"reference": reference, "resolved": row["resolved"]})[:16]
            if vid not in variants: variants[vid] = {"variant_id": vid, "native_reference": reference, "native_enemy": row, "stages": []}
            variants[vid]["stages"].append(level); rows.append(vid); all_prefabs.add(row["resolved"]["prefabKey"])
        counts = Counter(); controls = []; spawn_sources = []
        for wi, w in enumerate(native["waves"]):
            for fi, f in enumerate(w["fragments"]):
                for ai, a in enumerate(f["actions"]):
                    record = {"wave": wi, "fragment": fi, "action": ai, "native": a}
                    if a["actionType"] == "SPAWN":
                        counts[a["key"]] += a["count"]
                        candidates = [vid for vid in rows if variants[vid]["native_enemy"]["native_id"] == a["key"]]
                        record.update(variant_candidates=candidates, resolution_status="unique" if len(candidates) == 1 else "ambiguous_preserved")
                        spawn_sources.append(record)
                    else: controls.append(record)
        if dict(counts) != plan["spawn_counts_by_key"] or sum(counts.values()) != plan["spawn_count"]: raise ValueError("root plan/native spawn mismatch")
        control_counts = Counter()
        for c in controls: control_counts[c["native"]["actionType"]] += c["native"]["count"]
        if dict(control_counts) != plan["control_counts"]: raise ValueError("root plan/native control mismatch")
        used = sorted({r["native"]["routeIndex"] for r in spawn_sources})
        cp_counts = Counter(cp["type"] for i in used for cp in native["routes"][i]["checkpoints"] or [])
        stages[level] = {"source": identity(path), "root_plan_source": identity(plan_path), "native_level_document": native,
            "resolved_variant_ids": rows, "spawn_sources": spawn_sources, "spawn_count": sum(counts.values()),
            "controls": controls, "control_counts": dict(control_counts),
            "stories": {c["native"]["key"]: story_source(c["native"]["key"]) for c in controls if c["native"]["actionType"] == "STORY"},
            "active_route_checkpoint_counts": dict(cp_counts), "used_route_indices": used,
            "active_runes": plan["applicable_runes"], "inactive_runes": plan["inactive_runes"],
            "runnable": False, "gaps": ["native_controls_and_route_specials_not_converted", "source_versions_alignment",
                "complex_enemy_drivers_and_passive_behaviors_require_models"]}
    assets = NativeAssets(); prefab_paths = {key: [] for key in all_prefabs}
    for path in sorted((ROOT.parent/"data/battle").glob("enm_pfb*.ab_unpacked/CAB-*")):
        if path.name.endswith(".resS"): continue
        for obj in UnityPy.load(str(path)).objects:
            if obj.type.name == "GameObject":
                name = obj.read().m_Name
                if name in prefab_paths: prefab_paths[name].append(path)
    if any(len(v) != 1 for v in prefab_paths.values()): raise ValueError("exact prefab source absent/ambiguous")
    before = library_identity(); prefabs = {}; animations = {}; keys = set(); projectile_keys = set()
    for key, paths in sorted(prefab_paths.items()):
        path = paths[0]; prefab = assets.closure(path, key); prefab["geometry_sources"] = geometry_source(assets, prefab); prefabs[key] = prefab
        try:
            animation = animation_sources({key: {"source": path.relative_to(ROOT.parent).as_posix()}})[key]
            animation["status"] = "exact_source_bound_spine"
        except (ValueError, KeyError) as exc:
            animation = {"status": "native_animation_gap", "error": type(exc).__name__+": "+str(exc)}
            if str(exc) == "Skeleton identity differs from selected exact prefab":
                animation = exact_shared_skeleton(key, path, assets)
                animation["preliminary_strict_name_rejection"] = str(exc)
        animations[key] = animation; keys |= find_templates(prefab)
        for component in prefab["components"].values():
            def collect(v):
                if isinstance(v, dict):
                    for k, child in v.items():
                        if "projectile" in k.lower() and isinstance(child, str) and child: projectile_keys.add(child)
                        collect(child)
                elif isinstance(v, list):
                    for child in v: collect(child)
            collect(component["raw"])
    if library_identity() != before: raise ValueError("shared Spine library mutated")
    projectile_paths = [p for p in (ROOT.parent/"data/battle/prefabs").glob("*projectiles.ab_unpacked/CAB-*") if not p.name.endswith(".resS")]
    projectiles = {}
    for key in sorted(projectile_keys):
        matches = [p for p in projectile_paths if any(o.type.name == "GameObject" and o.read().m_Name == key for o in assets.load(p)[0].values())]
        if len(matches) == 1:
            projectiles[key] = assets.closure(matches[0], key)
            projectiles[key]["geometry_sources"] = geometry_source(assets, projectiles[key]); keys |= find_templates(projectiles[key])
        else: projectiles[key] = {"status": "native_projectile_gap", "matching_paths": [str(p) for p in matches]}
    template_source = bson_source(keys)
    dump_path = ROOT.parent/"Ark_data/dump.cs"; dump = dump_path.read_text(encoding="utf8")
    declarations = {}
    for class_name in ("HpRatioToggleChecker", "AuraAbility", "PhysicsRange", "HitBehaviour", "RangedAttack", "ParacurveMovement", "AdvancedMovement"):
        match = "public class "+class_name+" :"
        if match not in dump:
            declarations[class_name] = {"status": "declaration_not_found", "method_body_recovered": False}; continue
        start = dump.index(match); end = dump.index("\n// Namespace:", start)
        declarations[class_name] = {"text": dump[start:end], "method_body_recovered": False}
    matrix = []; abilities = []; selectors = []
    for vid, record in variants.items():
        row = record["native_enemy"]; key = row["resolved"]["prefabKey"]; p = prefabs[key]; a = animations[key]
        roots = [c for c in p["components"].values() if "_modes" in c["raw"]]
        if len(roots) != 1: raise ValueError("exact native enemy root ambiguous")
        modes = []
        for index, pointer in enumerate(roots[0]["raw"]["_modes"]):
            if pointer["m_FileID"]: raise ValueError("external mode pointer unhandled")
            mode = p["components"][str(pointer["m_PathID"])]
            nodes = {}
            for role in ("_combat", "_attack", "_attackTrigger"):
                ref = mode["raw"][role]
                if ref["m_FileID"]: nodes[role] = {"status": "external_pointer_gap", "pointer": ref}; continue
                node = p["components"].get(str(ref["m_PathID"]))
                if not ref["m_PathID"]: nodes[role] = {"status": "native_null", "pointer": ref}; continue
                if node is None: raise ValueError("local mode node absent")
                binding = None
                if node["raw"].get("_animKey") and a["status"] in {"exact_source_bound_spine", "exact_serialized_pointer_shared_skeleton"}:
                    try: binding = resolve_animation(node["raw"]["_animKey"], a["animator"]["fields"]["_animations"], a["parsed"])
                    except (ValueError, KeyError) as exc: binding = {"status": "binding_gap", "reason": str(exc)}
                nodes[role] = {"path_id": ref["m_PathID"], "native_class": node["native_class"], "raw": node["raw"], "animation_binding": binding}
            modes.append({"index": index, "mode_path_id": pointer["m_PathID"], "raw_mode": mode["raw"], "nodes": nodes})
        hierarchy = {g["path_id"]: g for g in p["hierarchy"]}
        mode_go = {m["raw_mode"]["m_GameObject"]["m_PathID"]: m["index"] for m in modes}
        components = deepcopy(p["components"])
        for c in components.values():
            go = c["gameobject_path_id"]; branch = []
            while go in hierarchy:
                branch.append(hierarchy[go]["name"])
                if go in mode_go: c["mode_index"] = mode_go[go]; break
                go = hierarchy[go]["parent_path_id"]
            c["hierarchy_branch"] = branch
        passive = [c for c in components.values() if c["raw"].get("_buffs") or c["raw"].get("_additiveActiveBuffs") or
            c["native_class"] in ("HpRatioToggleChecker", "EnemySkill", "PassiveAttachmentAbility")]
        combat = modes[0]["nodes"]["_combat"]; fields = combat.get("raw", {}); binding = combat.get("animation_binding") or {}
        hits = [e for e in binding.get("events", []) if e["name"] == "OnAttack"]
        gaps = []
        if row["resolved"].get("applyWay") != "MELEE": gaps.append("non_melee_target_driver_requires_explicit_conversion")
        if len(modes) != 1: gaps.append("multi_mode_phase_and_attack_selection_body_pending")
        if combat.get("native_class") != "MeleeAttack": gaps.append("combat_class_requires_explicit_model")
        if fields.get("_damageType") != 1: gaps.append("non_physical_damage_must_use_actual_enum_not_plan_classification")
        if passive or row["resolved"].get("skills") or row["resolved"].get("talentBlackboard"): gaps.append("passive_skill_talent_driver_not_converted")
        if fields.get("_projectileKey") or fields.get("_activeBuffs"): gaps.append("projectile_onhit_dependencies_not_converted")
        if len(hits) != 1 or fields.get("_waitForAttackEvent") != 1: gaps.append("attack_signal_multi_or_missing_no_fallback")
        authored = not gaps; suffix = vid.replace("@", "/level_")
        if authored:
            sid = "selector/chapter02/"+suffix; aid = "ability/chapter02/"+suffix+"/normal"
            selectors.append({"id": sid, "kind": "selector", "region": {"type": "all", "blocked_only": True},
                "filters": [{"tag": "player"}, {"state": "alive"}], "limit": 1})
            abilities.append({"id": aid, "kind": "ability", "activation": {"mode": "automatic_attack"}, "selector": sid,
                "timeline": [{"at_seconds": hits[0]["seconds"], "effect": {"op": "damage", "damage_type": "physical", "scale": fields["_atkScale"]}}],
                "metadata": {"variant_id": vid, "combat_path_id": combat["path_id"], "binding": binding,
                    "timing_profile": "unscaled_source_event_model", "client_verified": False}})
        record.update(prefab_key=key, modes=modes, components=components, normal_model_authored=authored)
        checker_values = [{"path_id": pid, "native": c["raw"]} for pid, c in components.items() if c["native_class"] == "HpRatioToggleChecker"]
        bb = {r["key"]: r["value"] for r in row["resolved"].get("talentBlackboard", [])}
        disagreements = []
        for checker in checker_values:
            for bb_key, value in bb.items():
                if bb_key.endswith("hp_ratio") and value != checker["native"]["_maxHpRatio"]:
                    disagreements.append({"serialized_checker_path_id": checker["path_id"], "serialized_maxHpRatio": checker["native"]["_maxHpRatio"],
                        "DB_talent_key": bb_key, "DB_talent_value": value, "loadMinHpRatioFromBlackboard": checker["native"]["_loadMinHpRatioFromBlackboard"],
                        "resolution": "preserve_both_native_LoadData_and_source_version_alignment_unverified"})
        record["source_disagreements"] = disagreements
        matrix.append({"variant_id": vid, "native_id": row["native_id"], "native_level": row["native_level"], "override": row["stage_override"],
            "stages": record["stages"], "motion": row["resolved"]["motion"], "apply_way": row["resolved"]["applyWay"],
            "mode_count": len(modes), "actual_combat_classes": [m["nodes"]["_combat"].get("native_class") for m in modes],
            "actual_damage_types": [m["nodes"]["_combat"].get("raw", {}).get("_damageType") for m in modes],
            "separate_attack_nodes": [m["nodes"]["_attack"].get("path_id") != m["nodes"]["_combat"].get("path_id") for m in modes],
            "actual_attack_classes": [m["nodes"]["_attack"].get("native_class") for m in modes],
            "passive_or_skill_components": [{"native_class": c["native_class"], "branch": c["hierarchy_branch"], "raw": c["raw"]} for c in passive],
            "source_disagreements": disagreements,
            "attack_frames": [e["frame"] for e in hits], "normal_model_authored": authored, "model_gaps": gaps,
            "client_pending": ["native_animation_scaling_and_fsm", "source_versions_alignment"]})
    audit = {"schema": "ark-sim/chapter02-native-source-audit/v1", "status": "native_sources_preserved_models_partial",
        "stages": stages, "variants": variants, "prefabs": prefabs, "animations": animations, "projectiles": projectiles,
        "bson": template_source, "native_monoscripts": assets.scripts, "spine_reader_identity": before, "shared_reader_unchanged": True,
        "native_class_declarations": declarations,
        "builder_sha256": sha(Path(__file__)), "source_identities": {"enemy_DB": identity(DEFAULT_DB), "enemy_lock": identity(lock_path),
            "native_manifest": identity(manifest_path), "dump": identity(dump_path)}, "helper_sha256": {name: sha(ROOT/"tools"/name) for name in (
                "build_chapter01_enemy_sources.py", "build_mainline_00_11_sources.py", "build_mainline_dependencies.py",
                "extract_campaign_animation_bindings.py", "build_kalts_skill_recipe.py", "fetch_campaign_reference.py")},
        "formal_approved": False, "client_verified": False}
    package = {"schemaVersion": 2, "manifest": {"id": "package/campaign/chapter02/simple_attacks", "version": "0.1.0",
        "requires": ["preset/ark_standard"], "metadata": {"source": "packages/campaign/chapter02_sources/native.reference.json",
            "scope": "only_verified_single_mode_uncomplicated_melee", "formal_approved": False, "client_verified": False}},
        "abilities": abilities, "selectors": selectors}
    return {"native.reference.json": audit, "dependency.matrix.json": {"schema": "ark-sim/chapter02-dependencies/v1", "enemies": matrix,
        "stage_summary": {l: {k: s[k] for k in ("spawn_count", "control_counts", "active_route_checkpoint_counts", "active_runes", "inactive_runes", "gaps", "runnable")} for l, s in stages.items()}, "formal_approved": False}, "attacks.model.json": package}


def assertions(values):
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    audit = values["native.reference.json"]; model = values["attacks.model.json"]; probes = {}
    for ability in model["abilities"]:
        vid = ability["metadata"]["variant_id"]; row = audit["variants"][vid]["native_enemy"]["resolved"]; a = row["attributes"]
        frame = ability["metadata"]["binding"]["events"]; frame = next(e["frame"] for e in frame if e["name"] == "OnAttack")
        scale = ability["timeline"][0]["effect"]["scale"]; expected = 2000000-max(a["atk"]*scale-30, a["atk"]*scale*.05)
        data = deepcopy(model); data["entities"] = [{"id": "unit/probe_enemy", "kind": "entity", "tags": ["enemy"], "components": {
            "attributes": {"base": {"max_hp": a["maxHp"], "atk": a["atk"], "def": a["def"], "mres": a["magicResistance"],
                "attack_interval": a["baseAttackTime"], "attack_speed_ratio": a["attackSpeed"]/100}},
            "resources": {"hp": {"initial": a["maxHp"], "capacity": a["maxHp"], "role": "health"}}, "spatial": {}, "abilities": [ability["id"]]}},
            {"id": "unit/probe_player", "kind": "entity", "tags": ["player"], "components": {"attributes": {"base": {"max_hp": 2000000, "def": 30, "mres": 0}},
                "resources": {"hp": {"initial": 2000000, "capacity": 2000000, "role": "health"}}, "spatial": {}}}]
        data["scenarioDraft"] = {"id": "scenario/chapter02_attack_probe", "ruleset": "ruleset/ark_standard", "map": {"rows": 1, "cols": 1},
            "initialEntities": [{"definition": "unit/probe_enemy", "instanceAlias": "enemy"}, {"definition": "unit/probe_player", "instanceAlias": "blocker"},
                {"definition": "unit/probe_player", "instanceAlias": "other"}]}
        s = Engine.create(Compiler().compile(data)); s.ctx.set("enemy", ("runtime", "blocked_by"), s.session.world.resolve("blocker"))
        s.advance(frame); assert s.ctx.resources.current("blocker", "hp") == 2000000
        s.advance(1); assert s.ctx.resources.current("blocker", "hp") == expected and s.ctx.resources.current("other", "hp") == 2000000
        probes[vid] = {"frame": frame, "native_atk": a["atk"], "native_scale": scale, "synthetic_defender_def": 30,
            "expected_hp": expected, "actual_hp": s.ctx.resources.current("blocker", "hp"), "nonblocked_hp": 2000000,
            "program_fingerprint": s.program.fingerprint, "runtime_fingerprint": s.runtime_fingerprint, "passed": True}
    assert audit["stages"][LEVELS[0]]["spawn_count"] == 52 and audit["stages"][LEVELS[1]]["spawn_count"] == 36
    return {"schema": "ark-sim/chapter02-source-assertions/v1", "passed": True, "variant_count": len(audit["variants"]),
        "simple_attack_count": len(model["abilities"]), "actual_probes": probes, "implementation_digest": implementation_digest(),
        "full_stage_executed": False, "formal_approved": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    values = build(); report = assertions(values)
    report["source_artifact_sha256"] = {name: hashlib.sha256((json.dumps(data, ensure_ascii=False, indent=2)+"\n").encode()).hexdigest() for name, data in values.items()}
    values["assertions.json"] = report; OUT.mkdir(parents=True, exist_ok=True)
    for name, data in values.items():
        path = OUT/name
        if args.check:
            if not path.exists() or read(path) != data: raise SystemExit("chapter02 drift: "+name)
        else: path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf8", newline="\n")
    print("chapter02 source assertions/probes passed; variants", report["variant_count"], "simple attacks", report["simple_attack_count"], "no full-stage claim")
