import sys,json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_wave_track_v2_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
from ark_sim import Compiler
from ark_sim.domains.timeline import validate_finish_request
import pytest
CORE='d12060329b762439077c4c03110120c87e486fd462bf6c941d6636a759543f52'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 peer=[ROOT/'tests_v2/test_m8_timeline.py']+[ROOT/'tools/candidates/chapter07_foundation_v1'/n for n in ['test_finish_timeline_wave_v1.py','test_finish_timeline_wave_edges_v1.py','test_finish_timeline_fault_v1.py']]
 paths=list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+list(Path(__file__).parent.glob('*.py'))+peer+[ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'packages/campaign/chapter08_consumers/bsnake/source.closure.v1.json',ROOT/'validation/campaign/chapter08_wave_track_source_counter_v1/report.json',ROOT/'validation/campaign/chapter08_wave_track_terminal_counter_v2/report.json'];before={str(p):sha(p) for p in paths};assert implementation_digest()==CORE
 literal=json.loads((ROOT/'validation/campaign/chapter08_wave_track_source_counter_v1/report.json').read_bytes());validate_finish_request(literal['literal_request']);Compiler().compile(literal['input']);cases=[];start=time.monotonic()
 class Capture:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
 tests=[Path(__file__).with_name(n) for n in ['test_track_v4.py','test_boundaries_v4.py','test_controls_v4.py']]+peer
 code=pytest.main([str(p) for p in tests]+['-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]);after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE;out=ROOT/'validation/campaign/chapter08_wave_track_final_v1/verification.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();r={'passed':code==0,'actual_exit':code,'core':CORE,'parent_core':'20e8126120668fece832e8b6e23fd53a68fb013656a4476b5ad8e53850f6dd30','source_before':before,'source_after':after,'literal_source_required_request_and_original_counter_input_compile':True,'cases':cases,'elapsed':time.monotonic()-start,'scope':'Onlynew bool track_source_at_next_wave true with finishAndSkipfalse/delta0/allManagedfalse. RealHP0alivewaiting source remains sameUID and shifts wave0->1 at23 without birth orHPgrant. Native source-effectBSON9ec literal and wholeclosure742d preserved. Pending original births5/20/28/clearcontrols25/post3/pre5 preserved; nextwave SourcealoneblocksWave untiltrueRetire60, otheroldwave members retained. Repeat idempotent/dead/unmanaged/stale/bool/sourceincarnation/domainfault atomic/lastwave no phantom/realObjectiveLife0 terminal cancels pending tracker (lifecycle optin only) and CP15/25/head. Source scheduler/client body referencepolicy explicit. Original41timeline cases unchanged.','new_cases':18,'legacy_cases':41,'whole_stage_executed':False,'primary_modified':False};f=out;f.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'sha':sha(f),'cases':len(cases),'core':CORE}));raise SystemExit(code)
if __name__=='__main__':main()
