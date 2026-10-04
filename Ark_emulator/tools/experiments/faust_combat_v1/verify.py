import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_block_status_v2_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
PIN='c3ddfc98e173f7135567ac17e45f75801a02e92ad1d2b478c83fdc97531027ea';assert implementation_digest()==PIN
cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_combat.py')),'-q','--tb=short'],plugins=[Capture()]))
assert implementation_digest()==PIN;target=ROOT/'validation/campaign/faust_combat_v1/author_v3.json';target.parent.mkdir(parents=True,exist_ok=True)
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'cases':cases,'full_stage_executed':False},f,indent=2)
print(json.dumps({'sha':hashlib.sha256(target.read_bytes()).hexdigest()}));raise SystemExit(code)
