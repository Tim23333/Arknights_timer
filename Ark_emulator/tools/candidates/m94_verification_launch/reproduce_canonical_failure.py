"""Fresh actual-source focused reproduction without changing running core/tools."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate';OUT=ROOT/'validation/campaign/m94_complete_c4'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));import ark_sim
from ark_sim.adapters.api import implementation_digest
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 import pytest
 pin=implementation_digest();assert pin=='cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7' and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
 files=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]+[ROOT/'tests_v2/test_canonical_kalts.py',Path(__file__)];before={str(p):sha(p) for p in files};cases=[]
 class Results:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
 code=int(pytest.main([str(ROOT/'tests_v2/test_canonical_kalts.py')+'::test_canonical_mechanism[no_owned_token_must_not_interrupt_ordinary_heal]','-q','--tb=long'],plugins=[Results()]))
 after={str(p):sha(p) for p in files};assert before==after and implementation_digest()==pin
 dest=OUT/'canonical_kalts_fresh_failure.json';dest.write_text(json.dumps({'core':pin,'exitcode':code,'cases':cases,'guard_before':before,'guard_after':after,'scope':'Exact original canonical expectation, no new expected value or core change'},indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'exitcode':code,'report_sha':sha(dest)}));raise SystemExit(code)
if __name__=='__main__':main()
