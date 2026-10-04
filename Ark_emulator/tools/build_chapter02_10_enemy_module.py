"""Exact 2-10 table/AB variants and explicit reference AoE policy; no stage flattening."""
import argparse,json,hashlib
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'packages/campaign/chapter02_units/main_02-10.enemies.reference_module.json'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
FILES={'source':'packages/campaign/chapter02_sources/native.reference.json','projectiles':'packages/campaign/chapter02_behavior/projectiles.partial.json','boss':'packages/campaign/chapter02_behavior/reference50/skulsr.model.json','status':'packages/campaign/chapter02_units/defdrn.status.m42.model.json','boxes':'packages/campaign/chapter02_behavior/aoemag.physics.reference.json'}
PINS={'source':'97447895b3edc69f0f60113ea96bc240c25c0fe980897614e93a94dd75e0d492','projectiles':'d1b8929579a01d2a3e1cc246eccb5f1a7f05fadd9a2d627b972c27874fca979b','boss':'7cdd091a4ce55f73f40a591dc7eb87f54e135afacfeaf1f33b71f2e04d8c2b6a','status':'5d2127bacff398b667120d26a1f09d7032b4ec0cf19a4bc9801d4c6446569a53'}
def standard_state(motion):return {'side':1,'motion':2 if motion=='FLY' else 1,'category':1,'profession':0,'unit_type':1,'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[],'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False}
def build(aoemag_primary_policy='reference_2.2'):
 from tools.campaign_content_composition import reachable_content,compose_modules
 if aoemag_primary_policy not in ['reference_2.2','source_point_circle']:raise ValueError('Explicit Aoemag primary range policy required')
 data={};locks={}
 for key,name in FILES.items():
  raw=(ROOT/name).read_bytes();value=hashlib.sha256(raw).hexdigest()
  if key in PINS and value!=PINS[key]:raise ValueError('Frozen dependency drift: '+name)
  data[key]=json.loads(raw);locks[name]=value
 native=data['source'];stage=native['stages']['level_main_02-10'];vids=stage['resolved_variant_ids']
 # Verify the actual fixed assets/tables behind the frozen extracted PPtr graph.
 identities={}
 def lock_records(value):
  if isinstance(value,dict):
   if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):identities[value['path']]=value['sha256']
   for child in value.values():lock_records(child)
  elif isinstance(value,list):
   for child in value:lock_records(child)
 lock_records(native)
 for name,pin in identities.items():
  target=ROOT.parent/name
  if sha(target)!=pin:raise ValueError('Actual raw source bytes drift: '+name)
 locks.update({str((ROOT.parent/name).resolve()):pin for name,pin in identities.items()})
 if len(vids)!=12:raise ValueError('Actual twelve variants required')
 projectile_units=[u for u in data['projectiles']['entities'] if u['metadata']['native_variant'] in vids and any(key in u['id'] for key in ['enemy_1011_wizard','enemy_1028_mocock'])]
 scene=lambda rows:{'id':'scene/closure/2_10','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':30,'cols':20},'initialEntities':[{'definition':u['id'],'position':{'row':i*2,'col':1}} for i,u in enumerate(rows)]}
 projectiles,_=reachable_content(scene(projectile_units),[('frozen_projectiles',data['projectiles'])]);projectiles.pop('scenarioDraft')
 authored={'schemaVersion':2,'entities':[],'abilities':[],'selectors':[],'behaviors':[],'rules':[{'id':'rule/ch2_10/steering','kind':'rule','contract':'movement.steering','implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}},{'id':'rule/ch2_10/cross_cells','kind':'rule','contract':'area.members','implementation':{'type':'provider','provider':'ark.area.cell_offsets'}},{'id':'rule/ch2_10/combat_priority','kind':'rule','contract':'targeting.score','implementation':{'type':'expression','expression':"(-1000000 if 'blocked_by' in inputs.source.components.runtime and inputs.source.components.runtime.blocked_by == inputs.candidate.id else 0) - 100000 * (inputs.candidate.components.attributes.base.taunt_level if 'taunt_level' in inputs.candidate.components.attributes.base else 0) + inputs.distance"},'metadata':{'profile':'Apply only to an explicitly source-bound combat INPUT_TARGET2 ability; blocked target first then declared base taunt/distance/stable-ID model, native comparator pending'}}]}
 reusable=[('projectiles',projectiles),('boss',data['boss']),('status',data['status'])];defs,_=compose_modules(reusable);replacements={};rows=[]
 for vid in vids:
  v=native['variants'][vid];resolved=v['native_enemy']['resolved'];a=resolved['attributes'];root=next(c['raw'] for c in v['components'].values() if c['native_class']=='Enemy');mover=next(c['raw'] for c in v['components'].values() if c['native_class']=='MoveController');name=v['native_enemy']['native_id'];modes=v['modes']
  if a.get('hpRecoveryPerSec')!=0 or a.get('spRecoveryPerSec')!=0 or a.get('stunImmune') is not False:raise ValueError('Nonzero regen or stun immunity needs explicit consumer: '+vid)
  if root['_delayToBorn']!=0:raise ValueError('Unexpected born delay needs an actual born module: '+vid)
  if root.get('_commonAbilities') or root.get('_generalAbilities') or root.get('_activeBuffs'):raise ValueError('Additional root abilities/buffs require consumer: '+vid)
  matches=[u for u in defs.values() if u['kind']=='entity' and u.get('metadata',{}).get('native_variant',u.get('metadata',{}).get('native_variant_id'))==vid]
  if matches:unit=deepcopy(matches[0]);consumer='reused exact selected source module'
  else:
   if len(modes)!=1:raise ValueError('Unexpected multimode ordinary unit: '+vid)
   mode=modes[0];node=mode['nodes']['_combat'];raw=node['raw'];assert node['native_class']=='MeleeAttack' and raw['_atkScale']==1 and raw['_damageType'] in [1,2] and raw['_extraDamageType']==0 and raw['_epDamageRatio']==0 and not raw['_activeBuffs']
   suffix=name+'/'+vid.split('/')[-1];uid='unit/chapter02/'+suffix;sid='selector/ch2_10/'+suffix;aid='ability/ch2_10/'+suffix;bid='behavior/ch2_10/'+suffix
   unit={'id':uid,'kind':'entity','tags':['enemy','ground'],'metadata':{'native_variant':vid,'native_category':1},'components':{'attributes':{'base':{'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],'move_speed':a['moveSpeed'],'attack_interval':a['baseAttackTime'],'attack_speed_ratio':a['attackSpeed']/100}},'resources':{'hp':{'initial':a['maxHp'],'capacity':a['maxHp'],'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[aid],'behavior':{'machine':bid}}}
   selector={'id':sid,'kind':'selector','region':{'type':'all','blocked_only':True},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1};timeline=[];policy={'target_key':'normal','blocked_target':True,'stop_on_target':False,'stop_cast_groups':['normal']}
   if name=='enemy_1018_aoemag':
    boxes=data['boxes']['colliders'];sizes=[b['source_collider']['raw']['m_Size'] for b in boxes];assert sorted((b['x'],b['y']) for b in sizes)==[(1,3),(3,1)]
    assert raw['_waitForAttackEvent']==0 and raw['_preDelay']==0.6669999957084656 and raw['_alwaysIncludeTarget']==1
    trigger=mode['nodes']['_attackTrigger']['raw'];go=trigger['m_GameObject']['m_PathID'];cfgs=[c for c in v['components'].values() if c['native_class']=='AdvancedSelector' and c['raw']['m_GameObject']['m_PathID']==go];assert len(cfgs)==1
    circles=[g for g in native['prefabs'][name]['geometry_sources'] if g['gameobject_path_id']==go and g['unity_type']=='CircleCollider2D'];assert len(circles)==1
    radius=2.2 if aoemag_primary_policy=='reference_2.2' else circles[0]['raw']['m_Radius'];defaults=standard_state('WALK');defaults['side']=0
    selector.update(region={'type':'radius','radius':radius},eligibility={'rule':'rule/chapter02/qualification','parameters':{'source_configuration':cfgs[0]['raw'],'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':defaults}},metadata={'native_selector_pointer':cfgs[0]['path_id'] if 'path_id' in cfgs[0] else next(k for k,c in v['components'].items() if c==cfgs[0]),'source_radius':circles[0]['raw']['m_Radius'],'declared_primary_radius':radius,'primary_range_policy':aoemag_primary_policy})
    timeline=[{'at_seconds':raw['_preDelay'],'effect':{'op':'area','center':'target','membership_rule':'rule/ch2_10/cross_cells','parameters':{'offsets':[[0,0],[-1,0],[1,0],[0,-1],[0,1]]},'filters':[{'tag':'player'},{'state':'alive'}],'effects':[{'op':'damage','damage_type':'arts','scale':raw['_atkScale'],'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}]}}]
    policy={'target_key':'normal','stop_on_target':True,'stop_cast_groups':['normal']};consumer='declared reference target-centered cross5 from source two boxes, preDelay21 not OnAttack24'
   else:
    if resolved.get('talentBlackboard'):raise ValueError('Unconsumed ordinary talent BB: '+vid)
    if raw['_waitForAttackEvent']!=1:raise ValueError('Unknown ordinary attack clock')
    events=[e for e in node['animation_binding']['events'] if e['name']=='OnAttack'];assert len(events)==1
    timeline=[{'at_seconds':events[0]['seconds'],'effect':{'op':'damage','damage_type':'physical' if raw['_damageType']==1 else 'arts','scale':raw['_atkScale'],'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}}];consumer='blocked INPUT_TARGET melee, source exact OnAttack frame'
   authored['selectors'].append(selector);authored['abilities'].append({'id':aid,'kind':'ability','selector':sid,'activation':{'mode':'automatic_attack','parameters':{'auto_only':True}},'timeline':timeline,**({'rules':{'targeting.score':'rule/ch2_10/combat_priority'}} if name=='enemy_1018_aoemag' else {}),'metadata':{'source_combat':node,'clock_policy':consumer}});authored['behaviors'].append({'id':bid,'kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'normal','selector':sid}],'cast_groups':[{'key':'normal','abilities':[aid]}],'parameters':policy}]}})
   authored['entities'].append(unit)
  unit['components']['spatial'].update(motion_mode=1 if resolved['motion']=='FLY' else 0,steering={'rule':'rule/ch2_10/steering','parameters':{'response_factor':mover['_steeringFactor'],'max_acceleration':mover['_maxSteeringForce'],'arrival_radius':.05}});unit['components']['selection_state']=standard_state(resolved['motion']);unit['components']['attributes']['base']['block_cost']=root['_blockVolume'];unit['components']['lifecycle']['leak_loss']=resolved['lifePointReduce']
  if 'massLevel' in a:unit['components']['attributes']['base']['mass_level']=a['massLevel']
  elif not unit.get('metadata',{}).get('declared_mass_policy'):raise ValueError('Undefined mass must remain explicit')
  unit['metadata'].update(native_reference=v['native_reference'],reference_state_policy='source fixed motion/category-default1/side-enemy1 plus explicit ordinary status defaults; getters remain feedback',zero_recovery_stun_policy='source0/0/False guarded; no driver needed for0')
  if matches and len(modes)==1 and modes[0]['nodes'].get('_combat',{}).get('native_class')=='RangedAttack':
   combat=modes[0]['nodes']['_combat'];assert combat['raw']['_selectTargetSource']==2
   for identifier in unit['components']['abilities']:
    ability=deepcopy(defs[identifier]);ability.setdefault('rules',{})['targeting.score']='rule/ch2_10/combat_priority';ability.setdefault('metadata',{})['combat_input_target_source']=combat
    replacements[identifier]={'definition':ability,'reason':'Actual combat RangedAttack INPUT_TARGET2 shares attack packet but must consume existing blocker; unblocked taunt/distance remains explicit model comparator','source':FILES['source']+' sha256 '+locks[FILES['source']]}
  if matches:replacements[unit['id']]={'definition':unit,'reason':'Exact stage table/prefab mover, typed motion/status and source leak/mass/block; no selected ability replacement','source':FILES['source']+' sha256 '+locks[FILES['source']]}
  else:authored['entities'][-1]=unit
  actions=[x for x in stage['spawn_sources'] if vid in x['variant_candidates']];assert all(x['variant_candidates']==[vid] for x in actions)
  rows.append({'variant_id':vid,'native_reference':v['native_reference'],'native_motion':resolved['motion'],'unit_definition':unit['id'],'spawn_count':sum(x['native']['count'] for x in actions),'consumer':consumer,'owned_abilities':unit['components']['abilities'],'source_root':root,'source_mover':mover,'source_attributes':a,'source_modes':modes,'source_talent_blackboard':resolved.get('talentBlackboard',[])})
 modules=[*reusable,('ordinary_generated',authored)];all_defs,_=compose_modules(modules,replacements);units=[all_defs[r['unit_definition']] for r in rows];p,report=reachable_content(scene(units),modules,replacements,manifest_id='package/chapter02/main_02-10/enemies/reference')
 p.pop('scenarioDraft');meta=p['manifest']['metadata'];meta.update(stage='level_main_02-10',source_locks=locks,builder_sha256=sha(__file__),variant_bindings=rows,source_stats_policy='exact selected DB refs/level/overrides, no generic page stat substitution',aoemag_reference={'url':'https://prts.wiki/w/高阶术师','checked_date':'2026-10-03','rule':'target and its four neighbor cells all allied units; standard display radius2.2','source_radius':2.0999999046325684,'selected_policy':aoemag_primary_policy,'axes':'declared target-centered row/col cross union; source Unity XY/attachment-body mapping not reconstructed'},model_delivery_ready=True,stage_executed=False,client_verified=False,formal_approved=False,required_core_features=['M45 synchronous reentry','M46 area.members'],feedback_pending=['source methodbody/default selector ownership/type getters','aoemag boxXY/body overlap to cell/target-anchor mapping','source2.1 versus reference2.2 primary radius','existing birth0/mover unscaled authored clocks .05 arrival model','defdrn undefined mass0 fallback','Skullshatterer serialized40/DB-reference50 feedback'],remaining_stage=['native timeline/routes/options/runes and stage fields/fixed12 commands/full runthrough'])
 return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--aoemag-primary-policy',default='reference_2.2',choices=['reference_2.2','source_point_circle']);a=ap.parse_args();p=build(a.aoemag_primary_policy);raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode();OUT.parent.mkdir(parents=True,exist_ok=True)
 if a.check:assert OUT.read_bytes()==raw
 else:OUT.write_bytes(raw)
 print(json.dumps({'passed':True,'sha256':sha(OUT),'variants':len(p['manifest']['metadata']['variant_bindings']),'definitions':len(p['definitions'])}))
