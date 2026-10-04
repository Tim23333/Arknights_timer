import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_ability_arbitration_v3_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
PIN='455de2ea24f042c445483b9c05df6c1e95421db496be385e034f99ec3f20f1ae'
assert implementation_digest()==PIN;cases=[]
class Reports:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_arbitration.py')),'-q','--tb=short'],plugins=[Reports()]))
assert implementation_digest()==PIN
target=ROOT/'validation/campaign/ability_arbitration_v1/author_v3_effective_inputs.json'
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'cases':cases,'full_stage_executed':False},f,indent=2)
print(json.dumps({'report_sha':hashlib.sha256(target.read_bytes()).hexdigest()}));raise SystemExit(code)
