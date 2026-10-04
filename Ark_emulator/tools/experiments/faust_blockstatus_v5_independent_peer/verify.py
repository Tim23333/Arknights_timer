import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_block_status_v5_candidate';OUT=ROOT/'validation/campaign/faust_blockstatus_v5_independent_peer';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import ark_sim,pytest
PIN='635526ee6d6a0e0124ef2ab439fa4729c1caf28dc184bb62936d55b6f58e6baf'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 roots={'source':(RUNTIME/'ark_sim','*.py'),'catalog':(RUNTIME/'ark_sim','*.json'),'peer':(Path(__file__).parent,'*.py')}
 g={name:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern)) if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()}
 paths=['tools/campaign_ordered_checkpoint.py','packages/campaign/chapter05_boss/faust/combat.v4.reference.json','packages/campaign/chapter05_boss/faust/source.audit.json','packages/campaign/chapter05_sources/native.reference.json','tools/candidates/block_status_v1/block_status.py'];g['consumed']={str(ROOT/p):sha(ROOT/p) for p in paths};return g
before=guard();assert implementation_digest()==PIN;cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_peer.py')),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
after=guard();assert before==after and implementation_digest()==PIN;m=next(m for n,m in sys.modules.items() if n.endswith('faust_blockstatus_v5_independent_peer.test_peer'));actual={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('ark_sim') and getattr(m,'__file__',None)};assert all(Path(p).is_relative_to(RUNTIME/'ark_sim') for p in actual.values())
OUT.mkdir(parents=True,exist_ok=True);target=OUT/'verification.json'
with target.open('x',encoding='utf8') as f:json.dump({'role':'Independent Faust partial source and projected blocking v3 peer','core_start':PIN,'core_end':implementation_digest(),'guards_equal':True,'start_manifest':before,'end_manifest':after,'cases':cases,'actual_inputs':m.INPUTS,'full_captures':m.CAPTURES,'actual_modules':actual,'limits':'Sourcecombat partial only; selector hatred/criticalCD17 andshared5s/native projectile body are declared policies; branch+SummonBallis/fullstage/client acceptance not included'},f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed'],'sha256':sha(target)}));sys.exit(code)
