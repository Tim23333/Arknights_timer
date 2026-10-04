"""Source-only author gate, unchanged3992/currentfields bytes guarded."""
import json,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import pytest,ark_sim
from ark_sim.adapters.api import implementation_digest
from tools.chapter08_volcano.build_module_v1 import OUT,sha
CORE='3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000'
def main():
    assert implementation_digest()==CORE
    p=json.loads(OUT.read_bytes());paths=list((ROOT/'ark_sim').rglob('*.py'))+list((ROOT/'ark_sim').rglob('*.json'))+list((ROOT/'tools/chapter08_volcano').glob('*.py'))+[OUT,ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/build_reference_stage_scenario_v2.py',OUT.parents[2]/'chapter08_source_prepare/integration/source.plan.v1.json']+[Path(n) for n in p['manifest']['metadata']['source_locks']]
    paths += [ROOT/'tools/chapter08_environment/policies_v1.py',ROOT/'packages/campaign/chapter08_consumers/environment/infection.module.v3.json']
    before={str(x):sha(x) for x in paths};start=time.monotonic();code=int(pytest.main([str(ROOT/'tools/chapter08_volcano/test_source_v2.py'),'-q']));after={str(x):sha(x) for x in paths};assert before==after and implementation_digest()==CORE
    out=ROOT/'validation/campaign/chapter08_volcano_author_v2/verification.json';assert not out.exists();out.parent.mkdir(parents=True,exist_ok=True);r={'passed':code==0,'actual_exit':code,'core':CORE,'runtime':ark_sim.__file__,'before':before,'after':after,'elapsed':time.monotonic()-start,'scope':'Native6cells1000PURE/random8..12/realnamedRNG samples,typedground/category/free/camo,currentafterhook500/sourceBBstrict/CPheadallstateevents. Sharedsourcegeometry literal retained, cellcombat reference not client collision proof.','client_verified':False,'whole_stage_executed':False,'independent_reviewed':False};out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'exit':code,'sha':sha(out)}));raise SystemExit(code)
if __name__=='__main__':main()
