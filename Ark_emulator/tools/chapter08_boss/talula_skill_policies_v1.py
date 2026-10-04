"""Source selector exclusion and composed providers, no world access."""


def eligibility(inputs, params, context):
    result = context.calculate('targeting.eligibility',inputs,rule_id=params['base_rule']).value
    if not result['accepted']:
        return dict(result)
    rows = inputs['candidate']['components'].get('buffs',{}).get('instances',[])
    if any(i['definition']==params['timer'] and (i['expires_at'] is None or context['time']<i['expires_at'])
            and i.get('applicability',{}).get('active',True) for i in rows):
        return {'accepted':False,'reason':'native_dragon_fire_present'}
    return dict(result)


def decision(inputs,params,context):
    from tools.chapter08_boss.talula_policies_v1 import decision as original
    normal = original(inputs,params,context)
    if inputs['cast_groups'].get('skill'):
        return {'move':False,'attack':False}
    return normal


def providers():
    from tools.chapter08_boss.talula_policies_v1 import providers as attacks
    from tools.chapter08_boss.dragon_fire_policies_v1 import providers as burns
    return {**attacks(),**burns(),'reference.c8.talula.burn_eligibility':{'callable':eligibility,'version':'1'},
        'reference.c8.talula.skills_behavior':{'callable':decision,'version':'1'}}
