import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m37_projectile_refs_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent));sys.path.append(str(ROOT))
import test_units as tests
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
package=json.loads(tests.OUT.read_bytes());paths=[Path(__file__),Path(tests.__file__),ROOT/'tools/build_chapter02_airdrp_units.py',tests.OUT,RUNTIME/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/content/presets/ark_standard.json']
for key,pin in package['manifest']['metadata']['source_locks'].items():p=ROOT/key;assert sha(p)==pin;paths.append(p)
start={str(p):sha(p) for p in paths};core=implementation_digest();cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main([str(Path(tests.__file__)),'-q'],plugins=[Results()]);end={str(p):sha(p) for p in paths};report={'passed':code==0 and start==end and core==implementation_digest(),'core_start':core,'core_end':implementation_digest(),'module_path':ark_sim.__file__,'source_start':start,'source_end':end,'cases':cases,'fixture_inputs':tests.INPUTS,'scope':'exact stage variants, actual stats/owned combat and post-born declared movement only; birth model separate; no client/fullstage claim','formal_approved':False};out=ROOT/'validation/campaign/chapter02_airdrp/post_born_final.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':len(cases),'fixtures':len(tests.INPUTS),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
