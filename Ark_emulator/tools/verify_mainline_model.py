"""Execute partial mainline integration without issuing formal acceptance."""
import argparse
import gc
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.verify_v2_baseline import observations, write


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(package, commands, ticks, checkpoint_at, output, seed=None, require_victory=False, verify_replay=True):
    package_bytes, command_bytes = package.read_bytes(), commands.read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    package_copy, commands_copy = output.with_suffix(".package.json"), output.with_suffix(".commands.json")
    package_copy.write_bytes(package_bytes)
    commands_copy.write_bytes(command_bytes)
    report = {"schema": "ark-sim/partial-stage-model-validation/v1", "passed": False,
        "formal_stage_accepted": False, "complete_operator_count": 0, "client_validated": False,
        "package_sha256": sha(package_copy), "commands_sha256": sha(commands_copy), "ticks": ticks,
        "package_snapshot": str(package_copy), "commands_snapshot": str(commands_copy)}
    try:
        program = Compiler().compile(json.loads(package_bytes))
        sim = Engine.create(program, seed=123 if seed is None else seed)
        report["model_seed"] = sim.seed
        report.update(program_fingerprint=program.fingerprint, runtime_fingerprint=sim.runtime_fingerprint)
        timeline = program.scenario.get("timeline")
        if timeline is not None:
            expected = Counter()
            for wave in timeline["waves"]:
                for fragment in wave["fragments"]:
                    for action in fragment["actions"]:
                        if action["kind"] == "spawn":
                            expected[action["spawn"]["definition"]] += action.get("count", 1)
        else:
            expected = Counter(task["payload"]["definition"] for task in sim.session.scheduler.pending
                               if task["kind"] == "domain.wave" and task["at"] < ticks)
        for item in json.loads(command_bytes):
            action = dict(item)
            sim.submit(action, at=action.pop("at"))
        sim.session.advance(checkpoint_at)
        checkpoint = sim.checkpoint()
        start = time.perf_counter()
        while sim.session.time < ticks:
            sim.session.advance(min(100, ticks-sim.session.time))
            print(json.dumps({"tick": sim.session.time, "state": sim.ctx.state()["result"],
                "kills": sim.ctx.state()["kills"], "elapsed_seconds": round(time.perf_counter()-start, 3)}), flush=True)
            if require_victory and sim.ctx.state()["finished"]:
                break
        events = sim.session.events
        observed_commands = [thaw(e) for e in events if e["type"] in ("command.accepted", "command.rejected")]
        if any(e["type"] == "command.rejected" for e in observed_commands):
            raise AssertionError(f"unexpected rejected command: {observed_commands}")
        actual = Counter(e["definition_id"] for e in sim.session.world.entities() if "enemy" in e["tags"])
        conserved = actual == expected
        if timeline is not None and not require_victory:
            conserved = all(actual[key] <= expected[key] for key in actual) and sum(actual.values())+sim.ctx.state()["pending_waves"] == sum(expected.values())
        if not conserved:
            raise AssertionError("native spawn conservation failed")
        if require_victory and (sim.ctx.state()["result"] != "victory" or sim.ctx.state()["leaks"] or sim.ctx.state()["pending_waves"]):
            raise AssertionError(f"full model victory was not achieved: {sim.ctx.state()}")
        original = observations(sim)
        end_time = sim.session.time
        record = sim.export_replay()
        report.update(state=sim.ctx.state(), observed_commands=observed_commands,
            spawned_by_definition=dict(actual), observations=original,
            checkpoint_at=checkpoint_at, end_time=end_time,
            checkpoint_resume_equal=False if verify_replay else None, replay_equal=False if verify_replay else None,
            event_counts=dict(Counter(e["type"] for e in events)))
        if verify_replay:
            # Retain only hashes, summary and the small prefix checkpoint. Do
            # not keep three complete event histories live simultaneously.
            del events, sim
            gc.collect()
            print("Checking sequential checkpoint continuation...", flush=True)
            restored = Engine.restore(program, checkpoint)
            restored.session.advance(end_time-checkpoint_at)
            if observations(restored) != original:
                raise AssertionError("partial checkpoint continuation differs")
            report["checkpoint_resume_equal"] = True
            write(output, report)
            del restored, checkpoint
            gc.collect()
            print("Checking sequential command replay...", flush=True)
            repeated = replay(program, record)
            if observations(repeated) != original:
                raise AssertionError("partial command replay differs")
            report["replay_equal"] = True
        report["passed"] = True
    except Exception as exc:
        if "sim" in locals():
            report["state"] = sim.ctx.state()
            report["leak_events"] = [{"event": thaw(e), "definition": sim.ctx.entity(e["payload"]["target"])["definition_id"]}
                for e in sim.session.events if e["type"] == "entity.exited"]
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        write(output, report)
        raise
    write(output, report)
    print("Partial stage integration verified; formal acceptance remains false.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=ROOT/"packages/campaign/mainline_models/level_main_00-10.json")
    parser.add_argument("--commands", type=Path, default=ROOT/"scenarios/campaign/00_10_model_probe.json")
    parser.add_argument("--ticks", type=int, default=600)
    parser.add_argument("--checkpoint-at", type=int, default=100)
    parser.add_argument("--output", type=Path, default=ROOT/"validation/campaign/m6_00_10_probe_20261002.json")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--require-victory", action="store_true")
    parser.add_argument("--no-replay", action="store_true", help="Exploratory run only; replay fields stay null")
    args = parser.parse_args()
    if not 0 <= args.checkpoint_at < args.ticks:
        parser.error("checkpoint-at must be below positive ticks")
    run(args.package, args.commands, args.ticks, args.checkpoint_at, args.output,
        seed=args.seed, require_victory=args.require_victory, verify_replay=not args.no_replay)
