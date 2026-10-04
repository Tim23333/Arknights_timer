import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_branch_program_v5_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
PIN='9eaa953a43ec2ab2fd5fbd8b874c7f4dcd83474df577c110fc3bee5a5ac0eb34';assert implementation_digest()==PIN
cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_branches.py')),str(Path(__file__).with_name('test_faust_source.py')),'-q','--tb=short'],plugins=[Capture()]))
assert implementation_digest()==PIN;target=ROOT/'validation/campaign/branch_program_v1/author_v5_with_source.json'
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'cases':cases,'full_stage_executed':False},f,indent=2)
print(json.dumps({'sha':hashlib.sha256(target.read_bytes()).hexdigest()}));raise SystemExit(code)
