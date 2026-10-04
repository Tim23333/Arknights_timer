import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));import pytest
paths=[ROOT/'tools/build_reference_stage_scenario_v3.py',ROOT/'tools/build_reference_stage_scenario_v2.py',ROOT/'packages/campaign/chapter05_plans/source.plan.json']
guards={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_adapter.py')),'-q','--tb=short'],plugins=[Capture()]))
assert guards=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
out=ROOT/'validation/campaign/chapter05_predefine_adapter/initial.json';out.parent.mkdir(parents=True,exist_ok=True)
with out.open('x',encoding='utf8') as f:json.dump({'exitcode':code,'cases':cases,'guards':guards,'runtime_or_full_stage_executed':False},f,indent=2)
print(json.dumps({'sha':hashlib.sha256(out.read_bytes()).hexdigest()}));raise SystemExit(code)
