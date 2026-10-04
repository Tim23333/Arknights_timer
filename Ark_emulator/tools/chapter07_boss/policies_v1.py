"""Pure Patriot source policies; no world access, IDs or labels in kernel."""
from ark_sim.contracts import thaw
from ark_sim.domains.providers import BUILTIN_PROVIDERS
def spear_eligibility(inputs,params,context):
 base=context.calculate('targeting.eligibility',{k:inputs[k] for k in ['source','candidate','selector','parameters','selection_states']},rule_id=params['base_rule']).value
 tile=inputs.get('candidate_spatial_tile')
 if tile is None:raise ValueError('Actual candidate_spatial_tile projection required for sourceBuildableType2')
 buildable=tile['tile'].get('buildableType',0)
 if type(buildable) is not int or buildable<0:raise ValueError('Actual tile buildableType must be typed mask')
 return {'accepted':base['accepted'] and bool(buildable & params['buildable_mask']),'reason':'native_buildabletype2_AND_typedtarget'}
def spear_selection(inputs,params,context):
 rows=[]
 for actor in inputs['candidates']:
  attrs=actor['components'].get('attributes',{});base=attrs.get('base',{}).get('taunt_level',params['default_taunt']);mods=[m for m in attrs.get('modifiers',[]) if m['attribute']=='taunt_level']
  taunt=context.calculate('attributes.effective',{'base':base,'modifier_layers':mods,'order':[{'layer':x} for x in params['attribute_layers']]},rule_id=params['attribute_rule']).value
  rows.append((-taunt,inputs['scores'][str(actor['id'])],actor['id']))
 rows.sort();count=inputs['limits']['count'];return [r[2] for r in rows[:len(rows) if count is None else count]]
def providers():
 return {**BUILTIN_PROVIDERS,'reference.ch7.patrt_spear_eligibility':spear_eligibility,'reference.ch7.patrt_spear_selection':spear_selection}
