import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_faust_complete_v3_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))
import pytest
from ark_sim.adapters.api import implementation_digest
PIN='c6cdbc1754634628913d2e3419fd9eb5ea13f3569fe4d70c14ca20c8147c9a6f';assert implementation_digest()==PIN
cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
tests=['tools/experiments/faust_complete_v1/test_complete.py','tools/experiments/block_status_v1/test_policy.py',
       'tools/experiments/branch_program_v1/test_branches.py','tools/experiments/branch_program_v1/test_faust_source.py',
       'tests_v2/test_buff_mode_lifecycle.py','tests_v2/test_spatial.py','tools/experiments/chapter05_special/test_units.py']
code=int(pytest.main([*[str(ROOT/p) for p in tests],'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
assert implementation_digest()==PIN;target=ROOT/'validation/campaign/faust_complete_v1/components_v3.json'
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'cases':cases,'full_stage_executed':False},f,indent=2)
print(json.dumps({'sha':hashlib.sha256(target.read_bytes()).hexdigest()}));raise SystemExit(code)
