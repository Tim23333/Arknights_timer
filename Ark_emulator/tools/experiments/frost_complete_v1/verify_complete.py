import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
PIN='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90';assert implementation_digest()==PIN
cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_complete.py')),'-q','--tb=short'],plugins=[Capture()]))
assert implementation_digest()==PIN;target=ROOT/'validation/campaign/frost_complete_v1/complete_v5.json'
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'catalog_sha':hashlib.sha256((RUNTIME/'ark_sim/rules/contracts.json').read_bytes()).hexdigest(),'exitcode':code,'cases':cases,'full_stage_executed':False},f,indent=2)
print(json.dumps({'report_sha':hashlib.sha256(target.read_bytes()).hexdigest()}));raise SystemExit(code)
