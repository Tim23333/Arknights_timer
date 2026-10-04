import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_selection_settle_v5_candidate';OUT=ROOT/'validation/campaign/selection_settle_v5_fresh_independent_peer';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import pytest
PIN='6350e435fe690aa0bf03e4df7d41864c6e031d4b2c2818dbfeb1d75c5e46db26';old=['tools/experiments/selection_settle_independent_peer_v2/test_peer.py','tools/experiments/selection_settle_independent_peer_v2/test_boundary.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 paths=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]+list(Path(__file__).parent.glob('*.py'))+[ROOT/p for p in old+['tools/campaign_ordered_checkpoint.py','packages/campaign/chapter05_units/special/model.selection_settle.reference.json','packages/campaign/chapter05_sources/native.reference.json']];return {str(p):sha(p) for p in paths}
before=guard();assert implementation_digest()==PIN;cases=[]
class Capture:
 def pytest_runtest_logreport(self,report):
  if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main(old+[str(Path(__file__).with_name('test_fresh.py')),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
after=guard();assert before==after and implementation_digest()==PIN;mods=[m for n,m in sys.modules.items() if n.endswith('selection_settle_independent_peer_v2.test_peer') or n.endswith('selection_settle_independent_peer_v2.test_boundary') or n.endswith('selection_settle_v5_fresh_independent_peer.test_fresh')];OUT.mkdir(parents=True,exist_ok=True);target=OUT/'verification.json'
with target.open('x',encoding='utf8') as f:json.dump({'role':'Independent selection settle original15 plus3 fresh state/control/sequence cases','core_start':PIN,'core_end':implementation_digest(),'guards_equal':True,'guard_before':before,'guard_after':after,'cases':cases,'actual_inputs':[p for m in mods for p in m.INPUTS],'captures':[p for m in mods for p in m.CAPTURES],'limits':'Query settlement mechanism/source special consumers only; originalfailed89d8 receipt unchanged, no full stage/client acceptance'},f,ensure_ascii=False,indent=2)
print(json.dumps({'exit':code,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed'],'sha256':sha(target)}));sys.exit(code)
