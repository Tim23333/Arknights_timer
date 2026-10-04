import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_branch_program_v5_candidate';OUT=ROOT/'validation/campaign/branch_program_v5_facts_independent_peer';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import ark_sim,pytest
PIN='9eaa953a43ec2ab2fd5fbd8b874c7f4dcd83474df577c110fc3bee5a5ac0eb34'
old='tools/experiments/branch_program_v3_independent_peer_v2/test_peer.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 roots={'source':(RUNTIME/'ark_sim','*.py'),'catalog':(RUNTIME/'ark_sim','*.json'),'peer':(Path(__file__).parent,'*.py')}
 g={name:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern)) if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()};g['consumed']={str(ROOT/p):sha(ROOT/p) for p in [old,'tools/campaign_ordered_checkpoint.py']};return g
before=guard();assert implementation_digest()==PIN;cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([old,str(Path(__file__).with_name('test_facts.py')),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
after=guard();assert before==after and implementation_digest()==PIN;mods=[m for n,m in sys.modules.items() if n.endswith('branch_program_v3_independent_peer_v2.test_peer') or n.endswith('branch_program_v5_facts_independent_peer.test_facts')]
OUT.mkdir(parents=True,exist_ok=True);target=OUT/'verification.json'
with target.open('x',encoding='utf8') as f:json.dump({'role':'Independent original13 branch assertions plus2 facts/gate cases','core_start':PIN,'core_end':implementation_digest(),'guards_equal':True,'start_manifest':before,'end_manifest':after,'cases':cases,'actual_inputs':[p for m in mods for p in m.INPUTS],'full_captures':[p for m in mods for p in m.CAPTURES],'limits':'Generic program facts and conditions only; Faust full branch/source/stage acceptance separate'},f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed'],'sha256':sha(target)}));sys.exit(code)
