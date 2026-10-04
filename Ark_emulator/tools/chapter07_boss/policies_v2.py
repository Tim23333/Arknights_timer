"""Explicit source unhurtable policy; all other damage hooks still execute."""
from ark_sim.contracts import thaw
from tools.chapter07_boss.policies_v1 import providers as previous
def invulnerability(inputs,params,context):
 value=inputs['effect'].get('parameters',{}).get('consider_unhurtable',True)
 if type(value) is not bool:raise ValueError('consider_unhurtable requires strict source boolean')
 if not value:return thaw(inputs['effect']['settlement'])
 return {'accepted':False,'amount':0,'allocations':[],'events':[]}
def providers():return {**previous(),'reference.ch7.patrt_invulnerability':invulnerability}
