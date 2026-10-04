"""Read-only exact native 7-17 source and existing prefix review; rejects nonlife changes."""
import json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def exact(a,b):
 if type(a)!=type(b):return False
 if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
 if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
 return a==b
def only_life(parent,child):
 c=deepcopy(child)
 try:
  for field in ['initial','capacity']:c['scenarioDraft']['resources']['life'][field]=parent['scenarioDraft']['resources']['life'][field]
 except KeyError:return False
 return exact(parent,c)
def main():
 draft=ROOT/'packages/campaign/chapter07_stage_models/level_main_07-15.native_draft.v2.json';plan=ROOT/'packages/campaign/chapter07_plans/source.plan.json';roster=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json';prefix=ROOT/'validation/campaign/chapter07_join_prefix_v1/verification.json';cp=prefix.parent/'source200.json';rp=prefix.parent/'replay.json';a=json.loads(draft.read_bytes());n=json.loads(plan.read_bytes())['stages']['level_main_07-15']['native_document'];s=a['scenarioDraft'];r=json.loads(roster.read_bytes());pr=json.loads(prefix.read_bytes());assert pr['passed'] and pr['source_package_sha']=='77d416b5c848194582ec30383acfc53159f5296f527938781fc4ac0fc09decbe' and pr['checkpoint_sha']==sha(cp);assert pr['events']==60605;assert exact(s['roster'],r['manifest']['metadata']['roster']) and len(s['roster'])==12;assert exact(a['manifest']['metadata']['native_options'],n['options']);assert exact(a['manifest']['metadata']['native_predefines'],n['predefines']);assert exact([x['raw'] for x in s['metadata']['rune_policy']],n['runes']) and all(x['difficulty_bit']==1 and x['active'] is False for x in s['metadata']['rune_policy']);assert s['seed']==n['randomSeed'];assert s['resources']['life']['initial']==3 and s['resources']['dp']['initial']==10 and s['parameters']['deploy_capacity']==9
 from tools.chapter06_review.stage_converter_v6 import route_ir,map_plan
 assert exact(s['map']['tiles'],map_plan(n)['tiles']);actual=[]
 for wi,w in enumerate(s['timeline']['waves']):
  assert w['pre_delay_seconds']==n['waves'][wi]['preDelay'] and w['post_delay_seconds']==n['waves'][wi]['postDelay']
  for fi,f in enumerate(w['fragments']):
   for x in f['actions']:
    raw=x['metadata']['native_action'];ai=x['metadata']['native_action_index'];assert exact(raw,n['waves'][wi]['fragments'][fi]['actions'][ai]);
    if x['kind']=='spawn':
     actual.append(x);assert exact(x['spawn']['route'],route_ir(n['routes'][raw['routeIndex']],len(n['mapData']['map'])))
 assert sum(x['count'] for x in actual)==37
 source=json.loads((ROOT/'packages/campaign/chapter07_sources/native.reference.json').read_bytes());defs={d['id']:d for d in a['definitions']};variants=a['manifest']['metadata']['variant_bindings'];assert len(variants)==6
 for v in variants:
  raw=source['variants'][v['variant_id']]['native_enemy']['resolved']['attributes'];unit=defs[v['unit']]
  for dst,src in {'max_hp':'maxHp','atk':'atk','def':'def','mres':'magicResistance','move_speed':'moveSpeed','attack_interval':'baseAttackTime'}.items():assert unit['components']['attributes']['base'][dst]==raw[src]
  assert unit['components']['resources']['hp']['initial']==raw['maxHp']
 ov=ROOT/'packages/campaign/chapter07_stage_models/level_main_07-15.native_draft.v2.life99999.strict_v2.json';originalOverlay=json.loads(ov.read_bytes());restored=deepcopy(originalOverlay);goal=restored['manifest']['metadata'].pop('goal_base_life_authoring');profile=restored['scenarioDraft']['metadata'].pop('runthrough_profile');assert goal['native']=={'initial':3,'capacity':3} and goal['selected_initial']==goal['selected_capacity']==99999 and profile['base_life']==99999 and exact(profile['fixed12'],s['roster']);assert originalOverlay['scenarioDraft']['resources']['life']=={'initial':99999,'capacity':99999};assert only_life(a,restored)
 negative=[];overlay=deepcopy(a)
 for field in ['initial','capacity']:overlay['scenarioDraft']['resources']['life'][field]=99999
 assert only_life(a,overlay)
 paths=[('HP',['definitions',next(i for i,d in enumerate(a['definitions']) if d['kind']=='entity'),'components','resources','hp','initial']),('clock',['scenarioDraft','timeline','waves',0,'pre_delay_seconds']),('DP',['scenarioDraft','resources','dp','initial']),('seed',['scenarioDraft','seed']),('route',['scenarioDraft','timeline','waves',0,'fragments',0,'actions',0,'metadata','native_action','count'])]
 for label,path in paths:
  bad=deepcopy(overlay);node=bad
  for key in path[:-1]:node=node[key]
  node[path[-1]]+=1;assert not only_life(a,bad);negative.append(label)
 files=[draft,plan,roster,prefix,cp,rp,ov,ROOT/'packages/campaign/chapter07_sources/native.reference.json',Path(__file__)];pins={str(p):sha(p) for p in files};out=ROOT/'validation/campaign/chapter07_717_readonly_review_v4/verification.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();rep={'passed':True,'source_pins':pins,'native_births':37,'new3992_overlay_restored_exact':True,'new3992_native_HP_checked_variants':6,'prefix_identity_historical4f16':True,'prefix_actual600_births':1,'prefix_events':60605,'native_routes_all_actions_type_exact':True,'native_runes':n['runes'],'roster12_exact':True,'only_life_mutation_negatives':negative,'scope':'Read-only structural source review and existing exact CP/replay source binding. No source module accuracy admission, no old4f16 process migrated to3992, no new full stage execution.','whole_stage_executed':False};out.write_text(json.dumps(rep,indent=2)+'\n',encoding='utf8');print(sha(out))
if __name__=='__main__':main()
