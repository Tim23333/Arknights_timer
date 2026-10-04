"""Bounded 300-tick M14 prefix with fixed old command inputs, not full-stage."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT.parent / "unpack_work/campaign_m12_projection_candidate"
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(CANDIDATE))
import ark_sim
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay


if __name__ == "__main__":
    content = ROOT / "packages/campaign/mainline_models/level_main_00-10.m14_timeline.json"
    command_path = ROOT / "validation/campaign/m12_primary_00_10_full_20261002.commands.json"
    before = implementation_digest()
    assert before == "bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11"
    assert Path(ark_sim.__file__).resolve().parent == CANDIDATE / "ark_sim"
    program = Compiler().compile(content); s = Engine.create(program, seed=123)
    selected = [c for c in json.loads(command_path.read_bytes()) if c["at"] < 300]
    for c in selected:
        action = dict(c); at = action.pop("at"); s.submit(action, at=at)
    s.advance(150); cp = s.checkpoint(); r = Engine.restore(program, cp); s.advance(150); r.advance(150)
    assert first_difference(s.snapshot(), r.snapshot()) is None
    assert first_difference(s.snapshot(), replay(program, s.export_replay()).snapshot()) is None
    accepted = [e for e in s.session.events if e["type"] == "command.accepted"]
    rejected = [e for e in s.session.events if e["type"] == "command.rejected"]
    assert len(accepted) == len(selected) and not rejected
    assert implementation_digest() == before
    output = {"schema": "ark-sim/m14-bounded-prefix/v1", "passed": True, "implementation_before": before,
        "implementation_after": implementation_digest(), "actual_import": ark_sim.__file__, "program_fingerprint": program.fingerprint,
        "runtime_fingerprint": s.runtime_fingerprint, "content_sha256": hashlib.sha256(content.read_bytes()).hexdigest(),
        "command_source_sha256": hashlib.sha256(command_path.read_bytes()).hexdigest(), "selected_commands": selected,
        "prefix_ticks": 300, "checkpoint_tick": 150, "checkpoint_equal": True, "commands_replay_equal": True,
        "accepted_commands": len(accepted), "rejected_commands": len(rejected), "kills": s.ctx.state()["kills"], "leaks": s.ctx.state()["leaks"],
        "pending_spawns": s.ctx.state()["pending_waves"], "event_count": len(s.session.events), "full_stage_executed": False,
        "formal_approval": False}
    path = ROOT / "validation/campaign/m14_00_10_prefix.json"; path.write_text(json.dumps(output, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps(output))
