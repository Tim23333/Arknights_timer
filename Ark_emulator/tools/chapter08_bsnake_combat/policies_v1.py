"""Pure source qualification, tuple hatred and source-dependent protection."""
from collections.abc import Mapping

def eligibility(inputs,params,context):
 result=context.calculate('targeting.eligibility',inputs,rule_id=params['base_rule']).value
 if not isinstance(result,Mapping) or type(result['accepted']) is not bool:raise ValueError('Typed qualification required')
 if not result['accepted']:return dict(result)
 blocker=inputs['source']['components'].get('runtime',{}).get('blocked_by')
 if blocker is not None and inputs['candidate']['id']!=blocker:return {'accepted':False,'reason':'actual_blocker_identity'}
 return dict(result)

def selection(inputs,params,context):
 rows=[]
 for actor in inputs['candidates']:
  attrs=actor['components'].get('attributes',{});mods=[m for m in attrs.get('modifiers',[]) if m['attribute']=='taunt_level'];hate=context.calculate('attributes.effective',{'base':attrs.get('base',{}).get('taunt_level',0),'modifier_layers':mods,'order':[{'layer':x} for x in ('flat','direct_ratio','final_ratio')]},rule_id='rule/ark_attribute_layers').value
  rows.append(((-hate,-actor['id']),actor['id']))
 rows.sort();limit=inputs['limits']['count'];return [x[1] for x in rows[:limit]]

def decision(inputs,params,context):
 normal=inputs['mode'] in (0,1);eligible=bool(inputs['eligible_ids'].get('normal'));busy=bool(inputs['cast_groups'].get('normal'));return {'move':normal and inputs['blocked_by'] is None and not eligible and not busy,'attack':normal and eligible and not busy}

def protect(inputs,params,context):
 rows=inputs['source'].get('components',{}).get('buffs',{}).get('instances',[]);now=context['time'];marked=any(i['definition']==params['dragon_fire'] and i.get('applicability',{}).get('active',True) and (i['expires_at'] is None or now<i['expires_at']) for i in rows)
 amount=inputs['effect']['settlement']['amount'];return {'accepted':True,'amount':amount*(1-params['resistance']) if marked else amount,'allocations':[],'events':[]}

def providers():
 from tools.chapter08_boss.dragon_fire_policies_v3 import providers as fire
 from tools.chapter08_buff_lifetime.policies_v1 import providers as clock
 return {**fire(),**clock(),'reference.c8.bsnake.normal_eligibility':{'callable':eligibility,'version':'1'},'reference.c8.bsnake.hatred':{'callable':selection,'version':'1'},'reference.c8.bsnake.normal_decision':{'callable':decision,'version':'1'},'reference.c8.bsnake.burned_source_protect':{'callable':protect,'version':'1'}}
