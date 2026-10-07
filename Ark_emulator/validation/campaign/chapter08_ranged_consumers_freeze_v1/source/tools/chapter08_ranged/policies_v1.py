"""Pure source marker qualification and dual combat policy; no world access."""
from collections.abc import Mapping

def marker_live(actor,marker,time):
 return any(i['definition']==marker and i.get('applicability',{}).get('active',True) and (i['expires_at'] is None or time<i['expires_at']) for i in actor['components'].get('buffs',{}).get('instances',[]))
def eligibility(inputs,params,context):
 decision=context.calculate('targeting.eligibility',inputs,rule_id=params['base_rule']).value
 if not isinstance(decision,Mapping) or set(decision)!={'accepted','reason'} or type(decision['accepted']) is not bool:raise ValueError('Strict source eligibility decision')
 if not decision['accepted']:return dict(decision)
 if params['require_marker'] and not marker_live(inputs['candidate'],params['marker'],context['time']):return {'accepted':False,'reason':'native_marker_missing'}
 return dict(decision)
def decision(inputs,params,context):
 blocked=inputs['blocked_by'] is not None;key='combat' if blocked else 'attack';eligible=bool(inputs['eligible_ids'][key]);busy=bool(inputs['cast_groups']['normal']);return {'move':not blocked and not eligible and not busy,'attack':eligible and not busy}
def score(inputs,params,context):
 attrs=inputs['candidate']['components'].get('attributes',{});base=attrs.get('base',{}).get('taunt_level',0);mods=[m for m in attrs.get('modifiers',[]) if m['attribute']=='taunt_level'];taunt=context.calculate('attributes.effective',{'base':base,'modifier_layers':mods,'order':[{'layer':x} for x in ('flat','direct_ratio','final_ratio')]},rule_id='rule/ark_attribute_layers').value;return inputs['distance']-taunt*100000

def providers():
 from ark_sim.domains.providers import BUILTIN_PROVIDERS
 return {**BUILTIN_PROVIDERS,'reference.c8.qualification':{'callable':eligibility,'version':'1'},'reference.c8.dual_combat':{'callable':decision,'version':'1'},'reference.c8.taunt':{'callable':score,'version':'1'}}
