"""Exact C4 dcross/wizard2 clocks and projectile operands, explicit range policy."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/chapter04_sources/native.reference.json'
PIN='3e392d80d000e27a50f11f2f33b0fa0f6be35dc1e91d7e321e2b9cf9681c4603'
FRAMEWORK=ROOT/'packages/campaign/chapter01_models/projectile_lifecycle/metadata_corrected/model.json'
FRAMEWORK_PIN='09c06de158b44d25891ae38b3c58688a86eff9f9ded674b3d057f291b79d2133'
OUT=ROOT/'packages/campaign/chapter04_units/ranged'


def build(range_policy):
    if range_policy not in ('table','source_circle'):
        raise ValueError('Explicit range policy required')
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=PIN or hashlib.sha256(FRAMEWORK.read_bytes()).hexdigest()!=FRAMEWORK_PIN:
        raise ValueError('Frozen ranged source/framework changed')
    source=json.loads(SOURCE.read_bytes())
    p={'schemaVersion':2,'manifest':{'id':'package/ch4/ranged/'+range_policy,'requires':['preset/ark_standard'],
        'metadata':{'source_locks':{str(SOURCE.relative_to(ROOT)):PIN,str(FRAMEWORK.relative_to(ROOT)):FRAMEWORK_PIN},
            'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'range_policy':range_policy,
            'variant_bindings':[],'whole_stage_executed':False,'actual_client_verified':False,
            'feedback_pending':['Point radius versus native collider/body overlaps; dcross table2.2 versus source circle2.0',
                'Base taunt/distance/ID target order versus native comparator',
                '2D projectile homing and source retained lifetime5/10 policies versus native mount/animation scaling']}},
        'entities':[],'abilities':[],'selectors':[],'behaviors':[],'projectiles':[],
        'rules':[deepcopy(r) for r in json.loads(FRAMEWORK.read_bytes())['rules']
            if r['contract'] in ('projectile.trajectory','projectile.collision')]}
    p['rules'] += [
        {'id':'rule/ch4/ranged_steering','kind':'rule','contract':'movement.steering',
         'implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}},
        {'id':'rule/ch4/ranged_qualification','kind':'rule','contract':'targeting.eligibility',
         'implementation':{'type':'provider','provider':'model.targeting.eligibility'}},
        {'id':'rule/ch4/ranged_priority','kind':'rule','contract':'targeting.score','implementation':{'type':'expression',
         'expression':"(-1000000 if 'blocked_by' in inputs.source.components.runtime and inputs.source.components.runtime.blocked_by == inputs.candidate.id else 0) - 100000 * (inputs.candidate.components.attributes.base.taunt_level if 'taunt_level' in inputs.candidate.components.attributes.base else 0) + inputs.distance"}}]
    for vid,v in source['variants'].items():
        if not any(key in vid for key in ('enemy_1012_dcross@','enemy_1011_wizard_2@')):continue
        if v['passive_and_skill_components'] or v.get('additional_animation_drivers') or len(v['modes'])!=1:
            raise ValueError('Additional ranged state needs a consumer')
        resolved=v['native_enemy']['resolved'];a=resolved['attributes'];prefab=source['prefabs'][v['prefab_key']]
        root=next(c['raw'] for c in prefab['components'].values() if c.get('native_class')=='Enemy')
        mover=next(c['raw'] for c in prefab['components'].values() if c.get('native_class')=='MoveController')
        if root['_commonAbilities'] or root['_delayToBorn'] or a['hpRecoveryPerSec'] or a['spRecoveryPerSec'] or a['stunImmune']:
            raise ValueError('Unconsumed ranged root/regen/immunity')
        mode=v['modes'][0];node=mode['nodes']['_attack'];raw=node['raw'];combat=mode['nodes']['_combat']
        if node['native_class']!='RangedAttack' or raw['_waitForAttackEvent']!=1 or raw['_selectTargetSource']!=2 or raw['_atkScale']!=1 or raw['_extraDamageType'] or raw['_epDamageRatio'] or raw['_activeBuffs']:
            raise ValueError('Unexpected ranged packet consumer')
        frames=[e for e in node['animation_binding']['events'] if e['name']=='OnAttack']
        expected_frame=20 if 'dcross' in vid else 19
        if len(frames)!=1 or frames[0]['frame']!=expected_frame:
            raise ValueError('Unexpected ranged attack frame')
        trigger=mode['nodes']['_attackTrigger'];go=trigger['raw']['m_GameObject']['m_PathID']
        configs=[c for c in prefab['components'].values() if c.get('native_class')=='AdvancedSelector' and c['raw']['m_GameObject']['m_PathID']==go]
        circles=[c for c in prefab['geometry_sources'] if c['unity_type']=='CircleCollider2D' and c['gameobject_path_id']==go]
        if len(configs)!=len(circles) or len(configs)!=1:raise ValueError('Exact trigger selector/collider required')
        cfg=configs[0]['raw']
        if cfg['_limitTargetNum']!=1 or cfg['_maxNum']!=1:raise ValueError('Multi-target selector not implemented')
        projectile=source['projectiles'][raw['_projectileKey']]
        simple=next(c for c in projectile['components'].values() if c.get('native_class')=='SimpleProjectile')
        motion=next(c for c in projectile['components'].values() if c.get('native_class')=='AdvancedMovement')
        sp,mp=simple['raw'],motion['raw']
        if [sp['_lifeTimeType'],sp['_maxHitNum'],sp['_canHitSameTargetMultipleTimes'],sp['_stopWhenSourceInvalid'],sp['_alwaysHitTraceTargetInTheEnd'],mp['_forceReachedWhenTimeup'],mp['_speed']] != [1,1,0,0,1,1,10.0]:
            raise ValueError('Unexpected projectile lifecycle/motion')
        defaults={'side':0,'motion':1,'category':1,'profession':0,'unit_type':1,
            'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[],
            'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False}
        uid='unit/ch4/'+vid.split('@')[0]+'/'+vid.split('/')[-1];sid='selector/'+uid;pid='projectile/'+uid;aid='ability/'+uid;bid='behavior/'+uid
        radius=resolved['rangeRadius'] if range_policy=='table' else circles[0]['raw']['m_Radius']
        p['selectors'].append({'id':sid,'kind':'selector','region':{'type':'radius','radius':radius},
            'filters':[{'tag':'player'},{'state':'alive'}],'limit':1,'eligibility':{'rule':'rule/ch4/ranged_qualification',
            'parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':defaults}}})
        p['projectiles'].append({'id':pid,'kind':'projectile','motion':{'rule':'rule/projectile/trajectory','parameters':{'mode':'homing','speed':mp['_speed']}},
            'collision':{'rule':'rule/projectile/collision','parameters':{'enabled':True,'radius':0}},
            'lifetime_seconds':sp['_lifeTime'],'max_hits':sp['_maxHitNum'],'can_hit_same_target':False,
            'stop_after_max':True,'stop_after_first':False,'attach_at_launch':False,
            'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'cancel','target_hidden':'cancel',
                'finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':True,'hit_on_expire':True},'on_invalid':[]})
        timeline=[{'at_seconds':frames[0]['seconds'],'effect':{'op':'damage','damage_type':{1:'physical',2:'arts'}[raw['_damageType']],
            'scale':1,'projectile_definition':pid,'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}}]
        p['abilities'].append({'id':aid,'kind':'ability','selector':sid,'activation':{'mode':'automatic_attack','parameters':{'auto_only':True}},
            'rules':{'targeting.score':'rule/ch4/ranged_priority'},'timeline':timeline})
        abilities=[aid];selectors=[{'key':'ranged','selector':sid}];groups=[{'key':'ranged','abilities':[aid]}]
        parameters={'target_key':'ranged','stop_on_target':True,'stop_cast_groups':['ranged']}
        decision_rule='rule/ark_behavior_decision'
        if combat['native_class']=='MeleeAttack':
            cr=combat['raw'];events=[e for e in combat['animation_binding']['events'] if e['name']=='OnAttack']
            if cr['_damageType']!=1 or cr['_waitForAttackEvent']!=1 or len(events)!=1 or events[0]['frame']!=20:raise ValueError('Unknown dcross blocked combat branch')
            cs=sid+'/combat';ca=aid+'/combat';p['selectors'].append({'id':cs,'kind':'selector','region':{'type':'all','blocked_only':True},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1})
            p['abilities'].append({'id':ca,'kind':'ability','selector':cs,'activation':{'mode':'automatic_attack','parameters':{'auto_only':True}},
                'timeline':[{'at_seconds':events[0]['seconds'],'effect':{'op':'damage','damage_type':'physical','scale':1,'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}}]})
            abilities.insert(0,ca);selectors.append({'key':'combat','selector':cs});groups.append({'key':'combat','abilities':[ca]})
            p['abilities'][-2]['activation']['condition']="'blocked_by' not in inputs.source.components.runtime or inputs.source.components.runtime.blocked_by == None"
            decision_rule='rule/ch4/dcross_decision'
            p['rules'].append({'id':decision_rule,'kind':'rule','contract':'behavior.decision',
                'implementation':{'type':'graph','nodes':[
                    {'id':'blocked','expression':'inputs.blocked_by != None'},
                    {'id':'busy','expression':"inputs.cast_groups.combat != [] or inputs.cast_groups.ranged != []"},
                    {'id':'target','expression':"inputs.blocked_by in inputs.eligible_ids.combat if nodes.blocked else inputs.eligible_ids.ranged != []"},
                    {'id':'visible','expression':'inputs.visibility.alive and inputs.visibility.active and not inputs.visibility.hidden'},
                    {'id':'result','expression':"{'move':nodes.visible and inputs.controls.move and not nodes.blocked and not nodes.busy and not nodes.target,'attack':nodes.visible and inputs.controls.attack and inputs.controls.abilities and not nodes.busy and nodes.target}"}],
                'output':'nodes.result'}})
            parameters={}
        p['behaviors'].append({'id':bid,'kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],
            'decision':{'rule':decision_rule,'default_mode':0,'profiles':[{'mode':0,'selectors':selectors,'cast_groups':groups,'parameters':parameters}]}})
        p['entities'].append({'id':uid,'kind':'entity','tags':['enemy','ground'],'metadata':{'native_variant_id':vid},'components':{
            'attributes':{'base':{'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],
                'attack_interval':a['baseAttackTime'],'attack_speed_ratio':a['attackSpeed']/100,'move_speed':a['moveSpeed'],
                'block_cost':root['_blockVolume'],'mass_level':a['massLevel']}},'selection_state':{**defaults,'side':1,'unit_type':2},
            'resources':{'hp':{'initial':a['maxHp'],'capacity':a['maxHp'],'role':'health'}},
            'spatial':{'motion_mode':0,'steering':{'rule':'rule/ch4/ranged_steering','parameters':{'response_factor':mover['_steeringFactor'],'max_acceleration':mover['_maxSteeringForce'],'arrival_radius':.05}}},
            'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':resolved['lifePointReduce']},'abilities':abilities,'behavior':{'machine':bid}}})
        p['manifest']['metadata']['variant_bindings'].append({'variant_id':vid,'unit_definition':uid,'source_attributes':a,
            'source_combat':combat,'source_attack':node,'source_selector':configs[0],'source_trigger':trigger,
            'source_circle':circles[0],'selected_radius':radius,'source_simple_projectile':simple,'source_motion':motion,
            'projectile_definition':pid,'source_root':root,'source_mover':mover})
    if len(p['entities'])!=2:raise ValueError('Expected both exact ranged variants')
    return p


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for policy in ('table','source_circle'):
        raw=(json.dumps(build(policy),ensure_ascii=False,indent=2)+'\n').encode('utf8');path=OUT/(policy+'.reference_model.json')
        if args.check:
            if path.read_bytes()!=raw:raise ValueError('Ranged content bytes changed')
        else:OUT.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        print(json.dumps({'policy':policy,'sha256':hashlib.sha256(raw).hexdigest(),'units':2}))
