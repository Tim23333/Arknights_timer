"""Selected source ordinary bodies; unsupported source channel fails closed."""
import copy,json,hashlib
from pathlib import Path
from tools.chapter10_bloodline_v1 import build as blood
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT/'packages/campaign/chapter10_source_prepare/enemies.native.v1.json';BSON=ROOT/'packages/campaign/chapter10_source_prepare/bson.transitive.v2.json'
P='ch10/stage17_ordinary/';VAMPIRE='buff/'+P+'vampire';LORD='buff/'+P+'lord_parent'
def entity_id(key):return 'unit/'+P+key
def vamp_heal(inputs,params,context):
    owner=context['source'];casts=owner['components']['runtime']['casts']
    if not any(b['definition']==VAMPIRE and b['source']==b['target']==owner['id'] and (b['expires_at'] is None or context['time']<b['expires_at']) for b in owner['components']['buffs']['instances']):return 0
    matches=[c for c in casts.values() if c['ability']==params['ability'] and c.get('event_payload',{}).get('source')==owner['id']]
    if len(matches)!=1:raise ValueError('Damage-scale heal requires actual owned output-damage callback cast')
    return matches[0]['event_payload']['amount']*params['ratio']
def lord_atk(inputs,params,context):
    count=0
    for b in context['owner']['components'].get('buffs',{}).get('instances',[]):
        if b['definition']==LORD and (b['expires_at'] is None or context['time']<b['expires_at']):count+=len(b.get('aura_members',{}))
    modifiers=copy.deepcopy(list(inputs['modifier_layers']))
    modifiers.append({'attribute':'atk','layer':'direct_ratio','value':params['ratio']*min(params['maximum'],count),'stacks':1})
    return context.calculate('attributes.effective',{**inputs,'modifier_layers':modifiers},rule_id=params['base_rule']).value
def providers():
    from tools.chapter10_remaining_v1.build import providers as remaining
    return {**blood.providers(),**remaining(),'source.ch10.stage17.vampire':{'callable':vamp_heal,'version':'actual-owned-output-health-damage-event2.2-v1'},'source.ch10.stage17.lord':{'callable':lord_atk,'version':'native-source-ratio-per-real-aura-member-cap-v1'}}
def source(key):
    d=json.loads(SOURCE.read_bytes());return next(v for v in d['variants'].values() if v['prefab_key']==key),d['prefabs'][key]
def build(key):
    if key=='enemy_1223_dmech':raise ValueError('Source dmech20s owned resource-transfer attachment not supported by frozen joint damage-only attachment; source counter required, no fake damage or Manfred binding')
    if key not in ['enemy_1229_darmy','enemy_1228_dslime','enemy_1226_dklord']:raise ValueError('Exact selected source variant required')
    v,pref=source(key);raw=v['native_enemy']['resolved'];a=raw['attributes'];node=v['modes'][0]['nodes']['_combat'];animation=node['animation_binding'];bb={x['key']:x['valueStr'] if x['valueStr'] is not None else x['value'] for x in raw['talentBlackboard']}
    data=blood.build_all();package={k:copy.deepcopy(data.get(k,[])) for k in ['entities','abilities','buffs','rules','selectors','projectiles']};package['schemaVersion']=2
    base={'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],'move_speed':a['moveSpeed'],'attack_interval':a['baseAttackTime'],'attack_speed_ratio':a['attackSpeed']/100,'mass_level':a['massLevel'],'block_cost':1}
    body={'id':entity_id(key),'kind':'entity','tags':['enemy',key,*(raw.get('enemyTags') or [])],'components':{'attributes':{'base':base},'resources':{'hp':{'role':'health','initial':a['maxHp'],'capacity':a['maxHp']}},'selection_state':{'side':1,'category':1,'motion':1,'unit_type':2},'spatial':{'motion_mode':0,'route_motion_mode':0},'abilities':['ability/'+P+key+'/combat'],'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':raw.get('lifePointReduce',1)}}}
    selector='selector/'+P+'blocker';package['selectors'].append({'id':selector,'kind':'selector','region':{'type':'all','blocked_only':True},'filters':[{'state':'alive'},{'tag':'player'}],'limit':1})
    damage_type={1:'physical',2:'arts'}[node['raw']['_damageType']];effect={'op':'damage','damage_type':damage_type,'scale':node['raw']['_atkScale']}
    if key=='enemy_1229_darmy':
        packet='rule/'+P+'darmy_ep';package['rules'].append({'id':packet,'kind':'rule','contract':'elemental.packet','parameters':{'ratio':bb['epdamage.attack@ep_damage_ratio']},'implementation':{'type':'expression','expression':'inputs.source_attributes.atk * params.ratio'}})
        effect={'op':'elemental_attack','health_effect':effect,'element_effect':{'op':'elemental_damage','element':'DARK','amount_rule':packet}}
    if key=='enemy_1228_dslime':
        aid='ability/'+P+'slime_vampire';rid='rule/'+P+'slime_heal';buff=next(c for c in pref['components'].values() if c['native_class']=='PassiveBuffAbility')['raw']['_buffs'][0]
        body['components']['buffs']={'initial':[VAMPIRE]};body['components']['abilities'].append(aid)
        package['buffs'].append({'id':VAMPIRE,'kind':'buff','metadata':{'native':buff,'BSON':json.loads(BSON.read_bytes())['templates']['enemy_dslime_vampire']}})
        package['rules'].append({'id':rid,'kind':'rule','contract':'healing.base','parameters':{'ratio':bb['vampire.heal_scale'],'ability':aid},'implementation':{'type':'provider','provider':'source.ch10.stage17.vampire'}})
        package['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'passive','event':'damage.accepted','condition':'inputs.payload.source == inputs.source.id','parameters':{'auto_only':True}},'timeline':[{'at':0,'effect':{'op':'heal','target':'source','rules':{'healing.base':rid}}}],'metadata':{'native_hook':'Owned PassiveBuffAbility ON_AFTER_OUTPUT_DAMAGE; real accepted health delta, no heals from incoming/foreign damage'}})
    if key=='enemy_1226_dklord':
        from tools.chapter10_remaining_v1.build import build as old
        mark=next(b for b in package['buffs'] if b['id']==blood.MARK);prior=old('enemy_1226_dklord_2',bloodsucker_mark=mark)
        aura=copy.deepcopy(next(b for b in prior['buffs'] if b['id']=='buff/ch10/remaining/lord_parent'));aura['id']=LORD;child=copy.deepcopy(next(b for b in prior['buffs'] if b['id']=='buff/ch10/remaining/lord_child'));child['id']='buff/'+P+'lord_child';aura['aura']['buff']=child['id'];aura['aura']['selector']='selector/'+P+'lord_aura'
        sel=copy.deepcopy(next(s for s in prior['selectors'] if s['id']=='selector/ch10/remaining/lord_aura'));sel['id']=aura['aura']['selector']
        for rule in prior['rules']:
            if rule['id']=='rule/ch10/remaining/blood_eligibility':package['rules'].append(copy.deepcopy(rule))
        package['selectors'].append(sel);package['buffs'].extend([aura,child]);body['components']['buffs']={'initial':[LORD]}
        blood.attach_death_source(body,raw['talentBlackboard']);rid='rule/'+P+'lord_atk';body['components']['attributes']['attribute_rules']={'atk':{'attributes.effective':rid}}
        package['rules'].append({'id':rid,'kind':'rule','contract':'attributes.effective','parameters':{'ratio':bb['aura.atk'],'maximum':int(bb['aura.max_valid_stack_cnt']),'base_rule':'rule/ark_attribute_layers'},'dependencies':['rule/ark_attribute_layers'],'implementation':{'type':'provider','provider':'source.ch10.stage17.lord'}})
    package['abilities'].append({'id':'ability/'+P+key+'/combat','kind':'ability','activation':{'mode':'automatic_attack','interval_seconds':a['baseAttackTime']},'selector':selector,'duration_seconds':animation['duration']['seconds'],'timeline':[{'at_seconds':animation['events'][0]['seconds'],'effect':effect}],'metadata':{'native_combat':node}})
    package['entities'].append(body)
    package['manifest']={'id':'package/'+P+key,'metadata':{'native_variant':v,'native_prefab':pref,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'source_BSON_sha256':hashlib.sha256(BSON.read_bytes()).hexdigest(),'whole_consumer_complete':True,'client_verified':False,'reference_policy':{'combat':'source OnAttack/full animation normalized exact30fps frames; independent source cycle, blocked-only native melee','darmy_empty':'Source EmptyAbility no actions/SP/clock: EP .37 BB directly bound to pure packet parameters, raw node retained, no extra fabricated cast','dslime_heal':'Explicit reference mapping, not recovered native method body: ON_AFTER_OUTPUT_DAMAGE DAMAGE_SCALE maps to actual primary health delta of damage.accepted, through owned passive cast. Overkill uses capped HP loss, absorbed barrier/invincible HP0 uses0; postRES amount is used. Preserves heal immunity/bounds. Native/client equivalence of this output event remains unverified.','lord':'Base source14000/1000/.15 cap6 distinct from_2; native DEATH childdzomg/delay1; source-backed aura eligibility shared'}}}
    return package
