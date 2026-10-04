import json,sys,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_selection_context_clock_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT));import pytest,ark_sim
from ark_sim.adapters.api import implementation_digest

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 modules=[ROOT/'packages/campaign/chapter08_consumers/ranged'/n for n in ['uoffcr.module.v3.json','ucommd.module.v2.json','uamord.module.v4.json']];files=list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+list(Path(__file__).parent.glob('*.py'))+modules+[ROOT/'tools/campaign_ordered_checkpoint.py'];
 for p in modules:files += [Path(n) for n in json.loads(p.read_bytes())['manifest']['metadata']['source_locks']]
 before={str(p):sha(p) for p in files};start=time.monotonic();cases=[]
 class Capture:
  def pytest_runtest_logreport(self,r):
   if r.when=='call':cases.append({'case':r.nodeid,'outcome':r.outcome,'failure':str(r.longrepr) if r.failed else None})
 code=pytest.main([str(Path(__file__).with_name(n)) for n in ['test_uoffcr_guarded_v3.py','test_ucommd_guarded_v3.py','test_uamord_guarded_v3.py','test_projectile_lifecycle_guarded_v2.py']]+['-q','--tb=short'],plugins=[Capture()]);after={str(p):sha(p) for p in files};assert before==after and implementation_digest()=='26c47ef786b1a6fb24c01ad65a5fbb181e27b1b0b0dd138ccd26b728163f6407';out=ROOT/'validation/campaign/chapter08_ranged_final_guarded/verification.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();r={'passed':code==0,'actual_exit':code,'core':implementation_digest(),'runtime':ark_sim.__file__,'module_pins':{str(p):sha(p) for p in modules},'source_before':before,'source_after':after,'elapsed':time.monotonic()-start,'cases':cases,'scope':'3actualsource variants: uoffcr15/15/60,330physical;ucommd18/17/66,550physical/blockcost2;uamord19/84,340arts/currentRES andDEFignore, actualtuple SPECIFIED_BUFF3 plus taunt-at-last declared reference. Every originalHP/SPabsence/no borrowedimmunity, typedgates/marker/puretemporal expiry/currentDEF orRES/ASPD/publicDP/blockpriority/capture/lifecycle and true orderedCP/head. Genericsettle_blocking reused beforecapture; no gameIDkernel modification. MarkerNPCfullbody/ASPDmaxAnimScale/nativecomparison/body/client remain explicit reference policies.','whole_stage_executed':False,'client_verified':False,'independent_reviewed':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha':sha(out),'actual_exit':code,'cases':len(cases)}));raise SystemExit(code)
if __name__=='__main__':main()
