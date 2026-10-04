"""Source-backed lasso plus ordinary attack through generic V2 primitives."""
from pathlib import Path
from copy import deepcopy
import argparse,hashlib,json

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/chapter04_dmage/source.reference.json'
PIN='bac0af413f5a2380e623c180e3c8b8c1852e2a425e4058e8c0f0ec217eb34681'
OUT=ROOT/'packages/campaign/chapter04_dmage/module.reference.json'

def build():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==PIN
    src=json.loads(SOURCE.read_bytes());v=src['variant'];a=v['native_enemy']['resolved']['attributes']
    bb=src['blackboard'];graph=src['source_graph'];raw=graph['skill_attack']['raw'];skill=graph['enemy_skill']['raw']
    assert skill['_maxTriggerTime']==1 and skill['_ignoreSilence']==0 and skill['_castLikeAttack']==0
    assert raw['_waitForProjectileInvalid']==1 and raw['_fireAttackFinishWhenProjectileInvalid']==1
    assert raw['_useCachedAtkOnly']==0 and raw['_affectedBySlowDown']==0
    assert raw['_projectileKey']=='projectile_dmage' and raw['_attackType']==4 and raw['_damageType']==2
    assert raw['_extraProjectileKeys']==[] and raw['_epDamageRatio']==0 and raw['_extraDamageType']==0
    active=raw['_activeBuffs'];assert len(active)==1 and active[0]['templateKey']=='empty'
    assert active[0]['attributes']['abnormalFlags']==[0] and active[0]['lifeTimeType']==2
    assert src['animations']['Skill_Begin']['duration']['frame']==26
    assert src['animations']['Skill_Loop']['events'][0]['frame']==0
    harpoon=next(c['raw'] for c in graph['projectile']['components'].values() if c.get('native_class')=='HarpoonMovement')
    link=next(c['raw'] for c in graph['projectile']['components'].values() if c.get('native_class')=='LassoProjectile')
    assert harpoon['_speed']==10 and link['_linkDuration']==5 and link['_lifeTime']==5
    assert link['_splitDamage']==1 and link['_keepHitTarget']==1 and link['_isSilenceable']==1
    uid='unit/ch4/'+v['prefab_key']+'/'+v['variant_id'].split('/')[-1]
    aid='ability/'+uid+'/lasso';basic='ability/'+uid+'/normal';attach='attachment/'+uid+'/lasso'
    hold='buff/'+uid+'/caster_hold';stun='buff/'+uid+'/target_stun';recovery='buff/'+uid+'/end_recovery'
    selector='selector/'+uid+'/lasso';normal='selector/'+uid+'/normal';behavior='behavior/'+uid
    def simple_provider(ident,contract,provider,params=None):
        return {'id':ident,'kind':'rule','contract':contract,'implementation':{'type':'provider','provider':provider},'parameters':params or {}}
    defaults={'side':0,'motion':1,'category':1,'profession':0,'unit_type':1,
        'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[],
        'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False}
    normal_trigger=v['modes'][0]['nodes']['_attackTrigger']['raw']['m_GameObject']['m_PathID']
    native=json.loads((ROOT/'packages/campaign/chapter04_sources/native.reference.json').read_bytes())
    prefab=native['prefabs'][v['prefab_key']]
    basic_projectile=native['projectiles'][graph['normal_attack']['raw']['_projectileKey']]
    basic_simple=next(c['raw'] for c in basic_projectile['components'].values() if c.get('native_class')=='SimpleProjectile')
    basic_motion=next(c['raw'] for c in basic_projectile['components'].values() if c.get('native_class')=='AdvancedMovement')
    assert basic_simple['_lifeTime']==10 and basic_motion['_speed']==10
    normal_config=next(c['raw'] for c in prefab['components'].values()
        if c.get('native_class')=='AdvancedSelector' and c['gameobject_path_id']==normal_trigger)
    assert normal_config['_postFilter']==4 and graph['skill_selector']['raw']['_postFilter']==12
    def select(ident,radius,cfg,excluded):
        return {'id':ident,'kind':'selector','region':{'type':'radius','radius':radius},
            'filters':[{'tag':'player'},{'state':'alive'}],'limit':1,'exclude_abnormal_flags':excluded,
            'eligibility':{'rule':'rule/ch4/dmage_eligibility','parameters':{'source_configuration':cfg,
                'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':defaults}}}
    damage={'op':'damage','damage_type':'arts','scale':bb['atk_scale'],
        'damage_flags':{'source_attack_type':'BUFF','ignore_for_sp':False},
        'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}
    p={'schemaVersion':2,'manifest':{'id':'package/ch4/dmage/reference','requires':['preset/ark_standard'],
        'metadata':{'source_locks':{str(SOURCE.relative_to(ROOT)):PIN,
            src['source_path']:src['source_sha256']},'variant_bindings':[{'variant_id':v['variant_id'],'unit_definition':uid}],
            'raw_source_audit':src,'reference_policies':src['planned_policies'],
            'source_attack_type':'BUFF','ignore_for_sp_policy':False,
            'ignore_for_sp_native_serialized':False,
            'whole_stage_executed':False,'client_verified':False,'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}},
        'rules':[simple_provider('rule/ch4/dmage_eligibility','targeting.eligibility','model.targeting.eligibility'),
            simple_provider('rule/ch4/dmage_trajectory','projectile.trajectory','model.projectile.trajectory'),
            simple_provider('rule/ch4/dmage_collision','projectile.collision','model.projectile.collision'),
            simple_provider('rule/ch4/dmage_steering','movement.steering','ark.movement.steering_velocity'),
            {'id':'rule/ch4/dmage_priority','kind':'rule','contract':'targeting.score',
                'implementation':{'type':'expression','expression':"-100000 * (inputs.candidate.components.attributes.base.taunt_level if 'taunt_level' in inputs.candidate.components.attributes.base else 0) - inputs.candidate.id"}}],
        'selectors':[select(selector,bb['range_radius'],graph['skill_selector']['raw'],[0]),
                     select(normal,v['native_enemy']['resolved']['rangeRadius'],normal_config,[])],
        'buffs':[{'id':hold,'kind':'buff','selection_flags':{'abnormal_flags':[0]},
            'control':{'move':False,'attack':False,'abilities':False,'block':False,'interrupt':False},
            'stacking':{'mode':'refresh','max_stacks':1}},
            {'id':stun,'kind':'buff','selection_flags':{'abnormal_flags':[0]},
            'control':{'move':False,'attack':False,'abilities':False,'block':False,'interrupt':True},
            'stacking':{'mode':'refresh','max_stacks':1}},
            {'id':recovery,'kind':'buff','duration_seconds':raw['_minPostDelayWhenProjectileInvalid'],
            'control':{'move':False,'attack':False,'abilities':False,'block':False,'interrupt':False}}],
        'definitions':[{'id':attach,'kind':'attachment','duration_seconds':bb['hit_duration'],
            'flight_lifetime_seconds':link['_lifeTime'],'step_interval_seconds':1/30,'refresh_interval_seconds':1,
            'motion':{'rule':'rule/ch4/dmage_trajectory','parameters':{'mode':'homing','speed':harpoon['_speed']}},
            'target_buff':stun,'effect':damage,'damage_integral':True,'source_cancel_flags':[0,12],
            'ignored_owned_source_flags':active[0]['attributes']['abnormalFlags'],
            'force_reach_on_timeout':bool(harpoon['_forceReachedWhenTimeup']),
            'lifecycle':{'source_invalid':'cancel','target_invalid':'cancel','source_hidden':'cancel','target_hidden':'cancel'},
            'max_packets':None,'completion_blocking':False,'source_recovery_buff':recovery,
            'recovery_on':['complete','target_invalid','source_flags','flight_timeout'],
            'metadata':{'endpoint_policy':'left-endpoint actual-quantum damage integral; half-open control lifetime',
                'target_stun_policy':'infinite cast/link-owned lease refreshed each1s, no one-second expiry gaps',
                'raw_link_duration5_retained':True,'duration_override':'source BB hit_duration20',
                'captured_target_policy':'retain captured identity, cancel on inactive/hidden; no reselect for spent cast'}}],
        'abilities':[{'id':aid,'kind':'ability','selector':selector,'wait_for_channels':True,
            'rules':{'targeting.score':'rule/ch4/dmage_priority'},
            'activation':{'mode':'manual','forbidden_source_flags':[0,12],
                'costs':[{'resource':'lasso_uses','amount':1}],
                'parameters':{'auto_only':True,'auto_when_ready':True,'requires_targets':True,'cancel_pending_attacks':True},
                'on_start':[{'op':'apply_buff','target':'source','buff':hold,'bind_to_cast':True}]},
            'timeline':[{'at':src['animations']['Skill_Begin']['duration']['frame'],
                'effect':{'op':'begin_attachment','attachment':attach}}]},
            {'id':basic,'kind':'ability','selector':normal,'activation':{'mode':'automatic_attack','parameters':{'auto_only':True}},
                'rules':{'targeting.score':'rule/ch4/dmage_priority'},
                'timeline':[{'at':src['animations']['Attack']['events'][0]['frame'],
                    'effect':{'op':'damage','damage_type':'arts','scale':1,'projectile_definition':'projectile/'+uid+'/normal',
                        'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}}]}],
        'projectiles':[{'id':'projectile/'+uid+'/normal','kind':'projectile',
            'motion':{'rule':'rule/ch4/dmage_trajectory','parameters':{'mode':'homing','speed':basic_motion['_speed']}},
            'collision':{'rule':'rule/ch4/dmage_collision','parameters':{'enabled':True,'radius':0}},
            'lifetime_seconds':basic_simple['_lifeTime'],'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':True,
            'attach_at_launch':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'cancel',
                'target_hidden':'cancel','finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':True,'hit_on_expire':True},'on_invalid':[]}],
        'behaviors':[{'id':behavior,'kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],
            'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,
                'selectors':[{'key':'ranged','selector':normal}],
                'cast_groups':[{'key':'normal','abilities':[basic]},{'key':'lasso','abilities':[aid]}],
                'parameters':{'target_key':'ranged','stop_on_target':True,'stop_cast_groups':['normal','lasso']}}]}}],
        'entities':[{'id':uid,'kind':'entity','tags':['enemy','ground'],'metadata':{'native_variant_id':v['variant_id']},
            'components':{'attributes':{'base':{'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],
                'move_speed':a['moveSpeed'],'attack_interval':a['baseAttackTime'],'attack_speed_ratio':a['attackSpeed']/100,
                'block_cost':1,'mass_level':a['massLevel']}},'selection_state':{**defaults,'side':1,'unit_type':2},
                'resources':{'hp':{'initial':a['maxHp'],'capacity':a['maxHp'],'role':'health'},
                    'lasso_uses':{'initial':skill['_maxTriggerTime'],'capacity':skill['_maxTriggerTime'],'role':'finite_cast_count'}},
                'abilities':[aid,basic],'behavior':{'machine':behavior},
                'spatial':{'motion_mode':0,'steering':{'rule':'rule/ch4/dmage_steering','parameters':{'response_factor':8,'max_acceleration':10,'arrival_radius':.05}}},
                'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':v['native_enemy']['resolved']['lifePointReduce']}}}]}
    return p

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:assert OUT.read_bytes()==raw,'Dmage module bytes changed'
    else:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        with OUT.open('xb') as file:file.write(raw)
    print(json.dumps({'path':str(OUT),'sha256':hashlib.sha256(raw).hexdigest()}))
