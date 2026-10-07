"""Literal strength start/finish listeners consume live Buff ownership."""
def application(inputs, params, context):
    wanted=params['derived'];assert list(inputs['allowed'])==[wanted]
    now=context['time']
    live=[i for i in inputs['instances'] if i.get('expires_at') is None or now<i['expires_at']]
    marker=any(i['definition']==params['marker'] for i in live)
    derived=[i for i in live if i['definition']==wanted]
    if params['mode']=='start':
        ops=[{'kind':'apply','buff':wanted,'stacks':1}] if marker and not derived else []
    elif params['mode']=='finish':
        ops=[{'kind':'remove','buff':wanted,'instance':i['id'],'generation':i['generation']} for i in derived] if not marker else []
    else:raise ValueError('Source start/finish listener mode required')
    return {'accepted':True,'operations':ops}
def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS,'reference.ch7.strength_listener':{'callable':application,'version':'1.0.0'}}
