import pytest
from tools.witness_deployed_support import CASES,run_case


@pytest.mark.parametrize('case',list(CASES))
def test_canonical_extension(case):
    run_case(case)
