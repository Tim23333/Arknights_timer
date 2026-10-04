import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));import pytest
from ark_sim.adapters.api import implementation_digest
PIN='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90';assert implementation_digest()==PIN
paths=[ROOT/'packages/campaign/chapter05_units/special/model.ranged_guard.reference.json',ROOT/'packages/campaign/chapter05_sources/native.reference.json',Path(__file__).with_name('test_units.py')]
guards={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_units.py')),'-q','--tb=short'],plugins=[Capture()]))
assert implementation_digest()==PIN and guards=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};target=ROOT/'validation/campaign/chapter05_special/author_ranged_guard_bound.json';target.parent.mkdir(parents=True,exist_ok=True)
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'cases':cases,'guards':guards,'full_stage_executed':False},f,indent=2)
print(json.dumps({'sha':hashlib.sha256(target.read_bytes()).hexdigest()}));raise SystemExit(code)
