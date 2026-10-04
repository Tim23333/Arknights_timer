"""Execute unchanged independent v7 expectations against the repaired v8 core."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_tile_targets_v8_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import pytest
PIN='99a7aeff1cfe91806b1c0cf283e138fce75a5150d821535976072e4dd3080074'
TEST=ROOT/'tools/experiments/tile_targets_v7_independent_peer/test_peer.py'
original=hashlib.sha256(TEST.read_bytes()).hexdigest();assert implementation_digest()==PIN;cases=[]
class Reports:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(TEST),'-q','--tb=short','--import-mode=importlib'],plugins=[Reports()]))
assert implementation_digest()==PIN and original==hashlib.sha256(TEST.read_bytes()).hexdigest()
target=ROOT/'validation/campaign/tile_targets_v1/independent_cases_recheck_v8.json'
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'independent_test_sha':original,'cases':cases,'old_v7_failure_preserved':True},f,indent=2)
print(json.dumps({'report_sha':hashlib.sha256(target.read_bytes()).hexdigest()}));raise SystemExit(code)
