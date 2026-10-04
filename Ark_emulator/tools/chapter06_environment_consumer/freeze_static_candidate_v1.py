"""Three-file candidate source delivery, real native route triple evidence and focused compatibility."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PARENT=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate';CAND=ROOT.parent/'unpack_work/campaign_declared_static_tile_v1_candidate';OUT=ROOT/'validation/campaign/chapter06_environment_candidate_v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 verify=OUT/'verification.json';v=json.loads(verify.read_bytes());assert v['passed'] and v['actual_exit']==0 and v['source_before']==v['source_after'];route=Path('E:/ArkSimEvidence/chapter06_environment_v7/verification.json');r=json.loads(route.read_bytes());assert r['passed'] and r['CP_resume_equal'] and r['public_head_equal'] and r['source_before']==r['source_after'];assert all(sha(Path(p))==h for p,h in r['source_after'].items());refs=[]
 for name,x in r['observations'].items():
  ref=x['export'];p=Path(ref['path']);assert p.stat().st_size==ref['bytes'] and sha(p)==ref['sha256'];refs.append(ref)
 changed=[]
 for p in (CAND/'ark_sim').rglob('*'):
  if p.is_file() and p.suffix in ('.py','.json') and sha(p)!=sha(PARENT/p.relative_to(CAND)):changed.append(p.relative_to(CAND))
 assert len(changed)==3;delta=[]
 for rel in changed:
  p=CAND/rel;copy=OUT/'source_delta'/rel;copy.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,copy);assert sha(p)==sha(copy);delta.append({'path':str(rel),'parent_sha':sha(PARENT/rel),'candidate_sha':sha(p),'archive':str(copy)})
 noopt=OUT/'noopt.json';assert json.loads(noopt.read_bytes())['passed'];a=json.loads(Path('E:/ArkSimEvidence/chapter06_static_noopt_v1/candidate.json').read_bytes());assert a['cases'][0]['snapshot']['state']['damage_dealt']==850 and a['cases'][1]['snapshot']['state']['damage_dealt']==60;record={'candidate_core':v['core'],'parent_core':'a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a','delta':delta,'actual48_focused_checks':{'report':str(verify),'sha':sha(verify),'actual_exit':0},'noopt_actual_all_values':{'report':str(noopt),'sha':sha(noopt),'only_three_snapshot_runtimeFP_plus_topcore_identity':True,'actual_custom850_60':True,'actual_0_1_prefix150':True,'full_baseline0_1':False},'complete_source_route_geometry_proof':{'report':str(route),'sha':sha(route),'actual_exit':0,'actor':'Exact source snsbr HP3400/ATK360/DEF100/move1.1; not Boss mechanics','native_boss_route1_unshortened':True,'all_native_waits_offsets_preserved':True,'end6500':True,'events':69457,'actual_three_complete_logs':refs,'CP500_and_head_all_values_equal':True,'portal_visibility_events':r['actual_portal_visibility_events']},'model_policies':['Generic opt-in source static tile declaration with exact mask/height/BB/effects binding. Unknown tile names without a profile remain rejected.','True ground mask2 blocks WALK and permits FLY; MELEE1 build follows existing deployment contract. Exact clipped border uses existing one-ULP outward profile.','Native Tile prefab empty _data mask0 differs from actual source stage palette FLY_ONLY2/MELEE1. Both raw source operands retained, stage palette consumed; method bodies/client alignment remain unverified.','Portals are native source DISAPPEAR/APPEAR with explicit transition policy; no automatic pairing/teleport inferred.'],'independent_reviewed':False,'source_conflicts_explicit':True,'whole_stage_executed':False,'primary_modified':False,'client_verified':False};out=OUT/'freeze.json';assert not out.exists();out.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out),'delta_files':len(delta),'actual_source_route':True,'independent_pending':True}))
if __name__=='__main__':main()
