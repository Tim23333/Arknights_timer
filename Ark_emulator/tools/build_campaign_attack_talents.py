"""Source-backed attack-side talents. Model profiles do not imply client approval."""
from __future__ import annotations
import argparse
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUTPUT=ROOT/'packages/campaign/talents.attack.json'
NORMALIZED=ROOT/'packages/campaign/operators.normalized.json'
NAMES=('myrtle','bpipe','chen','liskam','angel','amgoat')
IDS=('char_151_myrtle','char_222_bpipe','char_010_chen','char_107_liskam','char_103_angel','char_180_amgoat')


def read(path):return json.loads(path.read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def bb(candidate):
    rows=candidate['blackboard'];result={r['key']:r['value'] for r in rows}
    if len(result)!=len(rows) or any(v is None for v in result.values()):raise ValueError('Ambiguous/missing talent blackboard')
    return result


def source():
    import UnityPy
    from tools.build_kalts_skill_recipe import decode_bson_document
    from tools.extract_campaign_animation_bindings import unity_payload,character_bindings
    normalized=read(NORMALIZED)
    records={r['character_id']:r for r in normalized['operators'] if r['character_id'] in IDS}
    if len(records)!=6:raise ValueError('Six fixed attack-side operators required')
    result={};templatekeys={'empty','switch_mode_restart_fsm'}
    for cid in IDS:
        row=records[cid]
        if row['config']['level']!=70 or row['config']['potential_rank']!=0 or row['config']['potential']!=1 or row['config']['elite_phase']!=2:
            raise ValueError('Attack talents require E270 potential1')
        if row['config']['trust_percent']!=100 or row['config']['equipment_level']!=0 or row['config']['equipment_id'] is not None or row['config']['mastery']!=3:
            raise ValueError('Attack talent source configuration changed')
        if any(t['selected_candidate']['requiredPotentialRank']!=0 for t in row['talents']):
            raise ValueError('A potential-upgraded talent escaped selected configuration')
        paths=[p for p in (ROOT.parent/'data/charpack'/(cid+'.ab_unpacked')).glob('CAB-*') if not p.name.endswith('.resS')]
        if len(paths)!=1:raise ValueError(f'Native charpack missing/ambiguous: {cid}')
        trees={}
        for obj in UnityPy.load(str(paths[0])).objects:
            if obj.type.name!='MonoBehaviour':continue
            raw=obj.read_typetree();fields={k:v for k,v in raw.items() if not k.startswith('m_')}
            trees[str(obj.path_id)]={'script_path_id':raw['m_Script']['m_PathID'],
                'gameobject_path_id':raw['m_GameObject']['m_PathID'],'fields':fields}
            def collect(value):
                if isinstance(value,dict):
                    if value.get('templateKey'):templatekeys.add(value['templateKey'])
                    for child in value.values():collect(child)
                elif isinstance(value,list):
                    for child in value:collect(child)
            collect(fields)
        result[cid]={'normalized':row,'charpack':{'path':paths[0].relative_to(ROOT.parent).as_posix(),
            'sha256':sha(paths[0])},'components':trees}
    path=ROOT.parent/'data/anon_textassets/buff_template_data.dat'
    payload=unity_payload(path.read_bytes());values,spans=decode_bson_document(payload)
    frozen={}
    for key in sorted(templatekeys):
        if key not in values:raise ValueError(f'Native BSON template absent: {key}')
        lo,hi=spans[(key,)];raw=payload[lo:hi]
        frozen[key]={'parsed':values[key],'bson_payload_offset':lo,'bson_document_base64':base64.b64encode(raw).decode(),
            'bson_document_sha256':hashlib.sha256(raw).hexdigest()}
    # Fail on source changes that invalidate the authored mechanics, rather
    # than retaining old behavior merely because a template name still exists.
    def buff(cid,key):
        found=[b for t in result[cid]['components'].values() for b in t['fields'].get('_buffs',[]) if b['buffKey']==key]
        if len(found)!=1:raise ValueError(f'Native talent buff missing/ambiguous: {key}')
        return found[0]
    checks=[(IDS[0],'myrtle_t_1',{13:0}),(IDS[2],'chen_t_2',{1:1,2:1}),
        (IDS[3],'liskam_t_2',{3:0}),(IDS[4],'angel_t_1',{7:0}),
        (IDS[4],'angel_t_2',{0:1,1:1}),(IDS[5],'amgoat_t_1',{1:1})]
    for cid,key,expected in checks:
        rows=buff(cid,key)['attributes']['attributeModifiers']
        if {r['attributeType']:r['formulaItem'] for r in rows}!=expected or any(r['loadFromBlackboard']!=1 for r in rows):
            raise ValueError(f'Native attribute formula changed: {key}')
    if buff(IDS[1],'bpipe_t_1')['disableOverride']!=1 or buff(IDS[1],'bpipe_tr_1')['templateKey']!='kill_to_add_cost':
        raise ValueError('Bpipe native critical/kill trait source changed')
    proc=values['bpipe_t_1']['eventToActions']['ON_CALCULATE_DAMAGE']
    if [a['$type'].split('+')[1].split(',')[0] for a in proc]!=['IsBlackboardZero','Dice','AtkScaleUp','SplashDamage']:
        raise ValueError('Bpipe native damage action order changed')
    if proc[1]['_probKey']!='prob' or proc[3]['_damageType']!='PHYSICAL' or not proc[3]['_excludeTarget']:
        raise ValueError('Bpipe native damage mask/exclusion changed')
    randomset=values['amgoat_t_2']['eventToActions']['ON_OWNER_LOCATE'][0]
    if randomset['_convertToInt'] is not False or randomset['_targetKey']!='sp':
        raise ValueError('Eyja native random SP conversion changed')
    lisk=next(t['fields'] for t in result[IDS[3]]['components'].values() if t['fields'].get('_alwaysIncludeSelf')==1)
    pointer=lisk['_selector']
    if pointer['m_FileID']!=0:raise ValueError('Liskarm native random selector external')
    ls=result[IDS[3]]['components'][str(pointer['m_PathID'])]['fields']
    if ls['_selectNum']!=1 or ls['_excludeSelf']!=1 or ls['_alwaysAppendSelf']!=0:
        raise ValueError('Liskarm native self/friend selection changed')
    deck=next(t['fields'] for t in result[IDS[1]]['components'].values() if '_deckBuffs' in t['fields'])
    if deck['_options']['selector']['categoryMask']!=512 or deck['_deckBuffs'][0]['buff']['templateKey']!='modify_sp[born]':
        raise ValueError('Bpipe native deck category/born callback changed')
    dump=ROOT.parent/'Ark_data/dump.cs'
    assets={};eyja=character_bindings(IDS[-1],assets)
    return {'normalized_sha256':sha(NORMALIZED),'operators':result,
        'bson':{'path':path.relative_to(ROOT.parent).as_posix(),'sha256':sha(path),
            'payload_sha256':hashlib.sha256(payload).hexdigest(),'templates':frozen},
        'eyja_animation':{'bindings':eyja,'assets':assets},
        'native_enum_source':{'path':dump.relative_to(ROOT.parent).as_posix(),'sha256':sha(dump),
            'attribute_HP_RECOVERY_PER_SEC':13,'attribute_ATTACK_SPEED':7,'profession_PIONEER':512,
            'time_mode_FROM_ATTACK_SPEED':0,'time_mode_SPECIFIED':2,'MIN_ANIM_SCALE':.1,
            'method_body_recovered':False},
        'helper_hashes':{name:sha(ROOT/'tools'/name) for name in
            ('build_kalts_skill_recipe.py','extract_campaign_animation_bindings.py','build_campaign_units.py')},
        'builder_sha256':sha(Path(__file__))}


def modifiers(identifier,rows):
    return {'id':identifier,'kind':'buff','modifiers':[
        {'attribute':a,'layer':layer,'value':value} for a,layer,value in rows]}


def selector(identifier,filters,region=None,limit=None):
    return {'id':identifier,'kind':'selector','region':region or {'type':'all'},
        'filters':[{'tag':'player'},{'state':'alive'}]+filters,'limit':limit}


def build(require_complete=False):
    if require_complete:raise ValueError('Complete native attack talents/clocks remain unsupported')
    from tools.build_campaign_units import build as units
    native=source();base=units()
    data={'schemaVersion':2,'status':'attack_talents_model_partial','manifest':{
        'id':'package/campaign/attack_talents','version':'0.1.0','requires':['preset/ark_standard'],
        'metadata':{'source':native,'client_validated':False,'formal_mainline_approved':False,
            'complete_operator_count':0,'pending':['native_rng_algorithm_and_consumption_order',
            'native_damage_event_blocked_hit_alignment','all_client_animation_scaling_and_fsm',
            'roster_birth_order_and_born_vs_locate_callback_alignment',
            'eyja_s3_native_signal_offset_unresolved','native_random_selector_selectNum_to_max_target_binding',
            'same_native_aura_priority_override_across_multiple_sources',
            'native_mode_restart_cancellation_of_pending_ordinary_casts','client_clock_unverified',
            'max_hp_buff_current_hp_rescaling_client_alignment',
            'source_version_alignment_official20260929_vs_local_native_assets'] }},'entities':[],'abilities':[],
        'buffs':[],'selectors':[],'rules':[]}
    for entity in base['entities']:
        cid=entity['metadata']['native_id']
        if cid not in IDS:continue
        actor=deepcopy(entity);row=native['operators'][cid]['normalized']
        actor['tags']+=['profession:'+row['raw_character']['profession']]
        actor['components']['buffs']={'initial':[]}
        sp=row['selected_skill']['level']['spData']
        actor['components']['resources']['sp']={'initial':sp['initSp'],'capacity':sp['spCost']}
        if sp['spType'] in ('INCREASE_WHEN_ATTACK','INCREASE_WHEN_TAKEN_DAMAGE'):
            actor['tags'].append('sp:attack_or_damage')
        data['entities'].append(actor)
    data['abilities']=[deepcopy(a) for a in base['abilities'] if any(a['id'].startswith('ability/'+cid+'/') for cid in IDS)]
    data['selectors']=[deepcopy(s) for s in base['selectors'] if any(s['id'].startswith('selector/'+cid+'/') for cid in IDS)]
    actors={a['metadata']['native_id']:a for a in data['entities']}
    candidates={cid:[bb(t['selected_candidate']) for t in native['operators'][cid]['normalized']['talents']] for cid in IDS}
    def initial(cid,buff):
        data['buffs'].append(buff);actors[cid]['components']['buffs']['initial'].append(buff['id'])
    # ADD12 native attackSpeed(100-based) maps to .12 in the ratio-based model.
    initial(IDS[4],modifiers('buff/talent_angel_speed', [('attack_speed_ratio','flat',candidates[IDS[4]][0]['attack_speed']/100)]))
    initial(IDS[4],modifiers('buff/talent_angel_blessing_self', [('atk','direct_ratio',candidates[IDS[4]][1]['atk']),
        ('max_hp','direct_ratio',candidates[IDS[4]][1]['max_hp'])]))
    initial(IDS[2],modifiers('buff/talent_chen_stats', [('atk','direct_ratio',candidates[IDS[2]][1]['atk']),
        ('def','direct_ratio',candidates[IDS[2]][1]['def'])]))
    initial(IDS[3],modifiers('buff/talent_liskam_res', [('mres','flat',candidates[IDS[3]][1]['magic_resistance'])]))
    # Source attribute13 is a continuous recovery rate; current probe explicitly
    # integrates it once per logical tick and does not fabricate a heal attack.
    myrtle_member={'id':'buff/talent_myrtle_member','kind':'buff','stacking':{'mode':'independent'},
        'interval_seconds':1/30,'effects':[{'op':'regenerate','scale':0,
            'additions':candidates[IDS[0]][0]['hp_recovery_per_sec']/30}]}
    myrtle_parent={'id':'buff/talent_myrtle_parent','kind':'buff',
        'aura':{'selector':'selector/talent_vanguard','buff':myrtle_member['id']}}
    data['selectors'].append(selector('selector/talent_vanguard',[{'tag':'profession:PIONEER'}]))
    data['buffs'].append(myrtle_member);initial(IDS[0],myrtle_parent)
    eyja_member=modifiers('buff/talent_eyja_atk',[('atk','direct_ratio',candidates[IDS[5]][0]['atk'])])
    eyja_member['stacking']={'mode':'independent'}
    data['selectors'].append(selector('selector/talent_casters',[{'tag':'profession:CASTER'}]))
    data['buffs'].append(eyja_member);initial(IDS[5],{'id':'buff/talent_eyja_parent','kind':'buff',
        'aura':{'selector':'selector/talent_casters','buff':eyja_member['id']}})
    chen_parent={'id':'buff/talent_chen_parent','kind':'buff','interval_seconds':candidates[IDS[2]][0]['interval'],
        'effects':[{'op':'modify_resource','selector':'selector/talent_attack_damage_sp','resource':'sp',
            'delta':candidates[IDS[2]][0]['sp'],'parameters':{'respect_recovery_freeze':True}}]}
    data['selectors'].append(selector('selector/talent_attack_damage_sp',[{'tag':'sp:attack_or_damage'}]))
    initial(IDS[2],chen_parent)
    # Calculate-damage Dice is sampled once for each actual packet. Splash is
    # a separate physical packet and core marks it with the source hook lock.
    bpipe=candidates[IDS[1]][0]
    normal_selector=next(s for s in data['selectors'] if s['id']=='selector/'+IDS[1]+'/normal_attack')
    splash=deepcopy(normal_selector);splash['id']='selector/talent_bpipe_splash';splash['limit']=1
    splash.setdefault('parameters',{})['exclude_primary']=True;data['selectors'].append(splash)
    extra={'op':'damage','damage_type':'physical','scale':bpipe['atk_scale'],'selector':splash['id']}
    request="{'op':'damage','damage_type':inputs.effect.damage_type,'attack':inputs.effect.attack,'defense':inputs.effect.defense,'resistance':inputs.effect.resistance,'scale':inputs.effect.scale*(params.atk_scale if nodes.proc else 1),'additions':inputs.effect.additions}"
    data['rules'].append({'id':'rule/talent_bpipe_request','kind':'calculation_rule','contract':'damage.request',
        'dependencies':[splash['id']],
        'parameters':{'prob':bpipe['prob'],'atk_scale':bpipe['atk_scale'],'extra':extra},
        'implementation':{'type':'graph','nodes':[{'id':'proc','expression':'inputs.samples[0].value < params.prob'},
            {'id':'result','expression':"{'accepted':True,'effect':"+request+",'effects':[params.extra] if nodes.proc else []}"}], 'output':'nodes.result'}})
    initial(IDS[1],{'id':'buff/talent_bpipe_critical','kind':'buff','damage_hooks':[
        {'phase':'before','rule':'rule/talent_bpipe_request','samples':{'stream':'imp','count':1}}]})
    data['rules'].append({'id':'rule/talent_chen_dodge','kind':'calculation_rule','contract':'damage.pipeline',
        'parameters':{'prob':candidates[IDS[2]][1]['prob']},'implementation':{'type':'graph','nodes':[
            {'id':'dodge','expression':'inputs.samples[0].value < params.prob'},
            {'id':'result','expression':"{'accepted':False,'amount':0,'allocations':[],'events':[]} if nodes.dodge else inputs.effect.settlement"}],
            'output':'nodes.result'}})
    initial(IDS[2],{'id':'buff/talent_chen_dodge','kind':'buff','damage_hooks':[
        {'phase':'after','rule':'rule/talent_chen_dodge','condition':'inputs.effect.damage_type == "physical"',
            'samples':{'stream':'imp','count':1}}]})
    initial(IDS[1],{'id':'buff/talent_bpipe_kill_dp','kind':'buff','events':[
        {'event':'combat.kill','condition':'inputs.payload.source == context.owner.id and "enemy" in inputs.payload.target_tags',
            'effects':[{'op':'modify_resource','target':'battle','resource':'dp',
                'delta':bb(native['operators'][IDS[1]]['normalized']['selected_trait_candidate'])['cost']}]}]})
    # Liskarm's source selector is Random1, excludeSelf1 and the linked ability
    # alwaysIncludeSelf1; no friend candidate still grants the self point.
    x5=read(ROOT/'ark_emulator/data_range_table.json')['x-5']
    data['selectors'].append(selector('selector/talent_liskam_friend',[],
        {'type':'grid_offsets','offsets':[[-g['row'],g['col']] for g in x5['grids']]},1))
    data['selectors'][-1].update(ordering='random',parameters={'random_stream':'imp','exclude_source':True})
    initial(IDS[3],{'id':'buff/talent_liskam_hit','kind':'buff','events':[
        {'event':'damage.accepted','condition':'inputs.payload.target == context.owner.id',
            'effects':[{'op':'modify_resource','resource':'sp','delta':candidates[IDS[3]][0]['sp'],
                'parameters':{'respect_recovery_freeze':True,'if_resource_present':True}},
                {'op':'modify_resource','selector':'selector/talent_liskam_friend','resource':'sp',
                    'delta':candidates[IDS[3]][0]['sp'],'parameters':{'respect_recovery_freeze':True,'if_resource_present':True}}]}]})
    # Native RandomSetter explicitly has convertToInt=false. This declared
    # replaceable model uses a float uniform draw rather than inventing integer
    # endpoints from a displayed description.
    eyjasp=candidates[IDS[5]][1]
    data['rules'].append({'id':'rule/talent_eyja_random_sp','kind':'calculation_rule','contract':'resource.recovery',
        'parameters':{'minimum':eyjasp['sp_min'],'maximum':eyjasp['sp_max']},
        'implementation':{'type':'expression','expression':'inputs.current+params.minimum+(params.maximum-params.minimum)*inputs.parameters.random_sample'}})
    data['abilities'].append({'id':'ability/talent_eyja_deploy_sp','kind':'ability','activation':{
        'mode':'on_deploy','on_start':[{'op':'random','target':'source','stream':'imp','probability':1,
            'on_success':[{'op':'modify_resource','resource':'sp','amount_rule':'rule/talent_eyja_random_sp'}]}]},
        'parameters':{'blocks_attacks':False},'timeline':[]})
    actors[IDS[5]]['components']['abilities'].append('ability/talent_eyja_deploy_sp')
    blessing=modifiers('buff/talent_angel_friend',[('atk','direct_ratio',candidates[IDS[4]][1]['atk']),
        ('max_hp','direct_ratio',candidates[IDS[4]][1]['max_hp'])])
    blessing['removal']={'on_source_death':'remove'}
    data['buffs'].append(blessing)
    data['selectors'].append(selector('selector/talent_angel_friend',[],limit=1))
    data['selectors'][-1].update(ordering='random',parameters={'random_stream':'imp','exclude_source':True})
    data['abilities'].append({'id':'ability/talent_angel_deploy_bless','kind':'ability','activation':{
        'mode':'on_deploy','on_start':[{'op':'apply_buff','buff':blessing['id'],'selector':'selector/talent_angel_friend'}]},
        'parameters':{'blocks_attacks':False},'timeline':[]})
    actors[IDS[4]]['components']['abilities'].append('ability/talent_angel_deploy_bless')
    # Deck owner presence is authoring/roster membership, not live aura presence.
    actors[IDS[1]]['components']['deck']={'on_create':[{'op':'modify_resource','resource':'sp',
        'delta':candidates[IDS[1]][1]['sp'],'parameters':{'if_resource_present':True},
        'condition':'"player" in inputs.targets[0].tags and "profession:PIONEER" in inputs.targets[0].tags'}]}
    bpipe_root=next(t['fields'] for t in native['operators'][IDS[1]]['components'].values() if '_modes' in t['fields'])
    actors[IDS[1]]['metadata']['native_withdraw_cost_recover_ratio']=bpipe_root['_withdrawCostRecoverRatio']
    actors[IDS[1]]['components']['deployable']['refund_ratio']=bpipe_root['_withdrawCostRecoverRatio']
    actors[IDS[1]]['components']['deployable'].setdefault('parameters',{})['refund_cap_raw_ratio']=bpipe_root['_maxWithdrawCostRatioOfRawCost']
    # Replace the former command-only packet with a genuine automatic model
    # clock, retaining a conspicuous uncalibrated first-signal offset profile.
    # No missing Spine event is synthesized or labelled native evidence.
    old_path=ROOT/'packages/campaign/skills.amgoat.json';old=read(old_path)
    old_defs={r['id']:r for section in ('abilities','buffs','selectors') for r in old[section]}
    aid='ability/campaign_amgoat_probe_packet';automatic=deepcopy(old_defs[aid])
    automatic['activation']={'mode':'automatic_attack','condition':'inputs.resources.mode.current == 1',
        'parameters':{'auto_only':True}}
    automatic['target_capture']='at_cast'
    automatic['metadata']={'status':'model_automatic_clock_not_client_calibrated',
        'clock_profile':'effective_interval_first_signal_zero_v1','native_signal_offset_verified':False,
        'native_random_count_binding_verified':False,'former_command_probe_replaced':True}
    skill_selector=deepcopy(old_defs[automatic['selector']])
    skill_selector.update(ordering='random',parameters={'random_stream':'imp'})
    s3=deepcopy(old_defs['ability/campaign_amgoat_s3'])
    s3.setdefault('parameters',{}).update(reset_attack_clock=True,cancel_pending_attacks=True)
    data['abilities'] += [s3,automatic,
        deepcopy(old_defs['ability/char_180_amgoat_mode_cleanup'])]
    data['selectors'].append(skill_selector)
    data['buffs'].append(deepcopy(old_defs['buff/campaign_amgoat_s3']))
    eyja=actors[IDS[5]]
    eyja['components']['attributes']['base']['max_targets']=1
    eyja['components']['resources']['mode']={'initial':0,'capacity':1}
    eyja['components']['resources']['sp']=deepcopy(old['entities'][0]['components']['resources']['sp'])
    eyja['components']['abilities'] += ['ability/campaign_amgoat_s3',aid,'ability/char_180_amgoat_mode_cleanup']
    next(a for a in data['abilities'] if a['id']=='ability/'+IDS[5]+'/normal_attack')['activation']['condition']='inputs.resources.mode.current == 0'
    data['manifest']['metadata']['source']['eyja_skill_recipe_sha256']=sha(old_path)
    overrides=[s3,automatic,skill_selector]
    # This timing profile is a replaceable inference from FROM_ATTACK_SPEED=0,
    # MIN_ANIM_SCALE=.1 and each serialized maxAnimScale. GetTimeScale's client
    # method body was not recovered; no client formula accuracy is claimed.
    timing_profiles={}
    for cid in IDS:
        components=native['operators'][cid]['components']
        root=next(t['fields'] for t in components.values() if '_modes' in t['fields'])
        attack_modes=[]
        for mode in root['_modes']:
            m=components[str(mode['m_PathID'])]['fields'];a=components[str(m['_attack']['m_PathID'])]['fields']
            if a.get('_timeMode') not in (0,2):raise ValueError('Native attack time mode unsupported')
            attack_modes.append(a)
        for index,a in enumerate(attack_modes):
            rid=f'rule/talent_clock/{cid}/{index}'
            maximum=a['_maxAnimScale']
            data['rules'].append({'id':rid,'kind':'calculation_rule','contract':'ability.windup',
                'parameters':{'minimum':.1,'maximum':maximum},'implementation':{'type':'expression',
                    'expression':('inputs.timing_parameters.seconds / max(params.minimum,min(inputs.attributes.attack_speed_ratio,params.maximum) if params.maximum > 0 else inputs.attributes.attack_speed_ratio)' if a['_timeMode']==0 else 'inputs.timing_parameters.seconds')},
                'metadata':{'profile':'from_attack_speed_divisor_model_v1','client_formula_verified':False,
                    'native_time_mode':a['_timeMode'],'native_max_anim_scale':maximum}})
            timing_profiles[(cid,index)]=rid
        normal=next(a for a in data['abilities'] if a['id']=='ability/'+cid+'/normal_attack')
        normal.setdefault('rules',{})['ability.windup']=timing_profiles[(cid,0)]
        overrides.append(deepcopy(normal))
    for name,cid,keys in [('bpipe',IDS[1],['ability/campaign_bpipe_normal','ability/campaign_bpipe_triple']),
        ('chen',IDS[2],['ability/campaign_chen_normal']),('angel',IDS[4],['ability/campaign_angel_normal','ability/campaign_angel_burst'])]:
        path=ROOT/f'packages/campaign/skills.{name}.json';recipe=read(path)
        native.setdefault('selected_recipe_sha256',{})[name]=sha(path)
        for index,key in enumerate(keys):
            row=deepcopy(next(a for a in recipe['abilities'] if a['id']==key))
            row.setdefault('rules',{})['ability.windup']=timing_profiles[(cid,index)]
            overrides.append(row)
        if name in ('bpipe','angel'):
            key=f'ability/campaign_{name}_s3';row=deepcopy(next(a for a in recipe['abilities'] if a['id']==key))
            row.setdefault('parameters',{}).update(reset_attack_clock=True,cancel_pending_attacks=True)
            overrides.append(row)
    data['manifest']['metadata']['skill_definition_overrides']=overrides
    # Public modular patches let the root join selected skills without fixture
    # stats or replay commands entering the integrated actor.
    data['manifest']['metadata']['unit_patches']={a['id']:{'buffs':deepcopy(a['components']['buffs']),
        'tags':deepcopy(a['tags']),
        'talent_abilities':[k for k in a['components']['abilities'] if '/normal_attack' not in k],
        'deployable':deepcopy(a['components']['deployable']),
        'deck':deepcopy(a['components'].get('deck',{}))}
        for a in data['entities']}
    data['manifest']['metadata']['coverage']={
        'myrtle':['vanguard25HPcontinuous_rate_tick_integration'],
        'bpipe':['roster_vanguard_initialSP6','killDP1','per_packet_prob25_scale130_and_extra_physical_target',
            'withdraw_refund_ratio1_capped_at_raw_cost_ratio1'],
        'chen':['periodic4s_attack_damageSP1','ATK_DEF5percent','physical_dodge10percent'],
        'liskam':['self_plus_random_adjacent_SP1_on_accepted_hit','RES10'],
        'angel':['AS12','self_ATK6_HP10percent','one_random_deployed_ally_blessing'],
        'amgoat':['casterATK14percent_aura','deploy_float_randomSP7to16','S3_auto_random_dynamic_target_model_clock']}
    data['manifest']['metadata']['model_profiles']={'myrtle_regen':'25 HP/sec logical-tick integration; native continuous attribute13',
        'eyja_s3':{'id':'effective_interval_first_signal_zero_v1','base_interval_seconds':1.6,
            'skill_interval_addition':-1.1,'first_signal_offset_seconds':0,
            'selection':'random_without_replacement_at_cast; dynamic effective max_targets',
            'client_calibrated':False,'native_first_signal_offset_verified':False,
            'evidence':'front Skill_Start/Loop/End no OnAttack; back lacks these animations; effective .5s interval alone does not prove native callback offset'}}
    data['manifest']['metadata']['model_profiles']['attack_windup']={
        'id':'from_attack_speed_divisor_model_v1','source_enum':'FROM_ATTACK_SPEED=0',
        'algorithm':'authored_delay/max(.1,min(effective_AS_ratio,native_maxAnimScale)); nonpositive max is unbounded',
        'client_formula_verified':False,'interval_addition_to_animation_scaling_relationship':'unresolved'}
    data['scenarioDraft']={'id':'scenario/attack_talent_model','ruleset':'ruleset/ark_standard',
        'map':{'rows':7,'cols':12},'resources':{'dp':{'initial':0,'capacity':99}},
        'roster':['unit/'+cid for cid in IDS],'initialEntities':[],
        'dependencies':['unit/'+cid for cid in IDS]}
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    text=json.dumps(build(),ensure_ascii=False,indent=2)+'\n'
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding='utf8')!=text:raise SystemExit('Attack talent sources/output drifted')
    else:OUTPUT.write_text(text,encoding='utf8')
    print('Six attack-side source-backed talent models; native gaps retained.')
