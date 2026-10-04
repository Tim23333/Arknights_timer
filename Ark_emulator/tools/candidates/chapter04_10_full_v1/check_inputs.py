"""Independent prepared-input assertions; no battle state mutation or grants."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate';OUT=ROOT/'validation/campaign/chapter04_10_full_v1'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from tools.build_campaign_runthrough_input import apply
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 r=json.loads((OUT/'prepared.json').read_bytes());assert implementation_digest()==r['core'];source=Path(r['source_package']);overlay=Path(r['overlay_package']);commands_path=Path(r['commands']);native=json.loads(source.read_bytes());run=json.loads(overlay.read_bytes());commands=json.loads(commands_path.read_bytes());scene=run['scenarioDraft'];defs={d['id']:d for d in run['definitions']};original=json.loads(Path(r['original_author_prefix_stage']).read_bytes());before={str(p):sha(p) for p in [source,overlay,commands_path,Path(__file__),ROOT/'tools/build_campaign_runthrough_input.py',ROOT/'tools/build_chapter04_10_stage.py']};restore=deepcopy(native);restore['scenarioDraft']['resources']['life']=original['scenarioDraft']['resources']['life'];restore['manifest']['metadata']['goal_base_life_authoring']=original['manifest']['metadata']['goal_base_life_authoring'];assert restore==original
 assert native['scenarioDraft']['resources']['life']=={'initial':3,'capacity':3} and native['manifest']['metadata']['native_options']['maxLifePoint']==3 and 'goal_base_life_authoring' not in native['manifest']['metadata'];assert run==apply(native,sha(source));assert scene['resources']['dp']['initial']==10 and scene['parameters']['deploy_capacity']==10 and scene['seed']==14705740 and len(scene['roster'])==12
 births=sum(a.get('count',1) for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn');assert births==43 and len(run['manifest']['metadata']['variant_bindings'])==7;Compiler().compile(native);Compiler().compile(run)
 aliases={};deploys=[];owned=[];timeline=[]
 for c in commands:
  assert type(c['at']) is int and c['at']>=0 and c['action'] in ('deploy','skill','withdraw')
  if c['action']=='deploy':
   assert c['entity'] in scene['roster'];alias=c['alias'];assert alias not in aliases;aliases[alias]=c['entity'];unit=defs[c['entity']];idx=c['row']*scene['map']['cols']+c['col'];tile=scene['map']['tiles'][idx];required=1 if unit['components']['deployable']['terrain']=='ground' else 2;assert tile['buildableType']&required;assert tile['tileKey'] not in ('tile_telin','tile_telout');deploys.append({'command':c,'actual_base_tile':tile,'base_cost':unit['components']['attributes']['base']['deploy_cost']});timeline.append((c['at'],alias,1))
  elif c['action']=='skill':
   assert c['source'] in aliases;unit=defs[aliases[c['source']]];assert c['ability'] in unit['components']['abilities'];a=defs[c['ability']];params={**a.get('parameters',{}),**a.get('activation',{}).get('parameters',{})};assert a['activation']['mode']=='manual' and not params.get('auto_only',False)
   if c['ability']=='ability/kalts_summon':
    pos=c['payload']['position'];tile=scene['map']['tiles'][pos['row']*scene['map']['cols']+pos['col']];assert tile['buildableType']&1 and tile['tileKey'] not in ('tile_telin','tile_telout');assert a['activation']['costs']==[{'owner':'battle','resource':'dp','amount':10}];owned.append({'command':c,'base_terrain':tile,'real_cost':10});timeline.append((c['at'],'mon3tr',1))
  else:
   assert c['source'] in aliases;timeline.append((c['at'],c['source'],-1))
   if aliases[c['source']]=='unit/char_003_kalts':timeline.append((c['at'],'mon3tr',-1))
 assert {d['command']['entity'] for d in deploys}==set(scene['roster']) and len(deploys)==12 and len(owned)==1
 active=set();max_own=0
 for at,key,direction in sorted(timeline):
  if direction==1:active.add(key)
  else:active.discard(key)
  max_own=max(max_own,len(active))
 assert max_own<=10
 after={p:sha(Path(p)) for p in before};assert before==after
 result={'role':'Independent native-parent/standard-overlay/command baseline legality check; dynamic RNG tile denial/control/death and real DP/SP admission remain runtime authoritative','core':r['core'],'native_life3_verified':True,'old7b5_preserved':True,'only_native_restoration_fields':['resources.life','goal_base_life_authoring removal'],'overlay_exact_standard_apply':True,'all_combat_definitions_actor_HP_map_DP_slots_seed_timeline_preserved':True,'births':43,'variants':7,'fixed12_deploy_commands':12,'deploy_base_terrain_checks':deploys,'owned_source_public_spawn_checks':owned,'max_nominal_own_slots':max_own,'native_slots':10,'public_auto_only_skill_calls':0,'guard_before':before,'guard_after':after,'full_stage_executed':False};dest=OUT/'input_review.json'
 if dest.exists():raise ValueError('Preserve prior check')
 dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'input_review_sha':sha(dest),'fixed12':12,'max_nominal_slots':max_own,'born':43,'source_sha':sha(source),'overlay_sha':sha(overlay)}))
if __name__=='__main__':main()
