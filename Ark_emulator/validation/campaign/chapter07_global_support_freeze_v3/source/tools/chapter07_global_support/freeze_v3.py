"""Exact global support consumer six real cases on explicit 4f16, no stage claim."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter07_global_support_freeze_v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 report=ROOT/'validation/campaign/chapter07_global_support_guarded_v3/verification.json';r=json.loads(report.read_bytes());assert r['passed'] and r['actual_exit']==0 and r['source_before']==r['source_after'];assert all(sha(Path(p))==h for p,h in r['source_after'].items());assert not OUT.exists();OUT.mkdir(parents=True);files=list(Path(__file__).parent.glob('*.py'))+list((ROOT/'packages/campaign/chapter07_global_support').glob('*.json'));evidence=[]
 for p in files:
  dst=OUT/'source'/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);assert sha(p)==sha(dst)
 for p in (ROOT/'validation/campaign/chapter07_global_support_guarded_v3').glob('*'):
  if p.is_file():evidence.append({'path':str(p),'sha':sha(p),'bytes':p.stat().st_size})
 obj={'core':r['core'],'source_variant':r['source_variant'],'module':{'path':r['module'],'sha':r['module_sha']},'actual6_author':{'path':str(report),'sha':sha(report),'actual_exit':0,'elapsed':r['elapsed']},'source_before':r['source_before'],'source_after':r['source_after'],'source_helpers':{str(p):sha(p) for p in files},'actual_CP5_and_public_head_evidence':evidence,'scope':r['scope'],'unlike_Patriot_source_version_conflicts':'.1/+100 and disableOverride1/maxStack-1 commander attrs retain independent parent contributions, unlike .2/+200/max1 Patriot. Original marker identity remains exact shared max1. Native missing body/stacking/self/disabled getter semantics declared replaceable policy, not inferred general proof.','old_7696_author4_evidence_not_migrated':{'path':str(ROOT/'validation/campaign/chapter07_global_support_v1.log'),'sha':sha(ROOT/'validation/campaign/chapter07_global_support_v1.log')},'independent_reviewed':False,'primary_modified':False,'new_core_changed':False,'whole_stage_executed':False,'client_verified':False};out=OUT/'freeze.json';out.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out)}))
if __name__=='__main__':main()
