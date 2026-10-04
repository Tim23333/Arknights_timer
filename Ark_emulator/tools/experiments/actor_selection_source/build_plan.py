import json,hashlib,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];SOURCE=ROOT/'packages/campaign/actor_selection_source/source.reference.json';OUT=SOURCE.with_name('binding.plan.json');PIN='28d8422dd06ff6ade085ce96786cc755c2c955df06695ffe750f5b4c3f00562c';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build():
 assert sha(SOURCE)==PIN;s=json.loads(SOURCE.read_bytes());assert s['defaults_used'] is False and len(s['actors'])==20
 for path,pin in s['source_locks'].items():assert sha(Path(path))==pin
 rows=[]
 for a in s['actors']:
  known={k:v['value'] for k,v in a['source_known_bindings'].items()};unknown=list(a['unknown_bindings']);assert not set(known)&set(unknown)
  rows.append({'actor_id':a['actor_id'],'source_literal_selection_state_patch':known,'source_field_provenance':a['source_known_bindings'],'prefab_source':a['prefab_source'],'unknown_fields':unknown,'runnable_complete_state':False,'native_client_verified':False,'version_pending':a['source_version_pending'],'math_profile_required_if_used':'do not fill missing category/side/unit_type/status from M25 probe defaults or identifier prefix'})
 assert next(r for r in rows if r['actor_id']=='token_10009_weedy_cannon')['source_literal_selection_state_patch']['category']==2
 bird=next(r for r in rows if r['actor_id']=='token_10003_cgbird_bird');assert 'category' in bird['unknown_fields'] and 'side' in bird['unknown_fields'] and 'unit_type' in bird['unknown_fields']
 assert next(r for r in rows if r['actor_id']=='trap_002_emp')['source_literal_selection_state_patch']['profession']==256
 return {'schema':'ark-sim/actor-selection-sparse-binding-plan/v1','source_sha256':PIN,'builder_sha256':sha(Path(__file__)),'actors':rows,'defaults_applied':False,'runtime_inputs_modified':False,'runtime_identity_target':'M26 7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe only after future explicit wrapper/identity verification','selector_source_records':s['native_selector_source'],'future_binding_steps':['use exact owned ability->native UnitMode/trigger/sameGO selector chain, or exact RangedAttack._selector PPtr; never prefab dictionary ordering','link source flags only after root GameObject/PPtr closure and selected skill/talent/mode trigger/lifetime evidence; whole asset list is not an active writer','map abnormal enum indices to Buff.selection_flags only for proven source contribution and exact half-open profile; no stun->targetfree derivation','bind selector eligibility rule with exact targeting.eligibility contract, and pure geometry rule with selector.eligibility contract; capability dependencies must actually reach them','any current enabled source field consuming unknown target state needs explicit mathematical policy marked client_pending or native raw-state/body comparator; no actual accuracy approval based on defaults'],'formal_approval':False}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode()
 if args.check:assert OUT.read_bytes()==raw
 else:OUT.write_bytes(raw)
 print(json.dumps({'passed':True,'check':args.check,'actors':20,'sha256':sha(OUT),'defaults_applied':False}))
