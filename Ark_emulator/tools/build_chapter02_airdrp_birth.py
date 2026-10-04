"""Birth clock is an explicit model policy; old post-born source stays frozen."""
from pathlib import Path
from copy import deepcopy
import json,hashlib,argparse
ROOT=Path(__file__).resolve().parents[1];PARENT=ROOT/'packages/campaign/chapter02_units/airdrp.post_born.partial.json';OUT=ROOT/'packages/campaign/chapter02_units/airdrp.birth.model.json';PIN='5ffcd1847eb87eba8830b5001a6fd6b386946f55eafd0c4e65684575c9e60f4b'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build(targetability,block_cost):
 if targetability not in ('targetable','target_free_eligibility'):raise ValueError('explicit birth targetability policy required')
 if type(block_cost) is not int or block_cost not in (0,1):raise ValueError('explicit birth block_cost model policy0 or1 required')
 assert sha(PARENT)==PIN;p=json.loads(PARENT.read_bytes());p['buffs']=[]
 for unit,record in zip(p['entities'],p['manifest']['metadata']['exact_stage_variant_bindings']):
  root=record['native_root'];duration=root['_delayToBorn'];assert duration==1.5 and root['_onlyDelayToBornOnTileStart']==0
  bid='buff/birth/'+record['variant_id'].replace('@','/level_')
  p['buffs'].append({'id':bid,'kind':'buff','duration_seconds':duration,'control':{'move':False,'attack':False,'abilities':False},'modifiers':[{'attribute':'block_cost','layer':'flat','value':block_cost-unit['components']['attributes']['base']['block_cost']}],'selection_flags':{'target_free':targetability=='target_free_eligibility'},'on_remove':[{'op':'emit','event':'enemy.birth_phase_finished','payload':{'native_variant_id':record['variant_id'],'duration_seconds':duration,'targetability_policy':targetability,'birth_block_cost':block_cost}}],'metadata':{'declared_birth_phase':True,'native_callback_verified':False}})
  unit['components']['buffs']={'initial':[bid]};unit['metadata']['post_born_model_only']=False;unit['metadata']['birth_model_policy']={'duration_seconds':duration,'begin':'entity creation at actual wave spawn; no upfront registration','movement_attack_abilities':'paused on[created,created+45tick)','targetability':targetability,'birth_block_cost':block_cost,'blocking_relation':'may hold relation at0 cost; no blocker capacity consumed until expiry; native relation timing awaits feedback','visibility':'visible/no route_hidden change, declared policy'}
 meta=p['manifest']['metadata'];meta['parent_post_born_sha256']=PIN;meta['birth_builder_sha256']=sha(__file__);meta['model_gaps']=[g for g in meta['model_gaps'] if not g.startswith('source delayToBorn')];meta['model_delivery_ready_for_declared_policy']=True
 meta['feedback_pending']=meta['client_pending']+['birth targetability/block relation/visible timing policy','target_free option only guaranteed for eligibility-configured external selectors; unconfigured selectors are not silently claimed covered']
 meta['source_locks']['packages/campaign/chapter02_units/airdrp.post_born.partial.json']=PIN
 meta['status']='source_bound_units_with_explicit_birth_and_combat_model';meta['current_goal_gate']='Complete simulation under declared reference/table policies; later user comparison separate, no client-body admission gate';p['manifest']['id']+='/birth45/'+targetability+'/'+str(block_cost)
 return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--targetability',required=True,choices=['targetable','target_free_eligibility']);ap.add_argument('--block-cost',required=True,type=int,choices=[0,1]);ap.add_argument('--check',action='store_true');a=ap.parse_args();p=build(a.targetability,a.block_cost);b=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode()
 if a.check:assert OUT.read_bytes()==b
 else:OUT.write_bytes(b)
 print(json.dumps({'passed':True,'check':a.check,'sha256':sha(OUT),'targetability':a.targetability,'birth_cost':a.block_cost}))
