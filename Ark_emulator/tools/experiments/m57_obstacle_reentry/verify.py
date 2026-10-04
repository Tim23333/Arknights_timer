import sys,json,hashlib,difflib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m57_obstacle_reentry_candidate';BASE=ROOT.parent/'unpack_work/campaign_m55_route_obstacle_candidate'
sys.path.insert(0,str(RUNTIME));import ark_sim
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import pytest,test_independent as t
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
files=[Path(__file__),Path(t.__file__),ROOT/'tools/candidates/m57_obstacle_reentry/prepare_candidate.py',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/experiments/m55_obstacle/test_contact.py',RUNTIME/'ark_sim/rules/contracts.json']
paths=[ROOT/'tests_v2'/x for x in ['test_spatial.py','test_activation_controls.py','test_buff_mode_lifecycle.py']];files+=paths
start={str(p):sha(p) for p in files};before=implementation_digest();cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',str(Path(t.__file__)),str(ROOT/'tools/experiments/m55_obstacle/test_contact.py'),*[str(p) for p in paths]],plugins=[Results()])
p=t.watched([{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}],rows=1);s=t.make(p);t.deploy(s);s.submit({'action':'skill','source':'barrier','ability':'ability/setup'},at=3);s.advance(13)
end={str(p):sha(p) for p in files};after=implementation_digest();out=ROOT/'validation/campaign/m57_obstacle_reentry';out.mkdir(parents=True,exist_ok=True)
diffs=[]
for f in sorted((RUNTIME/'ark_sim').rglob('*.py')):
 old=BASE/f.relative_to(RUNTIME)
 if f.read_bytes()!=old.read_bytes():diffs.append(str(f.relative_to(RUNTIME/'ark_sim')))
patch=''.join(difflib.unified_diff((BASE/'ark_sim/domains/movement.py').read_text().splitlines(True),(RUNTIME/'ark_sim/domains/movement.py').read_text().splitlines(True),fromfile='m55/domains/movement.py',tofile='m57/domains/movement.py'))
(out/'candidate.patch').write_text(patch,encoding='utf8')
r={'passed':code==0 and start==end and before==after,'core_start':before,'core_end':after,'actual_module':ark_sim.__file__,'source_start':start,'source_end':end,'changed_files':diffs,'cases':cases,'fixture_inputs':t.INPUTS,'counterexample_fixed':{'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'commands':s.export_replay()},'scope':'independent16 (public command CP/replay plus explicitly scoped API callback instrumentation), author contact and compatibility; no promotion/stage receipt','parent_failure':{'path':'validation/campaign/m55_roster_peer/initial_failure.json','sha256':sha(ROOT/'validation/campaign/m55_roster_peer/initial_failure.json')}}
(out/'final.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':r['passed'],'cases':len(cases),'core':before,'report_sha256':sha(out/'final.json'),'patch_sha256':sha(out/'candidate.patch')}));raise SystemExit(0 if r['passed'] else 1)
