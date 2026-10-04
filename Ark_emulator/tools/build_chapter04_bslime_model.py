"""Source bslime death trigger, stationary one-second projectile and impact."""
import argparse,hashlib,json
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/chapter04_sources/native.reference.json'
PIN='3e392d80d000e27a50f11f2f33b0fa0f6be35dc1e91d7e321e2b9cf9681c4603'
OUT=ROOT/'packages/campaign/chapter04_units/bslime.reference_model.json'


def build():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=PIN:raise ValueError('Frozen source changed')
    source=json.loads(SOURCE.read_bytes());v=next(v for k,v in source['variants'].items() if 'bslime@' in k)
    native=v['native_enemy']['resolved'];a=native['attributes'];pf=source['prefabs'][v['prefab_key']]
    talent=v['passive_and_skill_components'][0];raw=talent['raw'];node=json.loads(raw['_projectileActions']['SerializedState'])[0]
    template=source['bson_templates']['templates']['projectile_on_killed']['parsed']['eventToActions']['ON_OWNER_KILLED']
    if len(template)!=2 or template[0]['_abnormalFlag']!='SILENCED' or template[0]['_isUnset'] is not True or template[1]['_sourceType']!='BUFF_OWNER':raise ValueError('Death event adapter changed')
    bb={r['key']:r['value'] for r in native['talentBlackboard']}
    if bb!={'boom.atk_scale':4.0} or node['_damageType']!='PHYSICAL' or node['_attackType']!='SPLASH' or node['_noSource'] is not False or node['_ignoreForSp'] is not False:raise ValueError('Death damage consumer changed')
    projectile=source['projectiles']['projectile_bslime'];sp=next(c['raw'] for c in projectile['components'].values() if c['native_class']=='SimpleProjectile')
    hit=next(c['raw'] for c in projectile['components'].values() if c['native_class']=='HitBehaviour')
    circle=next(g for g in projectile['geometry_sources'] if g['unity_type']=='CircleCollider2D')
    if sp['_lifeTime']!=1.0 or sp['_stopWhenSourceInvalid']!=0 or sp['_alwaysReachInTheEnd']!=1 or hit['_onlyCheckHitWhenReachTarget']!=1 or hit['_ignoreCamouflage']!=1:raise ValueError('Stationary death projectile policy changed')
    root=next(c['raw'] for c in pf['components'].values() if c['native_class']=='Enemy');mover=next(c['raw'] for c in pf['components'].values() if c['native_class']=='MoveController')
    combat=v['modes'][0]['nodes']['_combat'];frames=[e for e in combat['animation_binding']['events'] if e['name']=='OnAttack']
    if len(frames)!=1 or frames[0]['frame']!=14:raise ValueError('Bslime normal clock changed')
    uid='unit/ch4/bslime/'+v['variant_id'].split('/')[-1];aid='ability/'+uid;sid='selector/'+uid;bid='behavior/'+uid;pid='projectile/'+uid
    defaults={'side':1,'motion':1,'category':1,'unit_type':2}
    result={'schemaVersion':2,'manifest':{'id':'package/ch4/bslime_source','requires':['preset/ark_standard'],'metadata':{
        'source_locks':{str(SOURCE.relative_to(ROOT)):PIN},'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'native_variant_id':v['variant_id'],'source_talent':talent,'source_template':template,'source_action':node,'source_simple':sp,'source_hit':hit,'source_circle':circle,
        'policies':{'death_boundary':'TRUE death only; emission before retirement while exact source active, immutable anchor body point; source ATK at_hit',
            'impact':'one-second expiry; point radius1.25 versus actual body overlap pending','source':'dead real enemy retained; no fake actor or no-source conversion',
            'completion':'declared pending death projectile blocks victory, defeat may cancel','silence':'typed SILENCED12 at death boundary; actual game timing feedback pending'},
        'whole_stage_executed':False,'actual_client_verified':False}},
        'entities':[{'id':uid,'kind':'entity','tags':['enemy','ground'],'metadata':{'native_variant_id':v['variant_id']},'components':{
            'attributes':{'base':{'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],'attack_interval':a['baseAttackTime'],
                'attack_speed_ratio':a['attackSpeed']/100,'move_speed':a['moveSpeed'],'mass_level':a['massLevel'],'block_cost':root['_blockVolume']}},
            'selection_state':defaults,'resources':{'hp':{'initial':a['maxHp'],'capacity':a['maxHp'],'role':'health'}},
            'spatial':{'motion_mode':0,'steering':{'rule':'rule/ch4/bslime_steering','parameters':{'response_factor':mover['_steeringFactor'],'max_acceleration':mover['_maxSteeringForce'],'arrival_radius':.05}}},
            'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':native['lifePointReduce'],
                'death_projectiles':[{'rule':'rule/ch4/bslime_death_gate','parameters':{},'projectile_definition':pid,
                    'effect':{'op':'area','center':'source','membership_rule':'rule/ch4/bslime_qualified_radius',
                        'filters':[{'tag':'player'}], 'effects':[{'op':'damage','damage_type':'physical','scale':bb['boom.atk_scale'],
                        'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}]}}]},
            'abilities':[aid],'behavior':{'machine':bid}}}],
        'abilities':[{'id':aid,'kind':'ability','selector':sid,'activation':{'mode':'automatic_attack','parameters':{'auto_only':True}},
            'timeline':[{'at_seconds':frames[0]['seconds'],'effect':{'op':'damage','damage_type':'physical','scale':1}}]}],
        'selectors':[{'id':sid,'kind':'selector','region':{'type':'all','blocked_only':True},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1}],
        'behaviors':[{'id':bid,'kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],
            'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'normal','selector':sid}],
                'cast_groups':[{'key':'normal','abilities':[aid]}],'parameters':{'target_key':'normal','blocked_target':True,'stop_on_target':False,'stop_cast_groups':['normal']}}]}}],
        'rules':[{'id':'rule/ch4/bslime_death_gate','kind':'rule','contract':'lifecycle.death_emission',
            'implementation':{'type':'expression','expression':'12 not in inputs.selection_state.abnormal_flags'}},
            {'id':'rule/ch4/bslime_steering','kind':'rule','contract':'movement.steering','implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}},
            {'id':'rule/ch4/bslime_fixed','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'model.projectile.trajectory'}},
            {'id':'rule/ch4/bslime_collision','kind':'rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'model.projectile.collision'}}],
        'projectiles':[{'id':pid,'kind':'projectile','motion':{'rule':'rule/ch4/bslime_fixed','parameters':{'mode':'fixed'}},
            'collision':{'rule':'rule/ch4/bslime_collision','parameters':{'enabled':False,'radius':0}},'lifetime_seconds':sp['_lifeTime'],
            'max_hits':None,'can_hit_same_target':False,'stop_after_max':False,'stop_after_first':False,'attach_at_launch':True,
            'completion_blocking':True,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'retain_position','target_hidden':'retain_position',
                'finish_on_reach':False,'hit_on_reach':False,'force_reach_on_expire':True,'hit_on_expire':True},'on_invalid':[]}]}
    cfg={'_'+k:value for k,value in hit['_targetOptions'].items()}
    cfg['_needProfessionMask']=int(bool(hit['_targetOptions']['professionMask']))
    cfg['_forceIgnoreCamouflage']=hit['_ignoreCamouflage']
    target_defaults={'side':0,'motion':1,'category':1,'profession':0,'unit_type':1,
        'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[],
        'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False}
    result['rules'].extend([
        {'id':'rule/ch4/bslime_qualified_radius','kind':'rule','contract':'area.members',
            'dependencies':['rule/ch4/bslime_qualification'],
            'parameters':{'radius':circle['raw']['m_Radius'],'eligibility':{'rule':'rule/ch4/bslime_qualification',
                'parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':target_defaults}}},
            'implementation':{'type':'provider','provider':'model.area.qualified_radius'}},
        {'id':'rule/ch4/bslime_qualification','kind':'rule','contract':'targeting.eligibility',
            'implementation':{'type':'provider','provider':'model.targeting.eligibility'}}])
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Bslime module bytes changed')
    else:OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'source_death_projectile':True}))
