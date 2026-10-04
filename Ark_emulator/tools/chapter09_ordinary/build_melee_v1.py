"""Source-bound ordinary C9 melee and silenceable refraction recipes."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
SOURCE=ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json'
PLAN=SOURCE.with_name('source.plan.v1.json')
CORE='82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'
OUT=ROOT/'packages/campaign/chapter09_consumers/ordinary'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build(key):
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    assert implementation_digest()==CORE
    assert sha(SOURCE)=='592afac29cc32d1aeaba3ea739eb6da5a218055e255a42f53315f4a2ca0962ff'
    source=json.loads(SOURCE.read_bytes())
    matches=[(vid,row) for vid,row in source['variants'].items() if row['prefab_key']==key]
    assert len(matches)==1
    vid,row=matches[0];resolved=row['native_enemy']['resolved'];attrs=resolved['attributes']
    assert resolved['applyWay']=='MELEE' and resolved['motion']=='WALK'
    assert attrs['hpRecoveryPerSec']==0 and not attrs['silenceImmune'] and not attrs['stunImmune']
    assert len(row['modes'])==1 and not row['modes'][0]['raw']['_generalAbilities']
    nodes=row['modes'][0]['nodes'];combat=nodes['_combat'];raw=combat['raw']
    assert combat['native_class']=='MeleeAttack' and nodes['_attack']['status']==nodes['_attackTrigger']['status']=='native_null'
    assert (raw['_damageType'],raw['_attackType'],raw['_elementDamageType'],raw['_epDamageRatio'])==(1,1,0,0)
    assert (raw['_waitForAttackEvent'],raw['_selectTargetTiming'],raw['_timeMode'])==(1,0,0)
    assert raw['_selector']['m_PathID']==0 and not raw['_activeBuffs']
    cs=source['prefabs'][key]['components'];root=next(c for c in cs.values() if c['native_class']=='Enemy')
    mover=next(c for c in cs.values() if c['native_class']=='MoveController')
    assert not root['raw']['_commonAbilities']
    passives=row['passive_and_skill_components'];assert len(passives)==1 and passives[0]['class']=='PassiveBuffAbility'
    inline=passives[0]['raw']['_buffs'];assert len(inline)==1
    buff=inline[0];assert (buff['buffKey'],buff['templateKey'],buff['loadFromDB'],buff['isSilenceable'],buff['lifeTimeType'])==('enemy_refracting','empty',0,1,2)
    assert buff['attributes']['attributeModifiers']==[{'attributeType':3,'formulaItem':0,'value':0.0,'loadFromBlackboard':1,'fetchBaseValueFromSourceEntity':0}]
    assert not buff['attributes']['abnormalFlags'] and not buff['attributes']['abnormalImmunes']
    bb={item['key']:item['value'] for item in resolved['talentBlackboard']}
    assert bb=={'refracting.magic_resistance':70.0}
    name=key.split('_',2)[2];identity=vid.split('/')[-1];stem='ch9/'+name
    uid='unit/'+stem+'/'+identity;aid='ability/'+stem+'/combat';sid='selector/'+stem+'/blocker'
    bid='buff/'+stem+'/refracting';behavior='behavior/'+stem+'/combat';rule='rule/'+stem+'/'
    animation=combat['animation_binding'];hit=[event for event in animation['events'] if event['name']=='OnAttack']
    assert len(hit)==1 and hit[0]['exact_authored_frame'] and animation['duration']['exact_authored_frame']
    p={'schemaVersion':2,'manifest':{'id':'package/'+stem+'/source_v1','requires':['preset/ark_standard'],
       'metadata':{'source_locks':{str(path):sha(path) for path in (SOURCE,PLAN,Path(__file__))},
                   'required_runtime':CORE,'native_variant':vid,'native_reference':row['native_reference'],
                   'source_root':root,'source_combat':combat,'source_passive':passives[0],
                   'native_source_stats':attrs,'reference_policy':{
                       'attack_target':'Actual blocker captured at cast; physical current source/target attributes at hit',
                       'timing':'Source OnAttack and complete animation duration divided by current ASPD; baseAttackTime supplies ordinary cycle',
                       'refracting':'Permanent owned inline empty Buff, source ADDITION MRES+70; silence flag12 disables modifier until removed',
                       'movement':'Native steering8/10, source grid model with reference arrival radius.05',
                       'undefined_immunities':'Undefined extra DB immunity fields remain defaults, not source-defined false values',
                       'AV':'Effect key retained as metadata; no renderer playback'},
                   'whole_stage_executed':False,'independent_reviewed':False,'client_verified':False}},
       'entities':[{'id':uid,'kind':'entity','tags':['enemy','ground'],'metadata':{'native_variant':vid,'native_reference':row['native_reference']},
         'components':{'attributes':{'base':{'max_hp':attrs['maxHp'],'atk':attrs['atk'],'def':attrs['def'],'mres':attrs['magicResistance'],
                    'move_speed':attrs['moveSpeed'],'attack_interval':attrs['baseAttackTime'],'attack_speed_ratio':attrs['attackSpeed']/100,
                    'mass_level':attrs['massLevel'],'block_cost':root['raw']['_blockVolume']}},
           'resources':{'hp':{'initial':attrs['maxHp'],'capacity_attribute':'max_hp','role':'health'}},
           'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2,'abnormal_immunes':[]},
           'spatial':{'motion_mode':0,'steering':{'rule':rule+'steering','parameters':{'response_factor':mover['raw']['_steeringFactor'],
                          'max_acceleration':mover['raw']['_maxSteeringForce'],'arrival_radius':.05}}},
           'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':resolved['lifePointReduce']},
           'abilities':[aid],'behavior':{'machine':behavior},'buffs':{'initial':[bid]}}}],
       'buffs':[{'id':bid,'kind':'buff','stacking':{'mode':'refresh','max_stacks':buff['maxStackCnt']},
          'modifiers':[{'attribute':'mres','layer':'flat','value':bb['refracting.magic_resistance']}],
          'active_rule':rule+'not_silenced','metadata':{'native_buff_key':buff['buffKey'],'native_inline':buff}}],
       'abilities':[{'id':aid,'kind':'ability','selector':sid,'activation':{'mode':'automatic_attack','parameters':{'auto_only':True}},
          'target_capture':'at_cast','duration_seconds':animation['duration']['seconds'],
          'rules':{'ability.windup':rule+'windup','ability.duration':rule+'duration'},
          'timeline':[{'at_seconds':hit[0]['seconds'],'effect':{'op':'damage','damage_type':'physical','scale':raw['_atkScale'],
              'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'},
              'damage_flags':{'source_attack_type':'NORMAL','ignore_for_sp':False}}}],
          'metadata':{'source_OnAttack_frame':hit[0]['frame'],'source_full_frame':animation['duration']['frame']}}],
       'selectors':[{'id':sid,'kind':'selector','region':{'type':'all','blocked_only':True},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1}],
       'behaviors':[{'id':behavior,'kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],
          'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'normal','selector':sid}],
             'cast_groups':[{'key':'normal','abilities':[aid]}],
             'parameters':{'target_key':'normal','blocked_target':True,'stop_on_target':False,'stop_cast_groups':['normal']}}]}}],
       'rules':[{'id':rule+'steering','kind':'rule','contract':'movement.steering','implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}},
          {'id':rule+'not_silenced','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'12 not in inputs.status.abnormal_flags'}},
          {'id':rule+'windup','kind':'rule','contract':'ability.windup','implementation':{'type':'expression','expression':'inputs.timing_parameters.seconds/max(inputs.attributes.attack_speed_ratio,.01)'}},
          {'id':rule+'duration','kind':'rule','contract':'ability.duration','implementation':{'type':'expression','expression':'inputs.duration_parameters.seconds/max(inputs.attributes.attack_speed_ratio,.01)'}}]}
    fixture=deepcopy(p);fixture['scenarioDraft']={'id':'scene/'+stem+'/compile','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':2},
                  'initialEntities':[{'definition':uid,'position':{'row':0,'col':0}}]}
    Compiler().compile(fixture)
    return p


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    for key in ['enemy_1165_duhond','enemy_1166_dusbr']:
        value=build(key);path=OUT/(key+'.module.v1.json');assert not path.exists()
        path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
        print(json.dumps({'module':str(path),'sha':sha(path),'actual_compile':True,'whole_stage':False}))
