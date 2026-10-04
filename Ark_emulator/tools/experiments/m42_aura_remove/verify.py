import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m42_aura_remove_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
import test_remove as tests
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=ROOT/'tools/experiments/defdrn_status/test_model.py';paths=[Path(__file__),Path(tests.__file__),source,ROOT/'tools/candidates/m42_aura_remove/prepare_candidate.py',ROOT/'packages/campaign/chapter02_units/defdrn.status.model.json',RUNTIME/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/content/presets/ark_standard.json'];start={str(p):sha(p) for p in paths};core=implementation_digest();assert core=='2746020dd269241d8802551ea63cb28243755ff0105a19bb09033c448f497420';cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',str(Path(tests.__file__)),str(source)],plugins=[Results()]);end={str(p):sha(p) for p in paths};core_end=implementation_digest()
module=sys.modules['test_model'];report={'passed':code==0 and start==end and core==core_end,'core_start':core,'core_end':core_end,'module':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'generic_fixture_inputs':tests.INPUTS,'defdrn_fixture_inputs':module.INPUTS,'scope':'generic synchronous membership remove+source-backed declared defdrn; later user client comparison separate','old_counterexample':'validation/campaign/defdrn_status/remove_history_m38/counterexample.json','client_verified':False,'formal_approved':False};out=ROOT/'validation/campaign/m42_aura_remove/final.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':len(cases),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
