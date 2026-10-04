"""Pure exact-source qualifications, lexicographic preference and delayed point payload."""
import math

def marker_live(actor,definition,time):
 return any(b['definition']==definition and b.get('applicability',{}).get('active',True) and (b['expires_at'] is None or time<b['expires_at']) for b in actor['components'].get('buffs',{}).get('instances',[]))
def selection(inputs,params,context):
 rows=[]
 for actor in inputs['candidates']:
  attrs=actor['components'].get('attributes',{});mods=[m for m in attrs.get('modifiers',[]) if m['attribute']=='taunt_level']
  taunt=context.calculate('attributes.effective',{'base':attrs.get('base',{}).get('taunt_level',0),'modifier_layers':mods,'order':[{'layer':x} for x in params['layers']]},rule_id=params['attribute_rule']).value
  preferred=marker_live(actor,params['marker'],context['time'])
  rows.append((not preferred,-taunt,actor['id']))
 rows.sort();count=inputs['limits']['count'];return [r[2] for r in rows[:len(rows) if count is None else count]]
def half_hp(inputs,params,context):
 owner=inputs['owner'];a=owner['components']['attributes'];mods=[m for m in a.get('modifiers',[]) if m['attribute']=='max_hp']
 maximum=context.calculate('attributes.effective',{'base':a['base']['max_hp'],'modifier_layers':mods,'order':[{'layer':x} for x in params['layers']]},rule_id=params['attribute_rule']).value
 hp=owner['components']['resources']['hp']['current']
 return owner['components'].get('runtime',{}).get('alive',True) and maximum>0 and params['minimum_ratio']*maximum<=hp<=params['maximum_ratio']*maximum
def delayed_point(inputs,params,context):
 record=inputs['positions'][0];state=dict(record.get('motion_state',{}));point=dict(state.get('captured_point',record['last_target']));done=state.get('reached_once',False)
 reached=not done and inputs['trajectory_parameters']['age_seconds']>=params['delay_seconds']
 return {'position':point,'reached':reached,'motion_state':{'captured_point':point,'reached_once':done or reached}}
def area_members(inputs,params,context):
 states=context['area_selection_states'];center=inputs['center_position'];result=[]
 for actor in inputs['candidates']:
  point=actor['components']['spatial']['position']
  if math.hypot(point['row']-center['row'],point['col']-center['col'])>params['radius']:continue
  response=context.calculate('targeting.eligibility',{'source':context['source'],'candidate':actor,'selector':{'healing':False},'parameters':params['eligibility']['parameters'],'selection_states':{'source':states['source'],'candidate':states['candidates'][str(actor['id'])]}},rule_id=params['eligibility']['rule']).value
  if response['accepted']:result.append(actor['id'])
 return result
def dual_decision(inputs,params,context):
 blocked=inputs['blocked_by'] is not None;key='combat' if blocked else 'attack';busy=bool(inputs['cast_groups']['normal']);eligible=bool(inputs['eligible_ids'][key])
 return {'move':not blocked and not eligible and not busy,'attack':eligible and not busy}
def providers():
 from ark_sim.domains.providers import BUILTIN_PROVIDERS
 return {**BUILTIN_PROVIDERS,**{name:{'callable':callable,'version':'1.0.0'} for name,callable in [('reference.c8.special.selection',selection),('reference.c8.special.half_hp',half_hp),('reference.c8.special.delayed_point',delayed_point),('reference.c8.special.area',area_members),('reference.c8.special.dual',dual_decision)]}}
