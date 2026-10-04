import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_faust_complete_v3_candidate';OUT=ROOT/'validation/campaign/faust_complete_v3_independent_peer';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import ark_sim,pytest
PIN='c6cdbc1754634628913d2e3419fd9eb5ea13f3569fe4d70c14ca20c8147c9a6f'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 roots={'source':(RUNTIME/'ark_sim','*.py'),'catalog':(RUNTIME/'ark_sim','*.json'),'peer':(Path(__file__).parent,'*.py')}
 g={name:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern)) if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()};paths=['tools/campaign_ordered_checkpoint.py','packages/campaign/chapter05_boss/faust/complete.v2.reference.json','packages/campaign/chapter05_boss/faust/combat.v4.reference.json','packages/campaign/chapter05_boss/faust/source.audit.json','packages/campaign/chapter05_boss/faust/branch.reference.json','packages/campaign/chapter05_sources/native.reference.json','packages/campaign/chapter05_plans/source.plan.json','validation/campaign/faust_complete_v1/freeze_v3.json'];g['consumed']={str(ROOT/p):sha(ROOT/p) for p in paths};return g
before=guard();assert implementation_digest()==PIN;cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_peer.py')),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
after=guard();assert before==after and implementation_digest()==PIN;m=next(m for n,m in sys.modules.items() if n.endswith('faust_complete_v3_independent_peer.test_peer'))
OUT.mkdir(parents=True,exist_ok=True);target=OUT/'verification.json'
with target.open('x',encoding='utf8') as f:json.dump({'role':'Independent Faust latest combined source/controller peer','core_start':PIN,'core_end':implementation_digest(),'guards_equal':True,'start_manifest':before,'end_manifest':after,'cases':cases,'actual_inputs':m.INPUTS,'full_captures':m.CAPTURES,'limits':'Existing dormant registration probes do not implement ballista shots; explicit shared-clock/CD/target policies/native body alignment/full5-10 remain separate'},f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed'],'sha256':sha(target)}));sys.exit(code)
