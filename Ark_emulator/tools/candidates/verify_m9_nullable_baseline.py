"""Fresh 0-1 model evidence using candidate code and primary content files."""
import hashlib
from pathlib import Path
import sys

PRIMARY = Path(__file__).resolve().parents[2]
CANDIDATE = PRIMARY.parent/"unpack_work/campaign_m9_candidate"
OUTPUT = PRIMARY/"docs/campaign/candidates/m9_nullable_baseline_20261002.json"
sys.path.insert(0, str(CANDIDATE))
sys.path.insert(1, str(PRIMARY))
import ark_sim
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().is_relative_to(CANDIDATE.resolve())
from tools import verify_v2_baseline as baseline
# Its ROOT is intentionally primary for content; its imported runtime must stay candidate.
sys.path.remove(str(CANDIDATE)); sys.path.insert(0, str(CANDIDATE))
for name, module in list(sys.modules.items()):
    if name == "ark_sim" or name.startswith("ark_sim."):
        if getattr(module, "__file__", None): assert Path(module.__file__).resolve().is_relative_to(CANDIDATE.resolve())


if __name__ == "__main__":
    report = {"schema": "ark-sim/candidate-nullable-baseline/v1", "date": "2026-10-02", "passed": False,
        "scope": "Fresh candidate 0-1 model/cp/replay; not a client/formal mainline receipt",
        "candidate_module_path": str(Path(ark_sim.__file__).resolve()), "implementation_digest": implementation_digest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    print("candidate:", report["candidate_module_path"], report["implementation_digest"], flush=True)
    try:
        baseline.check_custom(report)
        baseline.check_level(report, OUTPUT, 4500, 300)
        if implementation_digest() != report["implementation_digest"]:
            raise RuntimeError("candidate code changed during baseline execution")
        report["passed"] = True
    except Exception as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        baseline.write(OUTPUT, report)
        raise
    baseline.write(OUTPUT, report)
    print("fresh candidate baseline saved:", OUTPUT, flush=True)
