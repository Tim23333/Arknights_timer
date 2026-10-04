"""Independent canonical expected values; fixture never replaces native abilities."""
import pytest
from tools.witness_canonical_roster_trio import CASES,run_case


@pytest.mark.parametrize('case',list(CASES))
def test_canonical_mechanism(case):
    run_case(case)
