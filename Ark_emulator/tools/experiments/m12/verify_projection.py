"""Read-only same-input M11/M12 comparison preserving original c0 evidence."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]


def run(root):
    sys.path.insert(0, str(root.resolve()))
    import ark_sim
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    actual = Path(ark_sim.__file__).resolve()
    if actual.parent != root.resolve() / "ark_sim": raise RuntimeError("wrong actual import")
    before = implementation_digest(); source = ROOT / "packages/campaign/mainline_models/level_main_00-10.m12_projection.json"
    records = []
    for start, target in [((4, 4), (4.5, 5)), ((4, 4), (5.5, 5)), ((4.5, 4), (5, 5)), ((5.5, 4), (6, 5))]:
        p = json.loads(source.read_bytes())
        p["scenarioDraft"].update(id="scenario/m12_projection_actual", map={"rows": 9, "cols": 12}, waves=[], scheduledEffects=[], objectives={},
            initialEntities=[{"definition": "unit/char_151_myrtle", "instanceAlias": "myrtle", "position": {"row": start[0], "col": start[1]}},
                {"definition": "unit/enemy_1000_gopro", "instanceAlias": "enemy", "position": {"row": target[0], "col": target[1]}}])
        s = Engine.create(Compiler().compile(p)); s.advance(16)
        expected_source = [math.floor(x+.5) for x in start]; expected_target = [math.floor(x+.5) for x in target]
        expected = expected_source[0] == expected_target[0] and expected_target[1] in (expected_source[1], expected_source[1]+1)
        records.append({"source": start, "target": target, "expected_source_cell": expected_source, "expected_target_cell": expected_target,
            "expected_in_standard_range": expected, "actual_attack_count": len([e for e in s.session.events if e["type"] == "attack.accepted"]),
            "program_fingerprint": s.program.fingerprint, "runtime_fingerprint": s.runtime_fingerprint})
    if implementation_digest() != before: raise RuntimeError("runtime source changed during probes")
    return {"schema": "ark-sim/m12-projection-comparison/v1", "actual_import": actual.as_posix(), "implementation_digest": before,
        "content_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "cases": records,
        "original_c0_evidence_sha256": hashlib.sha256((ROOT / "validation/campaign/c0_corner_projection.json").read_bytes()).hexdigest(),
        "native_comparator_verified": False, "full_stage_executed": False, "formal_approval": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--runtime-root", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(); value = run(args.runtime_root)
    args.output.write_text(json.dumps(value, indent=2)+"\n", encoding="utf8", newline="\n")
    print(json.dumps(value))
