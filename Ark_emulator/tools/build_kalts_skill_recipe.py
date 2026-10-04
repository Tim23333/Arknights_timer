"""Native Kaltsit/Mon3tr source and model recipe; no official token skill IDs invented."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
NORMALIZED = ROOT / "packages/campaign/operators.normalized.json"
BUFF_SOURCE = ROOT.parent / "data/anon_textassets/buff_template_data.dat"
OUTPUT = ROOT / "packages/campaign/skills.kalts.json"
TOKEN = "token_10002_kalts_mon3tr"
HOST_SKILL = "ability/kalts_host_s3"
TOKEN_SKILL = "ability/kalts_token_s3_model"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_bson_document(raw, start=0):
    """Strict bounded BSON subset used by native buff template documents."""
    spans = {}
    def document(offset, array=False, path=()):
        if offset + 4 > len(raw):
            raise ValueError("BSON document truncated")
        size = struct.unpack_from("<i", raw, offset)[0]
        end = offset + size
        if size < 5 or end > len(raw) or raw[end-1] != 0:
            raise ValueError("BSON document length/terminator invalid")
        current, result = offset + 4, {}
        while current < end - 1:
            kind = raw[current]; current += 1
            stop = raw.find(b"\x00", current, end)
            if stop < 0:
                raise ValueError("BSON key truncated")
            key = raw[current:stop].decode("utf-8"); current = stop + 1
            if key in result:
                raise ValueError("duplicate native BSON key")
            def take(count):
                nonlocal current
                if current + count > end - 1:
                    raise ValueError("BSON value exceeds document")
                value = raw[current:current+count]; current += count
                return value
            if kind == 1:
                value = struct.unpack("<d", take(8))[0]
                if not math.isfinite(value):
                    raise ValueError("nonfinite BSON value")
            elif kind == 2:
                length = struct.unpack("<i", take(4))[0]
                if length < 1:
                    raise ValueError("BSON string length invalid")
                data = take(length)
                if data[-1] != 0:
                    raise ValueError("BSON string terminator invalid")
                value = data[:-1].decode("utf-8")
            elif kind in (3, 4):
                old = current
                value, current = document(current, kind == 4, path+(key,))
                if current > end - 1:
                    raise ValueError("nested BSON exceeds parent")
                spans[path+(key,)] = (old, current)
            elif kind == 8:
                byte = take(1)[0]
                if byte not in (0, 1):
                    raise ValueError("BSON boolean invalid")
                value = bool(byte)
            elif kind == 10:
                value = None
            elif kind == 16:
                value = struct.unpack("<i", take(4))[0]
            elif kind == 18:
                value = struct.unpack("<q", take(8))[0]
            elif kind == 5:
                length = struct.unpack("<i", take(4))[0]
                subtype = take(1)[0]
                if length < 0:
                    raise ValueError("BSON binary length invalid")
                value = {"binary_subtype": subtype, "base64": base64.b64encode(take(length)).decode()}
            else:
                raise ValueError(f"unreviewed BSON type {kind}")
            result[key] = value
        if current != end - 1:
            raise ValueError("BSON element alignment mismatch")
        if array:
            if list(result) != [str(i) for i in range(len(result))]:
                raise ValueError("BSON array indexes are not contiguous")
            result = list(result.values())
        return result, end
    result, end = document(start)
    if end != len(raw):
        raise ValueError("BSON payload has trailing bytes")
    return result, spans


def buff_templates():
    from tools.extract_campaign_animation_bindings import unity_payload
    raw = BUFF_SOURCE.read_bytes()
    payload = unity_payload(raw)
    values, spans = decode_bson_document(payload)
    keys = ("kalts_s_3[ratio_atk]", "kalts_token[finish_kill_mark]", "kalts_s_2_3[sp_cond]",
            "kalts_t_withdraw_token", "kalts_t_1[token_def_down]", "kalts_t_1[token_def_down_finish]")
    selected = {}
    for key in keys:
        lo, hi = spans[(key,)]
        selected[key] = {"parsed": values[key], "bson_payload_offset": lo,
            "bson_document_base64": base64.b64encode(payload[lo:hi]).decode(),
            "bson_document_sha256": hashlib.sha256(payload[lo:hi]).hexdigest()}
    return {"source_path": str(BUFF_SOURCE.relative_to(ROOT.parent)).replace("\\", "/"),
            "source_sha256": sha(BUFF_SOURCE), "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "templates": selected, "profile": "bounded BSON, class names kept as data, never imported or executed"}


def token_stats(raw):
    from tools.normalize_campaign_operators import interpolate, half_away_integer, ROUNDING_PROFILE, rational_json
    base, endpoints = interpolate(raw["phases"][2]["attributesKeyFrames"], 70)
    favor, favor_inputs = interpolate(raw["favorKeyFrames"], 50)
    if any(value is not False and value != 0 for value in favor.values()):
        raise ValueError("native token favor must be reviewed before applying a nonzero bonus")
    model = {k: v if isinstance(v, bool) else half_away_integer(v) if k in ROUNDING_PROFILE["integer_attributes"] else float(v)
             for k, v in base.items()}
    return {"elite_phase": 2, "level": 70, "model": model,
            "raw_rational": {k: v if isinstance(v, bool) else rational_json(v) for k, v in base.items()},
            "endpoints": endpoints, "favor_inputs": favor_inputs, "rounding_profile": ROUNDING_PROFILE,
            "client_formula_verified": False}


def recover_source():
    normalized = json.loads(NORMALIZED.read_bytes())
    host = next(row for row in normalized["operators"] if row["character_id"] == "char_003_kalts")
    token = normalized["dependent_characters"][TOKEN]["raw_character"]
    if host["talents"][0]["selected_candidate"]["tokenKey"] != TOKEN:
        raise ValueError("native host-token association changed")
    skill = host["selected_skill"]["level"]
    bb = {row["key"]: row["value"] for row in skill["blackboard"]}
    if skill["spData"]["spCost"] != 15 or skill["duration"] != 20 or bb != {"attack@atk": 2.6, "attack@def": 2.0, "attack@hp_ratio": 0.5}:
        raise ValueError("native selected skill model assumptions changed")
    templates = buff_templates()
    import UnityPy
    path = next(p for p in (ROOT.parent / "data/charpack/char_003_kalts.ab_unpacked").glob("CAB-*") if not p.name.endswith(".resS"))
    host_components = {}
    for obj in UnityPy.load(str(path)).objects:
        if obj.type.name == "MonoBehaviour":
            tree = obj.read_typetree()
            host_components[str(obj.path_id)] = {"script_path_id": tree["m_Script"]["m_PathID"],
                "fields": {k: v for k, v in tree.items() if not k.startswith("m_")}}
    frozen = json.loads((ROOT / "packages/campaign/roster.reference.json").read_bytes())["frozen"]
    skill_prefab = frozen["prefab_catalog"][skill["prefabId"]]
    wrapper = next(c["fields"] for c in skill_prefab["components"] if c["class"] == "AttackAbility")
    if wrapper["_onlyAvailableWhenTokenValid"] != 1 or wrapper["_allowSpRecoveryWhenAffecting"] != 0:
        raise ValueError("native token validity/SP gate changed")
    ratio = templates["templates"]["kalts_s_3[ratio_atk]"]["parsed"]["eventToActions"]["ON_BUFF_TRIGGER"][0]
    if ratio["_attributeType"] != "ATK" or ratio["_formulaType"] != "MULTIPLIER" or ratio["_isInversed"] or ratio["_endTime"] != 0:
        raise ValueError("native remaining ratio attribute profile changed")
    token_pack = ROOT.parent / "data/charpack" / (TOKEN + ".ab_unpacked")
    if token_pack.exists():
        raise ValueError("new native token prefab found; re-review probe and bind its native modes")
    token_art = next(p for p in (ROOT.parent / "data/chararts" / (TOKEN + ".ab_unpacked")).glob("CAB-*") if not p.name.endswith(".resS"))
    art_env = UnityPy.load(str(token_art))
    art_objects = list(art_env.objects)
    if any(obj.type.name == "TextAsset" for obj in art_objects):
        raise ValueError("new token animation TextAsset found; re-review source binding")
    return {"host": host, "token_raw": token, "token_stats": token_stats(token), "templates": templates,
            "host_charpack_sha256": sha(path), "host_charpack_components": host_components,
            "host_skill_prefab": skill_prefab,
            "token_asset_audit": {"charpack_present": False, "chararts_sha256": sha(token_art),
                "textasset_count": 0, "mono_count": sum(obj.type.name == "MonoBehaviour" for obj in art_objects),
                "status": "cached_token_art_is_UI_only_native_attack_frame_not_recovered"},
            "normalized_sha256": sha(NORMALIZED), "token_skill_id_slots": [s["skillId"] for s in token["skills"]]}


def build(*, require_complete=False):
    source = recover_source()
    host, stats = source["host"], source["token_stats"]["model"]
    level = host["selected_skill"]["level"]
    bb = {v["key"]: v["value"] for v in level["blackboard"]}
    gaps = ["native_token_prefab_and_battle_animation_assets_not_present_in_local_cache",
            "explicit_attack_signal_probe_not_native_animation_or_automatic_attack_cadence",
            "native_25s_redeploy_timer_and_card_slot_refresh_pending", "host_heal_priority_and_projectile_callbacks_pending",
            "native_token_death_rattle_1200_damage_and_stun_pending", "remaining_ratio_native_trigger_sampling_interval_pending",
            "model_rounding_and_client_frame_comparison_pending", "native_host_and_token_interrupt_detach_linkage_pending"]
    if require_complete:
        raise ValueError("complete Kaltsit token recipe unsupported: " + "; ".join(gaps))
    ranges = json.loads((ROOT / "ark_emulator/data_range_table.json").read_bytes())
    health = {"initial": stats["maxHp"], "capacity": stats["maxHp"], "capacity_attribute": "max_hp", "role": "health"}
    token = {"id": "unit/kalts_mon3tr_model", "kind": "entity", "tags": ["player", "mon3tr"],
        "metadata": {"native_token_id": TOKEN, "not_independent_operator": True, "status": "partially_implemented"},
        "rules": {"attributes.effective": "rule/kalts_time_layers"}, "components": {
            "spatial": {}, "lifecycle": {"policy": "policy/ark_lifecycle"},
            "deployable": {"base_cost": stats["cost"], "cooldown_seconds": stats["respawnTime"], "terrain": "ground"},
            "attributes": {"base": {"atk": stats["atk"], "def": stats["def"], "mres": 0,
                "max_hp": stats["maxHp"], "block_count": stats["blockCnt"], "block_cost": 1, "move_speed": 1,
                "attack_interval": stats["baseAttackTime"], "attack_speed_ratio": 1}},
            "resources": {"hp": health, "mode": {"initial": 0, "capacity": 1}, "no_kill": {"initial": 0, "capacity": 1}},
            "buffs": {"initial": ["buff/mon3tr_def_zero"]},
            "abilities": [TOKEN_SKILL, "ability/mon3tr_true_probe", "ability/mon3tr_normal_probe", "ability/token_leave", "ability/token_enter"]}}
    host_stats = host["stats"]["model_stats"]
    caster = {"id": "unit/kalts_host_model", "kind": "entity", "tags": ["player", "host"],
        "metadata": {"native_id": host["character_id"], "status": "partially_implemented"}, "components": {
            "spatial": {}, "lifecycle": {"policy": "policy/ark_lifecycle"}, "attributes": {"base": {
                "atk": host_stats["atk"], "def": host_stats["def"], "mres": host_stats["magicResistance"], "max_hp": host_stats["maxHp"]}},
            "resources": {"hp": {"initial": host_stats["maxHp"], "capacity": host_stats["maxHp"], "role": "health"},
                "sp": {"initial": level["spData"]["initSp"], "capacity": level["spData"]["spCost"], "recovery_rate": 1,
                    "recovery": {"mode": "periodic", "interval_seconds": 1, "selector": "selector/owned_mon3tr",
                        "selector_interval_seconds": .1, "empty_value": 0, "interrupt_when_empty": True},
                    "parameters": {"pause_at_full": True, "freeze_while_cast": True, "freeze_cast_modes": ["manual"]}}},
            "buffs": {"initial": ["buff/host_def_gate"]}, "abilities": ["ability/kalts_summon", HOST_SKILL]}}
    enemy = {"id": "unit/kalts_enemy_fixture", "kind": "entity", "tags": ["enemy"], "components": {
        "attributes": {"base": {"atk": 0, "def": 100000, "mres": 100, "max_hp": 100000}}, "spatial": {},
        "resources": {"hp": {"initial": 100000, "capacity": 100000, "role": "health"}}, "lifecycle": {"policy": "policy/ark_lifecycle"}}}
    selectors = [{"id": "selector/owned_mon3tr", "kind": "selector", "region": {"type": "all"},
        "filters": [{"tag": "mon3tr", "state": "alive", "owner": "source"}], "limit": 1},
        {"id": "selector/token_melee", "kind": "selector", "region": {"type": "grid_offsets",
            "offsets": [[g["row"], g["col"]] for g in ranges[source["token_raw"]["phases"][2]["rangeId"]]["grids"]], "rotate_with_facing": True},
         "filters": [{"tag": "enemy", "state": "alive"}], "limit": 1},
        {"id": "selector/host_token_range", "kind": "selector", "region": {"type": "grid_offsets",
            "offsets": [[g["row"], g["col"]] for g in ranges[host["normal_attack_source"]["range_id"]]["grids"]], "rotate_with_facing": True},
         "filters": [{"tag": "mon3tr", "owner": "source", "state": "alive"}], "limit": 1}]
    skill = {"id": HOST_SKILL, "kind": "ability", "metadata": {"native_skill_id": "skchr_kalts_3", "status": "partially_implemented"},
        "activation": {"mode": "manual", "costs": [{"resource": "sp", "amount": 15}], "on_start": [
            {"op": "trigger_ability", "target": "selected", "ability": TOKEN_SKILL}]},
        "parameters": {"blocks_attacks": False, "requires_targets": True}, "selector": "selector/owned_mon3tr",
        "duration_seconds": 20, "timeline": []}
    child = {"id": TOKEN_SKILL, "kind": "ability", "metadata": {"host_native_skill_id": "skchr_kalts_3", "token_native_skill_id": None},
        "activation": {"mode": "manual", "parameters": {"auto_only": True, "blocks_attacks": False}, "on_start": [
            {"op": "modify_resource", "target": "source", "resource": "mode", "value": 1},
            {"op": "modify_resource", "target": "source", "resource": "no_kill", "value": 1},
            {"op": "apply_buff", "target": "source", "buff": "buff/mon3tr_s3"}]}, "duration_seconds": 20, "timeline": []}
    probes = [{"id": f"ability/mon3tr_{'true' if mode else 'normal'}_probe", "kind": "ability",
        "metadata": {"explicit_synthetic_attack_signal": True, "native_animation_pending": True},
        "activation": {"mode": "manual", "condition": f"inputs.resources.mode.current == {mode}", "parameters": {"counts_as_attack": True}},
        "parameters": {"blocks_attacks": False}, "selector": "selector/token_melee", "timeline": [
            {"at": 0, "effect": {"op": "damage", "damage_type": "true" if mode else "physical", "read_mode": {"source_attributes": "at_hit"}}}]} for mode in (0, 1)]
    abilities = [skill, child, *probes,
        {"id": "ability/kalts_summon", "kind": "ability", "activation": {"mode": "manual", "on_start": [
            {"op": "modify_resource", "target": "battle", "resource": "dp", "delta": -stats["cost"]},
            {"op": "spawn", "definition": token["id"], "owner": "source", "position": {"row": 4, "col": 5},
             "parameters": {"max_owned": 1, "on_owner_retire": "remove"}}]}, "timeline": []},
        {"id": "ability/token_leave", "kind": "ability", "activation": {"mode": "manual"}, "timeline": [
            {"at": 0, "effect": {"op": "move", "target": "source", "position": {"row": 0, "col": 0}}}]},
        {"id": "ability/token_enter", "kind": "ability", "activation": {"mode": "manual"}, "timeline": [
            {"at": 0, "effect": {"op": "move", "target": "source", "position": {"row": 4, "col": 5}}}]}]
    penalty = {"op": "damage", "damage_type": "true", "rules": {"damage.pipeline": "rule/mon3tr_no_kill_penalty"},
        "condition": "inputs.targets[0].components.runtime.alive and inputs.targets[0].components.resources.no_kill.current == 1"}
    buffs = [{"id": "buff/mon3tr_s3", "kind": "buff", "duration_seconds": 20,
        "modifiers": [{"attribute": "atk", "layer": "direct_ratio", "value": bb["attack@atk"], "parameters": {"time_curve": {"type": "linear_remaining"}}},
                      {"attribute": "def", "layer": "direct_ratio", "value": bb["attack@def"]}],
        "events": [{"event": "combat.kill", "condition": "inputs.payload.source == context.owner.id and inputs.payload.target != context.owner.id",
                    "effects": [{"op": "modify_resource", "resource": "no_kill", "value": 0}]}],
        "on_remove": [penalty, {"op": "modify_resource", "resource": "mode", "value": 0}, {"op": "modify_resource", "resource": "no_kill", "value": 0}]},
        {"id": "buff/mon3tr_def_zero", "kind": "buff", "modifiers": [{"attribute": "def", "layer": "final_ratio", "value": -1}]},
        {"id": "buff/host_def_gate", "kind": "buff", "aura": {"selector": "selector/host_token_range", "buff": "buff/host_range_member"}},
        {"id": "buff/host_range_member", "kind": "buff", "stacking": {"mode": "independent"},
         "effects": [{"op": "remove_buff", "buff": "buff/mon3tr_def_zero"}],
         "on_remove": [{"op": "apply_buff", "buff": "buff/mon3tr_def_zero", "condition": "inputs.targets[0].components.runtime.alive"}]}]
    rules = [{"id": "rule/kalts_time_layers", "kind": "calculation_rule", "extends": "rule/ark_attribute_layers",
              "implementation": {"type": "provider", "provider": "ark.attributes.time_layers"}},
        {"id": "rule/mon3tr_no_kill_penalty", "kind": "calculation_rule", "contract": "damage.pipeline",
         "metadata": {"input_bindings": {"max_hp": {"entity": "source", "attribute": "max_hp"}}},
         "parameters": {"ratio": bb["attack@hp_ratio"]}, "implementation": {"type": "graph", "nodes": [
             {"id": "result", "expression": "{'accepted': True, 'amount': inputs.effect.max_hp * params.ratio, 'allocations': [], 'events': []}"}], "output": "nodes.result"}}]
    return {"schemaVersion": 2, "status": "partially_implemented", "manifest": {"id": "package/kalts_mon3tr_model", "version": "1",
        "metadata": {"native_source": source, "model_profile": "20s remaining-ratio continuous evaluation; source-backed endpoints; native sample cadence pending",
                     "client_validated": False, "native_token_animation_verified": False, "pending_mechanics": gaps}},
        "entities": [caster, token, enemy], "abilities": abilities, "buffs": buffs, "selectors": selectors, "rules": rules,
        "scenarioDraft": {"id": "scenario/kalts_mon3tr_model", "ruleset": "ruleset/ark_standard",
            "metadata": {"status": "partially_implemented", "not_formal_mainline": True}, "map": {"rows": 9, "cols": 9},
            "resources": {"dp": {"initial": 20, "capacity": 99, "parameters": {"mode": "reject"}}},
            "initialEntities": [{"definition": caster["id"], "instanceAlias": "host", "position": {"row": 4, "col": 4}},
                                {"definition": enemy["id"], "instanceAlias": "enemy", "position": {"row": 4, "col": 6}}]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = recover_source()
    if args.source_only:
        print(json.dumps({"token": TOKEN, "stats": {k: source["token_stats"]["model"][k] for k in ("maxHp", "atk", "def")},
            "templates": list(source["templates"]["templates"]), "null_skills": source["token_skill_id_slots"]}))
    else:
        value = build()
        if args.check:
            if json.loads(OUTPUT.read_bytes()) != value:
                raise ValueError("Kaltsit source/model identity changed")
        else:
            OUTPUT.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+"\n", encoding="utf-8")
        print(json.dumps({"output": str(OUTPUT), "status": "partially_implemented"}))


if __name__ == "__main__":
    main()
