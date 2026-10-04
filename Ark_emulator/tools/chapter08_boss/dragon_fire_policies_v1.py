"""Pure source-defined parent/derived-child lifetime and capped burn ramp."""


def live(instances, ident, time):
    return [i for i in instances if i['definition'] == ident and i.get('applicability',{}).get('active',True)
        and (i['expires_at'] is None or time < i['expires_at'])]


def apply(inputs, params, context):
    rows = inputs['instances']
    now = context['time']
    timer, child = params['timer'], params['child']
    if live(rows, timer, now):
        return {'accepted':False,'operations':[]}
    ops = []
    # Permanent child survives timer finish (native finishDerivedBuffIfParentFinishFalse).
    # A new parent application reuses it and its existing damage ramp.
    if not live(rows, child, now):
        ops.append({'kind':'apply','buff':child,'duration_seconds':None,'stacks':1})
    ops.append({'kind':'apply','buff':timer,'duration_seconds':params['duration'],'stacks':1})
    return {'accepted':True,'operations':ops}


def pipeline(inputs, params, context):
    rows = inputs['target']['components'].get('buffs',{}).get('instances',[])
    now = context['time']
    parents = live(rows, params['timer'], now)
    children = live(rows, params['child'], now)
    if not parents or len(children) != 1:
        return {'accepted':False,'amount':0,'allocations':[],'events':[]}
    elapsed = (now-children[0]['started_at'])*context['quantum']
    fraction = min(1,max(0,elapsed/params['increase_duration']))
    amount = params['base']+params['addition']*fraction
    return {'accepted':True,'amount':amount,'allocations':[],'events':[]}


def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS, 'reference.c8.dragon_fire.application':{'callable':apply,'version':'1'},
        'reference.c8.dragon_fire.pipeline':{'callable':pipeline,'version':'1'}}
