"""Complete selected native dkmage_2 body, source selectors and death chain."""
import json,copy,hashlib
from pathlib import Path
from tools.chapter10_chain_v1.native_module import mount
from tools.chapter10_bloodline_v1 import build as blood
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter10_consumers/remaining/source.closure.v1.json'
KEY='enemy_1225_dkmage_2';BODY='unit/ch10/dkmage_source/'+KEY
EMPTY='native/dkmage/5653700696913435974'
def ep_packet(inputs,params,context):
    record=inputs['source']['components']['lifecycle']['parameters']['native_owned_data'][EMPTY]
    if record['class']!='EmptyAbility' or record['path_id']!=5653700696913435974:raise ValueError('Native owned EpDamage container absent')
    return inputs['source_attributes']['atk']*record['blackboard']['epdamage.attack@ep_damage_ratio']*inputs['request']['parameters']['attack_scale']
def providers():
    return {**blood.providers(),'source.ch10.dkmage.packet':{'callable':ep_packet,'version':'owned-native-empty-data-bb-currentATK-v1'}}
def build():
    raw=json.loads(SOURCE.read_bytes());v=raw['variants'][KEY];pref=raw['prefabs'][KEY];resolved=v['native_enemy']['resolved'];a=resolved['attributes']
    mode=v['modes'][0];nodes=mode['nodes'];assert len(v['modes'])==1 and nodes['_combat']['path_id']==nodes['_attack']['path_id']
    assert mode['raw']['_generalAbilities']==[]
    root=next(c for c in pref['components'].values() if c['native_class']=='Enemy');assert root['raw']['_commonAbilities']==[]
    native_row=v['native_enemy']['raw_rows'][0]['enemyData'];assert native_row['skills'] is None and native_row['spData'] is None
    empty=next(c for c in pref['components'].values() if c['native_class']=='EmptyAbility')
    assert set(k for k in empty['raw'] if k.startswith('_'))=={'_selector','_metadata','_interruptAbilityOnDetach','_attachPassiveBuffsOnDummy','_ignoreIfOwnerDead','_forceAsDmgOrHealAbility'}
    assert empty['raw']['_selector']['m_PathID']==0
    chain=blood.build_all();p={k:copy.deepcopy(chain.get(k,[])) for k in ['entities','abilities','buffs','rules','selectors','projectiles']};p['schemaVersion']=2
    bb={r['key']:r['valueStr'] if r['valueStr'] is not None else r['value'] for r in resolved['talentBlackboard']}
    body={'id':BODY,'kind':'entity','tags':['enemy','sarkaz','dkmage'],'components':{'attributes':{'base':{'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],'move_speed':a['moveSpeed'],'attack_interval':a['baseAttackTime'],'attack_speed_ratio':a['attackSpeed']/100,'mass_level':a['massLevel'],'block_cost':root['raw']['_blockVolume']}},'resources':{'hp':{'role':'health','initial':a['maxHp'],'capacity':a['maxHp']}},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2},'spatial':{'motion_mode':0,'route_motion_mode':0},'abilities':[],'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':resolved.get('lifePointReduce',1),'parameters':{'native_owned_data':{EMPTY:{'class':'EmptyAbility','path_id':5653700696913435974,'raw':empty['raw'],'blackboard':bb}}}}}}
    blood.attach_death_source(body,resolved['talentBlackboard']);p['entities'].append(body)
    provenance=mount(p,body)
    config={k:z for k,z in next(c for c in pref['components'].values() if c['native_class']=='AdvancedSelector')['raw'].items() if k.startswith('_')}
    from ark_sim.domains.selection import DEFAULT_STATE
    for selector in p['selectors']:
        if selector['id'].startswith('selector/c10/dkmage_chain/'):
            selector['filters']=[{'state':'alive'}]
            selector['eligibility']['parameters']['source_configuration']=copy.deepcopy(config)
            selector['eligibility']['parameters']['defaults']=copy.deepcopy(DEFAULT_STATE)
    packet=next(r for r in p['rules'] if r['id']=='rule/c10/dkmage_chain/ep_packet')
    packet['implementation']={'type':'provider','provider':'source.ch10.dkmage.packet'}
    p['manifest']={'id':'package/ch10/dkmage_source/'+KEY,'metadata':{'native_variant':v,'native_prefab':pref,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'chain_provenance':provenance,'owned_node_mapping':{'_combat':'ability/c10/dkmage_chain','_attack':'same native path alias of _combat, not a second cast','_attackTrigger':'automatic_attack + real selector min1/keepTarget0','PassiveBuffAbility/deathrattle':blood.DEATH,'EmptyAbility/EpDamage':'lifecycle.parameters.native_owned_data, actually read by elemental.packet; native has no selector/clock/SP/events and is a parameter owner rather than an independent cast'},'source_policy':{'attack_frame':'37/66 at30fps, original float32 retained, maxAnimScale1 selected normalized source reference','priority':'one shared combat/attack native path; selector acquisition owns automatic attack; no general skills or SourceSkill components in this exact prefab','EP_container':'Data-only ownership projection is explicit reference representation of native EmptyAbility; no extra Buff invented, no empty cast granted; packet refuses absent/mismatched container','selector':'All native AdvancedSelector fields preserved (including postFilter4/abnormal25/combo2/exclude46). Eligibility consumes native mask/side/motion/free fields; ordering uses existing reference selection order. Native method bodies/client selection equivalence not claimed.','movement':'source WALK/.7 with independent physical and route mode; route supplied by stage','death':'literal BB child dzomg_2/delay1; immediate death plus authenticated managed delayed birth; count1 native BSON.'},'whole_consumer_complete':True,'client_verified':False}}
    return p
