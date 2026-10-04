import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_frost_complete_v2_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))
import pytest
from ark_sim.adapters.api import implementation_digest
PIN='a115e421da1a551bf76aa1a7cfa013f2efd51a60b8c1685e8353675327acd95c';assert implementation_digest()==PIN
tests=['tools/experiments/tile_targets_v1/test_tile_targets.py','tools/experiments/tile_targets_v7_independent_peer/test_peer.py',
       'tools/experiments/ability_arbitration_v1/test_arbitration.py','tools/experiments/frost_combat_v6/test_combat.py',
       'tools/experiments/frost_combat_root_peer/test_peer.py']
guards={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in tests};cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([*[str(ROOT/p) for p in tests],'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
assert implementation_digest()==PIN and guards=={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in tests}
target=ROOT/'validation/campaign/frost_complete_v1/components.json'
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'cases':cases,'test_sources':guards,'full_stage_executed':False},f,indent=2)
print(json.dumps({'report_sha':hashlib.sha256(target.read_bytes()).hexdigest()}));raise SystemExit(code)
