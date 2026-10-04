"""Explicit frozen candidate before unchanged V2 compatibility modules."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m28_unlimited_projectile_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
names=['test_content.py','test_domain_rules.py','test_abilities.py','test_event_resources.py','test_spatial.py','test_activation_controls.py','test_buff_mode_lifecycle.py']
paths=[ROOT/'tests_v2'/x for x in names];start={str(p):sha(p) for p in [Path(__file__),*paths]};core=implementation_digest();cases=[]
class Results:
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',*[str(p) for p in paths]],plugins=[Results()]);end={str(p):sha(p) for p in [Path(__file__),*paths]};assert implementation_digest()==core
report={'passed':code==0 and start==end,'implementation':core,'module_path':ark_sim.__file__,'test_start':start,'test_end':end,'cases':cases,'formal_approved':False}
out=ROOT/'validation/campaign/m28_unlimited/compatibility_final.json';out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'cases':len(cases),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
