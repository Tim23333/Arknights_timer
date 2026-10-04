"""Actual new joint scope, source wait and separate Aura/timer authority proofs."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 reports=[ROOT/'validation/campaign/shared_aura_patrt_joint_self_source_v2/verification.json',ROOT/'validation/campaign/shared_aura_joint_cross_guarded_v5/verification.json'];receipts=[];guards={}
 for p in reports:
  r=json.loads(p.read_bytes());assert r['passed'] and r['actual_exit']==0 and r['core']=='7696fcdc8e445c79469920e71c1ff94412b7c8ce1c5cf3ac51c956ddc30725cf' and r['source_before']==r['source_after'];assert all(sha(Path(f))==h for f,h in r['source_after'].items());guards.update(r['source_after']);receipts.append({'path':str(p),'sha':sha(p)})
 evidence=[]
 for name in ('shared_aura_patrt_joint_self_source_v2','shared_aura_joint_cross_guarded_v5'):
  for p in (ROOT/'validation/campaign'/name).glob('*'):
   if p.is_file():evidence.append({'path':str(p),'sha':sha(p),'bytes':p.stat().st_size})
 out=ROOT/'validation/campaign/shared_aura_joint_final_freeze_v2/freeze.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();r={'core':'7696fcdc8e445c79469920e71c1ff94412b7c8ce1c5cf3ac51c956ddc30725cf','actual_new_source_and3_cross_cases':receipts,'source_guards':guards,'actual_evidence':evidence,'old_failing_fixture_logs':{str(p):sha(p) for p in [ROOT/'validation/campaign'/name for name in ('shared_aura_joint_cross_v1.log','shared_aura_joint_cross_v2.log','shared_aura_joint_cross_v3.log')]},'scope':'Actual source required Aura + current joint own HP0/CP6/head; three fresh scope interactions distinguish qualified Aura selector and declared current timer lease. Prior wrong timing/removal/initial alias fixtures preserved. No proof migration from f592/43d8/b102; full Boss Immo source arithmetic116.704 belongs Root newjoint source175bd separately.','full_suite_passed':False,'primary_modified':False,'wholeC7_executed':False,'client_verified':False};out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out)}))
if __name__=='__main__':main()
