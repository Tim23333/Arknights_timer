"""New candidate author contract/source cases plus existing focused compatibility."""
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_infinite_buff_plan_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest,ark_sim
from ark_sim.adapters.api import implementation_digest
CORE='b20d8bd43e6db219186dca4c01c759b4fa3b44262bddbb5173ab952bf256b188';OUT=ROOT/'validation/campaign/infinite_buff_plan_guarded_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()==CORE
 files=list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))+list((ROOT/'tools/candidates/infinite_buff_plan').glob('*.py'))+list((ROOT/'tools/chapter07_strength_melee').glob('*.py'))+list((ROOT/'packages/campaign/chapter07_strength_melee').glob('*.json'))+[ROOT/'tools/campaign_ordered_checkpoint.py'];modules=list((ROOT/'packages/campaign/chapter07_strength_melee').glob('*.v4.json'))
 for p in modules:
  m=json.loads(p.read_bytes());assert m['manifest']['metadata']['required_runtime']==CORE
  for f,h in m['manifest']['metadata']['source_locks'].items():assert sha(Path(f))==h;files.append(Path(f))
 tests=[ROOT/'tools/candidates/infinite_buff_plan/test_plan_v1.py',ROOT/'tools/chapter07_strength_melee/test_source_guarded_v4.py'];tests+=list((ROOT/'tests_v2').glob('test_buff_application*.py'));files+=tests;before={str(p):sha(p) for p in files};started=time.monotonic();code=pytest.main([str(p) for p in tests]+['-q']);after={str(p):sha(p) for p in files};assert before==after and implementation_digest()==CORE;OUT.mkdir(parents=True,exist_ok=True);out=OUT/'verification.json';assert not out.exists();r={'passed':code==0,'actual_exit':code,'core':CORE,'runtime':ark_sim.__file__,'elapsed':time.monotonic()-started,'source_before':before,'source_after':after,'modules':{str(p):sha(p) for p in modules},'tests':[str(p) for p in tests],'scope':'Explicit None permanent plan, full-plan prevalidation and no partial stores; three source listener .25sec first8 then24 removal; actual base/BSON BB multiplier/noSP/frame/cycle/DP/damage; source CP7 and10 disk SHAload/resume/head. Native method bodies/comparator/source marker emitter and client calibration pending.','full_suite_passed':False,'independent_reviewed':False,'primary_modified':False,'whole_stage_executed':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'actual_exit':code,'sha':sha(out),'elapsed':r['elapsed']}));raise SystemExit(code)
if __name__=='__main__':main()
