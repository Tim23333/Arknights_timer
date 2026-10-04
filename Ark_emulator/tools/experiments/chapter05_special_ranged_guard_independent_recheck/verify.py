import sys,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate';OUT=ROOT/'validation/campaign/chapter05_special_ranged_guard_independent_recheck';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import ark_sim,pytest
PIN='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 roots={'source':(RUNTIME/'ark_sim','*.py'),'catalog':(RUNTIME/'ark_sim','*.json'),'peer':(Path(__file__).parent,'*.py')}
 g={name:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern)) if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()};g['consumed']={str(ROOT/p):sha(ROOT/p) for p in ['tools/campaign_ordered_checkpoint.py','tools/chapter05/build_special_units.py','packages/campaign/chapter05_sources/native.reference.json','packages/campaign/chapter05_units/special/model.ranged_guard.reference.json']};return g
before=guard();assert implementation_digest()==PIN;subprocess.run([sys.executable,str(ROOT/'tools/chapter05/build_special_units.py'),'--check'],check=True,capture_output=True,text=True);cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_peer.py')),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
after=guard();assert before==after and implementation_digest()==PIN;m=next(m for n,m in sys.modules.items() if n.endswith('chapter05_special_ranged_guard_independent_recheck.test_peer'))
OUT.mkdir(parents=True,exist_ok=True);target=OUT/'verification.json'
with target.open('x',encoding='utf8') as f:json.dump({'role':'Independent ch5 exact special source consumers','core_start':PIN,'core_end':implementation_digest(),'guards_equal':True,'module_byte_check_passed':True,'start_manifest':before,'end_manifest':after,'cases':cases,'actual_inputs':m.INPUTS,'full_captures':m.CAPTURES,'limits':'Two exact variants only; attack-SP accepted damage/on-success Buff and native timing/body are declared policies, no full stage/client acceptance'},f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed'],'sha256':sha(target)}));sys.exit(code)
