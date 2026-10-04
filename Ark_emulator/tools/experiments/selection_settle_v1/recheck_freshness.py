"""Run all original independent expectations on the fresh-state repair."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_selection_settle_v5_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));import pytest
from ark_sim.adapters.api import implementation_digest
PIN='6350e435fe690aa0bf03e4df7d41864c6e031d4b2c2818dbfeb1d75c5e46db26';assert implementation_digest()==PIN
tests=[ROOT/'tools/experiments/selection_settle_independent_peer_v2/test_peer.py',ROOT/'tools/experiments/selection_settle_independent_peer_v2/test_boundary.py']
guards={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in tests};cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([*[str(p) for p in tests],'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
assert implementation_digest()==PIN and guards=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in tests}
out=ROOT/'validation/campaign/selection_settle_v1/freshness_recheck_v5.json'
with out.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'guards':guards,'cases':cases,'all_independent_assertions_unchanged':True,'full_stage_executed':False},f,indent=2)
print(json.dumps({'sha':hashlib.sha256(out.read_bytes()).hexdigest()}));raise SystemExit(code)
