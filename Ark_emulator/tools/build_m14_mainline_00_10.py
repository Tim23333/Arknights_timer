"""New source-preserving 0-10 managed Timeline on frozen M12, no old rewrite."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
INPUT = ROOT / "packages/campaign/mainline_models/level_main_00-10.m12_projection.json"
INPUT_SHA = "0fbba3f0548d2efaef97d7c1be98a620e65b6408755bfddbd49a132ef72fddf4"
NATIVE = ROOT / "packages/campaign/native_reference/level_main_00-10.json"
NATIVE_SHA = "f9dd4ac486b4dccfc4a152b86fbe698355b626df6b90a88992c85e6bb307cfe6"
STORY = ROOT / "packages/campaign/controls.00_10.reference.json"
OUTPUT = ROOT / "packages/campaign/mainline_models/level_main_00-10.m14_timeline.json"
CANDIDATE = ROOT.parent / "unpack_work/campaign_m12_projection_candidate"
CORE = "bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11"


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_bytes())
def encoded(v): return (json.dumps(v, ensure_ascii=False, indent=2)+"\n").encode("utf8")
def emit(event, payload): return {"op": "emit", "target": "battle", "event": event, "payload": payload}


def immediate_ui(native, wi, fi, ai, old_effect, story):
    provenance = {"native_action": deepcopy(native), "native_wave": wi, "native_fragment": fi, "native_action_index": ai,
        "action_start_source": "timeline.action.origins.action_start", "profile": "zero_lifetime_headless_UI_v1"}
    effects = [emit("m14.ui.started", provenance)]
    if native["actionType"] == "STORY":
        if native["key"] != "obt/tutorial/level/main_00-10" or native["blockFragment"]:
            raise ValueError("unproven async/replaced story cannot use zero-lifetime profile")
        key = native["key"]
        effects.append({"op": "input_lock", "target": "battle", "parameters": {"key": key, "enabled": True}})
        commands = [e["payload"] for e in old_effect["effects"] if e.get("event") == "story.command"]
        if len(commands) != 5: raise ValueError("native story command inventory changed")
        raw_commands = []
        for line in story["script"].splitlines():
            match = re.fullmatch(r"\[(HEADER|PopupDialog|Blocker)\((.*)\)\]\s*(.*)", line)
            if match is None: raise ValueError("unsupported raw native story line")
            raw_commands.append({"command": match[1], "native_parameters": match[2], "text": match[3]})
        if raw_commands != commands: raise ValueError("frozen UI commands do not consume exact native story text")
        effects += [emit("m14.ui.command_observed", {**provenance, "command": command, "UI_text_is_metadata": True}) for command in commands]
        effects.append({"op": "input_lock", "target": "battle", "parameters": {"key": key, "enabled": False}})
    else:
        effects.append(emit("m14.ui.command_observed", {**provenance, "enemy_info": deepcopy(old_effect["payload"]), "UI_text_is_metadata": True}))
    effects.append(emit("m14.ui.ack_finished", {**provenance, "completion_lifetime_ticks": 0, "native_UI_callback_verified": False}))
    return effects


def build():
    if sha(INPUT) != INPUT_SHA or sha(NATIVE) != NATIVE_SHA: raise ValueError("frozen M12/native input drift")
    p = read(INPUT); native = read(NATIVE); scene = p["scenarioDraft"]
    spawns = deepcopy(scene.pop("waves")); old_controls = scene.pop("scheduledEffects")
    story = read(STORY); cursor = 0; timeline = []; controls = []; source_counts = Counter()
    if sha((ROOT / story["path"]).resolve()) != story["sha256"] or hashlib.sha256(story["script"].encode("utf8")).hexdigest() != story["script_sha256"]:
        raise ValueError("native story file/script declaration mismatch")
    for wi, nw in enumerate(native["waves"]):
        wave = {"pre_delay_seconds": nw["preDelay"], "post_delay_seconds": nw["postDelay"],
            "max_wait_seconds": nw["maxTimeWaitingForNextWave"], "fragments": [], "metadata": {"native_wave": deepcopy(nw)}}
        for fi, nf in enumerate(nw["fragments"]):
            fragment = {"pre_delay_seconds": nf["preDelay"], "actions": [], "metadata": {"native_fragment_index": fi}}
            for ai, action in enumerate(nf["actions"]):
                source_counts[action["actionType"]] += action["count"]
                provenance = {"native_action": deepcopy(action), "native_wave": wi, "native_fragment": fi, "native_action_index": ai}
                common = {"delay_seconds": action["preDelay"], "interval_seconds": action["interval"],
                    "managed": action["managedByScheduler"], "blocks_wave": not action["dontBlockWave"], "blocks_fragment": action["blockFragment"]}
                if action["actionType"] == "SPAWN":
                    rows = spawns[cursor:cursor+action["count"]]
                    if len(rows) != action["count"]: raise ValueError("native spawn repeat mismatch")
                    first = deepcopy(rows[0]) if rows else None
                    for repeat, row in enumerate(rows):
                        if row["definition"] != "unit/"+action["key"] or row["parameters"]["native_route_index"] != action["routeIndex"]:
                            raise ValueError("native enemy/route source substitution")
                        reference = deepcopy(row); reference.pop("instanceAlias", None); reference.pop("at_seconds", None)
                        baseline = deepcopy(first); baseline.pop("instanceAlias", None); baseline.pop("at_seconds", None)
                        if reference != baseline: raise ValueError("source repeats differ beyond alias/timing; require distinct model action")
                    if rows:
                        spawn = deepcopy(first); spawn.pop("at_seconds", None)
                        # Use one native action/count instead of flattening repeats.
                        # New aliases explicitly bind native source action coordinates.
                        spawn["instanceAlias"] = f"m14/native/w{wi}/f{fi}/a{ai}"
                        spawn["parameters"].update(native_action_index=ai)
                        fragment["actions"].append({**common, "kind": "spawn", "count": action["count"], "spawn": spawn, "metadata": provenance})
                    cursor += action["count"]
                elif action["actionType"] in {"STORY", "DISPLAY_ENEMY_INFO"}:
                    candidates = [entry["effect"] for entry in old_controls if entry["effect"]["payload"]["native_action"] == action
                        and entry["effect"]["payload"]["native_wave"] == wi and entry["effect"]["payload"]["native_fragment"] == fi]
                    if len(candidates) != 1 or action["count"] != 1: raise ValueError("exact UI source identity/repeat unsupported")
                    effects = immediate_ui(action, wi, fi, ai, candidates[0], story)
                    fragment["actions"].append({"kind": "effects", "count": action["count"], "delay_seconds": action["preDelay"],
                        "interval_seconds": action["interval"], "effects": effects, "metadata": {**provenance,
                        "native_gate_flags": {key: action[key] for key in ("managedByScheduler", "dontBlockWave", "blockFragment")},
                        "zero_lifetime_member_elision": True, "completion_profile": "true_started_observation_ack_finished_same_tick"}})
                    controls.append(provenance)
                else: raise ValueError("unconverted native action "+action["actionType"])
            wave["fragments"].append(fragment)
        timeline.append(wave)
    if cursor != 35 or cursor != len(spawns) or source_counts != Counter({"SPAWN": 35, "STORY": 1, "DISPLAY_ENEMY_INFO": 1}):
        raise ValueError("native population/control conservation failed")
    scene["timeline"] = {"policy": "managed_clear", "negative_timeout_policy": "wait_for_clear", "waves": timeline,
        "metadata": {"native_control_flags_preserved": True, "UI_zero_lifetime_profile": True}}
    scene["id"] = "scenario/campaign_model/level_main_00-10/m14"
    scene["metadata"].update(model_status="new_managed_timeline_requires_new_whole_stage_evidence", model_validated=False,
        formal_mainline_approved=False, m14_timeline=True)
    p["manifest"]["id"] = "package/campaign/model/level_main_00-10/m14"
    p["manifest"]["metadata"]["m14_schedule_profile"] = {"id": "native_wave_fragment_managed_clear_logical_UI_v1",
        "negative_timeout_policy": "wait_for_clear", "native_sentinel_and_scheduler_body_verified": False,
        "wave_origin": "entry_before_preDelay", "fragment_origin": "after_fragment_preDelay", "UI_control_lifetime": 0,
        "UI_membership": "complete within synchronous action; source flags retained, no cross-tick member",
        "native_wall_time_pause_and_ack": "client_pending"}
    p["manifest"]["metadata"]["m14_sources"] = {"input": INPUT_SHA, "native": NATIVE_SHA, "builder": sha(Path(__file__)), "story_reference": sha(STORY)}
    for key in set(p)-{"scenarioDraft", "manifest", "status"}:
        if encoded(p[key]) != encoded(read(INPUT)[key]): raise ValueError("canonical definition section bytes changed: "+key)
    return p


def runtime():
    sys.path.insert(0, str(CANDIDATE))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    if Path(ark_sim.__file__).resolve().parent != CANDIDATE / "ark_sim" or implementation_digest() != CORE: raise RuntimeError("wrong fixed M12 runtime")
    return CORE


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    runtime(); p = build()
    from ark_sim import Compiler
    program = Compiler().compile(p)
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_bytes() != encoded(p): raise ValueError("M14 source/output drift")
    else: OUTPUT.write_bytes(encoded(p))
    print(json.dumps({"definitions": len(program.definitions), "native_spawns": 35, "implementation": CORE,
        "package_sha256": sha(OUTPUT), "whole_stage_executed": False, "formal_approval": False}))
