import sys,json,hashlib,io,contextlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_retained_area_payload_v16_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.experiments.retained_area_peer import test_peer_fixed as peer
OUT=ROOT/'validation/campaign/retained_area_independent_peer_v16';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
tests=[Path(peer.__file__),ROOT/'tools/experiments/retained_area_peer/test_failure_edges_fixed.py'];files=tests+[Path(__file__),ROOT/'tools/experiments/retained_buff_payload_peer/test_peer.py',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/candidates/chapter06_buff_join/retained_area_payload_v16.py',ROOT/'validation/campaign/retained_area_payload_v16/composition.json']+list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))
def guard():return {str(p):sha(p) for p in sorted(set(files))}
before=guard();assert implementation_digest()=='8b9f226882502ce9b9d8029102fff5832f2ba01e5449096502908b670d889e9b'
class Plugin:
 def __init__(self):self.rows=[]
 def pytest_runtest_teardown(self,item,nextitem):
  tmp=item.funcargs.get('tmp_path')
  if tmp:
   folder=OUT/'actual_ordered_cps'/item.name;folder.mkdir(parents=True,exist_ok=True)
   for p in tmp.glob('*.json'):(folder/p.name).write_bytes(p.read_bytes())
 def pytest_runtest_logreport(self,report):
  if report.when=='call':self.rows.append({'nodeid':report.nodeid,'outcome':report.outcome,'duration':report.duration,'failure':str(report.longrepr) if report.failed else None})
plugin=Plugin();buf=io.StringIO()
with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):code=pytest.main([*(str(t) for t in tests),'-q'],plugins=[plugin])
modules=[m for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).resolve()==Path(peer.__file__).resolve()];inputs=[];captures=[];seen=set()
for m in modules:
 if id(m) not in seen:seen.add(id(m));inputs.extend(m.INPUTS);captures.extend(m.CAPTURES)
after=guard();report={'core':implementation_digest(),'cases':plugin.rows,'exit':int(code),'output':buf.getvalue(),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Independent actualretained area2members60damage+Cold, publicprehit orderedCP/head exactallcheckpoint/events. Unselected/existingcallback-new-area/newdormantactivation cannotborrow. Truepacket nesteddisjointmembers allowed; overlapping revivedmember denied againstouteridentity. Malformedmembers/faultrollback cancelsnewjobs/restoresRNG andcleansallscopes. Syntheticgeometry radius1.1, notsourceSnslime nativeCollider/damage/Cold duration orwholeclaim.','fixture_initial_failures':'Forbiddenselfbuffcycle andrepeatedactivation callback correctedto unlaunchedotherbuff/firsttarget condition; invalidmember policy fixture removed mutuallyexclusive radius. Originalfiles/outcomes preserved, nocandidatefix and noexpectedrecipient weakening.'}
for name,value in [('inputs.json',inputs),('captures.json',captures),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'cases':len(plugin.rows),'passed':sum(x['outcome']=='passed' for x in plugin.rows),'guards_equal':before==after}))
