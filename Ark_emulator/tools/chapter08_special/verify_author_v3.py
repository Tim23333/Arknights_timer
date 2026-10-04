"""Execute actual source author tests with immutable receipts, not compile counts."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_area_projection_v2_candidate'));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 paths=[ROOT/'packages/campaign/chapter08_consumers/special'/n for n in ['source.closure.v1.json','emppnt.module.v3.json','empace.module.v3.json']]+list(Path(__file__).parent.glob('*.py'));before={str(p):sha(p) for p in paths};rows=[]
 class Capture:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':rows.append({'case':report.nodeid,'outcome':report.outcome,'error':str(report.longrepr) if report.failed else None})
 core=implementation_digest();assert core=='3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000';code=int(pytest.main([str(Path(__file__).with_name('test_author_v3.py')),'-q','--tb=short'],plugins=[Capture()]));after={str(p):sha(p) for p in paths};out=ROOT/'packages/campaign/chapter08_consumers/special/author.v3.tests.json';assert not out.exists();out.write_bytes((json.dumps({'status':'passed' if code==0 and before==after else 'failed','actual_exit':code,'runtime_sha256':core,'cases':rows,'guards_before':before,'guards_after':after,'guards_equal':before==after,'whole_stage_executed':False,'client_verified':False,'independent_reviewed':False},ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'actual_exit':code,'path':str(out),'sha256':sha(out)}));return code
if __name__=='__main__':raise SystemExit(main())
