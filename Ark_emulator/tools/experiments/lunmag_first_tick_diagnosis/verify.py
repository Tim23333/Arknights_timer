import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate';OUT=ROOT/'validation/campaign/lunmag_first_tick_diagnosis';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import pytest
PIN='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 paths=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]+list(Path(__file__).parent.glob('*.py'))+[ROOT/p for p in ['tools/experiments/chapter05_special_ranged_guard_independent_recheck/test_peer.py','packages/campaign/chapter05_units/special/model.ranged_guard.reference.json','packages/campaign/chapter05_sources/native.reference.json']];return {str(p):sha(p) for p in paths}
before=guard();assert implementation_digest()==PIN;cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_peer.py')),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
after=guard();assert before==after and implementation_digest()==PIN;m=next(m for n,m in sys.modules.items() if n.endswith('lunmag_first_tick_diagnosis.test_peer'));OUT.mkdir(parents=True,exist_ok=True);target=OUT/'verification.json'
with target.open('x',encoding='utf8') as f:json.dump({'role':'Known first-tick source2 error causal diagnosis, not source acceptance','core':PIN,'guards_equal':True,'guard_before':before,'guard_after':after,'cases':cases,'actual_inputs':m.INPUTS,'captures':m.CAPTURES,'known_bug_remains':True,'conclusion':'Unrelated target captured at time0 before movement creates blocker; captured target persists until hit. One pre-query blocking settle fixes eligibility without changing source values.'},f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'sha256':sha(target),'cases':len(cases)}));sys.exit(code)
