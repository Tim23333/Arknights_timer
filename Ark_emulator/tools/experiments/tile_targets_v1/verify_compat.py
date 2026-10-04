import hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_tile_targets_v7_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
PIN='42014647b8d510c6394b98221c138a0bc27a8ccab3354d653a65fc2767fb3833'
assert implementation_digest()==PIN
paths=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in {'.py','.json'}]
guards={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
cases=[]
class Reports:
    def pytest_runtest_logreport(self,report):
        r=report
        if r.when=='call':cases.append({'case':r.nodeid,'outcome':r.outcome,'failure':str(r.longrepr) if r.failed else None})
selected=['test_abilities.py','test_owned_deployment_constraints.py','test_replay.py','test_scenario_effects.py','test_spatial.py','test_reference_predefined_conversion.py']
code=int(pytest.main([*[str(ROOT/'tests_v2'/p) for p in selected],'-q','--tb=short'],plugins=[Reports()]))
assert guards=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths} and implementation_digest()==PIN
target=ROOT/'validation/campaign/tile_targets_v1/compat_v7.json'
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'cases':cases,'source_guards':guards},f,indent=2)
raise SystemExit(code)
