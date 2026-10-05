"""Source-owned Duspfr consumer; native rows retained, model policies explicit."""
import json,hashlib,base64,copy
from pathlib import Path
from tools.chapter09_ability_clock_v1 import flame_channel
from tools.chapter09_pillar_lifecycle_v1 import build as pillar
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json';DETAIL=ROOT/'packages/campaign/chapter09_source_prepare/source.detail.v1.json';REQ=ROOT/'packages/campaign/chapter09_consumers/linked_elemental/duspfr.consumer.requirements.v1.json'
BODY='unit/ch9/duspfr/body';FLAME='ability/ch9/duspfr/flame';TRAIT='buff/ch9/duspfr/deadboom';DEAD='buff/ch9/duspfr/deadlike'
def remap(value):
    if isinstance(value,str):
        return value.replace('unit/linked/source',BODY).replace('ability/linked/fire',FLAME).replace('rule/linked/','rule/ch9/duspfr/').replace('attachment/linked/fire','attachment/ch9/duspfr/flame').replace('buff/linked/','buff/ch9/duspfr/').replace('buff/ch9/flame/casting_state','buff/ch9/duspfr/casting_state')
    if isinstance(value,list):return [remap(x) for x in value]
    if isinstance(value,dict):return {k:remap(v) for k,v in value.items()}
    return value
def dead_plan(inputs,params,context):
    if 12 in context['selection_states']['target']['abnormal_flags']:return {'action':'finish','stage':inputs['state']['stage'],'actions':[]}
    if not any(b['definition']==TRAIT and b.get('applicability',{}).get('active',True) and (b['expires_at'] is None or context['time']<b['expires_at']) for b in inputs['target']['components'].get('buffs',{}).get('instances',[])):return {'action':'finish','stage':inputs['state']['stage'],'actions':[]}
    if inputs['state']['stage']=='normal':return {'action':'defer','stage':'terminal','actions':['begin','DieAnim','Suicide','PullDupilr','Damage','KillDuspfr']}
    return {'action':'none','stage':inputs['state']['stage'],'actions':[]}
def pillar_plan(inputs,params,context):
    if inputs['request']['health_after']>0 and pillar.READY not in pillar.ids(inputs['target']):return {'action':'none','stage':inputs['state']['stage'],'actions':[]}
    return pillar.plan(inputs,params,context)
def members(inputs,params,context):
    from math import hypot
    center=inputs['center_position'];result=[];kind=inputs['parameters']['kind'];states=context['area_selection_states']['candidates']
    for actor in inputs['candidates']:
        if actor['id']==context['source']['id']:continue
        pos=actor['components'].get('spatial',{}).get('position');state=states[str(actor['id'])]
        if pos is None or hypot(pos['row']-center['row'],pos['col']-center['col'])>2:continue
        buffs={b['definition'] for b in actor['components'].get('buffs',{}).get('instances',[]) if b['expires_at'] is None or context['time']<b['expires_at']}
        if not state['category']&1 or not state['motion']&(1 if kind=='players' else 3):continue
        if kind=='players' and state['side']!=0:continue
        if kind=='pillar' and pillar.ONDEAD not in buffs:continue
        if kind=='duspfr' and (state['side']!=1 or TRAIT not in buffs):continue
        if kind!='pillar' and state['target_free']:continue
        if state['camouflage'] or state.get('invisible',False):continue
        result.append(actor['id'])
    return result
def providers():
    from ark_sim.domains.selection import eligibility_profile
    return {**flame_channel.providers(),**pillar.providers(),'reference.ch9.duspfr_eligibility':{'callable':eligibility_profile,'version':'explicit-native-mask-v1'},'reference.ch9.duspfr_dead_plan':{'callable':dead_plan,'version':'source-unsilenced-owned-trait-once-v2'},'reference.ch9.duspfr_members':{'callable':members,'version':'native-typed-circle2-v1'},'reference.ch9.pillar_positive_plan':{'callable':pillar_plan,'version':'native-candead-on-take-damage-v1'}}
def build(include_pillar=True):
    from ark_sim.domains.selection import DEFAULT_STATE,SWITCHES
    source=json.loads(SOURCE.read_bytes());detail=json.loads(DETAIL.read_bytes());requirements=json.loads(REQ.read_bytes());row=next(v for v in source['variants'].values() if v['prefab_key']=='enemy_1173_duspfr');attrs=row['native_enemy']['resolved']['attributes'];assert (attrs['maxHp'],attrs['atk'],attrs['def'],attrs['moveSpeed'])==(8000,500,400,.8)
    p=remap(flame_channel.package());p['entities']=[p['entities'][0]];p.pop('scenarioDraft',None)
    body=p['entities'][0]['components'];body['attributes']['base'].update(move_speed=.8,mass_level=3,block_cost=1);body['spatial']={'motion_mode':0,'steering':{'rule':'rule/ch9/duspfr/steering','parameters':{'response_factor':8,'max_acceleration':10,'arrival_radius':.05}}}
    p['rules'].append({'id':'rule/ch9/duspfr/steering','kind':'rule','contract':'movement.steering','implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}})
    cs=source['prefabs']['enemy_1173_duspfr']['components'];trigger=next(x for x in cs.values() if x['native_class']=='AdvancedSelector' and x['gameobject_name']=='Trigger');target=next(x for x in cs.values() if x['native_class']=='AdvancedSelector' and x['gameobject_name']=='Selector');eligibility='rule/ch9/duspfr/eligibility'
    p['rules'].append({'id':eligibility,'kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'reference.ch9.duspfr_eligibility'}})
    def selector(sid,raw,radius):
        config={**{k:0 for k in SWITCHES},**raw};config.pop('m_GameObject',None);config.pop('m_Script',None)
        return {'id':sid,'kind':'selector','region':{'type':'radius','radius':radius},'filters':[{'state':'alive'}],'limit':1,'eligibility':{'rule':eligibility,'parameters':{'source_configuration':config,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':copy.deepcopy(DEFAULT_STATE)}}}
    p['selectors']=[selector('selector/ch9/duspfr/flame_trigger',trigger['raw'],1),selector('selector/ch9/duspfr/flame_target',target['raw'],2),{'id':'selector/ch9/duspfr/blocker','kind':'selector','region':{'type':'all','blocked_only':True},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1}]
    flame=p['abilities'][0];flame['selector']='selector/ch9/duspfr/flame_target';flame['trigger_selector']='selector/ch9/duspfr/flame_trigger';flame['activation']['forbidden_source_flags']=[0,12,16];p['definitions'][0]['source_cancel_flags']=[0,12,16]
    p['abilities'].append({'id':'ability/ch9/duspfr/blocked_attack','kind':'ability','activation':{'mode':'automatic_attack','interval_seconds':2},'selector':'selector/ch9/duspfr/blocker','duration_seconds':1,'timeline':[{'at_seconds':13/30,'effect':{'op':'damage','damage_type':'physical','scale':1}}],'metadata':{'source_OnAttack_frame':13,'source_full_frame':30,'native_attack_trigger':'NeverTrigger; only actual blocked combat permitted'}});body['abilities'].append('ability/ch9/duspfr/blocked_attack')
    boom=detail['deadboom_source_beforezero'];bson=boom['BSON'];assert hashlib.sha256(base64.b64decode(bson['document_base64'])).hexdigest()==bson['document_sha256']
    p['buffs'] += [{'id':TRAIT,'kind':'buff','metadata':{'native_BSON':bson,'consumer':'Unsilenced current zero-health request -> finite owned five-way parallel callbacks'}},{'id':DEAD,'kind':'buff','duration_seconds':3,'selection_flags':{'abnormal_flags':[15,2,5,3,6],'abnormal_immunes':[0,16],'abnormal_combo_immunes':[0]},'control':{'move':False,'attack':False}}]
    p['rules'] += [{'id':'rule/ch9/duspfr/depletion','kind':'rule','contract':'resource.depletion','implementation':{'type':'provider','provider':'reference.ch9.duspfr_dead_plan'}},{'id':'rule/ch9/duspfr/dead_members','kind':'rule','contract':'area.members','implementation':{'type':'provider','provider':'reference.ch9.duspfr_members'}}]
    def area(kind,effects):return {'op':'area','center':'source','target':'source','membership_rule':'rule/ch9/duspfr/dead_members','selection_projection':{'defaults':DEFAULT_STATE},'parameters':{'kind':kind},'effects':effects}
    actions={'begin':{'at_seconds':0,'effects':[{'op':'remove_buff','buff':TRAIT,'remove_all':True,'parameters':{'retain_definitions':[TRAIT]}},{'op':'apply_buff','buff':DEAD}]}}
    for child in boom['actual_child_nodes']:
        raw=child['node']['raw'];name=child['node']['gameobject_name'];aid='ability/ch9/duspfr/dead_'+name
        if name=='DieAnim':seconds=0;duration=source['animations']['enemy_1173_duspfr']['parsed']['animations']['Die']['duration']['seconds'];effects=[]
        else:seconds=raw['_preDelay'];duration=seconds
        if name=='Suicide':effects=[{'op':'instant_kill','target':'source','parameters':{'cause':'duspfr_suicide','skip_rebirth':False,'source_policy':'none','origin':{'native':'DeadBoom/Suicide','source_node':child['path_id']}}}]
        elif name=='PullDupilr':effects=[area('pillar',[{'op':'apply_buff','buff':pillar.READY},{'op':'damage','damage_type':'true','scale':raw['_atkScale']}])]
        elif name=='Damage':effects=[area('players',[{'op':'damage','damage_type':'arts','scale':raw['_atkScale']}])]
        elif name=='KillDuspfr':effects=[area('duspfr',[{'op':'damage','damage_type':'true','scale':raw['_atkScale']}])]
        p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual','parameters':{'blocks_attacks':False}},'duration_seconds':duration,'timeline':[{'at_seconds':seconds,'effects':effects}] if effects else [],'metadata':{'native_child':child,'parallel_source_group':boom['parallel_group'],'native_element_type':raw.get('_elementDamageType',0),'native_ep_ratio':raw.get('_epDamageRatio',0)}});body['abilities'].append(aid);actions[name]={'at_seconds':0,'effects':[],'owned_ability':aid}
    body['buffs']['initial'].append(TRAIT);body['depletion']={'resource':'hp','rule':'rule/ch9/duspfr/depletion','selection_context':True,'initial_stage':'normal','parameters':{},'stages':{'normal':{'active':True,'selectable':True},'terminal':{'active':False,'selectable':False}},'actions':actions}
    if include_pillar:
        partner=pillar.build();partner['entities'][0]['components']['depletion']['trigger']='health_zero_or_damage';partner['entities'][0]['components']['depletion']['rule']='rule/ch9/duspfr/pillar_plan';partner['rules'].append({'id':'rule/ch9/duspfr/pillar_plan','kind':'rule','contract':'resource.depletion','implementation':{'type':'provider','provider':'reference.ch9.pillar_positive_plan'}})
        for field in ['entities','abilities','buffs','rules']:p[field].extend(partner[field])
    p['manifest']={'id':'package/ch9/duspfr/full_source_v1','metadata':{'source_locks':{str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in [SOURCE,DETAIL,REQ,Path(__file__)]},'native_variant':row['native_reference'],'literal_native_stats':attrs,'literal_skill_rows':row['native_enemy']['resolved']['skills'],'literal_normal_attack':requirements['source_combat'],'literal_Flame':requirements['source_Flame'],'literal_trigger':requirements['source_skilltrigger'],'literal_geometries':requirements['source_geometries'],'literal_deadboom':boom,'reference_policy':{'geometry':'Collider centers use Euclidean radius1 trigger/radius2 target; native ValidateTarget method absent, typed selection version retained','harpoon':'Travel planar homing10 at1/30; contact-first .5 packets; native Harpoon/Lasso raw preserved, no native method proof','Flame_clock':'Birth-ready automatic trigger; 10.6 castingstate/6pulse/10cooldown; source silence/stun/freeze and target invalid cancel link; repeat after cooldown','Suicide_clock':'Literal float32 1.10000002384 under model ceil ticks (34 at30fps), distinct from3s deadlike buff lifetime','DeadBoom':'Five owned concurrent casts, native Damage has elementDamageType0/epRatio0 and arts health500; no invented FIRE EP on explosion','positive_pillar':'Native candead ON_TAKE_DAMAGE can start collapse at actual positive HP4500; opt-in damage lifecycle profile, no fake zero/HP1'},'whole_enemy_complete':False,'pending':['actual author/independent gates','durable Buff distinction and visuals','client method/Collider/harpoon equivalence']}}
    return p
