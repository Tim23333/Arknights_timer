import sys,json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
from tools.chapter09_ordinary_review.source_fields_v1 import audit
import pytest
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 paths=list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+list(Path(__file__).parent.glob('*.py'))+[ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json',ROOT/'packages/campaign/chapter09_source_prepare/source.plan.v1.json',ROOT/'tools/campaign_ordered_checkpoint.py']+[ROOT/'packages/campaign/chapter09_consumers/ordinary'/(key+'.module.v1.json') for key in ('enemy_1165_duhond','enemy_1166_dusbr')];before={str(p):sha(p) for p in paths};fields=audit();cases=[];start=time.monotonic()
 class Capture:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
 code=pytest.main([str(Path(__file__).with_name('test_peer_v2.py')),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]);after={str(p):sha(p) for p in paths};assert before==after;out=ROOT/'validation/campaign/chapter09_ordinary_independent_final';out.mkdir(exist_ok=False);f=out/'verification.json';f.write_text(json.dumps({'passed':code==0,'actual_exit':code,'core':implementation_digest(),'cases':cases,'fields':fields,'elapsed':time.monotonic()-start,'source_before':before,'source_after':after,'scope':'IndependentrawDB/PP/nullrange/noSkills/inlineMRES70 ADDITION permanent/silenceable, exactbaseHP/ATK/DEF/MRES. DifferentDEF173 physical127/107; actualdeploy0 thenfirstcast1 native18hitrelative19, cycles42/60/full30/42. PublicASPD1.25 hitrelative15(full24/34), truecasterstart1 retained clocks. Silence6 to18 mirror300/1000/300 arts at4/7/19 andMRES70 restores, noSPborrow. Publicretire9 preventsnative18; unblockednoattack. ActualCP9/11/12/head exact. Renderer/sourcebody reference policies unchanged; oldv1 absolute18 assertion fixturefail preserved notgamespacebug. AllrawCP temporaryElogs cleaned immediately aftercompletedproof; onlycompacthash/count receipts retained.','author_fixture_imports':False,'whole_stage_executed':False,'client_verified':False},indent=2),encoding='utf8');print(json.dumps({'sha':sha(f),'actual_exit':code,'cases':len(cases)}));raise SystemExit(code)
if __name__=='__main__':main()
