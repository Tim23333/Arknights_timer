import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate';OUT=ROOT/'validation/campaign/m94_independent_boundary_peer_v2'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import ark_sim,pytest
PIN='cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 roots={'core':(RUNTIME/'ark_sim','*.py'),'catalog_json':(RUNTIME/'ark_sim','*.json'),'peer':(Path(__file__).parent,'*')}
 g={name:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern)) if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()}
 paths=[ROOT/p for p in ['packages/campaign/chapter04_boss/m86/rebirth_immunity.reference_model.json','packages/campaign/chapter04_boss/m61/rebirth.reference_model.json','packages/campaign/chapter04_boss/m70/immunity.reference_model.json','packages/campaign/chapter04_sources/native.reference.json','packages/campaign/chapter04_dmage/source.reference.json','packages/campaign/chapter04_dmage/module.combat_guard.reference.json','packages/campaign/skills.chen.json','tools/campaign_ordered_checkpoint.py','tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py','tools/build_chapter04_dmage_combat_guard.py','tools/candidates/m94_verification_launch/freeze_core.py','tools/experiments/m94_independent_cross_peer/test_cross.py']]
 g['consumed']={str(p):sha(p) for p in paths};return g
before=guard();assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_boundary.py')),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
after=guard();assert before==after and implementation_digest()==PIN
m=next(m for n,m in sys.modules.items() if n.endswith('m94_independent_boundary_peer_v2.test_boundary'));actual={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('ark_sim') and getattr(m,'__file__',None)};assert all(Path(p).is_relative_to(RUNTIME/'ark_sim') for p in actual.values())
OUT.mkdir(parents=True,exist_ok=True);target=OUT/'verification.json'
with target.open('x',encoding='utf8') as f:json.dump({'role':'Independent M94 cross-module peer; M93 author does not self-accept M93','core_start':PIN,'core_end':implementation_digest(),'guards_equal':True,'start_manifest':before,'end_manifest':after,'cases':cases,'actual_inputs':m.INPUTS,'full_captures':m.CAPTURES,'actual_modules':actual,'limits':'Fresh synthetic drivers consume frozen source modules; no full stage/client acceptance'},f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed'],'report_sha256':sha(target)}));sys.exit(code)
