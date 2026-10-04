import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m67_connectivity_snapshot_candidate';sys.path.insert(0,str(RUNTIME));import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import pytest,test_m67_completed as t
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();files=[Path(__file__),Path(t.__file__),ROOT/'tools/campaign_ordered_checkpoint.py',RUNTIME/'ark_sim/rules/contracts.json'];start={str(p):sha(p) for p in files};core=implementation_digest();assert core=='138cf9a4927f20162b207d07cb34441a41aabe887e0a06630fcd36cef9a6a07b';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'passed':call.excinfo is None})
code=pytest.main(['-q',str(Path(t.__file__))],plugins=[Results()]);end={str(p):sha(p) for p in files};last=implementation_digest();out=ROOT/'validation/campaign/m67_roster_peer';out.mkdir(parents=True,exist_ok=True);r={'passed':code==0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'actual_inputs':t.INPUTS,'fixtures':t.CAPTURES,'scope':'independent connectivity review, candidate may be unsealed; no promotion/stage receipt'};(out/'completed_review.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':r['passed'],'cases':len(cases),'core':core,'stable':core==last and start==end,'sha256':sha(out/'completed_review.json')}));raise SystemExit(0 if r['passed'] else 1)
