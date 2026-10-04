import sys,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_frost_combat_v4_candidate';OUT=ROOT/'validation/campaign/frost_combat_v2'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import ark_sim,pytest
PIN='ba3a594e011760bfa6df1f566960e390043c6666b28944d3f46f4f94a575c3b6'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 roots={'source':(RUNTIME/'ark_sim','*.py'),'catalog':(RUNTIME/'ark_sim','*.json'),'parent':(ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate/ark_sim','*.py'),'tools':(ROOT/'tools/candidates/frost_combat_v1','*'),'experiments':(Path(__file__).parent,'*.py'),'models':(ROOT/'packages/campaign/chapter04_boss/frost_combat_v2','*.json')}
 g={name:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern)) if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()}
 paths=[ROOT/p for p in ['packages/campaign/chapter04_boss_plan/source.reference.json','packages/campaign/chapter04_sources/native.reference.json','packages/campaign/chapter04_boss/m86/rebirth_immunity.reference_model.json','tools/campaign_ordered_checkpoint.py','packages/campaign/chapter04_boss/frost_combat_v1/source.audit.json']];g['consumed']={str(p):sha(p) for p in paths};return g
before=guard();assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_combat.py')),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
after=guard();assert before==after and implementation_digest()==PIN
m=next(m for n,m in sys.modules.items() if n.endswith('frost_combat_v2.test_combat'));actual={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('ark_sim') and getattr(m,'__file__',None)};assert all(Path(p).is_relative_to(RUNTIME/'ark_sim') for p in actual.values())
target=OUT/'verification_initial.json'
with target.open('x',encoding='utf8') as f:json.dump({'role':'Frost partial source consumer author verification','core_start':PIN,'core_end':implementation_digest(),'guards_equal':True,'start_manifest':before,'end_manifest':after,'cases':cases,'actual_inputs':m.INPUTS,'full_captures':m.CAPTURES,'actual_modules':actual,'limits':['first17 normal packet is explicit reference policy, not native event body proof','Zero-flight frame28 blast is reference timing, raw .1s projectile retained in audit','IceShield tile query/RNG/token runtime missing; no whole 4-10 or client acceptance']},f,ensure_ascii=False,indent=2,allow_nan=True)
print(json.dumps({'exit':code,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed'],'report_sha':sha(target)}));sys.exit(code)
