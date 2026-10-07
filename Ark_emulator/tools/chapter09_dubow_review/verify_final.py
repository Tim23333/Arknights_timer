import json,hashlib,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 paths=list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+list(Path(__file__).parent.glob('*.py'))+[ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/chapter08_bsnake_combat/policies_v1.py',ROOT/'tools/chapter08_boss/dragon_fire_policies_v3.py',ROOT/'tools/chapter08_buff_lifetime/policies_v1.py',ROOT/'packages/campaign/chapter09_consumers/ordinary/enemy_1167_dubow.module.v1.json']
 module=json.loads(paths[-1].read_bytes());paths+=list(map(Path,module['manifest']['metadata']['source_locks']));before={str(p):sha(p) for p in paths};cases=[]
 class Capture:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
 start=time.monotonic();code=pytest.main([str(Path(__file__).with_name('test_peer_final.py')),'-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]);after={str(p):sha(p) for p in paths};assert before==after
 out=ROOT/'validation/campaign/chapter09_dubow_independent_final';out.mkdir(exist_ok=False);f=out/'verification.json';f.write_text(json.dumps({'passed':code==0,'actual_exit':code,'core':implementation_digest(),'cases':cases,'elapsed':time.monotonic()-start,'before':before,'after':after,'scope':'Fresh DEF193/RES87 physical57; distance1 speed10 launch21 hit24/full45; ASPD1.5 launch14 hit17/full30/cycle46 next hit63/full76; public retire22 launched arrow stillhit24; native radius2/fly/camo/targetfree rejection; raw source pins and one owned shared node. CP22/15/23 actual disk SHAload/head; temporary CP removed. No author fixture imported; renderer/body/whole/client unverified.','old_fixture_failures':[{'file':'test_peer_v1.py','actual_exit':1,'passed':4,'failed':2,'cause':'player side incorrectly neutral2; corrected player0 in newversion, no module mutation'}]},indent=2));g=out/'freeze.json';g.write_text(json.dumps({'verification_sha':sha(f),'core':implementation_digest(),'source_pins':after,'receipts':{str(p):sha(p) for p in (ROOT/'validation/campaign/chapter09_dubow_independent_final_cases').rglob('receipt.json')},'actual_exit':code,'unique_cases':len(cases)},indent=2));print(json.dumps({'report_sha':sha(f),'freeze_sha':sha(g),'cases':len(cases),'actual_exit':code}));raise SystemExit(code)
if __name__=='__main__':main()
