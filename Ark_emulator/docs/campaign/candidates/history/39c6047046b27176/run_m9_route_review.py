"""Candidate-only pytest entry; asserts loaded runtime origins before collecting."""
from pathlib import Path
import sys

PRIMARY = Path(__file__).resolve().parents[2]
CANDIDATE = PRIMARY.parent/"unpack_work/campaign_m9_candidate"
sys.path.insert(0, str(CANDIDATE))
sys.path.insert(1, str(PRIMARY/"tests_v2"))
sys.path.insert(2, str(PRIMARY))
import ark_sim
assert Path(ark_sim.__file__).resolve().is_relative_to(CANDIDATE.resolve())
from ark_sim.adapters.api import implementation_digest

if __name__ == "__main__":
    print("candidate_runtime:", ark_sim.__file__, "digest:", implementation_digest())
    import pytest
    requested = sys.argv[1:] or ["tools/candidates/test_m9_routes.py"]
    raise SystemExit(pytest.main([*requested, "-q", "--tb=short"]))
