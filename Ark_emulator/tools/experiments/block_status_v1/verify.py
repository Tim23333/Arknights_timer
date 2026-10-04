import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_block_status_v5_candidate'));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
PIN='635526ee6d6a0e0124ef2ab439fa4729c1caf28dc184bb62936d55b6f58e6baf';assert implementation_digest()==PIN
cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_policy.py')),'-q','--tb=short'],plugins=[Capture()]))
target=ROOT/'validation/campaign/block_status_v1/author_policy_v5.json'
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'cases':cases},f,indent=2)
raise SystemExit(code)
