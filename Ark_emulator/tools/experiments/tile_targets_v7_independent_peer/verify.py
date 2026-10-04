import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_tile_targets_v7_candidate';OUT=ROOT/'validation/campaign/tile_targets_v7_independent_peer';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import ark_sim,pytest
PIN='42014647b8d510c6394b98221c138a0bc27a8ccab3354d653a65fc2767fb3833'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 roots={'source':(RUNTIME/'ark_sim','*.py'),'catalog':(RUNTIME/'ark_sim','*.json'),'peer':(Path(__file__).parent,'*.py'),'author_tools':(ROOT/'tools/candidates/tile_targets_v1','*.py')}
 g={name:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern)) if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()}
 paths=[ROOT/p for p in ['tools/campaign_ordered_checkpoint.py','packages/campaign/chapter04_boss/ice_shield_v3/module.reference.json','packages/campaign/chapter04_boss_plan/source.reference.json']];g['consumed']={str(p):sha(p) for p in paths};return g
before=guard();assert implementation_digest()==PIN;cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_peer.py')),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
after=guard();assert before==after and implementation_digest()==PIN;m=next(m for n,m in sys.modules.items() if n.endswith('tile_targets_v7_independent_peer.test_peer'))
OUT.mkdir(parents=True,exist_ok=True);target=OUT/'verification.json'
with target.open('x',encoding='utf8') as f:json.dump({'role':'Independent tile v7 adversarial peer','core_start':PIN,'core_end':implementation_digest(),'guards_equal':True,'start_manifest':before,'end_manifest':after,'cases':cases,'actual_inputs':m.INPUTS,'full_captures':m.CAPTURES,'limits':'Generic tile runtime only; IceShield source490b audit preserved, no priority/integrated timing/stage/client acceptance'},f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed'],'sha256':sha(target)}));sys.exit(code)
