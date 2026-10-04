import sys,json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_chapter08_joint_v4_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
from tools.chapter08_bsnake_combat.build_module_v2 import CORE,OUT,D12
import pytest
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 paths=list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+list(Path(__file__).parent.glob('*.py'))+[OUT,D12,ROOT/'packages/campaign/chapter08_consumers/bsnake/source.closure.v1.json',ROOT/'packages/campaign/chapter08_consumers/bsnake/requirements.v2.json',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'validation/campaign/chapter08_bsnake_rebirth_selfboost_counter_v1/report.json',ROOT/'tools/chapter08_boss/dragon_fire_policies_v3.py',ROOT/'tools/chapter08_boss/dragon_fire_policies_v1.py',ROOT/'tools/chapter08_buff_lifetime/policies_v1.py'];before={str(p):sha(p) for p in paths};cases=[];start=time.monotonic()
 class Capture:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
 code=pytest.main([str(Path(__file__).with_name(x)) for x in ['test_source_v3.py','test_edges_v2.py','test_busy_v2.py']]+['-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]);after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE;out=ROOT/'validation/campaign/chapter08_bsnake_combat_final_v1/verification.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();obj={'passed':code==0,'actual_exit':code,'core':CORE,'module_sha':sha(OUT),'source_before':before,'source_after':after,'cases':cases,'elapsed':time.monotonic()-start,'scope':'NativePURE770/31frame/70fullbusy/135cycle normal0/1; real37500/75000/1155 firstRebirth used only isolatednormal fixture (firstscreen not consumed here). CurrentATK/ASPD, typedtargets, actualblock identity, twoSourceprofile passive0/reborn1 protection on reallive modifierSource dragonparent; childalone false/allthreeDamageTypes/expiry/silenceable mirror vs realBossimmune12, actualCP/head. Body/tie/range/ASPDgraphics referencepolicy explicit.','whole_stage_executed':False,'complete_boss':False,'primary_modified':False};f=out;f.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'sha':sha(f),'cases':len(cases)}));raise SystemExit(code)
if __name__=='__main__':main()
