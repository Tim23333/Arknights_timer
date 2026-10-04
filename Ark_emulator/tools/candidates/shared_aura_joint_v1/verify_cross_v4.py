"""Own joint evidence: source Aura waiting and fresh separate-authority interaction."""
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];CAND=ROOT.parent/'unpack_work/campaign_chapter07_foundation_v2_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
import pytest,ark_sim
from ark_sim.adapters.api import implementation_digest
CORE='7696fcdc8e445c79469920e71c1ff94412b7c8ce1c5cf3ac51c956ddc30725cf'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()==CORE;paths=list(Path(__file__).parent.glob('*.py'))+list((CAND/'ark_sim').rglob('*.py'))+list((CAND/'ark_sim').rglob('*.json'))+[ROOT/'tools/candidates/shared_aura_v1/test_shared_guarded_v9.py',ROOT/'tools/campaign_ordered_checkpoint.py'];before={str(p):sha(p) for p in paths};start=time.monotonic();code=pytest.main([str(Path(__file__).with_name('test_cross_scopes_guarded_v5.py')),'-q']);after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE;out=ROOT/'validation/campaign/shared_aura_joint_cross_guarded_v5/verification.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();r={'passed':code==0,'actual_exit':code,'core':CORE,'runtime':ark_sim.__file__,'source_before':before,'source_after':after,'elapsed':time.monotonic()-start,'scope':'Own fresh jointly enabled Aura + exact timer WaitingAction: tick5 actualHP0, CP6/head, timer9/13/17 three10damage, Aura continuously retains markers, Aura cannot select waiting attack selector; manual start outside real periodic lease rejected with identical checkpoints, no shared cast/projectile privileges. Fixture initial timer alias mistake/default lifecycle missing source target policy historical fails retained.','source_probe_report':'validation/campaign/shared_aura_patrt_joint_self_source_v2/verification.json','full_suite_passed':False,'primary_modified':False,'client_verified':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out),'actual_exit':code}));raise SystemExit(code)
if __name__=='__main__':main()
