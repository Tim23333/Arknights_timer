import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_block_status_v3_candidate'));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))
import pytest
from ark_sim.adapters.api import implementation_digest
PIN='f00b098ccf3ac05144d440dd18b554af87479e8ef0178eff4f2301e061f6a5d6';assert implementation_digest()==PIN
cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
tests=['test_buff_mode_lifecycle.py','test_spatial.py','test_owned_deployment_constraints.py']
code=int(pytest.main([*[str(ROOT/'tests_v2'/p) for p in tests],'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]))
target=ROOT/'validation/campaign/block_status_v1/compat_v3_existing_tests.json'
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'cases':cases},f,indent=2)
raise SystemExit(code)
