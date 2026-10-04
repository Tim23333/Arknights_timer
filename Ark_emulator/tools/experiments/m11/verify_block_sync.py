"""Run the same explicit new content against pinned base/candidate roots."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def run(root):
    sys.path.insert(0, str(root.resolve()))
    import ark_sim
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from tools.experiments.m11.build_block_sync import scene
    actual = Path(ark_sim.__file__).resolve()
    if actual.parent != root.resolve() / "ark_sim": raise RuntimeError("wrong actual runtime path")
    before = implementation_digest(); output = {}
    for tick in (0, 1, 2):
        s = Engine.create(Compiler().compile(scene()), seed=1101)
        if tick: s.advance(tick)
        s.submit({"action": "skill", "source": "myrtle", "ability": "ability/campaign_myrtle_s2"}); s.advance(25)
        enemy = s.session.world.resolve("enemy")
        starts = [e["time"] for e in s.session.events if e["type"] == "ability.started" and e["payload"]["source"] == enemy]
        damage = [{"time": e["time"], "amount": e["payload"]["amount"]} for e in s.session.events
            if e["type"] == "damage.accepted" and e["payload"]["source"] == enemy]
        output[str(tick)] = {"command_tick": tick, "command_accepted": any(e["type"] == "command.accepted" for e in s.session.events),
            "enemy_cast_ticks": starts, "enemy_damage": damage, "program_fingerprint": s.program.fingerprint,
            "runtime_fingerprint": s.runtime_fingerprint}
    path = Path(__file__).with_name("capacity.fixture.json")
    s = Engine.create(Compiler().compile(json.loads(path.read_bytes())))
    s.ctx.spatial.blocking(); s.ctx.buffs.apply("blocker", "blocker", "buff/less"); s.ctx.spatial.blocking()
    blocked = [s.ctx.spatial.blocked_by(s.session.world.resolve("enemy"+str(i))) for i in range(3)]
    output["capacity_reduction"] = {"expected_capacity": 1, "actual_blocked_members": sum(x is not None for x in blocked),
        "relations": blocked, "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if implementation_digest() != before: raise RuntimeError("runtime changed during comparison")
    return {"actual_import": actual.as_posix(), "implementation_digest": before, "cases": output,
        "scope": "short model counterexamples; no full-stage execution", "formal_approval": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--runtime-root", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(); value = run(args.runtime_root)
    args.output.write_text(json.dumps(value, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps(value))
