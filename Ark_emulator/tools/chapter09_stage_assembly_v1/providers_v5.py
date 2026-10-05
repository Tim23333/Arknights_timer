"""Input-target obstacle combat is separate from ordinary range selection."""


def blocker_eligibility(inputs, parameters, context):
    from ark_sim.domains.selection import eligibility_profile
    source = inputs['source']; target = inputs['candidate']
    blocked = source['components'].get('runtime', {}).get('blocked_by')
    ss = inputs['selection_states']['source']; ts = inputs['selection_states']['candidate']
    if (inputs['selector'].get('region', {}).get('blocked_only') is True
            and target['id'] == blocked and ts['category'] == parameters['obstacle_category']
            and ss['side'] == parameters['enemy_index'] and ts['side'] == parameters['ally_index']):
        return {'accepted': True, 'reason': 'actual_blocked_input_obstacle_reference'}
    return eligibility_profile(inputs, {}, context)


def providers():
    from tools.chapter09_ruin_v2.build import providers as base
    return {**base(), 'reference.ch9.blocked_input': {
        'callable': blocker_eligibility, 'version': 'native-input-target-obstacle-reference-v1'}}
