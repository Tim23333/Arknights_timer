"""Audit native control rows; author isolated headless profiles, not full stages."""
from __future__ import annotations
import argparse
import base64
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = ROOT / "packages/campaign/chapter01_sources/native.reference.json"
SOURCE_SHA = "a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd"
NPC = ROOT / "packages/campaign/chapter01_predefines/skill_model/model.json"
NPC_SHA = "e8a5b0114907b7f16977d7b061615c7501c59c072731784d53da81271b5d5b70"
OUT = ROOT / "packages/campaign/chapter01_controls"
RUNTIME = ROOT.parent / "unpack_work/campaign_m12_projection_candidate"
EXPECTED = "bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11"
LEVELS = ("level_main_01-11", "level_main_01-12")
NPC_UNIT = "unit/ch1_predefined_adnach_e0_l20"
DRIVER = "unit/chapter01_control_probe_driver"
PING = "ability/chapter01_control_probe_ping"


class ControlModelGap(ValueError): pass
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def encoded(v): return (json.dumps(v, ensure_ascii=False, indent=2)+"\n").encode("utf8")


def parameters(raw):
    if raw is None: return {}
    pattern = re.compile(r'\s*([A-Za-z_]\w*)\s*=\s*("(?:[^"\\]|\\.)*"|true|false|-?\d+(?:\.\d+)?)\s*(?:,|$)')
    result = {}; cursor = 0
    while cursor < len(raw):
        match = pattern.match(raw, cursor)
        if match is None or match[1] in result: raise ValueError("unconverted/duplicate story parameter: "+raw)
        result[match[1]] = json.loads(match[2]); cursor = match.end()
    return result


def audit_story(story):
    raw = base64.b64decode(story["payload_base64"], validate=True)
    path = ROOT.parent / story["source"]["path"]
    if sha(path) != story["source"]["sha256"] or hashlib.sha256(raw).hexdigest() != story["payload_sha256"] or raw.decode("utf8") != story["script"]:
        raise ValueError("native story source checksum/script mismatch")
    rows = []; cursor = 0
    for row in story["commands"]:
        item = deepcopy(row); cmd = row["command"]
        if row["syntax"] == "blank": item.update(classification="blank", decoded_parameters={})
        elif row["syntax"] == "assignment" and cmd == "name":
            item.update(classification="speaker_and_UI_text_metadata", decoded_parameters={"name": json.loads(row["parameters"])})
        elif cmd in {"HEADER", "PopupDialog", "Blocker", "Delay", "dialog"}:
            item["decoded_parameters"] = parameters(row["parameters"])
            item["classification"] = {"HEADER": "native_UI_flags", "PopupDialog": "UI_text_and_avatar_metadata",
                "Blocker": "UI_overlay_fields_not_proven_gameplay_input_lock", "Delay": "declared_time_unit_native_clock_unknown",
                "dialog": "dialog_UI_transition_confirmation_unknown"}[cmd]
        else: raise ControlModelGap("unconverted native story syntax/command at line "+str(row["line"]))
        item["headless_model_offset_seconds"] = cursor
        if cmd == "Delay":
            seconds = item["decoded_parameters"].get("time")
            if type(seconds) not in (int, float) or seconds < 0: raise ValueError("unsupported Delay.time")
            cursor += seconds
        rows.append(item)
    return {"native_source": deepcopy(story), "classified_rows": rows, "declared_delay_total": cursor,
        "clock_status": "game_time_vs_wall_time_and_native_pause_pending", "UI_text_interpreted_as_gameplay": False}


def emit(event, payload): return {"op": "emit", "target": "battle", "event": event, "payload": payload}
def lock(key, enabled): return {"op": "input_lock", "target": "battle", "parameters": {"key": key, "enabled": enabled}}


def story_profile(story):
    key = story["native_source"]["key"]; lockkey = "model/headless/"+key
    effects = [lock(lockkey, True)]
    for row in story["classified_rows"]:
        if row["classification"] == "blank": continue
        observation = emit("chapter01.headless_story.command_observed", {"story_key": key, "native_row": row,
            "policy": "instant_metadata_ack_with_declared_logical_Delay_v1", "native_command_completed": False})
        effects.append({"op": "schedule", "delay_seconds": row["headless_model_offset_seconds"], "effect": observation})
    # This completes a declared isolated model window, not a native action/barrier.
    effects += [{"op": "schedule", "delay_seconds": story["declared_delay_total"], "effect": lock(lockkey, False)},
        {"op": "schedule", "delay_seconds": story["declared_delay_total"], "effect": emit("chapter01.headless_story.model_window_ended",
            {"key": key, "native_story_completed": False, "native_fragment_released": False})}]
    return effects


def build():
    if sha(SOURCE) != SOURCE_SHA or sha(NPC) != NPC_SHA: raise ValueError("frozen chapter01/NPC input drift")
    raw = json.loads(SOURCE.read_bytes()); stories = {}; inventory = []; stages = {}
    for level in LEVELS:
        stage = raw["stages"][level]; doc = stage["native_level_document"]
        for key, story in stage["stories"].items(): stories[key] = audit_story(story)
        counts = Counter(); rows = []
        for control in stage["controls"]:
            action = control["native_action"]; kind = action["actionType"]; counts[kind] += action["count"]
            origin = {"level": level, "wave": control["wave"], "fragment": control["fragment"], "action_index": control["action_index"]}
            item = {**origin, "native_action": deepcopy(action), "timing": {"origin": "native_fragment_start_unresolved",
                "delay_seconds": action["preDelay"], "count": action["count"], "interval_seconds": action["interval"]},
                "native_route": deepcopy(doc["routes"][action["routeIndex"]]), "native_action_completion_converted": False}
            if kind in {"DISPLAY_ENEMY_INFO", "PREVIEW_CURSOR"}:
                item.update(status="executable_synchronous_metadata_observation", effects=[emit("chapter01.control.metadata_observed", {
                    **origin, "native_action": deepcopy(action), "native_preview_route": deepcopy(item["native_route"]) if action["autoPreviewRoute"] else None,
                    "native_UI_render_or_action_completion": False})],
                    pending=["native_UI_ack_or_managed_wave_lifetime_not_proven"])
            elif kind == "STORY":
                item.update(status="native_async_control_model_gap", effects=None,
                    story=action["key"], pending=["Timeline_effects_complete_synchronously_no_async_control_membership",
                    "native_fragment_barrier" if action["blockFragment"] else "native_managed_wave_control_lifetime",
                    "native_confirmation_and_game_vs_wall_clock"])
            elif kind == "ACTIVATE_PREDEFINED":
                matches = [p for p in doc["predefines"]["characterInsts"] if p["inst"]["characterKey"] == action["key"]]
                if len(matches) != 1 or action["count"] != 1: raise ControlModelGap("activation source instance/count ambiguous")
                inst = matches[0]
                if inst["alias"] is not None: raise ControlModelGap("spawn effect cannot preserve explicit predefine alias")
                if inst["inst"] != {"characterKey": "char_211_adnach", "level": 20, "phase": "PHASE_0", "favorPoint": 0, "potentialRank": 0}:
                    raise ControlModelGap("activation NPC config unsupported")
                item.update(status="executable_isolated_create_on_activation_profile", predefine=deepcopy(inst),
                    effects=[{"op": "spawn", "definition": NPC_UNIT, "position": deepcopy(inst["position"]), "facing": inst["direction"].lower()},
                        emit("chapter01.predefined.model_creation_requested", {**origin, "key": action["key"], "native_alias": inst["alias"],
                            "policy": "absent_until_activation_then_create_active_v1", "native_dormant_registry_converted": False})],
                    pending=["native_hidden_dormant_vs_create_birth_and_SP_clock", "native_predefined_registry_deployed_flag_and_activation_FSM",
                        "fullstage_fragment_origin_blocked_by_STORY_a", "native_routeIndex_placeholder_not_movement"])
            else: raise ControlModelGap("unknown native control type "+kind)
            rows.append(item); inventory.append(item)
        if dict(counts) != stage["control_counts"]: raise ValueError("native control conservation failed")
        stages[level] = {"native_level_document": deepcopy(doc), "native_control_counts": dict(counts), "controls": rows,
            "predefine_counts": {key: len(value or []) for key, value in doc["predefines"].items()},
            "predefined_token_gaps": [{"native_instance": deepcopy(t), "status": "trap_definition_and_runtime_not_converted"}
                for t in doc["predefines"]["tokenInsts"]]}
    package = json.loads(NPC.read_bytes())
    package["entities"].append({"id": DRIVER, "kind": "entity", "tags": ["player", "control_fixture"], "components": {
        "attributes": {"base": {"max_hp": 1000, "atk": 0, "def": 0, "mres": 0}}, "resources": {"hp": {"initial": 1000, "capacity": 1000, "role": "health"}},
        "abilities": [PING], "spatial": {}}})
    package["abilities"].append({"id": PING, "kind": "ability", "activation": {"mode": "manual"},
        "timeline": [{"at": 0, "effect": emit("chapter01.probe.command_accepted", {})}], "parameters": {"blocks_attacks": False}})
    npc_metadata = deepcopy(package["manifest"]["metadata"])
    package["manifest"]["id"] = "package/campaign/chapter01_isolated_controls"
    package["manifest"]["metadata"] = {"status": "isolated_control_profiles_only", "source_sha256": SOURCE_SHA,
        "NPC_model_sha256": NPC_SHA, "builder_sha256": sha(Path(__file__)), "native_fullstage_controls_converted": False,
        "headless_policy": "metadata instantly acknowledged; Delay logical game seconds; whole isolated story window inputlocked",
        "native_UI_confirmation_game_vs_wall_clock": "client_pending", "async_control_lifecycle": "model_gap",
        "NPC_activation_profile": "create absent actor at isolated captured fragment origin +2.99; preserve aliasNone; no route_hidden",
        "NPC_model_metadata": npc_metadata, "full_NPC_implemented": False,
        "cards_and_STORY_barriers": "source retained; no stage integration", "formal_stage_approved": False}
    reference = {"schema": "ark-sim/chapter01-controls-source/v1", "source_sha256": SOURCE_SHA, "builder_sha256": sha(Path(__file__)),
        "stages": stages, "stories": stories, "control_inventory": inventory, "full_stage_executed": False,
        "gap_matrix": {"STORY_blockFragment_and_managed_wave_lifetime": "model_gap", "Delay_clock_and_confirmation": "client_pending",
            "DISPLAY_PREVIEW": "metadata observation only", "ACTIVATE_PREDEFINED": "isolated create profile; native dormant registry pending",
            "1-11_fixed12_native_cards_composition": "pending", "1-12_trap_002_emp_E0L10": "source retained; executable dependency gap"}}
    return reference, package


def require_complete(reference, level):
    stage = reference["stages"][level]
    gaps = [r for r in stage["controls"] if not r["native_action_completion_converted"]]
    if gaps or stage["predefined_token_gaps"]:
        raise ControlModelGap(level+": native control lifecycle/barrier/predefine dependencies unresolved; no complete timeline authored")


def fixture(package, effects, delay=0):
    p = deepcopy(package)
    p["scenarioDraft"] = {"id": "scenario/chapter01_isolated_control_probe", "ruleset": "ruleset/ark_standard", "map": {"rows": 9, "cols": 12},
        "initialEntities": [{"definition": DRIVER, "instanceAlias": "driver", "position": {"row": 0, "col": 0}}],
        "timeline": {"policy": "time_only", "negative_timeout_policy": "skip_wait", "waves": [{"fragments": [{"actions": [
            {"kind": "effects", "delay_seconds": delay, "effects": deepcopy(effects), "count": 1}]}]}]}}
    return p


def runtime(path):
    path = path.resolve(); sys.path.insert(0, str(path))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    actual = Path(ark_sim.__file__).resolve()
    if actual.parent != path / "ark_sim" or implementation_digest() != EXPECTED: raise RuntimeError("wrong runtime root/identity")
    return {"actual_import": actual.as_posix(), "implementation_digest": EXPECTED}


def verify(reference, package, identity):
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.compare import first_difference
    from ark_sim.tools.replay import replay
    observations = []
    for item in reference["control_inventory"]:
        if item["native_action"]["actionType"] not in {"DISPLAY_ENEMY_INFO", "PREVIEW_CURSOR"}: continue
        a = item["native_action"]
        p = fixture(package, [])
        p["scenarioDraft"]["timeline"]["waves"][0]["fragments"][0]["actions"] = [{"kind": "effects", "delay_seconds": a["preDelay"],
            "count": a["count"], "interval_seconds": a["interval"], "effects": item["effects"]}]
        s = Engine.create(Compiler().compile(p)); s.advance(int((a["preDelay"]+(a["count"]-1)*a["interval"])*30)+2)
        events = [e for e in s.session.events if e["type"] == "chapter01.control.metadata_observed"]
        assert len(events) == a["count"]
        observations.append({"level": item["level"], "action_index": item["action_index"], "count": len(events), "ticks": [e["time"] for e in events]})
    story = reference["stories"]["obt/tutorial/level/main_01-11_b"]
    assert story["declared_delay_total"] == 18
    s = Engine.create(Compiler().compile(fixture(package, story_profile(story))), seed=111)
    # Timeline expands its same-tick action tasks during signal handling;
    # do not assume an already submitted t0 command runs after that expansion.
    s.advance(1)
    s.submit({"action": "skill", "source": "driver", "ability": PING}); s.advance(299)
    assert any(e["type"] == "command.rejected" and "input locked" in e["payload"]["reason"] for e in s.session.events)
    cp = s.checkpoint(); r = Engine.restore(s.program, cp); s.advance(241); r.advance(241)
    assert not s.ctx.state().get("input_locks")
    assert first_difference(s.snapshot(), r.snapshot()) is None
    s.submit({"action": "skill", "source": "driver", "ability": PING}); s.advance(2)
    assert any(e["type"] == "chapter01.probe.command_accepted" for e in s.session.events)
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None
    assert not [e for e in s.session.events if e["type"] in {"story.finished", "native.story.finished"}]
    activation = next(r for r in reference["control_inventory"] if r["native_action"]["actionType"] == "ACTIVATE_PREDEFINED")
    s = Engine.create(Compiler().compile(fixture(package, activation["effects"], delay=2.99)), seed=111)
    s.advance(90); assert not [e for e in s.session.world.entities() if e["definition_id"] == NPC_UNIT]
    restored = Engine.restore(s.program, s.checkpoint()); s.advance(1); restored.advance(1)
    born = [e for e in s.session.world.entities() if e["definition_id"] == NPC_UNIT]
    assert len(born) == 1 and born[0]["components"]["spatial"]["position"] == {"row": 3, "col": 6}
    assert born[0]["components"]["spatial"]["facing"] == "right" and born[0]["components"]["resources"]["hp"]["current"] == 677
    assert born[0]["components"]["resources"]["sp"]["current"] == 0
    assert not born[0]["components"]["runtime"].get("route_hidden")
    assert first_difference(s.snapshot(), restored.snapshot()) is None
    assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None
    for level in LEVELS:
        try: require_complete(reference, level)
        except ControlModelGap: pass
        else: raise AssertionError("unresolved native controls accepted as complete")
    if implementation_digest() != identity["implementation_digest"]: raise RuntimeError("runtime changed during probes")
    return {"schema": "ark-sim/chapter01-controls-assertions/v1", "passed": True, "runtime": identity, "metadata_observations": observations,
        "headless_story_b": {"Popup_offsets_seconds": [0, 4, 8, 12, 16], "logical_window_seconds": 18, "unlock_tick": 540,
            "locked_command_rejected": True, "unlocked_command_accepted": True, "checkpoint_equal": True, "commands_replay_equal": True,
            "native_story_completion_claimed": False}, "NPC_creation": {"isolated_fragment_origin": 0, "activation_tick": 90,
            "pre_activation_births": 0, "post_activation_births": 1, "HP": 677, "SP": 0, "checkpoint_equal": True, "commands_replay_equal": True,
            "native_dormant_registry_or_stage_absolute_time_claimed": False}, "full_native_timeline_rejected": list(LEVELS),
        "model_sha256": hashlib.sha256(encoded(package)).hexdigest(), "full_stage_executed": False, "formal_stage_approved": False}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--check", action="store_true"); args = p.parse_args()
    identity = runtime(RUNTIME); reference, model = build(); evidence = verify(reference, model, identity)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, value in (("native.reference.json", reference), ("model.json", model), ("assertions.json", evidence)):
        path = OUT/name
        if args.check:
            if not path.exists() or path.read_bytes() != encoded(value): raise ValueError("chapter01 controls artifact drift: "+name)
        else: path.write_bytes(encoded(value))
    print(json.dumps({"passed": True, "runtime": identity, "native_fullstage_controls_converted": False}))


if __name__ == "__main__": main()
