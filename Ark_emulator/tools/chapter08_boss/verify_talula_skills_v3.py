"""Guard real full-duration source skill tests in selected clock candidate."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_selection_context_clock_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
import pytest,ark_sim
from ark_sim.adapters.api import implementation_digest
from tools.chapter08_boss.build_talula_skills_v2 import OUT,sha
from tools.chapter08_boss.build_talula_skills_v1 import CORE
def main():
    assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().is_relative_to(CAND)
    p=json.loads(OUT.read_bytes());paths=list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+list((ROOT/'tools/chapter08_boss').glob('*.py'))+[OUT,ROOT/'tools/campaign_ordered_checkpoint.py']+[ROOT/n for n in p['manifest']['metadata']['source_locks']]
    before={str(x):sha(x) for x in paths};start=time.monotonic();code=int(pytest.main([str(ROOT/'tools/chapter08_boss/test_talula_skills_v3.py'),'-q']));after={str(x):sha(x) for x in paths};assert before==after and implementation_digest()==CORE
    out=ROOT/'validation/campaign/chapter08_talula_skills_author_v3/verification.json';assert not out.exists();out.parent.mkdir(parents=True,exist_ok=True)
    r={'passed':code==0,'actual_exit':code,'core':CORE,'runtime':ark_sim.__file__,'module_sha':sha(OUT),'source_before':before,'source_after':after,'elapsed_seconds':time.monotonic()-start,'scope':'Fourkey source original19/7/40init160/15sec clocks, actualdragon600/240 parent and1sec increasing packets, realDance4865/515/965 1095targetRES27, nativeSkill2mapping1.2/ASPD timing reference, completeCP/headeventsstate. Unrelated attacks isolatedexplicitly.','complete_boss':False,'whole_stage_executed':False,'client_verified':False,'independent_reviewed':False}
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'actual_exit':code,'sha':sha(out)}));raise SystemExit(code)
if __name__=='__main__':main()
