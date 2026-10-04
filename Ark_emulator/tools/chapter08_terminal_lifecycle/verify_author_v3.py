import sys,json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_terminal_lifecycle_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import pytest
import tools.chapter08_terminal_lifecycle.test_terminal_source_v1 as source
OUT=ROOT/'validation/campaign/chapter08_terminal_lifecycle_author_v3';source.OUT=OUT/'source'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 OUT.mkdir(parents=True,exist_ok=False);files=list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+list(Path(__file__).parent.glob('*.py'))+[ROOT/'tools/chapter08_bsnake/screen_policy_v1.py',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'validation/campaign/chapter08_bsnake_rebirth_selfboost_counter_v1/report.json',ROOT/'packages/campaign/chapter08_consumers/bsnake/source.closure.v1.json'];before={str(p):sha(p) for p in files};cases=[];start=time.monotonic()
 class Capture:
  def pytest_runtest_logreport(self,report):
   r=report
   if r.when=='call':cases.append({'case':r.nodeid,'outcome':r.outcome,'failure':str(r.longrepr) if r.failed else None})
 code=pytest.main([str(Path(__file__).with_name('test_terminal_source_v1.py')),str(Path(__file__).with_name('test_terminal_boundaries_v1.py')),'-q','--tb=short'],plugins=[Capture()]);after={str(p):sha(p) for p in files};assert before==after
 obj={'passed':code==0,'actual_exit':code,'core':implementation_digest(),'parent_core':'061d244eded4d41a74cdb78f5ab575e19f9b525883a3debf5269bab90007b854','source_before':before,'source_after':after,'cases':cases,'elapsed':time.monotonic()-start,'whole_stage_executed':False,'native_complete_boss':False,'scope':'Generic bounded exactzero terminal actor ownership/job/generation/HP0 typed/authenticated callbacks; sourcecomponent max50000 boost75000/1155 and first37500 then final0, 28s 10x3 actualdamage. Native fullmode/branch/hint/endBuff integration separately pending. Parent olddynamic lifetime reversegap retained; primary outside scope.'};f=OUT/'verification.json';f.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'core':implementation_digest(),'sha':sha(f),'cases':len(cases)}));raise SystemExit(code)
if __name__=='__main__':main()
