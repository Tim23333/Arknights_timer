import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m41_hole_contact_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import ark_sim,pytest,test_peer
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=[Path(__file__),Path(test_peer.__file__),ROOT/'packages/campaign/chapter02_tiles/m41.hole.profile.json',ROOT/'packages/campaign/chapter02_units/airdrp.birth_contact.model.json',ROOT/'packages/campaign/chapter02_tiles/source.reference.json',ROOT/'packages/campaign/chapter02_sources/native.reference.json',ROOT/'tools/campaign_ordered_checkpoint.py']
start={str(p):sha(p) for p in paths};core=implementation_digest();assert core=='43cdc7a22226ed71c8743976254048e6d4fd2258fff6668f06eb2966e78fe9d3';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',str(Path(test_peer.__file__))],plugins=[Results()]);end={str(p):sha(p) for p in paths};last=implementation_digest()
report={'passed':code==0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'fixtures':test_peer.INPUTS,'scope':'independent contact environment settlement, two source-backed born variants, public commands CP/durable/replay, instrumented failed retirement rollback','client_verified':False,'formal_approved':False}
out=ROOT/'validation/campaign/m41_peer/review.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':len(cases),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
