"""Freeze current six author cases and exact earlier failures without migration."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter07_sotisd_freeze_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 report=ROOT/'validation/campaign/chapter07_sotisd_guarded_final_v6/verification.json';r=json.loads(report.read_bytes());assert r['passed'] and r['actual_exit']==0 and r['source_before']==r['source_after'];assert all(sha(Path(p))==h for p,h in r['source_after'].items());assert not OUT.exists();OUT.mkdir(parents=True)
 evidence=[]
 for p in (ROOT/'validation/campaign/chapter07_sotisd_guarded_final_v6').glob('*'):
  if p.is_file():evidence.append({'path':str(p),'sha':sha(p),'bytes':p.stat().st_size})
 failures=[{'path':str(p),'sha':sha(p),'bytes':p.stat().st_size} for p in (ROOT/'validation/campaign').glob('chapter07_sotisd_author_v*.log')]
 paths=list((ROOT/'tools/chapter07_ordinary_remaining').glob('*.py'))+list((ROOT/'packages/campaign/chapter07_ordinary_remaining').glob('*.json'))
 for p in paths:
  target=OUT/'source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);assert sha(target)==sha(p)
 obj={'variant':'enemy_1081_sotisd@0/4d0de45d2830fb52','core':r['core'],'module':{'path':r['module'],'sha':r['module_sha']},'author6':{'path':str(report),'sha':sha(report),'actual_exit':0,'elapsed':r['elapsed']},'guards_before':r['source_before'],'guards_after':r['source_after'],'evidence':evidence,'historical_failures':failures,'new_freeze_helper':{'path':str(Path(__file__)),'sha':sha(Path(__file__))},'scope':r['scope'],'reference_policy':{'DBtaunt_absent_getter_default0_replaceable':True,'sourceBuff_true_flat1_not_base1':True,'live_integer_taunt_before_distance_comparator_reference':True,'source_native_method_body_and_client_comparator_pending':True,'source_midcast_TargetFree_and_animation_clamp_pending':True},'independent_reviewed':False,'core_changed':False,'primary_modified':False,'C7_whole_executed':False,'client_verified':False}
 out=OUT/'freeze.json';out.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'freeze_sha':sha(out),'author6_actual':True,'module_sha':r['module_sha']}))
if __name__=='__main__':main()
