import pytest
from tools.witness_canonical_night import CASES,h


@pytest.mark.parametrize('case',list(CASES))
def test_canonical_mechanism(case):
    h.run_case(case,CASES[case])
