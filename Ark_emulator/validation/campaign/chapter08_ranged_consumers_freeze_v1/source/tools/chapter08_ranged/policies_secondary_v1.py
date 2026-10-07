"""Exact tuple preferences for SecondaryFilter SPECIFIED_BUFF=3; body policy explicit."""
import math
from tools.chapter08_ranged.policies_v1 import providers as previous,marker_live

def selection(inputs,params,context):
 rows=[];origin=context['source']['components']['spatial']['position']
 for actor in inputs['candidates']:
  attrs=actor['components'].get('attributes',{});base=attrs.get('base',{}).get('taunt_level',0);mods=[m for m in attrs.get('modifiers',[]) if m['attribute']=='taunt_level'];hate=context.calculate('attributes.effective',{'base':base,'modifier_layers':mods,'order':[{'layer':x} for x in ('flat','direct_ratio','final_ratio')]},rule_id='rule/ark_attribute_layers').value;pos=actor['components']['spatial']['position'];distance=math.hypot(origin['row']-pos['row'],origin['col']-pos['col']);marked=marker_live(actor,params['marker'],context['time']);rows.append(((-hate,0 if marked else 1,distance,actor['id']),actor['id']))
 rows.sort();limit=inputs['limits']['count'];return [row[1] for row in rows[:limit]]
def providers():return {**previous(),'reference.c8.secondary_specified_buff':{'callable':selection,'version':'1'}}
