"""Unchanged original Aura ownership/review/skill recipes on fixed new candidate."""
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];CAND=ROOT.parent/'unpack_work/campaign_shared_aura_v6_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()=='f519c82f652b2662f7f5f4a9009bb19a650a266ea009f98ca9301b200374c3fb';tests=[ROOT/'tests_v2'/name for name in ('test_auras.py','test_aura_review.py','test_aura_skill_recipes.py')];paths=tests+[ROOT/'tests_v2/conftest.py',ROOT/'tests_v2/test_campaign_acceptance.py',Path(__file__)]+list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'));before={str(p):sha(p) for p in paths};start=time.monotonic();code=pytest.main([str(p) for p in tests]+['-q']);after={str(p):sha(p) for p in paths};assert before==after;out=ROOT/'validation/campaign/shared_aura_legacy_v1/verification.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();r={'passed':code==0,'actual_exit':code,'core':implementation_digest(),'source_before':before,'source_after':after,'elapsed':time.monotonic()-start,'tests':[str(p) for p in tests],'assertions_unchanged':True};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out),'actual_exit':code,'elapsed':r['elapsed']}));raise SystemExit(code)
if __name__=='__main__':main()
