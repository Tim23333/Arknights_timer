"""Actual new-operation execution and immutable candidate/source guards."""
import json,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_behavior_restart_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
CORE='44b4b97b8aad4a140e802d1fb014c619e7fd60e673cf6fa711a47bc6e755522a'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().is_relative_to(CAND)
    paths=list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+list((ROOT/'tools/chapter08_behavior_restart').glob('*.py'))+[ROOT/'tools/campaign_ordered_checkpoint.py']
    before={str(p):sha(p) for p in paths};start=time.monotonic();code=int(pytest.main([str(ROOT/'tools/chapter08_behavior_restart/test_restart_v1.py'),'-q']));after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE
    out=ROOT/'validation/campaign/chapter08_behavior_restart_v1/author_v2.json';assert not out.exists();out.parent.mkdir(parents=True,exist_ok=True)
    r={'passed':code==0,'actual_exit':code,'core':CORE,'runtime':ark_sim.__file__,'before':before,'after':after,'elapsed':time.monotonic()-start,'scope':'Explicit finite restart, actualownedcast cancel/initialcooldown40, CP/head complete events, late callbacks RNG/state/jobs rollback, ownedBuff releasefault, callbackretire stops remaining writes, recursionguard, strict compile/runtime and foreignownership, nooption oldtransition.'};out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'actual_exit':code,'sha':sha(out)}));raise SystemExit(code)
if __name__=='__main__':main()
