"""Independent odd-key typed profiles; importing this file never starts runtime."""
import copy,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
A='奇相/613';B='VOID@1193:peer'
CAPA=613;CAPB=1193
def packet_helper(inputs,parameters,context):
    return inputs['attack']*inputs['ratio']
def packet(inputs,parameters,context):
    from collections.abc import Mapping
    if not isinstance(context,Mapping) or hasattr(context,'session') or hasattr(context,'world'):
        raise ValueError('Independent packet received mutation capability')
    for value in (inputs,context,inputs['source']['components']['attributes']['base'],context['owner']['components']['attributes']['base']):
        try:value['peer_illegal_write']=1
        except TypeError:pass
        else:raise ValueError('Independent provider inputs/context are writable')
    if inputs['source']['sampled_at']!=context['time']:
        raise ValueError('Independent source timestamp not actual calculation context')
    if inputs['source']['id']!=context['source']['id'] or context['owner']['id']!=inputs['target']['id']:
        raise ValueError('Independent pure context ownership differs')
    quantum_result=context.calculate('time.quantize',{'seconds':7/30,'quantum':context['quantum'],'rounding':{'mode':'ceil'}},rule_id='rule/ark_time_quantize')
    if quantum_result.value!=7:raise ValueError('Independent nested pure calculation service changed')
    return context.invoke_provider('peer.elemental.packet_helper',{'attack':inputs['source_attributes']['atk'],'ratio':inputs['request']['parameters']['ratio']})
def quantize(inputs,parameters,context):
    if context['owner'].get('definition_id')!='unit/peer/ep_receiver':raise ValueError('Independent explicit time binding lost actual owner context')
    return math.ceil(inputs['seconds']/inputs['quantum'])
def registry():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS,
      'peer.elemental.packet_helper':{'callable':packet_helper,'version':'independent-pure-nested-product-v1'},
      'peer.elemental.packet':{'callable':packet,'version':'independent-readonly-owner-timestamp-v1'},
      'peer.elemental.quantize':{'callable':quantize,'version':'independent-actual-owner-ceil-v1'}}
def scene(recovery=0,fault=False,cap_delta=False):
    rules=[]
    def rule(key,contract,expression=None,provider=None):
        rid='rule/peer/ep/'+key
        rules.append({'id':rid,'kind':'rule','contract':contract,'implementation':{'type':'expression','expression':expression} if expression else {'type':'provider','provider':provider}})
        return rid
    cap=rule('capacity','elemental.capacity','inputs.parameters.capacity + inputs.attributes.target.element_delta')
    loss=rule('loss','elemental.loss','inputs.request.raw_amount * (1 - inputs.parameters.resistance / 100)')
    regen=rule('recovery','elemental.recovery','min(inputs.capacity, inputs.current + inputs.parameters.recovery_rate * inputs.delta_seconds)')
    duration=rule('duration','elemental.break_duration','inputs.parameters.break_duration_seconds')
    eligible=rule('eligible','elemental.eligibility','inputs.target.components.selection_state.side == 0')
    pkt=rule('packet','elemental.packet',provider='peer.elemental.packet')
    next(r for r in rules if r['id']==pkt)['parameters']={'provider_dependencies':['peer.elemental.packet_helper']}
    clock=rule('clock','time.quantize',provider='peer.elemental.quantize')
    def profile(capacity,seconds,resistance):
        callbacks=[{'op':'emit','target':'target','event':'peer.ep.break_actual','payload':{}}]
        if fault:callbacks=[{'op':'random','target':'target','stream':'peer.ep.fault_rng','probability':1,'on_success':[{'op':'apply_buff','target':'target','buff':'buff/peer/ep/fault'}]},
          {'op':'emit','target':'target','event':'peer.ep.fault','payload':{}}]
        return {'capacity':capacity,'resistance':resistance,'recovery_rate':recovery,'break_duration_seconds':seconds,
          'rules':{'elemental.capacity':cap,'elemental.loss':loss,'elemental.recovery':regen,'elemental.break_duration':duration},
          'on_break':callbacks,'on_end':[{'op':'emit','target':'target','event':'peer.ep.end_actual','payload':{}}]}
    receiver={'id':'unit/peer/ep_receiver','kind':'entity','tags':['player','receiver'],'rules':{'time.quantize':clock},'components':{
      'attributes':{'base':{'max_hp':2149,'atk':31,'def':91,'mres':27,'element_delta':0}},
      'resources':{'hp':{'role':'health','initial':2149,'capacity':2149}},'spatial':{},'selection_state':{'side':0,'category':1,'motion':1},
      'elemental':{'eligibility_rule':eligible,'elements':{A:profile(CAPA,7/30,10),B:profile(CAPB,11/30,0)}},
      'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    source={'id':'unit/peer/ep_source','kind':'entity','tags':['enemy','source'],'components':{
      'attributes':{'base':{'max_hp':3311,'atk':181,'def':67,'mres':41}},'resources':{'hp':{'role':'health','initial':3311,'capacity':3311}},
      'spatial':{},'selection_state':{'side':1,'category':1,'motion':1},'abilities':[],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    p={'schemaVersion':2,'rules':rules,'entities':[receiver,source],'abilities':[],
      'buffs':[{'id':'buff/peer/ep/fault','kind':'buff','duration_seconds':2,'modifiers':[{'attribute':'mres','layer':'flat','value':-5}],
        'interval_seconds':1/30,'effects':[{'op':'emit','target':'target','event':'peer.ep.buff_pulse','payload':{}}]}],
      'scenarioDraft':{'id':'scene/peer/elemental/odd','ruleset':'ruleset/ark_standard','map':{'rows':5,'cols':7},'resources':{'dp':{'initial':20,'capacity':20}},
        'roster':[receiver['id']],'initialEntities':[{'definition':receiver['id'],'instanceAlias':'receiver','position':{'row':2,'col':2}},
          {'definition':source['id'],'instanceAlias':'sender','position':{'row':2,'col':5}}],'commands':[]}}
    # Use the same preset contracts under an independently named ruleset with
    # full trace mode; the proof must preserve full traces rather than filtering.
    preset=json.loads((ROOT/'ark_sim/content/presets/ark_standard.json').read_bytes())
    full=copy.deepcopy(next(d for d in preset['rulesets'] if d['kind']=='ruleset'));full['id']='ruleset/peer/ep/full'
    full['parameters']['trace_mode']='full';p['rulesets']=[full];p['scenarioDraft']['ruleset']=full['id']
    return p
def ability(p,key,effect,at):
    source=next(d for d in p['entities'] if d['id']=='unit/peer/ep_source');aid='ability/peer/ep/'+key
    source['components']['abilities'].append(aid)
    p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':effect}]})
    p['scenarioDraft']['commands'].append({'at':at,'action':'skill','source':'sender','ability':aid})
def request(p,key,element,amount,at,packet_rule=False,health=False):
    element_effect={'op':'elemental_damage','target':2,'element':element}
    if packet_rule:element_effect.update(amount_rule='rule/peer/ep/packet',parameters={'ratio':amount})
    else:element_effect['amount']=amount
    effect=element_effect
    if health:
        element_effect.pop('target');effect={'op':'elemental_attack','target':2,'health_effect':{'op':'damage','damage_type':'true','scale':1},'element_effect':element_effect}
    ability(p,key,effect,at)
