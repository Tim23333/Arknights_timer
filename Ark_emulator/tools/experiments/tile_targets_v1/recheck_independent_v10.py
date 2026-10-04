import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_tile_targets_v10_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import pytest
PIN='2eeca1dc0a9a02f2ba42aed2285d0ea89062029de8e2c58506c30e41472462cb'
tests=[ROOT/'tools/experiments/tile_targets_v7_independent_peer/test_peer.py',ROOT/'tools/experiments/tile_targets_v8_independent_peer_v2/test_peer.py']
guards={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in tests};assert implementation_digest()==PIN;cases=[]
class Reports:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([*[str(p) for p in tests],'-q','--tb=short','--import-mode=importlib'],plugins=[Reports()]))
assert implementation_digest()==PIN and guards=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in tests}
target=ROOT/'validation/campaign/tile_targets_v1/independent_cases_recheck_v10.json'
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'independent_test_sha':guards,'cases':cases,'old_failures_preserved':True},f,indent=2)
print(json.dumps({'report_sha':hashlib.sha256(target.read_bytes()).hexdigest()}));raise SystemExit(code)
