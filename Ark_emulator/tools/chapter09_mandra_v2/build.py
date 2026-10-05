"""Source-correct second life; frozen V1 inputs, unchanged joint runtime."""
import json, hashlib
from pathlib import Path
from tools.chapter09_mandra_v1.build import build as prior, providers as prior_providers, PROFILE, BODY, PREFIX
ROOT=Path(__file__).resolve().parents[2]
CALLGRAPH=ROOT/'packages/campaign/chapter09_consumers/mandra_v2/source.reborn.callgraph.v2.json'
IMMUNE='buff/'+PREFIX+'native_immune'
DAMAGE=CALLGRAPH.with_name('damage_resistance.source.v1.json')
def shield(inputs,params,context):
    from tools.chapter09_mandra_v1.build import shield as old
    result=old(inputs,params,context)
    if inputs['effect'].get('damage_type','physical') not in ('physical','arts'):result['amount']=inputs['effect']['settlement']['amount']
    return result
def invulnerable(inputs,params,context):
    import copy
    result=copy.deepcopy(dict(inputs['effect']['settlement']));result['amount']=0
    for row in result.get('allocations',[]):
        if row.get('resource','hp')=='hp':
            if 'amount'in row:row['amount']=0
            if 'delta'in row:row['delta']=0
    return result
def immune_control(inputs,params,context):
    flags=set(inputs['parameters']['flags']);combos=set(inputs['parameters']['combos'])
    return not flags.intersection(inputs['status'].get('abnormal_immunes',[])) and not combos.intersection(inputs['status'].get('abnormal_combo_immunes',[]))
def providers():
    return {**prior_providers(),'reference.mandra.shield':{'callable':shield,'version':'native-physical-magical-one-minus60-v2'},'reference.mandra.invulnerable':{'callable':invulnerable,'version':'owned-timed-no-damage-v2'},'reference.mandra.immune_control':{'callable':immune_control,'version':'typed-native-control-immunity-v2'}}

def build(profile='talent_prefix'):
    p=prior(profile);damage=json.loads(DAMAGE.read_bytes());node=damage['templates']['damage_resistance']['parsed']['eventToActions']['ON_TAKE_DAMAGE'][0];assert node['_damageMask']=='PHYSICAL_AND_MAGICAL' and node['_filterDamageType'] and node['_isOneMinus'];graph=json.loads(CALLGRAPH.read_bytes());body=next(d for d in p['entities'] if d['id']==BODY)['components']
    native=graph['PassiveImmunity']['buff']['attributes']
    p['buffs'].append({'id':IMMUNE,'kind':'buff','selection_flags':{
        'abnormal_flags':native['abnormalFlags'],'abnormal_immunes':native['abnormalImmunes'],
        'abnormal_combo_immunes':native['abnormalComboImmunes']},'metadata':{'native_inline':graph['PassiveImmunity']}})
    p['rules'].append({'id':'rule/'+PREFIX+'invulnerable','kind':'rule','contract':'damage.pipeline','implementation':{'type':'provider','provider':'reference.mandra.invulnerable'}})
    next(b for b in p['buffs'] if b['id']=='buff/'+PREFIX+'invulnerable')['damage_hooks']=[{'phase':'after','rule':'rule/'+PREFIX+'invulnerable'}]
    stun=next(b for b in p['buffs'] if b['id']=='buff/ch9/pillar/stun10');stun['selection_flags']={'abnormal_flags':[0]};stun['control_rule']='rule/'+PREFIX+'stun_immunity';stun['parameters']={'flags':[0],'combos':[]}
    p['rules'].append({'id':'rule/'+PREFIX+'stun_immunity','kind':'rule','contract':'buff.applicability','implementation':{'type':'provider','provider':'reference.mandra.immune_control'}})
    body['buffs']['initial'].append(IMMUNE)
    body['rebirth']['retain_buffs']=[IMMUNE]
    # The existing generic protocol rebinds retained self Buffs only inside a
    # real consume callback. Infinite native immunity gains no waiting action
    # permission, artificial health or periodic task from this reapplication.
    body['rebirth']['on_finish']=body['rebirth']['on_begin']
    body['rebirth']['on_begin']=[{'op':'apply_buff','buff':IMMUNE,'target':'source'}]
    body['lifecycle']['leak_loss']=graph['native_lifePointReduce']
    metadata=p['manifest']['metadata'];p['manifest']['id']='package/ch9/mandra/source_v2/'+profile
    metadata['source_locks'].update({str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in [CALLGRAPH,DAMAGE,Path(__file__)]})
    metadata['reborn_source_callgraph']=graph;metadata['damage_resistance_source']=damage;metadata['reference_policy']['pillar_break']='Native PHYSICAL_AND_MAGICAL-only shield leaves TRUE unchanged; source pillar PURE12000 is never reduced4800; accepted actual source trait hit still breaks shield'
    metadata['reference_policy']['rebirth_application']='HP0 waiting has only source-listed retained immunity. Actual completing callback restores HP, enters mode2 and installs shield/area/invulnerability and cooldowns. Invulnerability3/5 and Ray10/Summon20/10 begin at actual completion;5s/100% restoration is explicit level0 PRTS reference versus preserved native0.5/preDelay4.5 values.'
    metadata['reference_policy']['retained_immunity_bridge']='Infinite source-listed immunity is rebound by real consume callback using existing generic self-Buff lease; no action/cast grant.'
    metadata['reference_policy']['leak_loss']='Native resolved.lifePointReduce2; only base99999 policy may override stage life.'
    return p
