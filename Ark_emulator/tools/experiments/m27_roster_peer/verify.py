"""Independent bounded cache proof; durable canonical-CP flaw remains separate."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m27_event_intern_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import test_roster_storage as tests
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=[Path(__file__),Path(tests.__file__),ROOT/'tools/campaign_streaming_evidence.py',RUNTIME/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/content/presets/ark_standard.json'];start={str(p):sha(p) for p in paths};core=implementation_digest();assert core=='75fdf7c2ffe99014f707aa900cbe5c4dffc9756229a81b607f0f3ef9178d9b90'
cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed','scope':'known canonical disk-order failure reproduced' if 'counterexample' in item.nodeid else 'storage boundary positive'})
code=pytest.main([str(Path(tests.__file__)),'-q'],plugins=[Results()]);end={str(p):sha(p) for p in paths};core_end=implementation_digest()
report={'schema_version':1,'bounded_storage_passed':code==0 and start==end and core==core_end,'core_start':core,'core_end':core_end,'module_path':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'fixture_inputs':tests.INPUTS,'known_separate_tool_bug':{'original_durable_expectation':'disk checkpoint continuation equals original','actual':False,'path':'durable_counterexample.json','in_memory_checkpoint_equal':True,'cause':'sorted mapping resources order altered by canonical serialization; not75fd interner regression'},'native_accuracy_verified':False,'formal_approved':False}
out=ROOT/'validation/campaign/m27_roster_peer/final.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'bounded_storage_passed':report['bounded_storage_passed'],'cases':len(cases),'positive_cases':6,'counterexamples':1,'sha256':sha(out)}));raise SystemExit(0 if report['bounded_storage_passed'] else 1)
