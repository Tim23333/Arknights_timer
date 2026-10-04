"""Pure source-driven listener/controller and hit-area policies, no kernel mutation."""
import math
from tools.chapter07_strength_melee.policies_v2 import application as strength_application
def mode_application(inputs,params,context):
 now=context['time'];live=[i for i in inputs['instances'] if i['expires_at'] is None or now<i['expires_at']];active=any(i['definition']==params['marker'] for i in live);mode=[i for i in live if i['definition']==params['mode_buff']]
 if params['listener']=='start':ops=[{'kind':'apply','buff':params['mode_buff'],'duration_seconds':None,'stacks':1}] if active and not mode else []
 elif params['listener']=='finish':ops=[{'kind':'remove','buff':params['mode_buff'],'instance':i['id'],'generation':i['generation']} for i in mode] if not active else []
 else:raise ValueError('Exact source trigger/revert required')
 return {'accepted':True,'operations':ops}
def mode_behavior(inputs,params,context):
 key='mode1' if inputs['state']=='enhanced' else 'mode0';target=bool(inputs['eligible_ids'][key]);busy=bool(inputs['cast_groups']['normal']);return {'move':not target and not busy,'attack':target and not busy}
def live_taunt_score(inputs,params,context):
 attrs=inputs['candidate']['components'].get('attributes',{});base=attrs.get('base',{}).get('taunt_level',0);mods=[m for m in attrs.get('modifiers',[]) if m['attribute']=='taunt_level'];taunt=context.calculate('attributes.effective',{'base':base,'modifier_layers':mods,'order':[{'layer':x} for x in ('flat','direct_ratio','final_ratio')]},rule_id='rule/ark_attribute_layers').value
 return inputs['distance']-taunt*100000
def mortar_box(inputs,params,context):
 center=inputs['center_position'];out=[]
 for e in inputs['entities']:
  if e['id']==context['source']['id']:continue
  state=inputs['selection_states'][str(e['id'])];source=inputs['source_selection_state'];p=e['components'].get('spatial',{}).get('position')
  if p is None or abs(p['row']-center['row'])>params['half_extent'] or abs(p['col']-center['col'])>params['half_extent']:continue
  if state['side']==source['side'] or state['side']==2 or not(state['motion']&3) or not(state['category']&1) or state['target_free']:continue
  # Native HitBehaviour ignoreCamouflage1; primary acquisition still refuses it.
  out.append(e['id'])
 return out
def providers():
 from ark_sim.domains.providers import BUILTIN_PROVIDERS
 return {**BUILTIN_PROVIDERS,'reference.c7.ranged_mode_application':{'callable':mode_application,'version':'1'},'reference.c7.ranged_mode_behavior':{'callable':mode_behavior,'version':'1'},'reference.c7.ranged_live_taunt':{'callable':live_taunt_score,'version':'1'},'reference.c7.ranged_strength':{'callable':strength_application,'version':'1'},'reference.c7.mortar_box':{'callable':mortar_box,'version':'1'}}
