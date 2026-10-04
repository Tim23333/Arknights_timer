import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_faust_complete_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
PIN='1b7f95a9a5436e95a052f361f4fc388805fa5ce519913192d87e975616a2aa1b';assert implementation_digest()==PIN
cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_complete.py')),'-q','--tb=short'],plugins=[Capture()]))
assert implementation_digest()==PIN;target=ROOT/'validation/campaign/faust_complete_v1/author_content_v2.json'
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'cases':cases,'full_stage_executed':False},f,indent=2)
print(json.dumps({'sha':hashlib.sha256(target.read_bytes()).hexdigest()}));raise SystemExit(code)
