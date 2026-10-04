import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m45_aura_reentry_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import ark_sim,pytest,test_peer
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=[Path(__file__),Path(test_peer.__file__),ROOT/'tools/campaign_ordered_checkpoint.py',RUNTIME/'ark_sim/rules/contracts.json'];start={str(p):sha(p) for p in paths};core=implementation_digest();assert core=='181eb512eaa01234775ab6ebfdb7ada7f98cb6eea998093bc31a3cb412c39670';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',str(Path(test_peer.__file__))],plugins=[Results()]);end={str(p):sha(p) for p in paths};last=implementation_digest();out=ROOT/'validation/campaign/m45_roster_peer/review.json';out.parent.mkdir(parents=True,exist_ok=True);report={'passed':code==0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'fixtures':test_peer.INPUTS,'scope':'independent samecast retire90/other source83/remote actual source, durable public commands, API failure retry and random draw budget','formal_approved':False};out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':len(cases),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
