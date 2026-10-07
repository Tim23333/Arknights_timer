"""Repeatable V2 model evidence, including the complete 0-1 command sequence.

Run from Ark_emulator: python tools/verify_v2_baseline.py.
This verifies the model and deterministic execution, not client frame accuracy.
"""
import argparse
import gc
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ark_sim import Compiler, Engine
from ark_sim.contracts import digest, thaw
from ark_sim.tools.replay import replay


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def observations(simulation):
    """Compare every observable event without building a second full log tree."""
    event_hash = hashlib.sha256()
    records = simulation.session.events
    for record in records:
        raw = json.dumps(thaw(record), ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
        event_hash.update(raw)
        event_hash.update(b"\n")
    state = {
        "time": simulation.session.time,
        "quantum": simulation.session.quantum,
        "world": simulation.session.world.snapshot(),
        "scheduler": simulation.session.scheduler.snapshot(),
        "random": simulation.session.random.snapshot(),
        "reaction_budget": simulation.session.reaction_budget,
        "program_fingerprint": simulation.program.fingerprint,
        "runtime_fingerprint": simulation.runtime_fingerprint,
        "attribute_cache": simulation.ctx.attributes.checkpoint_cache(),
        "commands": simulation._commands,
    }
    return {"state_sha256": digest(state), "events_sha256": event_hash.hexdigest(),
            "event_count": len(records)}


def check_custom(report):
    runs = {}
    for ruleset, expected in (("ruleset/ark_standard", 850), ("ruleset/custom_balance", 60)):
        program = Compiler().compile(ROOT / "packages/custom/custom_guard.json", ruleset=ruleset)
        simulation = Engine.create(program, seed=123)
        simulation.session.advance(30)
        damage = simulation.ctx.state()["damage_dealt"]
        if damage != expected:
            raise AssertionError(f"{ruleset}: expected {expected} damage, got {damage}")
        original = observations(simulation)
        repeated = replay(program, simulation.export_replay())
        if original != observations(repeated):
            raise AssertionError(f"{ruleset}: replay differs")
        runs[ruleset] = {"damage": damage, "expected": expected, "replay_equal": True,
                         "program_fingerprint": program.fingerprint, **original}
    report["custom_rulesets"] = runs


def check_level(report, output, max_ticks, checkpoint_at):
    package = ROOT / "packages/ark_content/level_main_00_01.json"
    commands = ROOT / "scenarios/level_main_00_01/commands.json"
    program = Compiler().compile(package)
    simulation = Engine.create(program, seed=123)
    for item in load(commands):
        action = dict(item)
        simulation.submit(action, at=action.pop("at"))
    simulation.session.advance(checkpoint_at)
    checkpoint = simulation.checkpoint()
    started = time.perf_counter()
    while not simulation.ctx.state()["finished"] and simulation.session.time < max_ticks:
        simulation.session.advance(min(150, max_ticks - simulation.session.time))
        state = simulation.ctx.state()
        print(json.dumps({"tick": simulation.session.time, "kills": state["kills"],
                          "leaks": state["leaks"], "pending_waves": state["pending_waves"],
                          "elapsed_seconds": round(time.perf_counter()-started, 3)}, ensure_ascii=False), flush=True)
    state = simulation.ctx.state()
    if not state["finished"]:
        raise AssertionError(f"0-1 did not finish before {max_ticks} logical units")
    if (state["result"], state["kills"], state["leaks"], state["pending_waves"]) != ("victory", 11, 0, 0):
        raise AssertionError(f"0-1 model baseline failed: {state}")
    end_time = simulation.session.time
    original = observations(simulation)
    record = simulation.export_replay()
    commands_observed = [thaw(item) for item in simulation.session.events
                         if item["type"] in ("command.accepted", "command.rejected")]
    if len(commands_observed) != 2 or any(item["type"] != "command.accepted" for item in commands_observed):
        raise AssertionError(f"Unexpected deployment result: {commands_observed}")
    level = {"status": "model_validated", "client_frame_validation": "pending",
             "content_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
             "commands_sha256": hashlib.sha256(commands.read_bytes()).hexdigest(),
             "program_fingerprint": program.fingerprint, "runtime_fingerprint": simulation.runtime_fingerprint,
             "quantum": simulation.session.quantum, "final_state": state,
             "end_time": end_time, "finished_seconds": state["finished_at"]*simulation.session.quantum,
             "commands_observed": commands_observed, "observations": original,
             "checkpoint_at": checkpoint_at, "checkpoint_resume_equal": False, "replay_equal": False}
    report["level_00_01"] = level
    write(output, report)
    replay_path = output.with_suffix(".replay.json")
    write(replay_path, record)
    del simulation
    gc.collect()
    print("Checking checkpoint continuation...", flush=True)
    restored = Engine.restore(program, checkpoint)
    restored.session.advance(end_time-restored.session.time)
    if observations(restored) != original:
        raise AssertionError("Checkpoint continuation differs from uninterrupted simulation")
    level["checkpoint_resume_equal"] = True
    write(output, report)
    del restored, checkpoint
    gc.collect()
    print("Checking command replay...", flush=True)
    repeated = replay(program, record)
    if observations(repeated) != original:
        raise AssertionError("0-1 complete command replay differs")
    level["replay_equal"] = True
    level["replay_file"] = str(replay_path.resolve())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "ark_sim/validation/reports/v2_baseline_20261002.json")
    parser.add_argument("--max-ticks", type=int, default=4500)
    parser.add_argument("--checkpoint-at", type=int, default=300)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if not 0 <= args.checkpoint_at < args.max_ticks:
        parser.error("checkpoint-at must be nonnegative and below max-ticks")
    report = {"schema": "ark-sim/model-validation/v2", "date": "2026-10-02",
              "scope": "Independent model expectations and deterministic continuation; no client frame oracle", "passed": False}
    try:
        check_custom(report)
        check_level(report, args.output, args.max_ticks, args.checkpoint_at)
        report["passed"] = True
    except Exception as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        write(args.output, report)
        raise
    write(args.output, report)
    print(f"Validated model evidence: {args.output}", flush=True)


if __name__ == "__main__":
    main()
