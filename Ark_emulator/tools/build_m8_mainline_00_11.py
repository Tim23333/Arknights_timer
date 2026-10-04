"""Compose an explicit managed-clear model without rewriting frozen M7 inputs."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_m7_mainline_00_11 import build as m7_build
from tools.build_m7_mainline_model import sha

OUTPUT = ROOT/"packages/campaign/mainline_models/level_main_00-11.m8.json"


def build(policy="managed_clear", negative_timeout_policy="wait_for_clear"):
    if policy not in ("managed_clear", "time_only") or negative_timeout_policy not in ("wait_for_clear", "skip_wait"):
        raise ValueError("explicit supported model timeline policies required")
    result = m7_build()
    source_path = ROOT/"packages/campaign/sources.00_11.reference.json"
    source = json.loads(source_path.read_bytes())
    control = json.loads((ROOT/"packages/campaign/controls.00_11.model.json").read_bytes())
    scene = result["scenarioDraft"]
    spawns = scene.pop("waves")
    cursor = 0
    waves = []
    for wi, native_wave in enumerate(source["native_wave_script"]):
        wave = {"pre_delay_seconds": native_wave["preDelay"], "post_delay_seconds": native_wave["postDelay"],
                "max_wait_seconds": native_wave["maxTimeWaitingForNextWave"], "fragments": []}
        for fi, native_fragment in enumerate(native_wave["fragments"]):
            fragment = {"pre_delay_seconds": native_fragment["preDelay"], "actions": []}
            for ai, native in enumerate(native_fragment["actions"]):
                common = {"delay_seconds": native["preDelay"], "interval_seconds": native["interval"],
                          "managed": native["managedByScheduler"], "blocks_wave": not native["dontBlockWave"],
                          "blocks_fragment": native["blockFragment"]}
                if native["actionType"] == "SPAWN":
                    # The frozen draft already proves exact coordinate/route translation.
                    rows = spawns[cursor:cursor+native["count"]]
                    if len(rows) != native["count"]:
                        raise ValueError("native spawn multiplicity differs from frozen conversion")
                    for repeat, row in enumerate(rows):
                        if row["definition"] != "unit/"+native["key"] or row["parameters"]["native_route_index"] != native["routeIndex"]:
                            raise ValueError("native action/source route mismatch")
                        spawn = deepcopy(row)
                        spawn.pop("at_seconds", None)
                        spawn["parameters"].update(native_action=ai, native_repeat=repeat)
                        fragment["actions"].append({**common, "kind": "spawn", "count": 1,
                            "delay_seconds": native["preDelay"]+repeat*native["interval"], "spawn": spawn})
                    cursor += native["count"]
                elif native["actionType"] == "STORY":
                    if native["count"] != 1:
                        raise ValueError("unproven repeated story conversion")
                    fragment["actions"].append({**common, "managed": False, "blocks_wave": False,
                        "blocks_fragment": False, "metadata": {"native_action": native,
                        "completion_policy": "synchronous_headless_ack"}, "kind": "effects", "count": 1,
                        "effects": [deepcopy(control["scheduledEffects"][0]["effect"])]})
                elif native["actionType"] == "DISPLAY_ENEMY_INFO":
                    matches = [entry["effect"] for entry in control["scheduledEffects"]
                        if entry["effect"].get("payload", {}).get("native_wave") == wi and
                        entry["effect"].get("payload", {}).get("native_fragment") == fi and
                        entry["effect"].get("payload", {}).get("native_action_index") == ai]
                    if len(matches) != native["count"]:
                        raise ValueError("missing exact enemy-info control action")
                    for repeat, effect in enumerate(matches):
                        fragment["actions"].append({**common, "managed": False, "blocks_wave": False,
                            "blocks_fragment": False, "metadata": {"native_action": native,
                            "completion_policy": "synchronous_headless_ack"}, "kind": "effects", "count": 1,
                            "delay_seconds": native["preDelay"]+repeat*native["interval"], "effects": [deepcopy(effect)]})
                else:
                    raise ValueError("unconverted native action: "+native["actionType"])
            wave["fragments"].append(fragment)
        waves.append(wave)
    if cursor != len(spawns) or cursor != 37:
        raise ValueError("native spawn inventory changed")
    scene.pop("scheduledEffects", None)
    scene["timeline"] = {"policy": policy, "negative_timeout_policy": negative_timeout_policy, "waves": waves}
    scene["id"] = "scenario/campaign_model/level_main_00-11/m8"
    scene["metadata"].pop("pending_checkpoint_types", None)
    scene["metadata"].update(runnable=True, model_validated=False, formal_mainline_approved=False, m8_timeline=True)
    result["status"] = "partial_executable_model_not_client_validated"
    result["manifest"]["id"] = "package/campaign/model/level_main_00-11/m8"
    meta = result["manifest"]["metadata"]
    meta["schedule_profile"] = {"id": "declared_wave_fragment_timeline_v1", "policy": policy,
        "negative_timeout_policy": negative_timeout_policy, "native_wave_gating_verified": False,
        "wave_origin": "entry_before_pre_delay", "fragment_origin": "after_fragment_pre_delay",
        "post_delay": "after_managed_gate", "control_completion": "synchronous_headless"}
    meta["pending"] = [p for p in meta["pending"] if p != "native_managed_wave_completion_gating_not_converted"]
    meta["pending"].extend(["native_managed_clear_policy_body_unverified", "native_negative_timeout_sentinel_unverified"])
    meta["m8_source_identities"] = {"builder": sha(Path(__file__)), "native_source": sha(source_path),
        "m7_composition_builder": sha(ROOT/"tools/build_m7_mainline_00_11.py"),
        "controls": sha(ROOT/"packages/campaign/controls.00_11.model.json")}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = build()
    from ark_sim import Compiler
    program = Compiler().compile(value)
    if args.check:
        if json.loads(OUTPUT.read_bytes()) != value:
            raise SystemExit("M8 composition changed")
    else:
        OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf8", newline="\n")
    print(f"M8 model compiled: {len(program.definitions)} definitions; 37 native spawns; client/formal pending")
