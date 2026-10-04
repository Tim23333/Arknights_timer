import sys,json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_rebirth_self_v2_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT));import pytest
from ark_sim.adapters.api import implementation_digest

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 files=list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+list(Path(__file__).parent.glob('*.py'))+[ROOT/'tools/chapter08_bsnake/screen_policy_v1.py',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'validation/campaign/chapter08_bsnake_rebirth_selfboost_counter_v1/report.json',ROOT/'tests_v2/test_buff_mode_lifecycle.py'];before={str(p):sha(p) for p in files};start=time.monotonic();cases=[]
 class Capture:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
 code=pytest.main([str(Path(__file__).with_name('test_self_actualguard_v6.py')),'tests_v2/test_buff_mode_lifecycle.py','-q','--tb=short'],plugins=[Capture()]);after={str(p):sha(p) for p in files};assert before==after and implementation_digest()=='f6fa921f6b6e93b58fb7bf3e9738dcef237fb666130dcaeac4dba7a76a093c65';out=ROOT/'validation/campaign/chapter08_rebirth_self_v2/author_guarded/verification.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();r={'passed':code==0,'actual_exit':code,'core':implementation_digest(),'source_before':before,'source_after':after,'elapsed':time.monotonic()-start,'cases':cases,'scope':'ActualfirstzeroHP retainedSelfBuff grant inrealbegin actor/gen/UID/source+self before actualbuffcommit; registry+incarnation persisted. FullCP75/head with37500HP/75000capacity/1155ATK. Manualrefresh atomicreject/foreign/stale/Boolgeneration/finishedforge/faultrollback/finallycontext/active_ruleFalse/withdraw/expiry/nextgen/periodicstats do not grant undeclaredcast; legacyBuffLifecycle unchanged. Finalzero restoration interface separate/unimplemented, no fakeHP.','whole_stage_executed':False,'primary_modified':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha':sha(out),'actual_exit':code,'cases':len(cases)}));raise SystemExit(code)
if __name__=='__main__':main()
