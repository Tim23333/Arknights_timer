"""Actual single-line revision identity and independent ref/quota boundaries."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m37_projectile_refs_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import test_refs as tests
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=[Path(__file__),Path(tests.__file__),ROOT/'tools/candidates/m37_projectile_refs/prepare_candidate.py',RUNTIME/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/content/presets/ark_standard.json'];start={str(p):sha(p) for p in paths};core=implementation_digest();assert core=='c77ce7a46101cf903fd9c6c56dcabddf5775008d091365cd7486ddeb47b8d740';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed','scope':'API instrumentation' if any(x in item.nodeid for x in ('nested','api_both','invalid_reference','same_target_true','invalid_callback')) else 'public command CP/replay'})
code=pytest.main([str(Path(tests.__file__)),'-q'],plugins=[Results()]);end={str(p):sha(p) for p in paths};core_end=implementation_digest()
report={'schema_version':1,'passed':code==0 and start==end and core==core_end,'core_start':core,'core_end':core_end,'module_path':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'fixture_inputs':tests.INPUTS,'scope':'generic ref/quota normalization; API reentry separate from recorded-command cases; no stage or native receipt','parent_failure':'validation/campaign/m30_roster_peer/alias_failure/counterexample.json','formal_approved':False}
out=ROOT/'validation/campaign/m37_projectile_refs/final.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':len(cases),'fixtures':len(tests.INPUTS),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
