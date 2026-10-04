import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate';OUT=ROOT/'validation/campaign/tile_targets_v10_independent_recheck';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import ark_sim,pytest
PIN='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90'
tests=['tools/experiments/tile_targets_v7_independent_peer/test_peer.py','tools/experiments/tile_targets_v8_independent_peer_v2/test_peer.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 roots={'source':(RUNTIME/'ark_sim','*.py'),'catalog':(RUNTIME/'ark_sim','*.json'),'helper':(Path(__file__).parent,'*.py')}
 g={name:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern)) if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()}
 g['consumed']={str(ROOT/p):sha(ROOT/p) for p in tests+['tools/campaign_ordered_checkpoint.py','packages/campaign/chapter04_boss/ice_shield_v3/module.reference.json']};return g
before=guard();assert implementation_digest()==PIN;cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main(tests+['-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
after=guard();assert before==after and implementation_digest()==PIN;mods=[m for n,m in sys.modules.items() if n.endswith('tile_targets_v7_independent_peer.test_peer') or n.endswith('tile_targets_v8_independent_peer_v2.test_peer')]
actual={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('ark_sim') and getattr(m,'__file__',None)};assert all(Path(p).is_relative_to(RUNTIME/'ark_sim') for p in actual.values())
OUT.mkdir(parents=True,exist_ok=True);target=OUT/'verification.json'
with target.open('x',encoding='utf8') as f:json.dump({'role':'Independent unchanged tile16 assertions on repaired complete v5, not rewriting old failure receipts','core_start':PIN,'core_end':implementation_digest(),'guards_equal':True,'start_manifest':before,'end_manifest':after,'cases':cases,'actual_inputs':[p for m in mods for p in m.INPUTS],'full_captures':[p for m in mods for p in m.CAPTURES],'actual_modules':actual,'limits':'Original negative expectations preserved; no complete stage/client acceptance'},f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed'],'sha256':sha(target)}));sys.exit(code)
