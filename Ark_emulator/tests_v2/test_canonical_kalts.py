import pytest
from tools.witness_canonical_kalts import CASES,h


@pytest.mark.parametrize('case',list(CASES))
def test_canonical_mechanism(case):
    h.run_case(case,CASES[case])
