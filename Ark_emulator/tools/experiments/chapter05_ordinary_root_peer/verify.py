import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
PIN='cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7';assert implementation_digest()==PIN
paths=[ROOT/'packages/campaign/chapter05_units/ordinary.reference_model.json',ROOT/'packages/campaign/chapter05_sources/native.reference.json',Path(__file__).with_name('test_peer.py')]
guards={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_peer.py')),'-q','--tb=short'],plugins=[Capture()]))
assert implementation_digest()==PIN and guards=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
target=ROOT/'validation/campaign/chapter05_ordinary_root_peer/complete_attributes.json';target.parent.mkdir(parents=True,exist_ok=True)
with target.open('x',encoding='utf8') as f:json.dump({'role':'Independent ordinary source consumer peer','core':PIN,'exitcode':code,'guards':guards,'cases':cases,'full_stage_executed':False},f,indent=2)
print(json.dumps({'sha':hashlib.sha256(target.read_bytes()).hexdigest()}));raise SystemExit(code)
