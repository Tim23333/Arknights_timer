"""Source-backed 0-10 controls with an explicit headless story policy."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_mainline_dependencies import build as dependencies

OUTPUT = ROOT / "packages/campaign/controls.00_10.model.json"


def story_reference():
    path = ROOT.parent / "unpack_work/release_20260831/hot_raw/main_00-10.dat"
    raw = path.read_bytes()
    size = struct.unpack_from("<I", raw)[0]
    if raw[4:4+size] != b"main_00-10":
        raise ValueError("unexpected story asset name")
    offset = (4+size+3)//4*4
    length = struct.unpack_from("<I", raw, offset)[0]
    if offset+4+length > len(raw) or any(raw[offset+4+length:]):
        raise ValueError("story bounds or trailing data changed")
    script = raw[offset+4:offset+4+length].decode("utf8")
    frozen = json.loads((ROOT/"packages/campaign/controls.00_10.reference.json").read_text(encoding="utf8"))
    if frozen["sha256"] != hashlib.sha256(raw).hexdigest() or frozen["script"] != script:
        raise ValueError("story source reference changed")
    commands = []
    for line in script.splitlines():
        match = re.fullmatch(r"\[(HEADER|PopupDialog|Blocker)\((.*)\)\]\s*(.*)", line)
        if match is None:
            raise ValueError("unsupported native story command")
        commands.append({"command": match[1], "native_parameters": match[2], "text": match[3]})
    if [c["command"] for c in commands] != ["HEADER", "PopupDialog", "PopupDialog", "PopupDialog", "Blocker"]:
        raise ValueError("native story sequence changed")
    return {"source": path.relative_to(ROOT.parent).as_posix(), "sha256": frozen["sha256"],
            "script_sha256": frozen["script_sha256"], "commands": commands}


def emit(name, payload):
    return {"op": "emit", "target": "battle", "event": name, "payload": payload}


def build():
    plan = dependencies()
    native = json.loads((ROOT/"packages/campaign/native_reference/level_main_00-10.json").read_text(encoding="utf8"))
    story = story_reference()
    scheduled, counts = [], {}
    cursor = 0
    for wi, wave in enumerate(plan["native_wave_script"]):
        cursor += wave["preDelay"]
        for fi, fragment in enumerate(wave["fragments"]):
            start = cursor+fragment["preDelay"]
            end = start
            for action in fragment["actions"]:
                if action["blockFragment"] or action["actionType"] not in ("SPAWN", "STORY", "DISPLAY_ENEMY_INFO"):
                    raise ValueError("unsupported native wave control gating")
                count = action["count"]
                if count:
                    end = max(end, start+action["preDelay"]+(count-1)*action["interval"])
                if action["actionType"] == "SPAWN":
                    continue
                counts[action["actionType"]] = counts.get(action["actionType"], 0)+count
                for repeat in range(count):
                    provenance = {"native_action": deepcopy(action), "native_wave": wi, "native_fragment": fi}
                    if action["actionType"] == "STORY":
                        if action["key"] != "obt/tutorial/level/main_00-10":
                            raise ValueError("unknown story reference")
                        lock = {"op": "input_lock", "target": "battle", "parameters": {"key": action["key"], "enabled": True}}
                        effects = [lock, emit("story.started", provenance)]
                        effects += [emit("story.command", c) for c in story["commands"]]
                        effects += [{**deepcopy(lock), "parameters": {"key": action["key"], "enabled": False}},
                                    emit("story.finished", {"key": action["key"], "policy": "headless_ack_zero_game_time_v1"})]
                        effect = emit("native.control", provenance)
                        effect["effects"] = effects
                    else:
                        route = deepcopy(native["routes"][action["routeIndex"]]) if action["autoPreviewRoute"] else None
                        effect = emit("enemy.info_displayed", {**provenance, "native_preview_route": route})
                    scheduled.append({"at_seconds": start+action["preDelay"]+repeat*action["interval"], "effect": effect})
            cursor = end
        cursor += wave["postDelay"]
    if counts != plan["control_counts"]:
        raise ValueError("native control conservation failed")
    return {"schema": "ark-sim/native-control-model/v1", "status": "explicit_headless_model",
        "source": story, "native_control_counts": counts, "scheduledEffects": scheduled,
        "model_policy": {"id": "headless_ack_zero_game_time_v1", "dialogue_acknowledged_at_same_logical_tick": True,
                         "blocker_input_lock_observable": True, "native_ui_wall_time_simulated": False},
        "client_validated": False, "formal_stage_approved": False,
        "pending": ["native_UI_input_and_pause_callback_order", "source_versions_alignment"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = build()
    if args.check:
        if json.loads(OUTPUT.read_text(encoding="utf8")) != value:
            raise SystemExit("native control model identity changed")
    else:
        OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
    print("0-10 story and enemy-info controls represented by explicit headless effects.")
