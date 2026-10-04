"""Explicit partial source-backed chapter02 dependencies; full load rejects gaps."""
from pathlib import Path
from copy import deepcopy
import json,hashlib,argparse,sys
ROOT=Path(__file__).resolve().parents[1];RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
SOURCE=ROOT/'packages/campaign/chapter02_sources/native.reference.json';OUT=ROOT/'packages/campaign/chapter02_behavior/projectiles.partial.json'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def build(require_complete=False):
 sys.path.insert(0,str(ROOT));from tools.build_chapter02_behavior_requirements import build as audit
 requirements=audit();d=read(SOURCE)
 # These are source content IDs, not runtime official-ID conditions.
 rows={r['native_enemy']['native_id']:r for r in d['variants'].values()}
 out={'schemaVersion':2,'manifest':{'id':'chapter02/minimum_source_dependencies','requires':['preset/ark_standard'],'metadata':{'status':'partial_declared_math_profile','builder_sha256':sha(__file__),'source_locks':requirements['source_locks'],'source_matrix_sha256':sha(ROOT/'packages/campaign/chapter02_behavior/requirements.reference.json'),'runtime_sha256':'7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe','model_gaps':['aoemag_PhysicsRange_not_authored','skulsr_threshold_LoadData_.4_vs_.5_unresolved','defdrn_silence_driver_and_TargetValidator_adapter','complex_projectile_and_mode_driver_content_pending'],'client_pending':['BB radius2.5 vs collider1 LoadData binding','native permission/comparator/animation scale/callback bodies','source-version alignment'],'actual_game_correct':False,'formal_approved':False}},'entities':[],'abilities':[],'selectors':[],'buffs':[],'behaviors':[],'rules':[]}
 if require_complete:raise ValueError('chapter02 full dependency closure unresolved: source threshold / physics / native behavior')
 for key in ('enemy_1005_yokai','enemy_1005_yokai_2','enemy_1017_defdrn'):
  r=rows[key];a=r['native_enemy']['resolved']['attributes'];uid='unit/chapter02/'+key
  assert r['native_enemy']['resolved']['motion']=='FLY'
  c={'attributes':{'base':{'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],'attack_interval':a['baseAttackTime'],'attack_speed_ratio':a['attackSpeed']/100,'move_speed':a['moveSpeed'],'block_cost':1}},'resources':{'hp':{'initial':a['maxHp'],'capacity':a['maxHp'],'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}
  e={'id':uid,'kind':'entity','tags':['enemy','fly'],'metadata':{'native_category':1,'native_variant':r['variant_id'],'native_motion':'FLY','native_body_verified':False},'components':c};out['entities'].append(e)
  if key!='enemy_1005_yokai_2':
   assert r['modes'][0]['nodes']['_combat']['native_class']=='EmptyAnimatedAbility' and r['modes'][0]['nodes']['_attack']['status']=='native_null'
   e['metadata']['combat_consumer']='explicit no attack; EmptyAnimatedAbility and no attack trigger'
   continue
  mode=r['modes'][0];node=mode['nodes']['_attack'];raw=node['raw'];assert raw['_waitForAttackEvent']==1 and raw['_atkScale']==1 and raw['_damageType']==1
  frames=[x for x in node['animation_binding']['events'] if x['name']=='OnAttack'];assert len(frames)==1 and frames[0]['frame']==8
  trigger=mode['nodes']['_attackTrigger']['raw'];go=trigger['m_GameObject']['m_PathID']
  selectors=[x for x in r['components'].values() if x['native_class']=='AdvancedSelector' and x['raw']['m_GameObject']['m_PathID']==go];assert len(selectors)==1
  circles=[x for x in d['prefabs'][key]['geometry_sources'] if x['gameobject_path_id']==go and x['unity_type']=='CircleCollider2D'];assert len(circles)==1 and circles[0]['raw']['m_Radius']==2
  cfg=selectors[0]['raw'];assert cfg['_maxNum']==1 and cfg['_limitTargetNum']==1
  defaults={'side':0,'motion':1,'category':1,'profession':0,'unit_type':1,'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[],'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False}
  c['selection_state']={**defaults,'side':1,'motion':2}
  sid='selector/chapter02/yokai_2';aid='ability/chapter02/yokai_2';bid='behavior/chapter02/yokai_2'
  out['rules'].append({'id':'rule/chapter02/qualification','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}})
  out['selectors'].append({'id':sid,'kind':'selector','region':{'type':'radius','radius':2},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1,'eligibility':{'rule':'rule/chapter02/qualification','parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':defaults}},'metadata':{'source_trigger_path_id':mode['nodes']['_attackTrigger']['path_id'],'source_combat_path_id':node['path_id'],'collider':circles[0]}})
  out['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'automatic_attack'},'selector':sid,'timeline':[{'at_seconds':frames[0]['seconds'],'effect':{'op':'damage','damage_type':'physical','scale':1}}],'metadata':{'source_frame':frames[0],'source_combat':raw,'timing_profile':'unscaled authored OnAttack; native scaling pending'}})
  out['behaviors'].append({'id':bid,'kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'attack','selector':sid}],'cast_groups':[{'key':'attack','abilities':[aid]}],'parameters':{'target_key':'attack','stop_on_target':True,'stop_cast_groups':['attack']}}]}})
  c['abilities']=[aid];c['behavior']={'machine':bid}
 r=rows['enemy_1017_defdrn'];aura=[x for x in r['components'].values() if x['native_class']=='AuraAbility'];assert len(aura)==1;raw=aura[0]['raw'];assert raw['_selfOption']==2 and raw['_removeBuffWhenTargetLeave']==1 and raw['_removeBuffWhenAbilityDetached']==1
 bb={x['key']:x['value'] for x in r['native_enemy']['resolved']['talentBlackboard']};assert bb=={'defup.def':300.0,'defup.range_radius':2.5}
 mod=raw['_buffs'][0]['attributes']['attributeModifiers'][0];assert (mod['attributeType'],mod['formulaItem'],mod['loadFromBlackboard'])==(2,0,1)
 # Dump enum explicitly names SelfOption.EXCLUDE2. BB-radius load remains pending.
 dump=(ROOT.parent/'Ark_data/dump.cs').read_text(encoding='utf8');assert 'public const AuraAbility.SelfOption EXCLUDE = 2;' in dump
 out['selectors'].append({'id':'selector/chapter02/defup','kind':'selector','region':{'type':'radius','radius':bb['defup.range_radius']},'parameters':{'exclude_source':True},'filters':[{'tag':'enemy'},{'state':'alive'},{'field':{'scope':'definition','path':['metadata','native_category'],'bits_any':3,'default':1}}], 'metadata':{'native_validator_pointer':raw['_targetValidator'],'source_aura':raw,'radius_profile':'declared DB blackboard radius; serialized CircleCollider1 retained in source matrix'}})
 out['buffs'] += [{'id':'buff/chapter02/defup_member','kind':'buff','stacking':{'mode':'independent'},'modifiers':[{'attribute':'def','layer':'flat','value':300}]},{'id':'buff/chapter02/defup_emitter','kind':'buff','aura':{'selector':'selector/chapter02/defup','buff':'buff/chapter02/defup_member'}}]
 out['entities'][-1]['components']['buffs']={'initial':['buff/chapter02/defup_emitter']}
 r=rows['enemy_1500_skulsr'];attach=[x for x in r['components'].values() if x['native_class']=='PassiveAttachmentAbility'];assert len(attach)==1;buff=attach[0]['raw']['_additiveActiveBuffs'][0];assert buff['lifeTime']==5 and buff['lifeTimeType']==1
 mod=buff['attributes']['attributeModifiers'][0];assert (mod['attributeType'],mod['formulaItem'],mod['value'],mod['loadFromBlackboard'])==(2,1,-.5,0)
 out['buffs'].append({'id':'buff/chapter02/skulsr_defdown','kind':'buff','duration_seconds':5,'stacking':{'mode':'refresh'},'modifiers':[{'attribute':'def','layer':'direct_ratio','value':-.5}],'metadata':{'source_component':attach[0],'attachment_driver_pending':True}})
 # Reuse the exact pure projectile rule definitions, not W abilities or data.
 framework=ROOT/'packages/campaign/chapter01_models/projectile_lifecycle/metadata_corrected/model.json'
 assert sha(framework)=='09c06de158b44d25891ae38b3c58688a86eff9f9ded674b3d057f291b79d2133'
 out['manifest']['metadata']['source_locks'][str(framework.relative_to(ROOT))]=sha(framework)
 out['rules'] += [deepcopy(x) for x in read(framework)['rules'] if x['contract'] in ('projectile.trajectory','projectile.collision')]
 out['projectiles']=[]
 for key,expected_frame in (('enemy_1011_wizard',19),('enemy_1028_mocock',22)):
  r=rows[key];a=r['native_enemy']['resolved']['attributes'];mode=r['modes'][0];node=mode['nodes']['_attack'];raw=node['raw']
  assert node['native_class']=='RangedAttack' and raw['_waitForAttackEvent']==1 and raw['_atkScale']==1
  events=[x for x in node['animation_binding']['events'] if x['name']=='OnAttack'];assert len(events)==1 and events[0]['frame']==expected_frame
  trigger=mode['nodes']['_attackTrigger']['raw'];go=trigger['m_GameObject']['m_PathID']
  cfgs=[x for x in r['components'].values() if x['native_class']=='AdvancedSelector' and x['raw']['m_GameObject']['m_PathID']==go];assert len(cfgs)==1
  colliders=[x for x in d['prefabs'][key]['geometry_sources'] if x['gameobject_path_id']==go and x['unity_type']=='CircleCollider2D'];assert len(colliders)==1
  projectile_key=raw['_projectileKey'];projectile=d['projectiles'][projectile_key]
  simple=[x for x in projectile['components'].values() if x['native_class']=='SimpleProjectile'];motion=[x for x in projectile['components'].values() if x['native_class'] in ('AdvancedMovement','ParacurveMovement')];assert len(simple)==len(motion)==1
  sp=simple[0]['raw'];mp=motion[0]['raw'];assert sp['_lifeTimeType']==1 and sp['_lifeTime']==10 and sp['_maxHitNum']==1 and sp['_canHitSameTargetMultipleTimes']==0 and sp['_stopWhenSourceInvalid']==0 and sp['_alwaysHitTraceTargetInTheEnd']==1
  assert mp.get('_speed') in (5,10) and mp['_forceReachedWhenTimeup']==1
  suffix=key.removeprefix('enemy_');sid='selector/chapter02/'+suffix;aid='ability/chapter02/'+suffix;bid='behavior/chapter02/'+suffix;pid='projectile/chapter02/'+suffix
  out['selectors'].append({'id':sid,'kind':'selector','region':{'type':'radius','radius':colliders[0]['raw']['m_Radius']},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1,'eligibility':{'rule':'rule/chapter02/qualification','parameters':{'source_configuration':cfgs[0]['raw'],'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(defaults)}},'metadata':{'native_trigger':mode['nodes']['_attackTrigger'],'source_geometry':colliders[0]}})
  out['projectiles'].append({'id':pid,'kind':'projectile','motion':{'rule':'rule/projectile/trajectory','parameters':{'mode':'homing','speed':mp['_speed'],**({'raise_height':mp['_raiseHeight'],'height_threshold':mp['_noRaiseHeightThreshold']} if motion[0]['native_class']=='ParacurveMovement' else {})}},'collision':{'rule':'rule/projectile/collision','parameters':{'enabled':True,'radius':0}},'lifetime_seconds':10,'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,'attach_at_launch':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'cancel','target_hidden':'cancel','finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':True,'hit_on_expire':True},'on_invalid':[],'metadata':{'source':projectile['source'],'simple':simple[0],'movement':motion[0],'profile':'homing 2D logical trajectory, first step after launch; native physics/body pending'}})
  out['abilities'].append({'id':aid,'kind':'ability','selector':sid,'activation':{'mode':'automatic_attack'},'timeline':[{'at_seconds':events[0]['seconds'],'effect':{'op':'damage','damage_type':{1:'physical',2:'arts'}[raw['_damageType']],'scale':raw['_atkScale'],'projectile_definition':pid,'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}}],'metadata':{'source_attack':node,'source_projectile_key':projectile_key,'timing':'actual authored event, unscaled profile; native sampling unknown'}})
  out['behaviors'].append({'id':bid,'kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'attack','selector':sid}],'cast_groups':[{'key':'attack','abilities':[aid]}],'parameters':{'target_key':'attack','stop_on_target':True,'stop_cast_groups':['attack']}}]}})
  out['entities'].append({'id':'unit/chapter02/'+key,'kind':'entity','tags':['enemy','ground'],'metadata':{'native_category':1,'native_variant':r['variant_id']},'components':{'attributes':{'base':{'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],'attack_interval':a['baseAttackTime'],'attack_speed_ratio':a['attackSpeed']/100,'move_speed':a['moveSpeed'],'block_cost':1}},'selection_state':{**deepcopy(defaults),'side':1},'resources':{'hp':{'initial':a['maxHp'],'capacity':a['maxHp'],'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'spatial':{},'abilities':[aid],'behavior':{'machine':bid}}})
 out['manifest']['metadata']['model_gaps'].remove('complex_projectile_and_mode_driver_content_pending')
 out['manifest']['metadata']['model_gaps'].append('skulsr_mode_driver_dual_projectile_and_onhit_attachment_pending')
 return out
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();p=build();b=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode();OUT.parent.mkdir(parents=True,exist_ok=True)
 if a.check:assert OUT.read_bytes()==b
 else:OUT.write_bytes(b)
 print(json.dumps({'passed':True,'check':a.check,'sha256':sha(OUT),'entities':len(p['entities']),'scope':'partial declared math; full closure rejected'}))
