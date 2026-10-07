"""Two ranged variant raw-source closure and unresolved consumer contracts only."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter07_ranged_preparation_freeze_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 profile=ROOT/'packages/campaign/chapter07_ranged_preparation/source.profile.v3.json';report=ROOT/'validation/campaign/chapter07_ranged_preparation_v3/audit.json';r=json.loads(report.read_bytes());assert r['passed'] and r['source_before']==r['source_after'] and r['profile_sha']==sha(profile);assert all(sha(Path(f))==h for f,h in r['source_after'].items());p=json.loads(profile.read_bytes());assert [len(x['all_source_modes']) for x in p['two_exact_variants']]==[2,1];assert [x['per_mode_OnAttack_frames'] for x in p['two_exact_variants']]==[[[21],[21]],[[16]]];assert not OUT.exists();OUT.mkdir(parents=True);paths=list(Path(__file__).parent.glob('*.py'))+[profile]
 for f in paths:
  dst=OUT/'source'/f.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dst);assert sha(f)==sha(dst)
 obj={'source_profile':{'path':str(profile),'sha':sha(profile)},'audit':{'path':str(report),'sha':sha(report)},'source_before':r['source_before'],'source_after':r['source_after'],'helpers':{str(f):sha(f) for f in paths},'scope':'Two exact ordinary ranged raw prefabs/selectors/ranges/projectile fullcomponents/BSON/BB/DB/level/SP/source mode closure. sotisp2modes each21 frame; soticn1mode16 frame. No collapsed modes or guessed attackType.','source_version_conflicts':p['source_version_conflicts'],'pending_consumer_contracts':[{'variant':x['variant_id'],'pending':x['pending_execution_contracts']} for x in p['two_exact_variants']],'first_draft_single_mode_assertion_and_relative_asset_path_failures_preserved_helpers':True,'runtime_created':False,'core_modified':False,'stage_created':False,'whole_stage_executed':False,'client_verified':False};out=OUT/'freeze.json';out.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'freeze_sha':sha(out),'source_only':True}))
if __name__=='__main__':main()
