"""Explicit candidate import before unchanged compatibility tests."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
CANDIDATE=ROOT.parent/'unpack_work/campaign_m16_terrain_candidate'
sys.path.insert(0,str(CANDIDATE))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==CANDIDATE/'ark_sim'
sys.path.append(str(ROOT))
import pytest
import json
import hashlib
from ark_sim.adapters.api import implementation_digest
files=[ROOT/'tests_v2'/f for f in (
 'test_content.py','test_domain_rules.py','test_spatial.py','test_owned_deployment_constraints.py',
 'test_m8_timeline.py','test_activation_controls.py','test_buff_mode_lifecycle.py')]
core=implementation_digest();start={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*files]};cases=[]
class Capture:
    def pytest_runtest_makereport(self,item,call):
        if call.when=='call':cases.append({'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'})
code=pytest.main(['-q',*[str(p) for p in files]],plugins=[Capture()])
end={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*files]}
stable=start==end and implementation_digest()==core
out=ROOT/'validation/campaign/m16_terrain/compatibility_final.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps({'passed':code==0 and stable,'implementation':core,'runtime_module':ark_sim.__file__,
  'source_at_start':start,'source_at_completion':end,'identity_stable':stable,'cases':cases,'formal_approval':False},indent=2)+'\n',encoding='utf8')
raise SystemExit(code or (0 if stable else 1))
