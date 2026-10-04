"""New source-aware logical lifecycle profiles; native UI/pause remain pending."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
CANDIDATE = ROOT.parent / "unpack_work/campaign_m13_control_nonspatial_candidate"
SOURCE = ROOT / "packages/campaign/chapter01_controls/native.reference.json"
PIN = "caa25dcdfbb2af5707a4d0d9ec86e8c73feec38fefdaad9481b5aa3df1ecc79a"
BASE = ROOT / "packages/campaign/chapter01_controls/model.json"
BASE_PIN = "ebd821beb558ea5ae6209278822ab5adc1dd35c6d8d821ef60401e8cfd5d788f"
OUT = ROOT / "packages/campaign/chapter01_controls/m13_nonspatial_profiles"


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def encoded(v): return (json.dumps(v, ensure_ascii=False, indent=2)+"\n").encode("utf8")
def emit(event, payload): return {"op": "emit", "target": "battle", "event": event, "payload": payload}


def build(ack_policy="immediate"):
    if ack_policy not in {"immediate", "external"}: raise ValueError("explicit acknowledgement policy required")
    if sha(SOURCE) != PIN or sha(BASE) != BASE_PIN: raise ValueError("frozen chapter01 control input drift")
    source = json.loads(SOURCE.read_bytes()); p = json.loads(BASE.read_bytes())
    definitions = []; actions = []; story_ids = {}
    for key, story in source["stories"].items():
        identifier = "control/chapter01/"+key.rsplit("/", 1)[-1]; story_ids[key] = identifier
        steps = []
        for row in story["classified_rows"]:
            if row["classification"] == "blank": continue
            steps.append({"kind": "effects", "effects": [emit("chapter01.control.source_row_observed", {"story_key": key,
                "native_row": row, "UI_text_is_metadata": True, "native_UI_completed": False})]})
            if row["command"] == "Delay": steps.append({"kind": "delay", "seconds": row["decoded_parameters"]["time"]})
            elif row["command"] in {"dialog", "PopupDialog"}: steps.append({"kind": "ack", "key": "line/"+str(row["line"])})
        lock = {"op": "input_lock", "target": "battle", "parameters": {"key": key, "enabled": True}}
        definitions.append({"id": identifier, "kind": "control", "clock_policy": "logical", "ack_policy": ack_policy,
            "steps": steps, "on_start": [lock], "on_complete": [{**deepcopy(lock), "parameters": {"key": key, "enabled": False}}],
            "on_cancel": [{**deepcopy(lock), "parameters": {"key": key, "enabled": False}}],
            "metadata": {"native_story_source": story["native_source"]["source"], "native_flags_and_rows": story["classified_rows"],
                "native_game_wall_pause_and_UI_confirmation": "client_pending", "model_completion_is_not_native_UI_completion": True}})
    for item in source["control_inventory"]:
        a = item["native_action"]; kind = a["actionType"]
        if kind == "STORY": identifier = story_ids[a["key"]]
        else:
            identifier = f"control/chapter01/{item['level']}/w{item['wave']}f{item['fragment']}a{item['action_index']}"
            definitions.append({"id": identifier, "kind": "control", "clock_policy": "logical", "ack_policy": "immediate",
                "steps": [{"kind": "effects", "effects": deepcopy(item["effects"])}],
                "metadata": {"native_action": a, "profile": item["status"], "native_UI_or_dormant_registry_completed": False}})
        actions.append({"source_origin": {key: item[key] for key in ("level", "wave", "fragment", "action_index")},
            "native_action": deepcopy(a), "template": {"kind": "control", "definition": identifier,
                "instanceAlias": f"chapter01/{item['level']}/w{item['wave']}f{item['fragment']}a{item['action_index']}",
                "delay_seconds": a["preDelay"], "count": a["count"], "interval_seconds": a["interval"],
                "managed": a["managedByScheduler"], "blocks_fragment": a["blockFragment"], "blocks_wave": not a["dontBlockWave"],
                "metadata": {"native_action": deepcopy(a), "native_fragment_origin_not_flattened": True}}})
    p["controls"] = definitions; p["manifest"]["id"] = "package/campaign/chapter01_control_lifecycle_"+ack_policy
    p["manifest"]["metadata"].update(status="source_backed_declared_logical_control_lifecycle_profiles",
        control_ack_policy=ack_policy, builder_sha256=sha(Path(__file__)), source_sha256=PIN,
        native_async_UI_and_pause_implemented=False, complete_stage=False, formal_stage_approved=False)
    matrix = {"schema": "ark-sim/chapter01-m13-control-source/v1", "source_sha256": PIN, "builder_sha256": sha(Path(__file__)),
        "ack_policy": ack_policy, "stages": source["stages"], "action_templates": actions,
        "conversion_scope": "real control lifecycle model with exact source gate flags; logical clock/confirmation are explicit profiles",
        "pending": ["native_UI_wall_clock_and_game_pause", "native_skip_callback_and_confirmation", "native_predefined_dormant_registry",
            "trap_002_emp_definition_filter_and_lifecycle", "fixed12_nativecards_composition", "complete_enemy_and_stage_integration"],
        "full_stage_executed": False, "formal_stage_approved": False}
    return matrix, p


def story_fixture(package, source, story_key):
    p = deepcopy(package)
    item = next(r for r in source["action_templates"] if r["native_action"]["key"] == story_key)
    action = deepcopy(item["template"]); action["delay_seconds"] = 0
    p["scenarioDraft"] = {"id": "scenario/chapter01_m13_story_fixture", "ruleset": "ruleset/ark_standard", "map": {"rows": 9, "cols": 12},
        "timeline": {"policy": "managed_clear", "negative_timeout_policy": "wait_for_clear", "waves": [{"fragments": [
            {"actions": [action]}, {"actions": [{"kind": "effects", "effects": [emit("chapter01.probe.next_fragment", {})]}]}]}]},
        "resources": {"lives": {"initial": 3, "capacity": 3}}, "objectives": {}}
    return p, action["instanceAlias"]


def verify(source, package):
    sys.path.insert(0, str(CANDIDATE))
    import ark_sim
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.compare import first_difference
    from ark_sim.tools.replay import replay
    actual = Path(ark_sim.__file__).resolve()
    if actual.parent != CANDIDATE / "ark_sim": raise RuntimeError("wrong runtime path")
    before = implementation_digest(); results = []
    for key in ("obt/tutorial/level/main_01-11_a", "obt/tutorial/level/main_01-11_b", "obt/tutorial/level/main_01-12"):
        p, alias = story_fixture(package, source, key)
        s = Engine.create(Compiler().compile(p), seed=1311); s.advance(1)
        if source["ack_policy"] == "external":
            while s.ctx.controls.instance(alias)["status"] != "completed":
                instance = s.ctx.controls.instance(alias)
                if instance["phase"] == "awaiting_ack":
                    s.submit({"action": "control_ack", "control": alias, "step": instance["waiting_step"]}); s.advance(1)
                else: s.advance(1)
        else: s.advance(541)
        instance = s.ctx.controls.instance(alias)
        assert instance["status"] == "completed" and not s.ctx.state().get("input_locks")
        s.advance(2)
        assert any(e["type"] == "chapter01.probe.next_fragment" for e in s.session.events)
        restored = Engine.restore(s.program, s.checkpoint()); s.advance(2); restored.advance(2)
        assert first_difference(s.snapshot(), restored.snapshot()) is None
        assert first_difference(s.snapshot(), replay(s.program, s.export_replay()).snapshot()) is None
        assert s.ctx.state()["pending_waves"] == 0 and s.ctx.state()["kills"] == 0 and s.ctx.state()["leaks"] == 0
        results.append({"story": key, "completed_at": instance["completed_at"], "status": instance["status"],
            "program_fingerprint": s.program.fingerprint, "runtime_fingerprint": s.runtime_fingerprint,
            "checkpoint_equal": True, "commands_replay_equal": True, "native_UI_completion_claimed": False})
    if implementation_digest() != before: raise RuntimeError("candidate changed during source probes")
    return {"schema": "ark-sim/chapter01-m13-control-assertions/v1", "passed": True, "actual_import": actual.as_posix(),
        "implementation_digest": before, "ack_policy": source["ack_policy"], "cases": results, "full_stage_executed": False, "formal_stage_approved": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for policy in ("immediate", "external"):
        source, p = build(policy); evidence = verify(source, p)
        for name, value in (("source", source), ("model", p), ("assertions", evidence)):
            path = OUT / (name+"."+policy+".json")
            if args.check:
                if not path.exists() or path.read_bytes() != encoded(value): raise ValueError("M13 profile drift: "+path.name)
            else: path.write_bytes(encoded(value))
    print("Two explicit logical lifecycle profiles and actual source story probes passed.")
