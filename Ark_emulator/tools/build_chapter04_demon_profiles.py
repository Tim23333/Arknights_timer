"""Explicit data-selectable demon animation branch profiles, no native dispatch inference."""
import argparse,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'packages/campaign/chapter04_sources/native.reference.json';PIN='3e392d80d000e27a50f11f2f33b0fa0f6be35dc1e91d7e321e2b9cf9681c4603';OUT=ROOT/'packages/campaign/chapter04_units/demon_profiles';VID='enemy_1010_demon@0/b6763feff65e5ee5';UID='unit/ch4/enemy_1010_demon/b6763feff65e5ee5'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build(policy):
 if policy not in ('with_pre_only','no_pre_only'):raise ValueError('Explicit known demon branch_policy is required')
 raw=SOURCE.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('Frozen demon source drift')
 s=json.loads(raw);v=s['variants'][VID];a=v['native_enemy']['resolved']['attributes'];resolved=v['native_enemy']['resolved'];n=v['modes'][0]['nodes']['_combat'];r=n['raw'];drivers=v['additional_animation_drivers']
 if len(drivers)!=1 or drivers[0]['native_class']!='NoPreOneshotAnimation' or n['native_class']!='MeleeAttack':raise ValueError('Demon exact PPtr class closure changed')
 d=drivers[0];dr=d['raw'];choice='_animWithPre' if policy=='with_pre_only' else '_animNoPre';binding=d['bindings'][choice];events=[e for e in binding['events'] if e['name']=='OnAttack']
 if dr['_animWithPre']!='Attack' or dr['_animNoPre']!='Attack_NoPre' or dr['_endAnim']!='Attack_Idle' or dr['_maxAnimScale']!=1 or len(events)!=1:raise ValueError('Branch source changed')
 if [d['bindings'][k]['events'][0]['frame'] for k in ('_animWithPre','_animNoPre')]!=[27,15] or d['bindings']['_endAnim']['events']:raise ValueError('Branch frames changed')
 if r['_animKey']!='' or r['_waitForAttackEvent']!=1 or r['_selectTargetSource']!=2 or r['_damageType']!=1 or r['_atkScale']!=1 or r['_activeBuffs'] or r['_extraDamageType'] or r['_epDamageRatio']:raise ValueError('Combat consumer changed')
 pf=s['prefabs'][v['prefab_key']];root=next(x['raw'] for x in pf['components'].values() if x['native_class']=='Enemy');mover=next(x['raw'] for x in pf['components'].values() if x['native_class']=='MoveController')
 if resolved['motion']!='WALK' or root['_delayToBorn']!=0 or a['hpRecoveryPerSec']!=0 or a['spRecoveryPerSec']!=0 or a['stunImmune'] is not False or v['passive_and_skill_components']:raise ValueError('Extra source dependency needs consumer')
 aid='ability/'+UID;sid='selector/'+UID;bid='behavior/'+UID
 base={'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],'move_speed':a['moveSpeed'],'attack_interval':a['baseAttackTime'],'attack_speed_ratio':a['attackSpeed']/100,'mass_level':a['massLevel'],'block_cost':root['_blockVolume']}
 p={'schemaVersion':2,'manifest':{'id':'package/ch4/demon/'+policy,'requires':['preset/ark_standard'],'metadata':{'builder_sha256':sha(__file__),'source_locks':{'packages/campaign/chapter04_sources/native.reference.json':PIN},'branch_policy':policy,'client_verified':False,'native_dispatch_pending':True,'animation_finish_policy':'Declared full authored branch duration; Attack_Idle visual return/body pending','variant_bindings':[{'variant_id':VID,'unit_definition':UID,'native_reference':v['native_reference'],'native_motion':resolved['motion'],'source_enemy_root':root,'source_mover':mover}],'raw_animation_driver':d,'raw_combat':n,'reference':{'url':'https://prts.wiki/w/萨卡兹大剑手','checked_date':'2026-10-03','scope':'Ground melee physical, standard level0 7500/600/230/50/interval2; no published branch dispatch condition','source_priority':'Fixed exact DB variant; website is reference cross-check'}}},'entities':[{'id':UID,'kind':'entity','tags':['enemy','ground'],'components':{'attributes':{'base':base},'resources':{'hp':{'initial':a['maxHp'],'capacity':a['maxHp'],'role':'health'}},'spatial':{'motion_mode':0,'steering':{'rule':'rule/ch4/demon_steering','parameters':{'response_factor':mover['_steeringFactor'],'max_acceleration':mover['_maxSteeringForce'],'arrival_radius':.05}}},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2},'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':resolved['lifePointReduce']},'abilities':[aid],'behavior':{'machine':bid}},'metadata':{'native_variant_id':VID,'native_reference':v['native_reference']}}],
 'abilities':[{'id':aid,'kind':'ability','selector':sid,'activation':{'mode':'automatic_attack','parameters':{'auto_only':True}},'target_capture':'at_cast','timeline':[{'at_seconds':events[0]['seconds'],'effect':{'op':'damage','damage_type':'physical','scale':1,'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}},{'at_seconds':binding['duration']['seconds'],'effect':{'op':'emit','event':'model.animation_branch_elapsed','parameters':{'branch_policy':policy}}}],'metadata':{'source_driver_path_id':d['path_id'],'branch_binding':binding,'source_combat_path_id':n['path_id']}}],
 'selectors':[{'id':sid,'kind':'selector','region':{'type':'all','blocked_only':True},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1}],
 'behaviors':[{'id':bid,'kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'normal','selector':sid}],'cast_groups':[{'key':'normal','abilities':[aid]}],'parameters':{'target_key':'normal','blocked_target':True,'stop_on_target':False,'stop_cast_groups':['normal']}}]}}],
 'rules':[{'id':'rule/ch4/demon_steering','kind':'rule','contract':'movement.steering','implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}}]}
 return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
 for policy in ('with_pre_only','no_pre_only'):
  p=build(policy);raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode();path=OUT/(policy+'.model.json')
  if args.check:
   if path.read_bytes()!=raw:raise ValueError('Demon profile output changed')
  else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
  print(json.dumps({'policy':policy,'sha256':hashlib.sha256(raw).hexdigest()}))
