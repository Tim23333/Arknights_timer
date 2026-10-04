"""Same legacy sync-effects input in explicitly selected M12/M13 roots."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]


def data():
    p = json.loads((ROOT / "tools/experiments/m11/capacity.fixture.json").read_bytes())
    p["scenarioDraft"]["initialEntities"] = p["scenarioDraft"]["initialEntities"][:2]
    p["scenarioDraft"]["waves"] = []
    p["scenarioDraft"]["timeline"] = {"policy": "time_only", "negative_timeout_policy": "skip_wait", "waves": [{"fragments": [{"actions": [
        {"kind": "effects", "delay_seconds": .1, "effects": [{"op": "emit", "target": "battle", "event": "legacy_sync"}]}]}]}]}
    return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--runtime-root", type=Path, required=True); ap.add_argument("--output", type=Path, required=True); args = ap.parse_args()
    sys.path.insert(0, str(args.runtime_root.resolve()))
    import ark_sim
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw
    assert Path(ark_sim.__file__).resolve().parent == args.runtime_root.resolve() / "ark_sim"
    before = implementation_digest(); s = Engine.create(Compiler().compile(data()), seed=1312); s.advance(20)
    assert not getattr(s.ctx, "controls", None) and "controls" not in s.ctx.state()
    assert not [e for e in s.session.events if e["type"].startswith("control.")]
    assert implementation_digest() == before
    r = {"actual_import": ark_sim.__file__, "implementation_digest": before, "program_fingerprint": s.program.fingerprint,
        "world": s.checkpoint()["kernel"]["world"], "random": s.checkpoint()["kernel"]["random"],
        "scheduler": s.checkpoint()["kernel"]["scheduler"], "events": [thaw(e) for e in s.session.events]}
    args.output.write_text(json.dumps(r, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps({"implementation_digest": before, "program_fingerprint": s.program.fingerprint, "events": len(r["events"])}))
