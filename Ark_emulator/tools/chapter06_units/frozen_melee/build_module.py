"""Exact two closed C6 native melee consumers; no unconsumed passive fallback."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'packages/campaign/chapter06_sources/native.reference.json'
PLAN=ROOT/'packages/campaign/chapter06_plans/source.plan.json'
COLD=ROOT/'packages/campaign/chapter06_cold/model.json'
OUT=ROOT/'packages/campaign/chapter06_units/frozen_melee'
PIN='efbf42be4db3ee14b98dcbdba72a516b35e54e2540e77ce64e32b060e8e5e6f3'
IDS=('enemy_1065_snwolf_2@0/a153592b593567e5','enemy_1069_icebrk@0/2115d20b3e309ca7')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def source():
    if sha(SOURCE)!=PIN or sha(COLD)!='e610f9446b077c6df7a86922e6719226e5a352a3826d6fe40c49e3296437b4dc':raise ValueError('Frozen source/module differs')
    return json.loads(SOURCE.read_bytes())
def build():
    s=source();p={'schemaVersion':2,'manifest':{'id':'package/chapter06/frozen_melee','requires':['preset/ark_standard'],'metadata':{'source_locks':{str(SOURCE.relative_to(ROOT)):PIN,str(COLD.relative_to(ROOT)):sha(COLD)},'builder_sha256':sha(Path(__file__)),'variant_bindings':[],'formal_approved':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False,'reference_policies':{'missing_DB_immunity':'Undefined wrappers use reference getter defaultFalse; retain native raw wrappers, do not reinterpret undefined as encodedFalse','frozen_dependency':'Read-only frozen Cold module exact e610..., pure provider registry and isolated4ef candidate required','frame_policy':'Native OnAttack seconds/frame at30Hz; current attack-speed applies via generic automatic_attack','born':'Exact source delayToBorn0; normal root getter defaults unchanged','windup':'Native16/29 frames divided effectiveASPD then ceil; min.01 and maximum animation-clamp relation remain explicitreplaceable policies, originalmaxAnimScale preserved','silence':'Native passiveisSilenceable0: sourceSilence does notremove targetFrozen atkscale; target predicate remainsactualflag16'}}},'entities':[],'abilities':[],'selectors':[],'behaviors':[],'rules':[{'id':'rule/ch6/units/steering','kind':'rule','contract':'movement.steering','implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}}]}
    for vid in IDS:
        v=s['variants'][vid];r=v['native_enemy']['resolved'];a=r['attributes'];prefab=s['prefabs'][v['prefab_key']]
        root=next(c for c in prefab['components'].values() if c['native_class']=='Enemy');mover=next(c for c in prefab['components'].values() if c['native_class']=='MoveController')
        nodes=v['modes'][0]['nodes'];combat=nodes['_combat'];raw=combat['raw'];passives=v['passive_and_skill_components']
        if len(v['modes'])!=1 or nodes['_attack'].get('native_class') or nodes['_attackTrigger'].get('native_class') or v['additional_animation_drivers']:raise ValueError('Extra mode/driver dependency')
        if combat['native_class']!='MeleeAttack' or any(raw.get(k) for k in ('_extraDamageType','_epDamageRatio','_activeBuffs')) or (raw['_selectTargetSource'],raw['_waitForAttackEvent'],raw['_atkScale'],raw['_damageType'])!=(2,1,1,1):raise ValueError('Nonclosed melee source')
        if root['raw']['_delayToBorn']!=0 or a['hpRecoveryPerSec']!=0 or a['spRecoveryPerSec']!=0 or r.get('skills'):raise ValueError('Extra born/recovery/skill dependency')
        ratio=None
        if len(passives)!=1 or passives[0]['class']!='PassiveBuffAbility':raise ValueError('Unexpected passive closure')
        buffs=passives[0]['raw']['_buffs']
        if len(buffs)!=1 or buffs[0]['templateKey']!='e2c_frozen_atkscale' or buffs[0]['isSilenceable']!=0 or any(buffs[0]['attributes'].values()):raise ValueError('Passive source changed')
        expected=1.5 if vid==IDS[0] else 2.5
        bb=r['talentBlackboard']
        if bb!=[{'key':'atkup.atk_scale','value':expected,'valueStr':None}]:raise ValueError('Exact frozen conditional scale')
        ratio=bb[0]['value']
        events=[e for e in combat['animation_binding']['events'] if e['name']=='OnAttack']
        if len(events)!=1:raise ValueError('Actual frame must bind once')
        uid='unit/ch6/'+vid.split('@')[0]+'/'+vid.split('/')[-1];aid='ability/'+uid;sid='selector/'+uid;bid='behavior/'+uid
        base={'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],'move_speed':a['moveSpeed'],'attack_interval':a['baseAttackTime'],'attack_speed_ratio':a['attackSpeed']/100,'mass_level':a['massLevel'],'block_cost':root['raw']['_blockVolume']}
        unit={'id':uid,'kind':'entity','tags':['enemy','ground'],'components':{'attributes':{'base':base},'resources':{'hp':{'initial':a['maxHp'],'capacity':a['maxHp'],'role':'health'}},'spatial':{'motion_mode':0,'steering':{'rule':'rule/ch6/units/steering','parameters':{'response_factor':mover['raw']['_steeringFactor'],'max_acceleration':mover['raw']['_maxSteeringForce'],'arrival_radius':.05}}},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2,'abnormal_immunes':[]},'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':r['lifePointReduce']},'abilities':[aid],'behavior':{'machine':bid}},'metadata':{'native_variant_id':vid,'native_reference':v['native_reference']}}
        if ratio:unit['components']['buffs']={'initial':['buff/ch6/cold/frozen_atkscale'+str(ratio)]}
        p['entities'].append(unit)
        p['selectors'].append({'id':sid,'kind':'selector','region':{'type':'all','blocked_only':True},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1})
        timing='rule/'+aid+'/windup'
        if (raw['_affectedBySlowDown'],raw['_timeMode'])!=(1,0):raise ValueError('Native timing dependency')
        p['rules'].append({'id':timing,'kind':'calculation_rule','contract':'ability.windup','parameters':{'minimum_speed':.01,'native_max_anim_scale':raw['_maxAnimScale']},'implementation':{'type':'expression','expression':'inputs.timing_parameters.seconds / max(inputs.attributes.attack_speed_ratio, params.minimum_speed)'},'metadata':{'reference_replaceable':True,'native_timing_fields':{k:raw[k] for k in ('_affectedBySlowDown','_timeMode','_maxAnimScale','_animKey')}}})
        p['abilities'].append({'id':aid,'kind':'ability','rules':{'ability.windup':timing},'selector':sid,'activation':{'mode':'automatic_attack','parameters':{'auto_only':True}},'target_capture':'at_cast','timeline':[{'at_seconds':events[0]['seconds'],'effect':{'op':'damage','damage_type':'physical','scale':1,'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}}],'metadata':{'source_combat':combat,'native_OnAttack_frame':events[0]['frame']}})
        p['behaviors'].append({'id':bid,'kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'normal','selector':sid}],'cast_groups':[{'key':'normal','abilities':[aid]}],'parameters':{'target_key':'normal','blocked_target':True,'stop_on_target':False,'stop_cast_groups':['normal']}}]}})
        p['manifest']['metadata']['variant_bindings'].append({'variant_id':vid,'unit_definition':uid,'native_reference':v['native_reference'],'source_enemy_root':root,'source_mover':mover,'passive_components':passives,'resolved_attributes':a,'raw_DB_rows':v['native_enemy']['raw_rows'],'OnAttack_frame':events[0]['frame'],'frozen_atk_scale':ratio})
    return p
def matrix():
    s=source();plan=json.loads(PLAN.read_bytes());priorities={'enemy_1006_shield_2':(1,'Plain melee14; first closed'),'enemy_1064_snsbr':(2,'Melee12 + exactTARGETFROZEN1.5; second closed'),'enemy_1065_snwolf_2':(3,'Melee16 + TARGETFROZEN1.5'),'enemy_1069_icebrk':(3,'Melee29 + TARGETFROZEN2.5'),'enemy_1066_snbow':(4,'Ranged12 + targetFrozen1.5, selector/projectile'),'enemy_1067_snslime':(5,'Melee14 + unsilenced death projectile/ATK2/Cold10'),'enemy_1068_snmage_2':(6,'Ranged20 + EnemySkill SP2/coldattack priority0/ReadyEffect'),'enemy_1510_frstar2':(7,'Two modes28/reborn10/HP50%/ATK+.5/invinc20, shields/branch/Cold5/10'),'enemy_1510_frstar2_s':(8,'Independent NeverTrigger/no normal frame, init16/23 skills, PURE NoSource2000/story')}
    rows=[]
    for vid,v in s['variants'].items():
        priority,scope=priorities[v['native_enemy']['native_id']]
        rows.append({'variant_id':vid,'priority':priority,'consumer_dependencies':scope,'stages':v['stages'],'native_reference':v['native_reference'],'attributes':v['native_enemy']['resolved']['attributes'],'modes':v['modes'],'passive_and_skill_components':v['passive_and_skill_components'],'authored_in_this_batch':vid in IDS,'independent_reviewed':False})
    return {'schema':'ark-sim/chapter06-units-dependency-priority/v1','plan_sha256':sha(PLAN),'native_sha256':PIN,'fixed_commit':plan['fixed_commit'],'stages':{k:{'variants':v['variant_ids'],'births':v['spawn_count'],'source_counts':v['spawn_by_key']} for k,v in plan['stages'].items()},'variants':sorted(rows,key=lambda r:(r['priority'],r['variant_id'])),'formal_approved':False,'whole_stage_executed':False,'client_verified':False}
if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True);write(OUT/'dependency.priority.json',matrix());write(OUT/'model.json',build());print(json.dumps({'module_sha256':sha(OUT/'model.json'),'matrix_sha256':sha(OUT/'dependency.priority.json')}))
