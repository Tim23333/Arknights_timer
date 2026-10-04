import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_ballista_directional_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));import pytest
from ark_sim.adapters.api import implementation_digest
PIN='49af646affbd800b2d65a25634700deb1444fcbc3e0d886516ad9509edab217b';assert implementation_digest()==PIN
paths=[ROOT/'packages/campaign/chapter05_predefines/runtime_ballista/module.v2.reference.json',ROOT/'packages/campaign/chapter05_predefines/source.reference.json',Path(__file__).with_name('test_peer.py')]
guards={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_peer.py')),'-q','--tb=short'],plugins=[Capture()]))
assert implementation_digest()==PIN and guards=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
out=ROOT/'validation/campaign/ballista_root_peer/initial.json';out.parent.mkdir(parents=True,exist_ok=True)
with out.open('x',encoding='utf8') as f:json.dump({'role':'Root independent ballista source consumer checks','core':PIN,'exitcode':code,'guards':guards,'cases':cases,'full_stage_executed':False},f,indent=2)
print(json.dumps({'sha':hashlib.sha256(out.read_bytes()).hexdigest()}));raise SystemExit(code)
