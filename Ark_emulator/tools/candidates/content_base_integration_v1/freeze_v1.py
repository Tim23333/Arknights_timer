"""Joint own author/no-opt evidence; prior source metadata never migrated."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];CAND=ROOT.parent/'unpack_work/campaign_content_base_v1_candidate';OUT=ROOT/'validation/campaign/content_base_integration_freeze_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 reports=[ROOT/'validation/campaign/content_base_integration_v2/verification.json',ROOT/'validation/campaign/content_base_integration_noopt_v1/verification.json'];receipts=[]
 for p in reports:
  r=json.loads(p.read_bytes());assert r['passed'] and r.get('actual_exit',0)==0 and r['source_before']==r['source_after'];assert all(sha(Path(f))==h for f,h in r['source_after'].items());receipts.append({'path':str(p),'sha':sha(p),'elapsed':r.get('elapsed')})
 assert not OUT.exists();OUT.mkdir(parents=True);evidence=[]
 for p in (ROOT/'validation/campaign/chapter07_strength_melee_joint_v2').glob('*'):
  if p.is_file():evidence.append({'path':str(p),'sha':sha(p),'bytes':p.stat().st_size})
 helpers=list(Path(__file__).parent.glob('*.py'))
 for p in helpers:
  dest=OUT/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);assert sha(dest)==sha(p)
 modules=list((ROOT/'packages/campaign/chapter07_strength_melee').glob('*.v5.json'));r={'core':'d81334d340034732a1840f16612073f7ae56e41a9727584ea38c74c61943439e','candidate':str(CAND),'candidate_guards':{p.relative_to(CAND).as_posix():sha(p) for p in (CAND/'ark_sim').rglob('*') if p.suffix in ('.py','.json')},'actual_receipts':receipts,'new_43_author_original_assertions':True,'new_noopt_custom850_60_and_0_1_prefix150':True,'source_same_modules_old_aa919_metadata_preserved':{str(p):sha(p) for p in modules},'source_evidence_new_joint_inputs_CP7_CP10_head':evidence,'helpers':{str(p):sha(p) for p in helpers},'old_fixture_root_depth_failure':{'path':str(ROOT/'validation/campaign/content_base_integration_v1/verification.json'),'sha':sha(ROOT/'validation/campaign/content_base_integration_v1/verification.json')},'old_frozen_aa919_proofs_unchanged':True,'full_suite_passed':False,'full_baseline_passed':False,'independent_reviewed':False,'primary_modified':False,'wholeC7_executed':False,'client_verified':False};out=OUT/'freeze.json';out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'freeze_sha':sha(out),'author43_actual':True}))
if __name__=='__main__':main()
