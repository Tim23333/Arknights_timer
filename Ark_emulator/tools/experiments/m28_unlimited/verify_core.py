"""Freeze the generic slice independently of further skulsr content work."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m28_unlimited_projectile_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import test_unlimited as tests
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=[Path(__file__),Path(tests.__file__),ROOT/'tools/candidates/m28_unlimited/prepare_candidate.py',ROOT/'packages/campaign/chapter02_behavior/skulsr.conflict.reference.json',RUNTIME/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/content/presets/ark_standard.json']
core_start=implementation_digest();assert core_start=='cb0e7a97a2621aaf4b14dc942181686906733acbcc61f6a5a23ebae9448e997b'
start={str(p):sha(p) for p in paths};cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main([str(Path(tests.__file__)),'-q'],plugins=[Results()]);end={str(p):sha(p) for p in paths};core_end=implementation_digest()
report={'schema_version':1,'scope':'generic unlimited hit cap/stop-first slice, not stage/native approval','passed':code==0 and start==end and core_start==core_end,'core_start':core_start,'core_end':core_end,'runtime_module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'fixture_inputs':tests.INPUTS,'null_semantics':'no total hit cap; explicit life/same-target/stop_first/invalid/reach policies remain; stop_after_max ignored only for capnull','historical_failure':'history_2fc1 counterexample 2 hits under stop_after_first, original files/test preserved','formal_approved':False}
out=ROOT/'validation/campaign/m28_unlimited/core_final.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':len(cases),'fixture_inputs':len(tests.INPUTS),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
