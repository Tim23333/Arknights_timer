"""Source EXTEND refresh timer and reset retained derived ramp after a gap."""
import math


def apply(inputs,params,context):
    from tools.chapter08_boss.dragon_fire_policies_v1 import live
    now=context['time'];rows=inputs['instances'];parents=live(rows,params['timer'],now)
    multiplier=inputs['attributes'].get(params['duration_attribute'],1)
    if type(multiplier) not in (int,float) or not math.isfinite(multiplier):raise ValueError('Status duration multiplier must be finite')
    multiplier=min(params['maximum_multiplier'],max(params['minimum_multiplier'],multiplier))
    ops=[]
    # The native permanent derived child is retained. Refreshing its existing
    # max1 instance resets its source ramp cursor only after timer absence.
    # Live-parent extension does not reapply child or restart its periodic phase.
    if not parents:ops.append({'kind':'apply','buff':params['child'],'duration_seconds':None,'stacks':1})
    ops.append({'kind':'apply','buff':params['timer'],'duration_seconds':params['duration']*multiplier,'stacks':1})
    return {'accepted':True,'operations':ops}


def providers():
    from tools.chapter08_boss.dragon_fire_policies_v1 import providers as old
    return {**old(),'reference.c8.dragon_fire.application_extend_reset':{'callable':apply,'version':'1'}}
