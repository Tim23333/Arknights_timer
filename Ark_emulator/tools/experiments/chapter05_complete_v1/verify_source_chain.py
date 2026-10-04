import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));import pytest
from ark_sim.adapters.api import implementation_digest
PIN='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525';assert implementation_digest()==PIN
paths=[ROOT/'packages/campaign/chapter05_stage_models/combined_v3/level_main_05-10.life99999.json',Path(__file__).with_name('test_source_chain.py')]
guards={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_source_chain.py')),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
assert implementation_digest()==PIN and guards=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
module=next(m for n,m in sys.modules.items() if n.endswith('chapter05_complete_v1.test_source_chain'))
out=ROOT/'validation/campaign/chapter05_complete_v1/source_chain_disk_v3.json'
with out.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'guards':guards,'cases':cases,'captures':module.CAPTURES,'full_stage_executed':False},f,indent=2)
print(json.dumps({'sha':hashlib.sha256(out.read_bytes()).hexdigest()}));raise SystemExit(code)
