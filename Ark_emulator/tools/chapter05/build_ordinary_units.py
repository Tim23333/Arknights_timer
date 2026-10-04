"""Exact ordinary C5 unit operands and native melee clocks, no passive skip."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter05_sources/native.reference.json'
PIN='323baee04eca79f6e750cf45d460ffe678667c1614763814436402e8187badd5'
OUT=ROOT/'packages/campaign/chapter05_units/ordinary.reference_model.json'


def build():
    raw=SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('C5 source operands drift')
    source=json.loads(raw);p={'schemaVersion':2,'manifest':{'id':'package/chapter05/ordinary_units','requires':['preset/ark_standard'],'metadata':{
        'source_locks':{'packages/campaign/chapter05_sources/native.reference.json':PIN},'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope':'Two exact uncomplicated melee variants; every passive/ranged/skill variant excluded',
        'client_verified':False,'formal_approved':False,'whole_stage_executed':False,'variant_bindings':[]}},'entities':[],'abilities':[],'selectors':[],'behaviors':[],
        'rules':[{'id':'rule/ch5/unit_steering','kind':'rule','contract':'movement.steering','implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}}]}
    for vid,v in source['variants'].items():
        if v['passive_and_skill_components'] or len(v['modes'])!=1 or v.get('additional_animation_drivers'):continue
        mode=v['modes'][0];nodes=mode['nodes'];combat=nodes['_combat']
        if nodes['_attack'].get('native_class') or nodes['_attackTrigger'].get('native_class'):continue
        is_fly=v['native_enemy']['resolved']['motion']=='FLY'
        if not is_fly and combat.get('native_class') not in ('MeleeAttack','MultiMeleeAttack'):continue
        resolved=v['native_enemy']['resolved'];a=resolved['attributes'];prefab=source['prefabs'][v['prefab_key']]
        root=next(row['raw'] for row in prefab['components'].values() if row['native_class']=='Enemy')
        mover=next(row['raw'] for row in prefab['components'].values() if row['native_class']=='MoveController')
        if root['_delayToBorn']!=0 or a.get('hpRecoveryPerSec')!=0 or a.get('spRecoveryPerSec')!=0 or a.get('stunImmune') is not False or resolved.get('talentBlackboard') or resolved.get('skills'):
            continue  # Explicitly excludes regen/talent/DB-skill dependencies; never drops them from a modeled actor
        uid='unit/ch5/'+vid.split('@')[0]+'/'+vid.split('/')[-1];sid='selector/'+uid;aid='ability/'+uid;bid='behavior/'+uid
        base={'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],'move_speed':a['moveSpeed'],
            'attack_interval':a['baseAttackTime'],'attack_speed_ratio':a['attackSpeed']/100,'mass_level':a['massLevel'],'block_cost':root['_blockVolume']}
        unit={'id':uid,'kind':'entity','tags':['enemy','fly' if is_fly else 'ground'],'components':{'attributes':{'base':base},
            'resources':{'hp':{'initial':a['maxHp'],'capacity':a['maxHp'],'role':'health'}},
            'spatial':{'motion_mode':1 if is_fly else 0,'steering':{'rule':'rule/ch5/unit_steering','parameters':{'response_factor':mover['_steeringFactor'],'max_acceleration':mover['_maxSteeringForce'],'arrival_radius':.05}}},
            'selection_state':{'side':1,'motion':2 if is_fly else 1,'category':1,'unit_type':2},'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':resolved['lifePointReduce']},'abilities':[]},
            'metadata':{'native_variant_id':vid,'native_reference':v['native_reference'],'no_extra_source_state':'born0/regen0/stunimmuneFalse asserted; actor getter defaults declared'}}
        frame=None
        if not is_fly:
            r=combat['raw']
            if r['_selectTargetSource']!=2 or r['_waitForAttackEvent']!=1 or r['_atkScale']!=1 or r['_damageType']!=1 or r['_extraDamageType'] or r['_epDamageRatio'] or r['_activeBuffs']:
                raise ValueError('Unexpected ordinary melee consumer')
            events=[e for e in combat['animation_binding']['events'] if e['name']=='OnAttack']
            multi=combat['native_class']=='MultiMeleeAttack'
            if multi:
                if r['_additionalTimes']!=1 or r['_splitDamage']!=1 or r['_waitAttackEventForAllAttacks']!=1 or r['_triggerDelta']!=0 or [e['frame'] for e in events]!=[12,23]:raise ValueError('Exact multi-hit source consumer differs')
                scale=.5
            else:
                if len(events)!=1:raise ValueError('Actual melee OnAttack must bind once')
                scale=1
            frame=[e['frame'] for e in events] if multi else events[0]['frame'];unit['components']['abilities']=[aid];unit['components']['behavior']={'machine':bid}
            p['selectors'].append({'id':sid,'kind':'selector','region':{'type':'all','blocked_only':True},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1})
            p['abilities'].append({'id':aid,'kind':'ability','selector':sid,'activation':{'mode':'automatic_attack','parameters':{'auto_only':True}},
                'target_capture':'at_cast','timeline':[{'at_seconds':event['seconds'],'effect':{'op':'damage','damage_type':'physical','scale':scale,'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}} for event in events],
                'metadata':{'source_combat_path_id':combat['path_id'],'source_node':combat,'fixed_OnAttack_frame':frame,
                    'split_policy':'Equal total attack before per-hit defense, source splitDamage1; native formula calibration pending' if multi else None}})
            p['behaviors'].append({'id':bid,'kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],
                'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'normal','selector':sid}],
                    'cast_groups':[{'key':'normal','abilities':[aid]}],'parameters':{'target_key':'normal','blocked_target':True,'stop_on_target':False,'stop_cast_groups':['normal']}}]}})
        p['entities'].append(unit);p['manifest']['metadata']['variant_bindings'].append({'variant_id':vid,'unit_definition':uid,
            'native_reference':v['native_reference'],'native_motion':resolved['motion'],'OnAttack_frame':frame,'source_enemy_root':root,'source_mover':mover})
    if len(p['entities'])!=2:raise ValueError('Expected two exact ordinary melee variants; source NoPre/ranged/passive consumers explicitly excluded')
    return p


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Ordinary C5 source package changed')
    else:OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'ordinary_entities':len(p['entities'])}))
