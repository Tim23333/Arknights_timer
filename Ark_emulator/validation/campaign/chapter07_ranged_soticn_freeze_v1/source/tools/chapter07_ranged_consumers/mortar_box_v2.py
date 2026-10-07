"""Pure native 3x3 mortar box; explicit domain projection required, no world reads."""
import math
from collections.abc import Mapping
from ark_sim.contracts import thaw

def mortar_box(inputs,params,context):
 options={**thaw(params),**thaw(inputs['parameters'])};half=options['half_extent']
 if type(half) not in (int,float) or not math.isfinite(half) or half<0:raise ValueError('finite nonnegative box half extent required')
 projection=context['area_selection_states'];center=inputs['center_position'];result=[]
 for actor in inputs['candidates']:
  pos=actor['components']['spatial']['position']
  if abs(pos['row']-center['row'])>half or abs(pos['col']-center['col'])>half:continue
  decision=context.calculate('targeting.eligibility',{'source':context['source'],'candidate':actor,'selector':{'healing':False},'parameters':options['eligibility']['parameters'],'selection_states':{'source':projection['source'],'candidate':projection['candidates'][str(actor['id'])]}},rule_id=options['eligibility']['rule']).value
  if not isinstance(decision,Mapping) or set(decision)!={'accepted','reason'} or type(decision['accepted']) is not bool:raise ValueError('strict native eligibility decision required')
  if decision['accepted']:result.append(actor['id'])
 return result
