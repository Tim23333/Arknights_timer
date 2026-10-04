"""Bounded generic field proof with separately preserved known static failures."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m31_tile_field_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import test_fields_peer as tests
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=[Path(__file__),Path(tests.__file__),ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'packages/campaign/chapter02_tiles/source.reference.json',ROOT/'validation/campaign/m31_roster_peer/static_route.fixture.json',RUNTIME/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/content/presets/ark_standard.json']
start={str(p):sha(p) for p in paths};core=implementation_digest();assert core=='7720452f53f4e8b1e0c3e2ba77ab03e0b0b8e8e3b2cdfabf79fe9499f967e96d';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main([str(Path(tests.__file__)),'-q'],plugins=[Results()]);end={str(p):sha(p) for p in paths};core_end=implementation_digest()
report={'schema_version':1,'bounded_field_cases_passed':code==0 and start==end and core==core_end,'core_start':core,'core_end':core_end,'source_start':start,'source_end':end,'module_path':ark_sim.__file__,'cases':cases,'fixture_inputs':tests.INPUTS,'known_blockers':['static_route.counterexample.json: static source actually moves, registry stale','static_override.counterexample.final.json: effective initial ability override accepted, damage50'],'native_source_file_guarded_only_not_used_as_native_case':True,'native_accuracy_verified':False,'formal_approved':False}
out=ROOT/'validation/campaign/m31_roster_peer/final.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'bounded_field_cases_passed':report['bounded_field_cases_passed'],'cases':len(cases),'known_blockers':2,'sha256':sha(out)}));raise SystemExit(0 if report['bounded_field_cases_passed'] else 1)
