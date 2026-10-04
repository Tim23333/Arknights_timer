import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m55_route_obstacle_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import ark_sim,pytest,test_peer
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();paths=[Path(__file__),Path(test_peer.__file__),ROOT/'tools/campaign_ordered_checkpoint.py',RUNTIME/'ark_sim/rules/contracts.json'];start={str(p):sha(p) for p in paths};core=implementation_digest();assert core=='5c33c17ec6c7d7d1a1677e0df88176e594237e9d6485262e430c94dba86912ea';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',str(Path(test_peer.__file__))],plugins=[Results()]);p=test_peer.INPUTS[-1]['fixture'];s=Engine.create(Compiler().compile(p),seed=55019);test_peer.deploy(s);s.submit({'action':'skill','source':'barrier','ability':'ability/setup'},at=3);s.advance(13)
end={str(p):sha(p) for p in paths};last=implementation_digest();out=ROOT/'validation/campaign/m55_roster_peer/initial_failure.json';out.parent.mkdir(parents=True,exist_ok=True);r={'passed':False,'expected_counterexample_confirmed':code!=0 and start==end and core==last,'core_start':core,'core_end':last,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'fixture_inputs':test_peer.INPUTS,'counterexample':{'expected':'No relation may bind the obstacle after its legal synchronous retirement; same-pass stale obstacle snapshot must not be published','snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'commands':s.export_replay()},'scope':'six independent positive mechanics and one legal retire-callback stale-view failure; no promotion'};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'confirmed':r['expected_counterexample_confirmed'],'cases':len(cases),'sha256':sha(out)}))
