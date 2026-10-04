"""Bind actual recursive Buff consumer author scope and guards."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
from tools.chapter08_boss.build_dragon_fire_v1 import OUT,sha
CORE='3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000'

def main():
    assert implementation_digest()==CORE
    p=json.loads(OUT.read_bytes());paths=list((ROOT/'ark_sim').rglob('*.py'))+list((ROOT/'ark_sim').rglob('*.json'))+list((ROOT/'tools/chapter08_boss').glob('*.py'))+[OUT,ROOT/'tools/campaign_ordered_checkpoint.py']+[ROOT/n for n in p['manifest']['metadata']['source_locks']]
    before={str(n):sha(n) for n in paths};start=time.monotonic();code=int(pytest.main([str(ROOT/'tools/chapter08_boss/test_dragon_fire_v2.py'),'-q']));after={str(n):sha(n) for n in paths};assert before==after and implementation_digest()==CORE
    dest=ROOT/'validation/campaign/chapter08_dragon_fire_author_v2/verification.json';assert not dest.exists();dest.parent.mkdir(parents=True,exist_ok=True)
    r={'passed':code==0,'actual_exit':code,'core':CORE,'runtime':ark_sim.__file__,'module_sha':sha(OUT),'source_before':before,'source_after':after,'elapsed_seconds':time.monotonic()-start,
        'scope':'Actual unshortened30.5s parent/1s child50+180*capped_elapsed30 ramp/30packets56..230, repeat no refresh, child retain/parent reapply, normalafterhook/sourceATK independence/public source retire, ordered CP/head full state/events.',
        'reference_policy':p['manifest']['metadata']['reference_policy'],'complete_boss':False,'whole_stage_executed':False,'independent_reviewed':False,'client_verified':False}
    dest.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'actual_exit':code,'verification_sha':sha(dest)}));raise SystemExit(code)
if __name__=='__main__':main()
