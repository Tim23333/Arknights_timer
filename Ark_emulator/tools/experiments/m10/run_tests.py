"""Run only isolated M10 tests with demonstrable candidate import priority."""
from pathlib import Path
import sys
PRIMARY = Path(__file__).resolve().parents[3]
CANDIDATE = PRIMARY.parent/"unpack_work/campaign_m10_cast_freeze_candidate"
sys.path.insert(0, str(CANDIDATE)); sys.path.insert(1, str(PRIMARY)); sys.path.insert(2, str(PRIMARY/"tests_v2"))
import ark_sim
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().is_relative_to(CANDIDATE.resolve())
if __name__ == "__main__":
    import pytest
    print("M10 candidate:", ark_sim.__file__, implementation_digest(), flush=True)
    raise SystemExit(pytest.main([*(sys.argv[1:] or ["tools/experiments/m10/tests"]), "-q", "--tb=short"]))
