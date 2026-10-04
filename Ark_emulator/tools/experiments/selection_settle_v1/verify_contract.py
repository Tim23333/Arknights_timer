import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_selection_settle_v3_candidate'));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))
import pytest
from ark_sim.adapters.api import implementation_digest
PIN='30e4cdfadc5a98eb59da20d89591f5f5d3d6acc8f2d9a997df5e761d759fb49d';assert implementation_digest()==PIN
cases=[]
class Capture:
    def pytest_runtest_logreport(self,report):
        if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
code=int(pytest.main([str(Path(__file__).with_name('test_contract.py')),str(ROOT/'tests_v2/test_abilities.py'),str(ROOT/'tests_v2/test_spatial.py'),'-q','--tb=short'],plugins=[Capture()]))
assert implementation_digest()==PIN;out=ROOT/'validation/campaign/selection_settle_v1/contract_compat.json'
with out.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':code,'cases':cases},f,indent=2)
raise SystemExit(code)
