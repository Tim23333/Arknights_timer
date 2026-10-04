"""Target initial duration scaling; dynamic remaining lifetime is separate."""
import math


def apply(inputs,params,context):
    from tools.chapter08_boss.dragon_fire_policies_v1 import live
    now=context['time'];rows=inputs['instances']
    if live(rows,params['timer'],now):return {'accepted':False,'operations':[]}
    attrs=inputs['attributes'];multiplier=attrs.get(params['duration_attribute'],1)
    if type(multiplier) not in (int,float) or not math.isfinite(multiplier):raise ValueError('Status duration multiplier must be finite')
    multiplier=min(params['maximum_multiplier'],max(params['minimum_multiplier'],multiplier))
    ops=[]
    if not live(rows,params['child'],now):ops.append({'kind':'apply','buff':params['child'],'duration_seconds':None,'stacks':1})
    ops.append({'kind':'apply','buff':params['timer'],'duration_seconds':params['duration']*multiplier,'stacks':1})
    return {'accepted':True,'operations':ops}


def providers():
    from tools.chapter08_boss.dragon_fire_policies_v1 import providers as old
    return {**old(),'reference.c8.dragon_fire.application_initial_resistance':{'callable':apply,'version':'1'}}
