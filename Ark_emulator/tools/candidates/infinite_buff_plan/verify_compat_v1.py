"""Unchanged existing effects/Buff/rules assertions on explicit new candidate."""
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_infinite_buff_plan_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import pytest,ark_sim
from ark_sim.adapters.api import implementation_digest
CORE='b20d8bd43e6db219186dca4c01c759b4fa3b44262bddbb5173ab952bf256b188'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()==CORE;tests=[ROOT/'tests_v2'/name for name in ('test_buff_mode_lifecycle.py','test_scenario_effects.py','test_domain_rules.py','test_rules.py')];paths=tests+[ROOT/'tests_v2/conftest.py',Path(__file__)]+list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'));before={str(p):sha(p) for p in paths};start=time.monotonic();code=pytest.main([str(p) for p in tests]+['-q']);after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE;out=ROOT/'validation/campaign/infinite_buff_plan_compat_v1/verification.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();r={'passed':code==0,'actual_exit':code,'core':CORE,'runtime':ark_sim.__file__,'source_before':before,'source_after':after,'elapsed':time.monotonic()-start,'tests':[str(p) for p in tests],'assertions_unchanged':True,'full_suite':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out),'actual_exit':code,'elapsed':r['elapsed']}));raise SystemExit(code)
if __name__=='__main__':main()
