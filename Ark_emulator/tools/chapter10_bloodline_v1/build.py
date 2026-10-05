"""Six source bloodline consumers; owned descendants on isolated candidate."""
import json,hashlib,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter10_source_prepare/enemies.native.v1.json'
BSON=ROOT/'packages/campaign/chapter10_source_prepare/bson.transitive.v2.json'
PREFIX='ch10/bloodline/'
MARK='buff/'+PREFIX+'bloodsucker_mark';DR='buff/'+PREFIX+'damage_resistance'
BLOCK='buff/'+PREFIX+'block_cnt';AURA='buff/'+PREFIX+'blocker_control';DEATH='buff/'+PREFIX+'death_rattle'
KEYS=('enemy_1220_dzoms','enemy_1220_dzoms_2','enemy_1222_dpvt','enemy_1222_dpvt_2','enemy_1221_dzomg','enemy_1221_dzomg_2')
def entity_id(key):return 'unit/'+PREFIX+key
def blocker(inputs,params,context):
    return {'accepted':inputs['source']['components']['runtime'].get('blocked_by')==inputs['candidate']['id'],'reason':'actual_native_blocker'}
def resistance(inputs,params,context):
    from ark_sim.contracts import thaw
    result=thaw(inputs['effect']['settlement'])
    if inputs['effect'].get('damage_type','physical') in ('physical','arts'):result['amount']*=1-params['ratio']
    return result
def death_qualified(inputs,params,context):
    e=inputs['entity'];return any(b['definition']==inputs['parameters']['buff'] and b['source']==b['target']==e['id'] and (b['expires_at'] is None or context['time']<b['expires_at']) for b in e['components']['buffs']['instances'])
def placement(inputs,params,context):
    samples={x['axis']:x['value'] for x in inputs['samples']}
    return {axis:inputs['anchor'][axis]+inputs['offset'][axis]+(2*samples[axis]-1)*inputs['random_range'][axis] for axis in ['row','col']}
def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS,'source.bloodline.blocker':{'callable':blocker,'version':'actual-blocker-v1'},
        'source.bloodline.resistance':{'callable':resistance,'version':'native-physical-magical90-v1'},
        'source.bloodline.death':{'callable':death_qualified,'version':'owned-native-self-buff-at-real-death-v1'},
        'reference.bloodline.placement':{'callable':placement,'version':'named-axis-uniform-point1-v1'}}
def attach_death_source(entity,rawResolvedBB,*,death_buff=DEATH,child_resolver=entity_id):
    bb={r['key']:r['valueStr'] if r['valueStr'] is not None else r['value'] for r in rawResolvedBB}
    if 'deathrattle.enemy_key' not in bb or 'deathrattle.delay' not in bb:raise ValueError('Death source requires literal declared child key/delay BB')
    child=child_resolver(bb['deathrattle.enemy_key']);components=entity['components']
    initial=components.setdefault('buffs',{}).setdefault('initial',[])
    if death_buff not in initial:initial.append(death_buff)
    components.setdefault('lifecycle',{})['death_spawns']={'actions':[{'key':'bloodsucker','definition':child,'count':1,'delay_seconds':bb['deathrattle.delay'],'inherit_route':True,'managed':'inherit_source','rule':'rule/'+PREFIX+'death','parameters':{'buff':death_buff},'placement':{'rule':'rule/'+PREFIX+'placement','stream':'ch10/bloodline/descendants','sample_axes':['row','col'],'offset':{'row':0,'col':0},'random_range':{'row':.10000000149011612,'col':.10000000149011612}}}]}
    return entity
def build_all():
    source=json.loads(SOURCE.read_bytes());bson=json.loads(BSON.read_bytes())
    selected={k:next(v for v in source['variants'].values() if v['prefab_key']==k) for k in KEYS}
    from ark_sim.domains.selection import DEFAULT_STATE,SWITCHES
    configs={**{k:0 for k in SWITCHES},'_targetSide':2,'_targetCategory':1,'_targetMotion':1}
    eligibility={'rule':'rule/'+PREFIX+'blocker','parameters':{'source_configuration':configs,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':DEFAULT_STATE}}
    p={'schemaVersion':2,'manifest':{'id':'package/ch10/bloodline/source_v1','metadata':{
        'source_locks':{str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in [SOURCE,BSON,Path(__file__)]},
        'source_variants':selected,'source_BSON':{k:bson['templates'][k] for k in ['empty','damage_resistance','enemy_bloodsucker_block_cnt[control]','enemy_vampires[bloodsucker_summon]']},
        'source_profile':{'fixed56_death_delay':1,'native_BSON_default_delay':0,'delay_policy':'Explicit fixed56 BB delay profile; method-body implicit BB substitution unresolved',
            'randomOffsetBound':.10000000149011612,'placement_reference':'Uniform point range via named RNG row/col samples, no recovered circle rejection/obstacle wrapper method',
            'native_no_FALLDOWN':'Only actual lifecycle reason dead issues; fall/exit/withdrawal are not death scope',
            'maxAnimScale':1,'clock_reference':'Literal resolved Spine hit/full divided by current ASPD; source base cycle remains independent shared attack clock; no attack can overlap blocking cast',
            'leak_default':'m_defined false native omitted lifePointReduce uses declared standard1; no blanket zero for descendants'},'runtime_implemented':False}},
        'rules':[],'buffs':[],'selectors':[],'abilities':[],'entities':[]}
    def expr(name,contract,text):return {'id':'rule/'+PREFIX+name,'kind':'rule','contract':contract,'implementation':{'type':'expression','expression':text}}
    p['rules']=[{'id':'rule/'+PREFIX+'blocker','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'source.bloodline.blocker'}},
        {'id':'rule/'+PREFIX+'resistance','kind':'rule','contract':'damage.pipeline','parameters':{'ratio':.9},'implementation':{'type':'provider','provider':'source.bloodline.resistance'}},
        {'id':'rule/'+PREFIX+'death','kind':'rule','contract':'lifecycle.death_emission','implementation':{'type':'provider','provider':'source.bloodline.death'}},
        {'id':'rule/'+PREFIX+'placement','kind':'rule','contract':'spawn.position','implementation':{'type':'provider','provider':'reference.bloodline.placement'}},
        expr('windup','ability.windup','inputs.timing_parameters.seconds/max(inputs.attributes.attack_speed_ratio,.01)'),
        expr('duration','ability.duration','inputs.duration_parameters.seconds/max(inputs.attributes.attack_speed_ratio,.01)')]
    p['selectors']=[{'id':'selector/'+PREFIX+'blocker','kind':'selector','region':{'type':'all'},'filters':[{'state':'alive'}],'limit':1,'eligibility':eligibility}]
    p['buffs']=[{'id':MARK,'kind':'buff','metadata':{'native_buff_key':'enemy_bloodsucker_mark','native_template':'empty','semantics':'Actual permanent source PassiveBuffAbility self marker, qualification consumed by bloodline/aura selectors'}},
        {'id':DR,'kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/'+PREFIX+'resistance'}]},
        {'id':BLOCK,'kind':'buff','stacking':{'mode':'add','max_stacks':6,'identity':['definition','target']},'modifiers':[{'attribute':'block_count','layer':'flat','value':1}]},
        {'id':AURA,'kind':'buff','aura':{'selector':'selector/'+PREFIX+'blocker','buff':BLOCK,'lease_policy':{'mode':'shared','identity':['definition','target'],'source_binding':'oldest_live_lease','external_child_collision':'reject','modifier_stacks':{'rule':'rule/ark_buff_stack_amount','maximum':6}}},'metadata':{'native_min':1,'native_max':-1,'native_useBlockAsMin':1,'owned_to_blocker':True}},
        {'id':DEATH,'kind':'buff','metadata':{'native_buff_key':'enemy_vampires[death_rattle]','native_template':'enemy_vampires[bloodsucker_summon]'}}]
    for key,v in selected.items():
        enemy=v['native_enemy']['resolved'];a=enemy['attributes'];mode=v['modes'][0]['nodes']['_combat'];binding=mode['animation_binding'];bb={r['key']:r['valueStr'] if r['valueStr'] is not None else r['value'] for r in enemy['talentBlackboard']}
        ability='ability/'+PREFIX+key+'/melee';hit=next(e['seconds'] for e in binding['events'] if e['name']=='OnAttack')
        p['abilities'].append({'id':ability,'kind':'ability','activation':{'mode':'automatic_attack','interval_seconds':a['baseAttackTime'],'parameters':{'auto_only':True}},'selector':'selector/'+PREFIX+'blocker','duration_seconds':binding['duration']['seconds'],'rules':{'ability.windup':'rule/'+PREFIX+'windup','ability.duration':'rule/'+PREFIX+'duration'},'timeline':[{'at_seconds':hit,'effect':{'op':'damage','damage_type':'physical','scale':1,'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'},'damage_flags':{'source_attack_type':'NORMAL','ignore_for_sp':False}}}],'metadata':{'native_combat':mode,'resolved_animation':binding}})
        is_sucker='dzoms' in key or 'dzomg' in key;components={'attributes':{'base':{'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],'move_speed':a['moveSpeed'],'attack_interval':a['baseAttackTime'],'attack_speed_ratio':a['attackSpeed']/100,'mass_level':a['massLevel'],'block_cost':1}},'resources':{'hp':{'initial':a['maxHp'],'capacity_attribute':'max_hp','role':'health'}},'spatial':{'motion_mode':0,'route_motion_mode':0},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2},'abilities':[ability],'buffs':{'initial':[MARK,DR,AURA] if is_sucker else [DEATH]},'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':enemy.get('lifePointReduce',1)}}
        if not is_sucker:
            child=bb['deathrattle.enemy_key'];components['lifecycle']['death_spawns']={'actions':[{'key':'bloodsucker','definition':entity_id(child),'count':1,'delay_seconds':bb['deathrattle.delay'],'inherit_route':True,'managed':'inherit_source','rule':'rule/'+PREFIX+'death','parameters':{'buff':DEATH},'placement':{'rule':'rule/'+PREFIX+'placement','stream':'ch10/bloodline/descendants','sample_axes':['row','col'],'offset':{'row':0,'col':0},'random_range':{'row':.10000000149011612,'col':.10000000149011612}}}]}
        p['entities'].append({'id':entity_id(key),'kind':'entity','tags':['enemy','bloodline',*(enemy.get('enemyTags') or [])],'components':components,'metadata':{'native_variant':v['variant_id'],'native_reference':v['native_reference'],'native_DB':v['native_enemy'],'native_prefab_source':source['prefabs'][key]['source']}})
    return p
def build(key):
    if key not in KEYS:raise ValueError('Exact source bloodline key required')
    p=build_all();p['manifest']['id']+='/'+key;p['manifest']['metadata']['primary_definition']=entity_id(key)
    return p
