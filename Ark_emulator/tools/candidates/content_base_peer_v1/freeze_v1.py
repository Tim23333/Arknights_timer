"""Independent peer receipt for Root three deltas; no self-review promotion claim."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/content_base_peer_freeze_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 report=ROOT/'validation/campaign/content_base_peer_guarded_v1/verification.json';r=json.loads(report.read_bytes());assert r['passed'] and r['actual_exit']==0 and r['source_before']==r['source_after'];assert all(sha(Path(f))==h for f,h in r['source_after'].items());assert not OUT.exists();OUT.mkdir(parents=True);helpers=list(Path(__file__).parent.glob('*.py'));evidence=[]
 for p in helpers:
  dst=OUT/'source'/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);assert sha(p)==sha(dst)
 for name in ('content_base_peer_guarded_final_v3','content_base_tile_peer_guarded_v2'):
  for p in (ROOT/'validation/campaign'/name).glob('*'):
   if p.is_file():evidence.append({'path':str(p),'sha':sha(p),'bytes':p.stat().st_size})
 old=ROOT/'validation/campaign/content_base_peer_no_source_v1.log';result={'core':r['core'],'peer_report':{'path':str(report),'sha':sha(report),'actual_exit':0,'elapsed':r['elapsed'],'cases':25},'guarded_runtime_source_before':r['source_before'],'guarded_runtime_source_after':r['source_after'],'helper_pins':{str(p):sha(p) for p in helpers},'actual_disk_CP_and_public_head_evidence':evidence,'historical_draft_contract_failure':{'path':str(old),'sha':sha(old)},'reviewed_delta_files':r['reviewed_delta_files'],'own_buffApplication_not_self_peer':True,'Root_probe_not_imported':True,'scope':r['scope'],'full_suite_passed':False,'full_baseline_passed':False,'whole_stage_executed':False,'client_verified':False,'primary_modified':False};out=OUT/'freeze.json';out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'freeze_sha':sha(out),'peer25_actual':True}))
if __name__=='__main__':main()
