import sys,json,hashlib,time,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_selection_context_clock_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT));os.environ['ARKSIM_M10_REVIEW_ROOT']=str(CAND)
import pytest,ark_sim
from ark_sim.adapters.api import implementation_digest

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 files=list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+list(Path(__file__).parent.glob('*.py'))+list((ROOT/'tools/chapter08_ranged').glob('*.py'))+[ROOT/'packages/campaign/chapter08_consumers/ranged/uoffcr.module.v1.json',ROOT/'packages/campaign/chapter08_source_prepare/integration/enemies.native.v1.json',ROOT/'tools/campaign_ordered_checkpoint.py'];tests=['tests_v2/test_spatial.py','tests_v2/test_m8_enemy_targeting.py','tests_v2/test_m8_enemy_targeting_v2.py','tests_v2/test_m7_spatial_review.py'];files += [ROOT/x for x in tests];before={str(p):sha(p) for p in files};assert implementation_digest()=='26c47ef786b1a6fb24c01ad65a5fbb181e27b1b0b0dd138ccd26b728163f6407';start=time.monotonic();cases=[]
 class Capture:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
 code=pytest.main([str(Path(__file__).parent/'test_uoffcr_guarded_v4.py'),str(Path(__file__).parent/'test_clock_edges_guarded_v3.py')]+tests+['-q','--tb=short'],plugins=[Capture()]);after={str(p):sha(p) for p in files};assert before==after;out=ROOT/'validation/campaign/chapter08_selection_clock_v1/author_guarded/verification.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();r={'passed':code==0,'actual_exit':code,'core':implementation_digest(),'runtime':ark_sim.__file__,'source_before':before,'source_after':after,'elapsed':time.monotonic()-start,'cases':cases,'scope':'Same5uoffcr source assertions plus exactmarkerexpiry15 beforetask/source+target retire/cancel/immutable time+quantum+seconds and same inputs, no queryWorld/RNG/eventmutation; existing4spatial/typedqualification testsets assertions unchanged. No C8 stage/client claim.','whole_stage_executed':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha':sha(out),'actual_exit':code,'cases':len(cases)}));raise SystemExit(code)
if __name__=='__main__':main()
