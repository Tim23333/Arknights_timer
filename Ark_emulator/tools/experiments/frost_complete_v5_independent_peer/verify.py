import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate';OUT=ROOT/'validation/campaign/frost_complete_v5_independent_peer';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import ark_sim,pytest
PIN='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 roots={'source':(RUNTIME/'ark_sim','*.py'),'catalog':(RUNTIME/'ark_sim','*.json'),'peer':(Path(__file__).parent,'*.py')}
 g={name:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern)) if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()}
 paths=[ROOT/p for p in ['tools/campaign_ordered_checkpoint.py','packages/campaign/chapter04_boss/frost_complete_v1/module.reference.json','packages/campaign/chapter04_boss/frost_combat_v6/first17.bb8.reference_ground.json','packages/campaign/chapter04_boss/ice_shield_v3/module.reference.json','packages/campaign/chapter04_boss/m86/rebirth_immunity.reference_model.json','packages/campaign/chapter04_boss/frost_combat_v1/source.audit.json','packages/campaign/chapter04_boss_plan/source.reference.json','packages/campaign/chapter04_sources/native.reference.json','validation/campaign/frost_complete_v1/freeze_v4.json']];g['consumed']={str(p):sha(p) for p in paths};return g
before=guard();assert implementation_digest()==PIN;cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_peer.py')),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
after=guard();assert before==after and implementation_digest()==PIN;m=next(m for n,m in sys.modules.items() if n.endswith('frost_complete_v5_independent_peer.test_peer'));actual={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('ark_sim') and getattr(m,'__file__',None)};assert all(Path(p).is_relative_to(RUNTIME/'ark_sim') for p in actual.values())
OUT.mkdir(parents=True,exist_ok=True);target=OUT/'verification.json'
with target.open('x',encoding='utf8') as f:json.dump({'role':'Independent combined Frost source/control/ownership peer','core_start':PIN,'core_end':implementation_digest(),'guards_equal':True,'start_manifest':before,'end_manifest':after,'cases':cases,'actual_inputs':m.INPUTS,'full_captures':m.CAPTURES,'actual_modules':actual,'limits':'Controlled scenarios with real frozen source consumers; normal17/Blastzero-flight/8s/ground/priority2>1/shared111 remain declared reference profiles, not native-body or full4-10/client acceptance'},f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed'],'sha256':sha(target)}));sys.exit(code)
