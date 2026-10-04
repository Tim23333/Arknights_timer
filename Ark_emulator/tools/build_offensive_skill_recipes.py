"""Manual offensive recipes; unresolved RNG/FSM stay explicit probe boundaries."""
import argparse
import json
from pathlib import Path
import sys

_PACKAGE_ROOT=str(Path(__file__).resolve().parents[1])
if _PACKAGE_ROOT not in sys.path:
    sys.path.insert(0,_PACKAGE_ROOT)

from tools.build_attack_skill_recipes import (ROOT,NORMALIZED,ROSTER,LOCK,FRAMES,RANGES,read,sha,
    character_components,entity,target,selector,scene)

BPIPE_SKILL='ability/campaign_bpipe_s3'
BPIPE_NORMAL='ability/campaign_bpipe_normal'
BPIPE_BURST='ability/campaign_bpipe_triple'
AMGOAT_SKILL='ability/campaign_amgoat_s3'
AMGOAT_NORMAL='ability/campaign_amgoat_normal'
AMGOAT_PACKET='ability/campaign_amgoat_probe_packet'


def source(cid):
    o=next(r for r in read(NORMALIZED)['operators'] if r['character_id']==cid)
    roster=read(ROSTER);frozen=next(r for r in roster['roster'] if r['character_id']==cid)
    level=o['selected_skill']['level'];prefab=roster['frozen']['prefab_catalog'][level['prefabId']]
    if o['config']!=frozen['config'] or o['selected_skill']['native_level_index']!=9:
        raise ValueError('Selected configuration drifted')
    if level['skillType']!='MANUAL' or level['spData']['spType']!='INCREASE_WITH_TIME' or level['spData']['maxChargeTime']!=1:
        raise ValueError('Recipe requires native manual/time-SP/one charge')
    for name in ('duration','prefabId'):
        if level[name]!=frozen['skill_level'][name]:
            raise ValueError(f'Official/local field mismatch {name}')
    for name in ('initSp','spCost','increment','maxChargeTime'):
        if level['spData'][name]!=frozen['skill_level']['spData'][name]:
            raise ValueError(f'Official/local SP mismatch {name}')
    bb={r['key']:r['value'] for r in level['blackboard']}
    if len(bb)!=len(level['blackboard']) or any(v is None for v in bb.values()) or bb!={r['key']:r['value'] for r in frozen['skill_level']['blackboard']}:
        raise ValueError('Selected skill blackboard missing/ambiguous/drifted')
    closure={(c['cabin'],c['pathID']):c for c in roster['frozen']['linked_components']}
    if any(closure.get((c['cabin'],c['pathID']))!=c for c in prefab['components']):
        raise ValueError('Skill native component closure drifted')
    cab,components,modes=character_components(cid)
    import UnityPy
    trees={obj.path_id:obj.read_typetree() for obj in UnityPy.load(str(cab)).objects if obj.type.name=='MonoBehaviour'}
    native_selectors=[]
    for mode in modes:
        ref=mode['_attack']['_selector']
        if ref['m_PathID']:
            if ref['m_FileID']!=0 or ref['m_PathID'] not in trees:
                raise ValueError('Native selector external/missing')
            tree=trees[ref['m_PathID']]
            data={'script_path_id':tree['m_Script']['m_PathID'],'fields':{k:v for k,v in tree.items() if not k.startswith('m_')}}
            components[str(ref['m_PathID'])]=data;native_selectors.append(data['fields'])
        else:
            native_selectors.append(None)
    frame_source=read(FRAMES);frames=frame_source['characters'][cid]
    ranges=read(RANGES)
    normal_range=ranges[o['normal_attack_source']['range_id']]
    skill_range=ranges[level['rangeId']] if level['rangeId'] else normal_range
    wrapper=next(c['fields'] for c in prefab['components'] if c['class']=='AttackAbility')
    if wrapper['_allowSpRecoveryWhenAffecting']!=0 or wrapper['_allowNoTarget']!=1:
        raise ValueError('Native SP freeze/no-target manual activation changed')
    buffs=[b for c in prefab['components'] for b in c['fields'].get('_buffs',[]) if b['templateKey'].startswith('switch_mode')]
    if len(buffs)!=1:
        raise ValueError('Native selected switch-mode buff ambiguous')
    pending=['full_unit_attributes_talents_and_deploy_lifecycle_pending',
             'native_animation_playback_and_mode_transition_client_alignment_pending',
             'native_range_table_correspondence_pending','native_mode_detach_end_tick_client_alignment_pending']
    metadata={'status':'partially_implemented','synthetic_attributes':True,'official_unit_complete':False,
        'client_validated':False,'native_selected_skill':o['selected_skill'],'native_skill_prefab':prefab,
        'native_character_components':components,'native_animation_frames':frames,'native_selectors':native_selectors,
        'native_normal_range':normal_range,'native_skill_range':skill_range,'pending_mechanics':pending,
        'source_hashes':{'normalized':sha(NORMALIZED),'roster':sha(ROSTER),'operator_source_lock':sha(LOCK),
                        'charpack':sha(cab),'effect_frames':sha(FRAMES),'range_json':sha(RANGES),
                        'attack_helper':sha(ROOT/'tools/build_attack_skill_recipes.py'),'offensive_builder':sha(Path(__file__))}}
    return o,level,bb,prefab,modes,native_selectors,frames,frame_source['meta']['tick'],normal_range,skill_range,buffs[0],metadata


def frame_delays(frames,animation,fps):
    events=[e for e in frames['anims'][animation]['ev'] if e['n']=='OnAttack']
    if not events or fps<=0:
        raise ValueError('Native animation attack events missing')
    # f retains exact source-frame positions; t was rounded to four decimals.
    return [e['f']/fps for e in events]


def skill_activation(identifier,level,buff):
    return {'id':identifier,'kind':'ability','metadata':{'status':'partially_implemented'},
        'activation':{'mode':'manual','costs':[{'resource':'sp','amount':level['spData']['spCost']}],
                      'on_start':[{'op':'modify_resource','target':'source','resource':'mode','delta':1},
                                  {'op':'apply_buff','target':'source','buff':buff}]},
        'parameters':{'blocks_attacks':False},'duration_seconds':level['duration'],
        'timeline':[]}


def cleanup(cid,buff):
    return {'id':f'ability/{cid}_mode_cleanup','kind':'ability',
        'activation':{'mode':'passive','event':'buff.removed','condition':
          f'inputs.payload.source == inputs.source.id and inputs.payload.target == inputs.source.id and inputs.payload.buff == "{buff}"'},
        'parameters':{'blocks_attacks':False},
        'timeline':[]}


def actor(cid,ids,level,interval):
    unit=entity(cid,ids,{'initial':level['spData']['initSp'],'capacity':level['spData']['spCost'],
        'recovery_rate':level['spData']['increment'],'recovery':{'mode':'periodic','interval_seconds':1},
        'parameters':{'pause_at_full':True,'freeze_while_cast':True,'freeze_cast_modes':['manual']}},interval)
    unit['components']['resources']['mode']={'initial':0,'capacity':1}
    return unit


def package(cid,unit,abilities,buffs,selectors,metadata):
    enemy=target();enemy['tags'].append('ground')
    return {'schemaVersion':2,'status':'partially_implemented',
        'manifest':{'id':f'package/offensive_{cid}','version':'1','metadata':metadata},
        'entities':[unit,enemy],'abilities':abilities,'buffs':buffs,'selectors':selectors,
        'scenarioDraft':scene(cid,unit,enemy)}


def build_bpipe(require_complete=False):
    cid='char_222_bpipe'
    o,level,bb,prefab,modes,native_selectors,frames,fps,normal_range,skill_range,native_buff,meta=source(cid)
    if len(modes)!=2 or modes[1]['_attack']['_additionalTimes']!=2 or modes[1]['_attack']['_waitAttackEventForAllAttacks']!=1:
        raise ValueError('Native three-animation-event attack changed')
    if modes[1]['_attack']['_triggerDelta']!=0 or any(m['_attack']['_damageType']!=1 for m in modes):
        raise ValueError('Native triple event/physical damage mismatch')
    if any(s is None or s['_targetMotion']!=1 or s['_maxNum']!=1 for s in native_selectors):
        raise ValueError('Native ground/single-target selector changed')
    modifiers=native_buff['attributes']['attributeModifiers']
    if {m['attributeType']:m['formulaItem'] for m in modifiers}!={8:1,1:1,2:1,5:0}:
        raise ValueError('Native Bagpipe attribute layers changed')
    normal=frame_delays(frames,'Attack_Loop',fps);triple=frame_delays(frames,modes[1]['_attack']['_animKey'],fps)
    if len(normal)!=1 or len(triple)!=3:
        raise ValueError('Native normal/triple animation event count mismatch')
    meta['pending_mechanics']+=['probability_extra_target_talent_rng_pending','team_vanguard_initial_sp_talent_pending',
        'kill_dp_and_withdraw_refund_trait_pending','next_attack_clock_rebase_on_native_mode_change_pending']
    if require_complete:
        raise ValueError('complete Bagpipe unsupported: '+';'.join(meta['pending_mechanics']))
    buff='buff/campaign_bpipe_s3';clean=cleanup(cid,buff)
    unit=actor(cid,[BPIPE_SKILL,BPIPE_NORMAL,BPIPE_BURST,clean['id']],level,1)
    unit['components']['attributes']['base']['def']=100
    normal_sel=selector(cid,normal_range);normal_sel['filters'].append({'tag':'ground'})
    skill_sel=selector(cid+'_s3',skill_range);skill_sel['filters'].append({'tag':'ground'})
    def attack(identifier,mode,sel,delays):
        return {'id':identifier,'kind':'ability','activation':{'mode':'automatic_attack',
            'condition':f'inputs.resources.mode.current == {mode}'},'selector':sel,'target_capture':'at_cast',
            'timeline':[{'at_seconds':time,'effect':{'op':'damage','damage_type':'physical'}} for time in delays]}
    buffs=[{'id':buff,'kind':'buff','duration_seconds':level['duration'],
        'on_remove':[{'op':'modify_resource','target':'source','resource':'mode','value':0}], 'modifiers':[
        {'attribute':'atk','layer':'direct_ratio','value':bb['atk']},
        {'attribute':'def','layer':'direct_ratio','value':bb['def']},
        {'attribute':'attack_interval','layer':'direct_ratio','value':bb['base_attack_time']},
        {'attribute':'block_count','layer':'flat','value':bb['block_cnt']}]}]
    meta['model_policy']={'ordinary_interval':1,'normal_hit_seconds':normal,'triple_hit_seconds':triple,
        'attack_interval_modifier':'source formula SCALER: base * (1 + .7), not flat addition',
        'animation':'source frame f /30 at1x; native playback scaling pending',
        'SP':'time only, frozen throughout manual skill; multi-hit damage never grants attack-SP',
        'damage_sampling':'live at-hit effective attack, physical'}
    return package(cid,unit,[skill_activation(BPIPE_SKILL,level,buff),
        attack(BPIPE_NORMAL,0,normal_sel['id'],normal),attack(BPIPE_BURST,1,skill_sel['id'],triple),clean],
        buffs,[normal_sel,skill_sel],meta)


def projectile_source(key):
    import UnityPy
    paths=[p for p in (ROOT.parent/'data/battle/prefabs').glob('*projectiles.ab_unpacked/CAB-*') if not p.name.endswith('.resS')]
    if len(paths)!=1:
        raise ValueError('Native projectile CAB ambiguous/missing')
    path=paths[0];env=UnityPy.load(str(path))
    objects={o.path_id:o.read_typetree() for o in env.objects if o.type.name=='GameObject'}
    rows={}
    for obj in env.objects:
        if obj.type.name=='MonoBehaviour':
            t=obj.read_typetree();name=objects.get(t.get('m_GameObject',{}).get('m_PathID'),{}).get('m_Name','')
            if name==key or name.startswith(key+'_'):
                rows[str(obj.path_id)]={'name':name,'script_path_id':t['m_Script']['m_PathID'],
                    'fields':{k:v for k,v in t.items() if not k.startswith('m_')}}
    speeds={r['fields']['_speed'] for r in rows.values() if '_speed' in r['fields']}
    if len(speeds)!=1 or next(iter(speeds))<=0:
        raise ValueError('Native projectile movement speed inconsistent/missing')
    return path,rows,next(iter(speeds))


def build_amgoat(require_complete=False):
    cid='char_180_amgoat'
    o,level,bb,prefab,modes,native_selectors,frames,fps,normal_range,skill_range,native_buff,meta=source(cid)
    if len(modes)!=2 or any(m['_attack']['_damageType']!=2 for m in modes):
        raise ValueError('Native two-mode magical attack missing')
    if modes[1]['_attack']['_waitForAttackEvent']!=1 or modes[1]['_attack']['_animKey']!='' or native_buff['templateKey']!='switch_mode_restart_fsm':
        raise ValueError('Native unresolved skill FSM changed; cannot infer cadence')
    if native_selectors[1]['_targetMotion']!=3 or native_selectors[1]['_selectNum']!=1:
        raise ValueError('Native random selector source changed')
    if {m['attributeType']:m['formulaItem'] for m in native_buff['attributes']['attributeModifiers']}!={1:1,8:0}:
        raise ValueError('Native Eyja attribute layer changed')
    cap=bb['attack@max_target']
    if cap!=int(cap) or cap<1:
        raise ValueError('Native BB maximum targets invalid')
    projectile,rows,speed=projectile_source(modes[1]['_attack']['_projectileKey'])
    meta['source_hashes']['projectile_cab']=sha(projectile);meta['native_skill_projectile_components']=rows
    meta['pending_mechanics']+=['native_rng_fsm_unknown','native_random_selector_selectNum_to_blackboard_max_target_binding_pending',
        'skill_attack_signal_clock_unknown_explicit_command_probe_only','deploy_random_sp_and_caster_atk_talent_pending',
        'native_projectile_arc_homing_alignment_pending']
    if require_complete:
        raise ValueError('complete Eyja unsupported: '+';'.join(meta['pending_mechanics']))
    buff='buff/campaign_amgoat_s3';clean=cleanup(cid,buff)
    unit=actor(cid,[AMGOAT_SKILL,AMGOAT_NORMAL,AMGOAT_PACKET,clean['id']],level,1.6)
    unit['components']['attributes']['base']['max_targets']=1
    normal_sel=selector(cid,normal_range)
    skill_sel=selector(cid+'_s3',skill_range);skill_sel.pop('limit');skill_sel['limit_attribute']='max_targets'
    normal_speed=frames['modes'][0]['attack']['projectileSpeed']
    normal={'id':AMGOAT_NORMAL,'kind':'ability','activation':{'mode':'automatic_attack','condition':'inputs.resources.mode.current == 0'},
        'selector':normal_sel['id'],'parameters':{'projectile_speed':normal_speed},'target_capture':'each_hit',
        'timeline':[{'at_seconds':delay,'effect':{'op':'damage','damage_type':'arts'}} for delay in frame_delays(frames,'Attack',fps)]}
    probe={'id':AMGOAT_PACKET,'kind':'ability','metadata':{'status':'partially_implemented',
        'synthetic_attack_signal':True,'not_native_fsm_or_rng':True},
        'activation':{'mode':'manual','condition':'inputs.resources.mode.current == 1',
                      'parameters':{'counts_as_attack':True}},
        'selector':skill_sel['id'],'target_capture':'each_hit',
        'parameters':{'blocks_attacks':False,'requires_targets':True,'projectile_speed':speed},
        'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'arts','read_mode':{'source_attributes':'at_launch'}}}]}
    buffs=[{'id':buff,'kind':'buff','duration_seconds':level['duration'],
        'on_remove':[{'op':'modify_resource','target':'source','resource':'mode','value':0}], 'modifiers':[
        {'attribute':'atk','layer':'direct_ratio','value':bb['atk']},
        {'attribute':'attack_interval','layer':'flat','value':bb['base_attack_time']},
        {'attribute':'max_targets','layer':'flat','value':cap-1}]}]
    meta['model_policy']={'skill_packet_driver':'explicit synthetic activate_ability command, no invented native cadence',
        'selection':'deterministic scored live/in-range probe; dynamic min(effective max_targets,N); native RNG is pending',
        'normal_interval':1.6,'skill_interval_attribute':0.5,'projectile_speed':speed,
        'damage_sampling':'ATK230 * magic mitigation; at_launch snapshot persists through delayed impact',
        'SP':'init55/cost80/time1; frozen while manual skill active, no per-target/per-packet SP'}
    return package(cid,unit,[skill_activation(AMGOAT_SKILL,level,buff),normal,probe,clean],buffs,[normal_sel,skill_sel],meta)


def build(name,require_complete=False):
    if name=='bpipe':return build_bpipe(require_complete)
    if name=='amgoat':return build_amgoat(require_complete)
    raise ValueError(f'Unsupported offensive recipe {name}')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--operator',choices=('bpipe','amgoat','all'),default='all');args=p.parse_args()
    for name in ('bpipe','amgoat') if args.operator=='all' else (args.operator,):
        result=build(name);path=ROOT/'packages/campaign'/f'skills.{name}.json'
        if args.check:
            if read(path)!=result:raise ValueError(f'{name}: source/output identity drifted')
        else:path.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
        print(f'{name}: partially_implemented; native complete explicitly unavailable')


if __name__=='__main__':main()
