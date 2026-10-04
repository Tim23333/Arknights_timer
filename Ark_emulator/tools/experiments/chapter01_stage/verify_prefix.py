"""Execute unchanged 1-11 source through its first post-tutorial enemy birth."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT.parent/"unpack_work/campaign_m15_category_candidate"
sys.path.insert(0, str(RUNTIME)); sys.path.insert(1, str(ROOT))
import ark_sim
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_chapter01_stage_models import build, encoded, CORE, INPUTS, sha, OUT


def main():
    if Path(ark_sim.__file__).resolve().parent != RUNTIME/"ark_sim" or implementation_digest() != CORE:
        raise RuntimeError("wrong frozen source integration runtime")
    level = "level_main_01-11"; package_path = OUT/(level+".partial.json")
    package = build(level)
    if package_path.read_bytes() != encoded(package): raise ValueError("generated stage input drift")
    before = {path: sha(ROOT/path) for path in package["manifest"]["metadata"]["source_locks"]}
    program = Compiler().compile(package); sim = Engine.create(program)
    sim.advance(95); checkpoint = sim.checkpoint(); sim.advance(710)
    desired = sim.snapshot(); events = tuple(sim.session.events)
    restored = Engine.restore(program, checkpoint); restored.advance(710)
    assert first_difference(desired, restored.snapshot()) is None
    assert first_difference(events, tuple(restored.session.events)) is None
    replayed = replay(program, sim.export_replay())
    assert first_difference(desired, replayed.snapshot()) is None
    assert first_difference(events, tuple(replayed.session.events)) is None
    births = [thaw(e) for e in events if e["type"] == "entity.created"]
    observations = [{"time": e["time"], "definition": e["payload"]["definition"], "actor": e["payload"]["target"]} for e in births]
    assert [(e["time"], e["definition"]) for e in observations] == [
        (90, "unit/chapter01_w"), (90, "unit/ch1_predefined_adnach_e0_l20"), (780, "unit/enemy_1000_gopro_2")]
    completed = [{"time": e["time"], "definition": e["payload"]["definition"]} for e in events if e["type"] == "control.completed"]
    assert {"time": 630, "definition": "control/chapter01/main_01-11_b"} in completed
    assert sim.ctx.state()["pending_waves"] == 43
    assert not sim.ctx.state().get("input_locks")
    assert all(sha(ROOT/path) == digest for path, digest in before.items())
    assert implementation_digest() == CORE
    report = {"schema": "ark-sim/chapter01-stage-prefix/v1", "passed": True, "whole_stage": False,
        "formal_stage_approved": False, "client_verified": False, "stage": level, "end_tick": 805,
        "runtime_module": str(Path(ark_sim.__file__).resolve()), "implementation": CORE,
        "package_sha256": sha(package_path), "source_locks": before,
        "helper_sha256": sha(Path(__file__)), "builder_sha256": sha(ROOT/"tools/build_chapter01_stage_models.py"),
        "test_source_sha256": sha(Path(__file__).with_name("test_stage_composition.py")),
        "births": observations, "controls_completed": completed, "pending_waves": 43,
        "checkpoint_split": 95, "checkpoint_equal": True, "replay_equal": True, "event_count": len(events),
        "events_sha256": hashlib.sha256(encoded(thaw(events))).hexdigest(),
        "pending_model_gaps": package["manifest"]["metadata"]["pending_model_gaps"]}
    output = ROOT/"validation/campaign/chapter01_stage_01_11_prefix_20261002.json"
    output.write_bytes(encoded(report))
    print(json.dumps({k: report[k] for k in ("passed", "whole_stage", "end_tick", "births", "checkpoint_equal", "replay_equal", "event_count")}))


if __name__ == "__main__": main()
