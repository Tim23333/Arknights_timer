"""Source-backed synthetic V2 attack-mode prototypes, never native-unit approval."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NORMALIZED=ROOT/'packages/campaign/operators.normalized.json'
ROSTER=ROOT/'packages/campaign/roster.reference.json'
LOCK=ROOT/'packages/campaign/operator_sources.lock.json'
FRAMES=ROOT.parent/'data/tables/effect_frames.json'
RANGES=ROOT/'ark_emulator/data_range_table.json'  # Read-only offline JSON only.
ANGEL_SKILL='ability/campaign_angel_s3'
ANGEL_NORMAL='ability/campaign_angel_normal'
ANGEL_BURST='ability/campaign_angel_burst'
CHEN_SKILL='ability/campaign_chen_s1'
CHEN_NORMAL='ability/campaign_chen_normal'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def character_components(cid):
    import UnityPy
    files=list((ROOT.parent/'data/charpack'/f'{cid}.ab_unpacked').glob('CAB-*'))
    if len(files)!=1:
        raise ValueError(f'{cid}: expected one explicit native charpack CAB')
    path=files[0];objects={}
    for obj in UnityPy.load(str(path)).objects:
        if obj.type.name=='MonoBehaviour':
            tree=obj.read_typetree()
            objects[obj.path_id]={'script_path_id':tree.get('m_Script',{}).get('m_PathID'),
                                 'fields':{k:v for k,v in tree.items() if not k.startswith('m_')}}
    roots=[i for i,t in objects.items() if '_modes' in t['fields']]
    if len(roots)!=1:
        raise ValueError(f'{cid}: native mode root missing/ambiguous')
    root=roots[0];selected={str(root):objects[root]};modes=[]
    for slot in objects[root]['fields']['_modes']:
        if slot['m_FileID']!=0:
            raise ValueError('Native mode external CAB mapping unresolved')
        mid=slot['m_PathID'];mode=objects[mid];selected[str(mid)]=mode
        linked={}
        for key in ('_attack','_attackTrigger'):
            ref=mode['fields'][key]
            if ref['m_FileID']!=0 or ref['m_PathID'] not in objects:
                raise ValueError('Native attack/trigger link unresolved')
            selected[str(ref['m_PathID'])]=objects[ref['m_PathID']]
            linked[key]=objects[ref['m_PathID']]['fields']
        modes.append({'path_id':mid,**linked})
    return path,selected,modes


def sources(cid):
    normalized=read(NORMALIZED);roster=read(ROSTER)
    operator=next(r for r in normalized['operators'] if r['character_id']==cid)
    reference=next(r for r in roster['roster'] if r['character_id']==cid)
    level=operator['selected_skill']['level']
    if operator['config']!=reference['config'] or operator['selected_skill']['native_level_index']!=9:
        raise ValueError('Fixed selected official configuration drifted')
    for name in ('duration','prefabId','rangeId'):
        if name not in reference['skill_level']:
            if level[name] in (None,0):
                continue  # Legacy extraction omitted zero/null; official table is authoritative.
            raise ValueError(f'Frozen local nondefault field missing: {name}')
        local=reference['skill_level'][name]
        if level[name]!=local:
            raise ValueError(f'Official/local skill field mismatch: {name}')
    for name in ('spCost','initSp','increment','maxChargeTime'):
        if name not in reference['skill_level']['spData']:
            if level['spData'][name]==0:
                continue
            raise ValueError(f'Frozen local nonzero SP field missing: {name}')
        if level['spData'][name]!=reference['skill_level']['spData'][name]:
            raise ValueError(f'Official/local SP mismatch: {name}')
    if level['skillType']!='AUTO' or level['spData']['maxChargeTime']!=1:
        raise ValueError('Prototype requires AUTO/one charge')
    values={r['key']:r['value'] for r in level['blackboard']}
    if len(values)!=len(level['blackboard']) or any(v is None for v in values.values()):
        raise ValueError('Skill blackboard missing/ambiguous')
    if values!={r['key']:r['value'] for r in reference['skill_level']['blackboard']}:
        raise ValueError('Official/local selected blackboard mismatch')
    prefab=roster['frozen']['prefab_catalog'][level['prefabId']]
    closure={(c['cabin'],c['pathID']):c for c in roster['frozen']['linked_components']}
    for component in prefab['components']:
        if closure.get((component['cabin'],component['pathID']))!=component:
            raise ValueError('Frozen skill CAB component closure mismatch')
    path,components,modes=character_components(cid)
    frames=read(FRAMES)['characters'][cid]
    rid=operator['normal_attack_source']['range_id']
    range_data=read(RANGES)[rid]
    metadata={'scope':'selected skill composition; synthetic attributes; not official E2 unit or mainline conversion',
        'official_unit_config_imported':False,'client_validated':False,'operator_id':cid,
        'source_hashes':{'normalized':sha(NORMALIZED),'roster':sha(ROSTER),'operator_source_lock':sha(LOCK),
                         'charpack':sha(path),'effect_frames':sha(FRAMES),'offline_range_json':sha(RANGES),
                         'recipe_builder':sha(Path(__file__))},
        'source_paths':{'charpack':str(path.resolve()),'effect_frames':'../data/tables/effect_frames.json'},
        'official_selected_skill':operator['selected_skill'],'native_skill_prefab':prefab,
        'native_character_components':components,'native_frames':frames,'native_range_id':rid,'native_range_row':range_data,
        'source_gaps':['talents and native full attributes/config not implemented',
                       'client animation/FSM playback scaling and same-tick mode expiry alignment pending',
                       'range coordinates read from offline historical JSON; current range_table calibration pending',
                       'native deployment/retreat/target tie-breaking and full character lifecycle pending']}
    return operator,level,values,prefab,modes,frames,range_data,metadata


def effect_damage(scale=1):
    return {'op':'damage','damage_type':'physical','scale':scale,
            'read_mode':{'source_attributes':'at_launch'}}


def entity(cid,abilities,sp,interval=1):
    return {'id':f'unit/{cid}_fixture','kind':'entity','tags':['player'],
        'metadata':{'status':'partially_implemented','synthetic_attributes':True},'components':{
        'attributes':{'base':{'atk':100,'max_hp':10000,'def':0,'mres':0,'attack_interval':interval,
                              'attack_speed_ratio':1,'attack_times':1,'block_count':1}},
        'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'},'sp':sp},
        'spatial':{},'behavior':{'machine':'behavior/player_combat'},'abilities':abilities,
        'lifecycle':{'policy':'policy/ark_lifecycle'}}}


def target():
    return {'id':'unit/attack_recipe_target','kind':'entity','tags':['enemy'], 'components':{
        'attributes':{'base':{'max_hp':100000,'def':10,'mres':0,'move_speed':0.1,'block_cost':1,
                              'atk':10,'attack_interval':1,'attack_speed_ratio':1}},
        'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},'spatial':{},
        'lifecycle':{'policy':'policy/ark_lifecycle'}}}


def selector(cid,range_data):
    return {'id':f'selector/{cid}_attack','kind':'selector',
        'region':{'type':'grid_offsets','offsets':[[g['row'],g['col']] for g in range_data['grids']],
                  'rotate_with_facing':False},
        'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1}


def scene(cid,actor,enemy):
    return {'id':f'scenario/{cid}_attack_recipe','ruleset':'ruleset/ark_standard',
        'metadata':{'status':'partially_implemented','not_formal_mainline':True},'map':{'rows':5,'cols':6},
        'initialEntities':[{'definition':actor['id'],'instanceAlias':'actor','position':{'row':2,'col':1}},
                           {'definition':enemy['id'],'instanceAlias':'target','position':{'row':2,'col':2}}]}


def attack_events(frames,anim):
    result=[e for e in frames['anims'][anim]['ev'] if e['n']=='OnAttack']
    if not result:
        raise ValueError(f'Native OnAttack events missing for {anim}')
    return result


def build_angel():
    cid='char_103_angel';o,level,bb,prefab,modes,frames,ranges,meta=sources(cid)
    if level['spData']['spType']!='INCREASE_WITH_TIME' or len(modes)!=2:
        raise ValueError('Expected native two-mode automatic time-SP operator')
    native=modes[1]['_attack'];normal=modes[0]['_attack']
    wrapper=next(c['fields'] for c in prefab['components'] if c['class']=='AttackAbility')
    if wrapper['_attackBlackboardModeIndex']!=1 or wrapper['_allowSpRecoveryWhenAffecting']!=0:
        raise ValueError('Native selected attack mode/SP freeze changed')
    if native['_damageType']!=1 or native['_waitForAttackEvent']!=1 or native['_waitAttackEventForAllAttacks']!=0:
        raise ValueError('Native burst damage/attack event semantics changed')
    if normal['_damageType']!=1 or normal['_waitForAttackEvent']!=1 or modes[1]['_attackTrigger']['_keepTarget']!=0:
        raise ValueError('Native normal/retarget semantics changed')
    times=bb['attack@times']
    if times!=int(times) or times<=0:
        raise ValueError('Native burst count must be positive integer')
    modebuff='buff/campaign_angel_overload';sel=f'selector/{cid}_attack'
    events=attack_events(frames,'Attack')
    if len(events)!=1:
        raise ValueError('Native first-launch animation event ambiguous')
    windup=events[0]['t'];delta=native['_triggerDelta']
    speed=frames['modes'][1]['attack']['projectileSpeed']
    if speed<=0 or native['_projectileKey']!=frames['modes'][1]['attack']['projectileKey']:
        raise ValueError('Native projectile identity/speed missing')
    duration=level['duration']
    manual={'id':ANGEL_SKILL,'kind':'ability','metadata':{'status':'partially_implemented','native_skill_id':o['config']['skill_id']},
        'activation':{'mode':'manual','costs':[{'resource':'sp','amount':level['spData']['spCost']}],
                      'parameters':{'auto_when_ready':True,'auto_only':True},
                      'on_start':[{'op':'modify_resource','target':'source','resource':'mode','delta':1},
                                  {'op':'apply_buff','target':'source','buff':modebuff}]},
        'parameters':{'blocks_attacks':False},'duration_seconds':duration,
        'timeline':[]}
    common={'kind':'ability','selector':sel,'target_capture':'each_hit','parameters':{'blocks_attacks':True}}
    basic={**common,'id':ANGEL_NORMAL,'activation':{'mode':'automatic_attack','condition':'inputs.resources.mode.current == 0'},
           'timeline':[{'at_seconds':windup,'effect':effect_damage()}]}
    burst={**common,'id':ANGEL_BURST,'activation':{'mode':'automatic_attack','condition':'inputs.resources.mode.current == 1'},
        'parameters':{'blocks_attacks':True,'projectile_speed':speed},
        'timeline':[{'at_seconds':windup,'repeat':{'rule':'rule/campaign_angel_repeat','count':1,'interval_seconds':delta},
                     'effect':effect_damage(bb['attack@atk_scale'])}]}
    reset={'id':'ability/campaign_angel_mode_cleanup','kind':'ability',
        'activation':{'mode':'passive','event':'buff.removed',
          'condition':f'inputs.payload.source == inputs.source.id and inputs.payload.target == inputs.source.id and inputs.payload.buff == "{modebuff}"'},
        'parameters':{'blocks_attacks':False},
        'timeline':[]}
    actor=entity(cid,[ANGEL_SKILL,ANGEL_NORMAL,ANGEL_BURST,reset['id']],
        {'initial':level['spData']['initSp'],'capacity':level['spData']['spCost'],'recovery_rate':level['spData']['increment'],
         'recovery':{'mode':'periodic','interval_seconds':1},
         'parameters':{'pause_at_full':True,'freeze_while_cast':True,'freeze_cast_modes':['manual']}})
    actor['components']['resources']['mode']={'initial':0,'capacity':1}
    enemy=target();meta['model_timing_policy']={'animation_playback':'unscaled 1x synthetic fixture',
        'first_shot_seconds':windup,'additional_shot_delta_seconds':delta,
        'repeat_sampling':'count captured at cast start via effective attack_times',
        'damage_sampling':'at_launch, physical scale1.1; projectile travel from declared speed',
        'expiry':'mode is set to0 synchronously by Buff.on_remove before end-tick sampling; existing next_attack clock is preserved',
        'auto_command_api':'AUTO lowered through auto_when_ready manual core mode with explicit auto_only command rejection'}
    return {'schemaVersion':2,'status':'partially_implemented',
        'manifest':{'id':'package/campaign_angel_s3_recipe','version':'1','metadata':meta},
        'entities':[actor,enemy],'abilities':[manual,basic,burst,reset],
        'buffs':[{'id':modebuff,'kind':'buff','duration_seconds':duration,
            'on_remove':[{'op':'modify_resource','target':'source','resource':'mode','value':0}], 'modifiers':[
            {'attribute':'attack_interval','layer':'flat','value':bb['base_attack_time']},
            {'attribute':'attack_times','layer':'flat','value':times-1}]}],
        'selectors':[selector(cid,ranges)],'rules':[{'id':'rule/campaign_angel_repeat','kind':'calculation_rule',
            'version':'1','contract':'ability.repeat','implementation':{'type':'expression',
            'expression':'{"count": floor(inputs.attributes.attack_times), "interval": inputs.repeat_parameters.interval_seconds}'}}],
        'scenarioDraft':scene(cid,actor,enemy)}


def build_chen():
    cid='char_010_chen';o,level,bb,prefab,modes,frames,ranges,meta=sources(cid)
    if level['spData']['spType']!='INCREASE_WHEN_ATTACK' or len(modes)!=1:
        raise ValueError('Expected native single-mode attack-SP operator')
    normal=modes[0]['_attack']
    if normal['_additionalTimes']!=1 or normal['_waitAttackEventForAllAttacks']!=1 or normal['_damageType']!=1:
        raise ValueError('Native normal double-hit semantics changed')
    damage=next(c['fields'] for c in prefab['components'] if '_atkScaleKey' in c['fields'])
    wrapper=next(c['fields'] for c in prefab['components'] if c['class']=='AttackAbility')
    if damage['_damageType']!=1 or damage['_atkScaleKey']!='atk_scale' or wrapper['_allowSpRecoveryWhenAffecting']!=0:
        raise ValueError('Native replacement damage/SP semantics changed')
    stun=next(b for b in damage['_activeBuffs'] if b['buffKey']=='stun')
    if stun['durationKey']!='stun' or stun['attributes']['abnormalFlags']!=[0]:
        raise ValueError('Native on-hit stun semantics changed')
    ev=attack_events(frames,'Attack')
    if len(ev)!=2:
        raise ValueError('Native double-hit animation events missing')
    sel=f'selector/{cid}_attack';stunid='buff/campaign_chen_stun'
    skill={'id':CHEN_SKILL,'kind':'ability','metadata':{'status':'partially_implemented','native_skill_id':o['config']['skill_id']},
        'activation':{'mode':'automatic_attack','costs':[{'resource':'sp','amount':level['spData']['spCost']}],
                      'parameters':{'replace_attack':True,'auto_only':True}},'selector':sel,'target_capture':'at_cast',
        'timeline':[{'at_seconds':damage['_preDelay'],'effect':{**effect_damage(bb['atk_scale']),
            'on_success':[{'op':'apply_buff','buff':stunid,
                           'condition':'inputs.targets[0].components.runtime.alive'}]}}]}
    basic={'id':CHEN_NORMAL,'kind':'ability','activation':{'mode':'automatic_attack'},'selector':sel,
           'target_capture':'at_cast','timeline':[{'at_seconds':e['t'],'effect':effect_damage()} for e in ev]}
    actor=entity(cid,[CHEN_SKILL,CHEN_NORMAL],{'initial':level['spData']['initSp'],'capacity':level['spData']['spCost'],
        'recovery_rule':'rule/campaign_chen_attack_sp','recovery':{'mode':'event','event':'attack.accepted','owner_role':'source',
            'amount':level['spData']['increment'],'condition':f'inputs.event.ability == "{CHEN_NORMAL}"'},
        'parameters':{'pause_at_full':True}},interval=frames['anims']['Attack']['d'])
    enemy=target();meta['model_timing_policy']={'animation_playback':'normal Attack source1.5s at1x synthetic fixture',
        'normal_hit_seconds':[e['t'] for e in ev],'skill_prefab_predelay_seconds':damage['_preDelay'],
        'skill_spine_attack_seconds':[e['t'] for e in attack_events(frames,'Skill')],
        'discrepancy':'prefab .533 differs from Spine Skill .4667; prefab drives prototype; client FSM alignment pending',
        'replacement':'ordered automatic_attack priority; if cost4 cannot pay, normal cast is selected',
        'sp':'one attack.accepted for normal double-hit cast; native skill affecting SP=false excludes replacement event'}
    meta['source_gaps'].append('native stun immunity/status-resistance and animation post-escape alignment pending')
    return {'schemaVersion':2,'status':'partially_implemented',
        'manifest':{'id':'package/campaign_chen_s1_recipe','version':'1','metadata':meta},
        'entities':[actor,enemy],'abilities':[skill,basic],
        'buffs':[{'id':stunid,'kind':'buff','duration_seconds':bb['stun'],
                  'control':{'move':False,'attack':False,'abilities':False,'block':False,'interrupt':True}}],
        'selectors':[selector(cid,ranges)],'rules':[{'id':'rule/campaign_chen_attack_sp','kind':'calculation_rule',
            'version':'1','contract':'resource.recovery','implementation':{'type':'expression',
            'expression':'inputs.current + inputs.parameters.amount'}}],
        'scenarioDraft':scene(cid,actor,enemy)}


def build(operator):
    if operator=='angel':
        return build_angel()
    if operator=='chen':
        return build_chen()
    raise ValueError(f'Unsupported attack recipe {operator!r}')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--operator',choices=('angel','chen','all'),default='all')
    p.add_argument('--check',action='store_true')
    args=p.parse_args()
    names=('angel','chen') if args.operator=='all' else (args.operator,)
    for name in names:
        result=build(name);path=ROOT/'packages/campaign'/f'skills.{name}.json'
        if args.check:
            if read(path)!=result:
                raise ValueError(f'{name}: recipe source/output identity drifted')
        else:
            path.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
        print(f'{name}: partially_implemented source-backed synthetic recipe')


if __name__=='__main__':
    main()
