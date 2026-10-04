"""Independent selected source proof with exact module/helper/core guards."""
import sys,json,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import pytest,ark_sim
from ark_sim.adapters.api import implementation_digest
CORE='3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert implementation_digest()==CORE
    module=ROOT/'packages/campaign/chapter08_consumers/environment/infection.module.v3.json';m=json.loads(module.read_bytes());paths=list((ROOT/'ark_sim').rglob('*.py'))+list((ROOT/'ark_sim').rglob('*.json'))+[module,Path(__file__),Path(__file__).with_name('test_infection_v1.py'),ROOT/'tools/chapter08_environment/policies_v1.py',ROOT/'tools/campaign_ordered_checkpoint.py']+[Path(n) for n in m['manifest']['metadata']['source_locks']]
    before={str(x):sha(x) for x in paths};start=time.monotonic();code=int(pytest.main([str(Path(__file__).with_name('test_infection_v1.py')),'-q']));after={str(x):sha(x) for x in paths};assert before==after and implementation_digest()==CORE
    out=ROOT/'validation/campaign/chapter08_infection_independent_v1/verification.json';assert not out.exists();out.parent.mkdir(parents=True,exist_ok=True);d={'passed':code==0,'actual_exit':code,'core':CORE,'runtime':ark_sim.__file__,'before':before,'after':after,'module_sha':sha(module),'elapsed_seconds':time.monotonic()-start,'scope':'Independent original300s offcell/return nonrefresh299x180/HP16180/ATK246→369 AS1.2→1.7,allside groundchar/free/camo/notfly/notdevice,and fullCP/head stateevents. Sourcegeometry/bodyreference remains declared.','author_fixture_reused':False,'whole_stage_executed':False,'client_verified':False};out.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'exit':code,'sha':sha(out)}));raise SystemExit(code)
if __name__=='__main__':main()
