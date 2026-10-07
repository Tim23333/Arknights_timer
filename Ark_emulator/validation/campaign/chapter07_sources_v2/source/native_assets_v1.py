"""Offline native dependency audit for the fixed chapter-1 final two stages.

Only exact source-bound uncomplicated melee attacks are authored. Boss modes,
skills, projectiles and tutorial actors are preserved as source dependencies.
"""
from __future__ import annotations
import argparse
import base64
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
LEVELS = ("level_main_01-11", "level_main_01-12")
OUT = ROOT/"packages/campaign/chapter01_sources"


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding="utf-8-sig"))
def identity(path): return {"path": path.relative_to(ROOT.parent).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size}


class NativeAssets:
    def __init__(self):
        self.cache = {}; self.scripts = {}
        self.script_paths = {p.name: p for p in (ROOT.parent/"data/anon").glob("*/CAB-*") if not p.name.endswith(".resS")}

    def script(self, pointer, path):
        objects, _, file = self.load(path)
        if pointer["m_FileID"]:
            external = file.externals[pointer["m_FileID"]-1].path.rsplit("/", 1)[-1]
            if external not in self.script_paths: raise ValueError("exact native MonoScript CAB unavailable")
            path = self.script_paths[external]; objects = self.load(path)[0]
        pid = pointer["m_PathID"]; key = path.name+":"+str(pid)
        if key not in self.scripts:
            if pid not in objects or objects[pid].type.name != "MonoScript": raise ValueError("native script pointer not MonoScript")
            self.scripts[key] = {"source": identity(path), "path_id": pid, "raw": objects[pid].read_typetree()}
        return key, self.scripts[key]["raw"]["m_ClassName"]

    def load(self, path):
        import UnityPy
        if path not in self.cache:
            env = UnityPy.load(str(path))
            objects = {o.path_id: o for o in env.objects}
            trees = {o.path_id: o.read_typetree() for o in env.objects if o.type.name in ("MonoBehaviour", "Transform")}
            self.cache[path] = (objects, trees, next(iter(objects.values())).assets_file)
        return self.cache[path]

    def closure(self, path, key):
        objects, trees, file = self.load(path)
        matches = [o for o in objects.values() if o.type.name == "GameObject" and o.read().m_Name == key]
        if len(matches) != 1: raise ValueError(f"exact prefab GameObject missing/ambiguous: {key}")
        root = matches[0]
        gos = {}
        def hierarchy(go):
            if go.path_id in gos: return
            gos[go.path_id] = go.read()
            transforms = [objects[c.component.path_id] for c in gos[go.path_id].m_Component if objects[c.component.path_id].type.name == "Transform"]
            if len(transforms) != 1: raise ValueError("prefab Transform missing/ambiguous")
            for pointer in trees[transforms[0].path_id]["m_Children"]:
                if pointer["m_FileID"]: raise ValueError("external Transform child not supported")
                child = trees[pointer["m_PathID"]]["m_GameObject"]
                hierarchy(objects[child["m_PathID"]])
        hierarchy(root)
        selected = {c.component.path_id for go in gos.values() for c in go.m_Component
                    if objects[c.component.path_id].type.name == "MonoBehaviour"}
        external = []
        def pointers(value, location):
            if isinstance(value, dict):
                if set(value) == {"m_FileID", "m_PathID"}:
                    if value["m_PathID"]:
                        if value["m_FileID"]:
                            index = value["m_FileID"]-1
                            external.append({"field": location, "pointer": value,
                                "external": file.externals[index].path if 0 <= index < len(file.externals) else None})
                        elif value["m_PathID"] in objects and objects[value["m_PathID"]].type.name == "MonoBehaviour":
                            if value["m_PathID"] not in selected:
                                selected.add(value["m_PathID"]); scan(value["m_PathID"])
                    return
                for name, child in value.items():
                    if name not in ("m_Script", "m_GameObject"): pointers(child, location+"."+name)
            elif isinstance(value, list):
                for i, child in enumerate(value): pointers(child, location+f"[{i}]")
        scanned = set()
        def scan(pid):
            if pid not in scanned:
                scanned.add(pid); pointers(trees[pid], str(pid))
        for pid in sorted(selected): scan(pid)
        records = {str(pid): {"script_path_id": trees[pid]["m_Script"]["m_PathID"],
            "gameobject_path_id": trees[pid]["m_GameObject"]["m_PathID"],
            "gameobject_name": objects[trees[pid]["m_GameObject"]["m_PathID"]].read().m_Name if trees[pid]["m_GameObject"]["m_PathID"] else None, "native_null_gameobject_preserved": not bool(trees[pid]["m_GameObject"]["m_PathID"]),
            "raw": trees[pid]} for pid in sorted(selected)}
        for pid, record in records.items():
            script_key, native_class = self.script(trees[int(pid)]["m_Script"], path)
            record.update(script_key=script_key, native_class=native_class)
        hierarchy_rows = []
        for pid, go in sorted(gos.items()):
            transform = next(trees[c.component.path_id] for c in go.m_Component if objects[c.component.path_id].type.name == "Transform")
            father = transform["m_Father"]["m_PathID"]
            parent_go = trees[father]["m_GameObject"]["m_PathID"] if father else None
            hierarchy_rows.append({"path_id": pid, "name": go.m_Name, "parent_path_id": parent_go})
        return {"source": identity(path), "root_gameobject_path_id": root.path_id,
            "hierarchy": hierarchy_rows,
            "components": records, "external_references": external}


def find_templates(value):
    found = set()
    def walk(item):
        if isinstance(item, dict):
            if item.get("templateKey"): found.add(item["templateKey"])
            for child in item.values(): walk(child)
        elif isinstance(item, list):
            for child in item: walk(child)
    walk(value)
    return found


def bson_source(keys):
    from tools.build_kalts_skill_recipe import decode_bson_document
    from tools.extract_campaign_animation_bindings import unity_payload
    path = ROOT.parent/"data/anon_textassets/buff_template_data.dat"
    payload = unity_payload(path.read_bytes()); values, spans = decode_bson_document(payload)
    selected = {}; missing = []
    for key in sorted(keys):
        if key not in values: missing.append(key); continue
        lo, hi = spans[(key,)]; raw = payload[lo:hi]
        selected[key] = {"parsed": values[key], "payload_offset": lo,
            "document_base64": base64.b64encode(raw).decode(), "document_sha256": hashlib.sha256(raw).hexdigest()}
    return {"source": identity(path), "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "templates": selected, "missing_templates": missing, "native_method_bodies_recovered": False}


def story_source(key):
    name = key.rsplit("/", 1)[-1]
    path = ROOT.parent/"unpack_work/release_20260831/hot_raw"/(name+".dat")
    if not path.exists(): return {"key": key, "status": "missing_native_story_textasset", "expected_path": str(path)}
    raw = path.read_bytes(); length = struct.unpack_from("<I", raw)[0]
    if raw[4:4+length].decode("utf8") != name: raise ValueError("story TextAsset name mismatch")
    offset = (4+length+3)//4*4; size = struct.unpack_from("<I", raw, offset)[0]
    if offset+4+size > len(raw) or any(raw[offset+4+size:]): raise ValueError("story size/padding invalid")
    payload = raw[offset+4:offset+4+size]; text = payload.decode("utf8")
    rows = []
    for line, raw_line in enumerate(text.splitlines(), 1):
        m = re.fullmatch(r"\[([A-Za-z_][A-Za-z_0-9]*)(?:\((.*)\)|=(.*))?\]\s*(.*)", raw_line)
        rows.append({"line": line, "raw_line": raw_line, "command": m[1] if m else None,
            "parameters": (m[2] if m[2] is not None else m[3]) if m else None,
            "syntax": "assignment" if m and m[3] is not None else "command" if m else "blank" if not raw_line else "unparsed",
            "text": m[4] if m else raw_line})
    return {"key": key, "status": "native_source_preserved_controls_not_converted", "source": identity(path),
        "payload_offset": offset+4, "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "payload_base64": base64.b64encode(payload).decode(), "script": text, "commands": rows,
        "command_counts": dict(Counter(r["command"] or r["syntax"] for r in rows)), "runnable": False}


def build():
    from tools.build_mainline_dependencies import build as plan_for, DEFAULT_DB
    from tools.fetch_campaign_reference import load_manifest, validate_lock, entry_for
    from tools.build_campaign_enemy_attacks import recover
    from tools.build_mainline_00_11_sources import animation_sources
    from tools.extract_campaign_animation_bindings import library_identity, resolve_animation
    manifest_path = ROOT/"packages/campaign/native_reference/reference.manifest.json"
    manifest = load_manifest(manifest_path)
    for level in LEVELS:
        entry = manifest["files"][level]; validate_lock(entry, level)
        raw = (ROOT/"packages/campaign/native_reference"/(level+".json")).read_bytes()
        if entry_for(raw, level) != entry: raise ValueError("locked native reference content drift: "+level)
    plans = {level: plan_for(level) for level in LEVELS}
    enemies = {}
    for plan in plans.values():
        for row in plan["resolved_enemies"]:
            key = row["native_id"]
            if key in enemies and enemies[key] != row:
                raise ValueError("stage-specific enemy DB variant requires separate source/model identity: "+key)
            enemies[key] = row
    before = library_identity(); normal = recover(set(enemies)); animations = animation_sources(normal)
    if library_identity() != before: raise ValueError("shared animation reader mutated")
    assets = NativeAssets(); records = {}; template_keys = set(); projectile_keys = set()
    for key, row in sorted(enemies.items()):
        prefab = assets.closure(ROOT.parent/normal[key]["source"], row["resolved"]["prefabKey"])
        roots = [r["raw"] for r in prefab["components"].values() if "_modes" in r["raw"]]
        if len(roots) != 1: raise ValueError("exact root mode list ambiguous")
        modes = []
        for i, pointer in enumerate(roots[0]["_modes"]):
            if pointer["m_FileID"]: raise ValueError("external mode cannot be inferred")
            mode = prefab["components"][str(pointer["m_PathID"])]["raw"]
            combat_pointer = mode["_combat"]
            if combat_pointer["m_FileID"]: raise ValueError("external combat cannot be inferred")
            combat = prefab["components"].get(str(combat_pointer["m_PathID"]), {}).get("raw")
            bound = None
            if combat and combat.get("_animKey"):
                bound = resolve_animation(combat["_animKey"], animations[key]["animator"]["fields"]["_animations"], animations[key]["parsed"])
            modes.append({"index": i, "path_id": pointer["m_PathID"], "raw_mode": mode,
                "combat_path_id": combat_pointer["m_PathID"], "combat": combat, "attack_animation": bound})
        hierarchy = {r["path_id"]: r for r in prefab["hierarchy"]}
        mode_gos = {m["raw_mode"]["m_GameObject"]["m_PathID"]: m["index"] for m in modes}
        for component in prefab["components"].values():
            go = component["gameobject_path_id"]; branch = []
            while go in hierarchy:
                branch.append(hierarchy[go]["name"])
                if go in mode_gos:
                    component["mode_index"] = mode_gos[go]; break
                go = hierarchy[go]["parent_path_id"]
            component["hierarchy_branch"] = branch
        for component in prefab["components"].values():
            raw = component["raw"]
            projectile_keys.update(v for k, v in raw.items() if k == "_projectileKey" and isinstance(v, str) and v)
            projectile_keys.update(raw.get("_extraProjectileKeys", []))
        template_keys |= find_templates(prefab)
        records[key] = {"native_enemy": row, "prefab": prefab, "animation": animations[key], "modes": modes,
            "boss_or_multimode": row["resolved"].get("levelType") == "BOSS" or len(modes) > 1}
    projectile_paths = [p for p in (ROOT.parent/"data/battle/prefabs").glob("*projectiles.ab_unpacked/CAB-*") if not p.name.endswith(".resS")]
    projectiles = {}
    for key in sorted(projectile_keys):
        matches = []
        for path in projectile_paths:
            objects = assets.load(path)[0]
            if any(o.type.name == "GameObject" and o.read().m_Name == key for o in objects.values()): matches.append(path)
        if len(matches) == 1:
            projectiles[key] = assets.closure(matches[0], key); template_keys |= find_templates(projectiles[key])
        else: projectiles[key] = {"status": "missing_or_ambiguous_native_projectile", "candidate_paths": [str(p) for p in matches]}
    abilities = []; selectors = []; matrix = []
    for key, record in records.items():
        row = record["native_enemy"]; fields = record["modes"][0]["combat"] or {}; gaps = []
        combat_class = record["prefab"]["components"].get(str(record["modes"][0]["combat_path_id"]), {}).get("native_class")
        if combat_class != "MeleeAttack": gaps += ["native_attack_class_driver_requires_conversion"]
        if fields.get("_splitDamage"): gaps += ["native_multi_melee_split_damage_formula_unverified"]
        if record["boss_or_multimode"]: gaps += ["native_boss_mode_hp_trigger_and_skill_driver_not_converted"]
        if row["resolved"].get("skills"): gaps += ["native_db_skills_require_exact_runtime_driver"]
        if row["resolved"]["applyWay"] != "MELEE": gaps += ["native_ranged_target_selector_and_projectile_impact_not_converted"]
        if fields.get("_projectileKey"): gaps += ["native_projectile_timing_and_payload_not_converted"]
        if fields.get("_activeBuffs"): gaps += ["native_on_hit_buffs_not_converted"]
        passive = [c for c in record["prefab"]["components"].values() if c["raw"].get("_buffs")]
        if passive: gaps += ["native_passive_buff_driver_not_converted"]
        hits = [e for e in (record["modes"][0]["attack_animation"] or {}).get("events", []) if e["name"] == "OnAttack"]
        if not hits or fields.get("_waitForAttackEvent") != 1: gaps += ["native_attack_signal_missing_no_fallback"]
        if fields.get("_damageType") not in (1, 2, 3): gaps += ["native_damage_enum_unconverted"]
        authored = not gaps
        if authored:
            sid = f"selector/{key}/blocked_target"
            selectors.append({"id": sid, "kind": "selector", "region": {"type": "all", "blocked_only": True},
                "filters": [{"tag": "player"}, {"state": "alive"}], "limit": 1})
            abilities.append({"id": f"ability/{key}/normal_attack", "kind": "ability", "activation": {"mode": "automatic_attack"},
                "selector": sid, "timeline": [{"at_seconds": e["seconds"], "effect": {"op": "damage",
                    "scale": fields["_atkScale"], "damage_type": {1: "physical", 2: "arts", 3: "true"}[fields["_damageType"]]}} for e in hits],
                "metadata": {"native_id": key, "combat_path_id": record["modes"][0]["combat_path_id"],
                    "source_animation_binding": record["modes"][0]["attack_animation"],
                    "timing_profile": "unscaled_source_event_model", "client_verified": False}})
        matrix.append({"native_id": key, "levels": [l for l, p in plans.items() if key in p["spawn_counts_by_key"]],
            "spawn_counts": {l: p["spawn_counts_by_key"].get(key, 0) for l, p in plans.items()},
            "apply_way": row["resolved"]["applyWay"], "mode_count": len(record["modes"]),
            "combat_class": combat_class,
            "db_skills": deepcopy(row["resolved"].get("skills", [])), "passive_component_count": len(passive),
            "attack_frames": [e["frame"] for e in hits], "normal_attack_authored": authored,
            "status": "source_backed_normal_attack_model_partial" if authored else "source_frozen_mechanics_pending", "gaps": gaps})
    stages = {}
    from tools.normalize_campaign_operators import load_sources
    characters, skills, _ = load_sources()
    for level, plan in plans.items():
        native_path = ROOT/"packages/campaign/native_reference"/(level+".json"); native = read(native_path)
        controls = [{"wave": wi, "fragment": fi, "action_index": ai, "native_action": a,
            "status": "native_control_source_not_converted"} for wi, w in enumerate(native["waves"])
            for fi, f in enumerate(w["fragments"]) for ai, a in enumerate(f["actions"]) if a["actionType"] != "SPAWN"]
        stories = {r["native_action"]["key"]: story_source(r["native_action"]["key"]) for r in controls if r["native_action"]["actionType"] == "STORY"}
        route_indices = sorted({a["routeIndex"] for w in native["waves"] for f in w["fragments"] for a in f["actions"] if a["actionType"] == "SPAWN"})
        checkpoint_counts = Counter(c["type"] for i in route_indices for c in native["routes"][i]["checkpoints"] or [])
        special_checkpoints = [{"route_index": i, "checkpoint_index": j, "native": c} for i in route_indices
            for j, c in enumerate(native["routes"][i]["checkpoints"] or []) if c["type"] not in ("MOVE", "WAIT_FOR_SECONDS", "WAIT_CURRENT_FRAGMENT_TIME")]
        offsets = [{"route_index": i, "checkpoint_index": j, "native": c} for i in route_indices
            for j, c in enumerate(native["routes"][i]["checkpoints"] or []) if any(c["reachOffset"].values())]
        predefines = native["predefines"] or {}; predefined_keys = set()
        for entries in predefines.values():
            rows = list(entries.values()) if isinstance(entries, dict) else entries or []
            for item in rows:
                if item.get("inst"): predefined_keys.add(item["inst"]["characterKey"])
        chars = {key: characters[key] for key in sorted(predefined_keys) if key in characters}
        missing = sorted(predefined_keys-set(chars)); skill_keys = {s["skillId"] for c in chars.values() for s in c.get("skills", [])}
        prefab_sources = {}
        for key in sorted(predefined_keys):
            paths = [p for p in (ROOT.parent/"data/charpack"/(key+".ab_unpacked")).glob("CAB-*") if not p.name.endswith(".resS")]
            external_version = None
            if not paths and key == "trap_002_emp":
                paths = [ROOT.parent/"unpack_work/campaign_external/battle_prefabs_tokens.20250327.ab"]
                external_version = "official_20250327_tokens_source_not_aligned_to_20260929_table"
                token_source = read(ROOT/"packages/campaign/support_tokens.reference.json")["source"]
                if paths[0].exists():
                    raw = paths[0].read_bytes()
                    if sha(paths[0]) != token_source["sha256"] or len(raw) != token_source["bytes"] or hashlib.md5(raw).hexdigest() != token_source["md5"]:
                        raise ValueError("official token source no longer matches frozen download proof")
            if len(paths) == 1 and paths[0].exists():
                closure = assets.closure(paths[0], key)
                if external_version:
                    closure["source_version_gap"] = external_version
                    closure["frozen_official_download_proof"] = token_source
                prefab_sources[key] = closure; template_keys |= find_templates(closure)
            else: prefab_sources[key] = {"status": "native_predefined_prefab_missing_or_ambiguous", "candidate_paths": [str(p) for p in paths]}
        predefined_skills = {}
        for skill_key in sorted(skill_keys):
            if skill_key != "sktok_emp": continue
            paths = [p for p in (ROOT.parent/"data/battle/prefabs").glob("*skills.ab_unpacked/CAB-*") if not p.name.endswith(".resS")]
            matches = [p for p in paths if any(o.type.name == "GameObject" and o.read().m_Name == skill_key for o in assets.load(p)[0].values())]
            if len(matches) == 1:
                predefined_skills[skill_key] = assets.closure(matches[0], skill_key); template_keys |= find_templates(predefined_skills[skill_key])
            else: predefined_skills[skill_key] = {"status": "native_predefined_skill_prefab_missing_or_ambiguous"}
        stages[level] = {"native_level": identity(native_path), "native_level_document": native, "dependency_plan": plan,
            "spawn_count": plan["spawn_count"], "control_counts": plan["control_counts"], "controls": controls, "stories": stories,
            "predefined_character_sources": chars, "predefined_skill_sources": {k: skills[k] for k in sorted(skill_keys) if k in skills},
            "predefined_prefab_sources": prefab_sources, "predefined_skill_prefabs": predefined_skills,
            "missing_predefined_character_sources": missing, "active_runes": plan["applicable_runes"], "inactive_runes": plan["inactive_runes"],
            "route_audit": {"spawn_referenced_route_indices": route_indices, "active_checkpoint_counts": dict(checkpoint_counts),
                "special_checkpoints": special_checkpoints, "nonzero_reach_offsets": offsets,
                "special_checkpoint_semantics_converted": False, "native_offset_steering_body_verified": False},
            "runnable": False, "gaps": ["native_tutorial_gameplay_controls_not_converted", "native_predefined_units_not_converted",
                "native_boss_and_ranged_mechanics_not_converted", "source_version_alignment", "native_scheduler_body_unverified",
                "native_nonzero_checkpoint_reach_offsets_not_converted"] + (["native_disappear_appear_checkpoint_not_converted"] if special_checkpoints else [])}
    dump = ROOT.parent/"Ark_data/dump.cs"; text = dump.read_text(encoding="utf8")
    start = text.index("public class HpRatioToggleChecker :")
    end = text.index("\n// Namespace:", start)
    declarations = {}
    for class_name in ("HpRatioToggleChecker", "EnemySkill", "RangedAttack", "MultiMeleeAttack", "SimpleProjectile", "ParacurveMovement", "AttachToTarget"):
        begin = text.index("public class "+class_name+" :")
        finish = text.index("\n// Namespace:", begin)
        declarations[class_name] = {"text": text[begin:finish], "method_bodies_recovered": False}
    for declaration in ("public enum AbstractAnimatedAbility.TimeMode", "public abstract class AbstractAnimatedAbility :"):
        begin = text.index(declaration); finish = text.index("\n// Namespace:", begin)
        declarations[declaration] = {"text": text[begin:finish], "method_bodies_recovered": False}
    bson = bson_source(template_keys)
    audit = {"schema": "ark-sim/chapter01-native-source-audit/v1", "status": "native_sources_preserved_mechanics_partial",
        "stages": stages, "enemies": records, "projectiles": projectiles, "bson": bson, "dependency_matrix": matrix,
        "native_monoscripts": assets.scripts,
        "spine_library_identity": before, "shared_reader_unchanged": True,
        "sources": {"enemy_database": identity(DEFAULT_DB), "enemy_lock": identity(ROOT/"packages/campaign/enemy_sources.lock.json"),
            "native_reference_manifest": identity(manifest_path),
            "characters": identity(ROOT.parent/"unpack_work/campaign_tables/character_table.json"),
            "skills": identity(ROOT.parent/"unpack_work/campaign_tables/skill_table.json"),
            "operator_table_lock": identity(ROOT/"packages/campaign/operator_sources.lock.json"), "dump": identity(dump)},
        "native_hp_checker_declaration": {"text": text[start:end], "method_bodies_recovered": False},
        "native_class_declarations": declarations,
        "builder_sha256": sha(Path(__file__)), "helper_sha256": {name: sha(ROOT/"tools"/name) for name in (
            "build_mainline_dependencies.py", "build_campaign_enemy_attacks.py", "build_mainline_00_11_sources.py",
            "extract_campaign_animation_bindings.py", "build_kalts_skill_recipe.py",
            "normalize_campaign_operators.py", "fetch_campaign_reference.py")},
        "client_validated": False, "formal_stage_approved": False}
    attack = {"schemaVersion": 2, "manifest": {"id": "package/campaign/enemy_attacks/chapter01", "version": "0.1.0",
        "requires": ["preset/ark_standard"], "metadata": {"source": "packages/campaign/chapter01_sources/native.reference.json",
            "status": "only_source_bound_uncomplicated_melee_attacks", "client_validated": False, "formal_stage_approved": False,
            "pending": ["native_attack_callback_scaling", "boss_and_ranged_skills_and_projectiles", "tutorial_predefines_and_controls"]}},
        "abilities": abilities, "selectors": selectors}
    assert len(matrix) == len(enemies)
    assert sum(plans[LEVELS[0]]["spawn_counts_by_key"].values()) == 45
    assert sum(plans[LEVELS[1]]["spawn_counts_by_key"].values()) == 30
    assert plans[LEVELS[0]]["control_counts"] == {"STORY": 2, "PREVIEW_CURSOR": 1, "ACTIVATE_PREDEFINED": 1, "DISPLAY_ENEMY_INFO": 3}
    assert plans[LEVELS[1]]["control_counts"] == {"STORY": 1, "DISPLAY_ENEMY_INFO": 2}
    assert all(r["native_id"] != "enemy_1504_cqbw" or not r["normal_attack_authored"] for r in matrix)
    return {"native.reference.json": audit, "attacks.model.json": attack,
            "dependency.matrix.json": {"schema": "ark-sim/chapter01-dependencies/v1", "enemies": matrix,
                "stages": {k: {name: v[name] for name in ("spawn_count", "control_counts", "active_runes", "inactive_runes", "route_audit", "gaps", "runnable")} for k, v in stages.items()},
                "formal_stage_approved": False}}


def compile_models(values):
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    package = deepcopy(values["attacks.model.json"])
    package["entities"] = [{"id": "unit/source_probe_"+str(i), "kind": "entity", "tags": ["enemy"],
        "components": {"attributes": {"base": {"max_hp": 100, "atk": 100, "def": 0, "mres": 0,
            "attack_interval": 2, "attack_speed_ratio": 1}}, "resources": {"hp": {"initial": 100, "capacity": 100}},
            "spatial": {}, "abilities": [a["id"]]}} for i, a in enumerate(package["abilities"])]
    package["scenarioDraft"] = {"id": "scenario/chapter01_source_probe", "ruleset": "ruleset/ark_standard",
        "map": {"rows": 1, "cols": 1}, "roster": [e["id"] for e in package["entities"]]}
    program = Compiler().compile(package)
    # Independent source-backed endpoint probes, explicitly synthetic blockers.
    expected = {"enemy_1000_gopro": (18, 1840), "enemy_1000_gopro_2": (18, 1770),
        "enemy_1002_nsabr": (12, 1830), "enemy_1027_mob": (12, 1780),
        "enemy_1029_shdsbr": (12, 1790), "enemy_1030_wteeth": (19, 1530)}
    audit = values["native.reference.json"]; probes = {}
    assert {a["metadata"]["native_id"] for a in package["abilities"]} == set(expected)
    for ability in package["abilities"]:
        key = ability["metadata"]["native_id"]; frame, hp = expected[key]
        attrs = audit["enemies"][key]["native_enemy"]["resolved"]["attributes"]
        d = deepcopy(values["attacks.model.json"])
        d["entities"] = [{"id": "unit/probe_enemy", "kind": "entity", "tags": ["enemy", "ground"],
            "components": {"attributes": {"base": {"max_hp": attrs["maxHp"], "atk": attrs["atk"],
                "def": attrs["def"], "mres": attrs["magicResistance"], "attack_interval": attrs["baseAttackTime"],
                "attack_speed_ratio": attrs["attackSpeed"]/100}}, "resources": {"hp": {"initial": attrs["maxHp"], "capacity": attrs["maxHp"]}},
                "spatial": {}, "abilities": [ability["id"]]}},
            {"id": "unit/probe_player", "kind": "entity", "tags": ["player", "ground"], "components": {
                "attributes": {"base": {"max_hp": 2000, "def": 30, "mres": 0}}, "spatial": {},
                "resources": {"hp": {"initial": 2000, "capacity": 2000, "role": "health"}}}}]
        d["scenarioDraft"] = {"id": "scenario/chapter01_attack_probe", "ruleset": "ruleset/ark_standard", "map": {"rows": 3, "cols": 3},
            "initialEntities": [{"definition": "unit/probe_enemy", "instanceAlias": "enemy", "position": {"row": 1, "col": 1}},
                {"definition": "unit/probe_player", "instanceAlias": "blocker", "position": {"row": 1, "col": 1}},
                {"definition": "unit/probe_player", "instanceAlias": "other", "position": {"row": 1, "col": 1}}]}
        runtime = Engine.create(Compiler().compile(d))
        runtime.ctx.set("enemy", ("runtime", "blocked_by"), runtime.session.world.resolve("blocker"))
        runtime.advance(frame)
        assert runtime.ctx.resources.current("blocker", "hp") == 2000
        runtime.advance(1)
        assert runtime.ctx.resources.current("blocker", "hp") == hp
        assert runtime.ctx.resources.current("other", "hp") == 2000
        probes[key] = {"impact_tick": frame, "native_atk": attrs["atk"], "synthetic_defender_def": 30,
            "expected_hp": hp, "actual_hp": runtime.ctx.resources.current("blocker", "hp"), "nonblocked_hp": 2000,
            "scope": "unscaled_source_frame_model_not_client_timing", "passed": True,
            "runtime_fingerprint": runtime.runtime_fingerprint, "program_fingerprint": runtime.program.fingerprint}
    return {"source_assertions_passed": True, "normal_attack_count": len(package["abilities"]),
            "compiler_definitions": len(program.definitions), "rules": len(program.rules),
            "actual_attack_endpoint_probes": probes,
            "implementation_digest": implementation_digest(),
            "full_stage_executed": False, "formal_stage_approved": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    values = build(); evidence = compile_models(values)
    evidence["source_artifact_sha256"] = {name: hashlib.sha256((json.dumps(value, ensure_ascii=False, indent=2)+"\n").encode("utf8")).hexdigest()
        for name, value in values.items()}
    values["assertions.json"] = evidence
    OUT.mkdir(parents=True, exist_ok=True)
    for name, value in values.items():
        path = OUT/name
        if args.check:
            if not path.exists() or read(path) != value: raise SystemExit("chapter01 source drift: "+name)
        else: path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps({"source_assertions_passed": evidence["source_assertions_passed"],
        "normal_attack_count": evidence["normal_attack_count"], "compiler_definitions": evidence["compiler_definitions"],
        "rules": evidence["rules"], "actual_endpoint_probes": len(evidence["actual_attack_endpoint_probes"]),
        "full_stage_executed": False, "formal_stage_approved": False, "output": OUT.as_posix()}))
