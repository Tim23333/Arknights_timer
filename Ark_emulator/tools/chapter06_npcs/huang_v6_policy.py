"""Pure source-content low-HP decision over effective attributes and status."""
from tools.chapter06_npcs.policies import providers as prior_providers


def low_hp_application(inputs, params, context):
    child = params['reaction']
    if list(inputs['allowed']) != [child]:
        raise ValueError('Exact finite low-HP reaction closure required')
    hp = inputs['target']['components']['resources']['hp']['current']
    cap = inputs['attributes']['max_hp']
    if hp >= cap * params['threshold']:
        return {'accepted': False, 'operations': []}
    if any(b['definition']==child for b in inputs['instances']):
        return {'accepted':False,'operations':[]}
    return {'accepted': True, 'operations': [
        {'kind': 'apply', 'buff': child, 'duration_seconds': context['quantum'], 'stacks': 1}]}


def providers():
    return {**prior_providers(), 'reference.c6.npc_low_hp':
            {'callable': low_hp_application, 'version': '1.0.0'},
            'reference.c6.npc_owner_heal':{'callable': owner_heal, 'version':'1.0.0'}}


def owner_heal(inputs,params,context):
    if inputs['source']['id'] != inputs['candidate']['id']:
        return {'accepted':False,'reason':'buff_owner_only'}
    if inputs['selection_states']['candidate']['heal_free']:
        return {'accepted':False,'reason':'heal_free'}
    return {'accepted':True,'reason':'source_buff_owner_heal'}
