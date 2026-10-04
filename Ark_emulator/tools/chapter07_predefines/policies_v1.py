"""Pure ore payload decisions over actual target Buff instances."""


def ore_finish(inputs, params, context):
    now = context.get('time')
    active = {item['definition'] for item in inputs['instances']
              if item.get('applicability', {}).get('active', True)
              and (item['expires_at'] is None or now < item['expires_at'])}
    mode = inputs['request']['mode']
    buff = params['damage'] if mode == 'damage' else params['switch']
    permitted = params['immune'] not in active if mode == 'damage' else params['listener'] in active
    if mode not in ('damage', 'switch') or set(inputs['allowed']) != {buff}:
        raise ValueError('Exact ore finish mode and allowed payload required')
    return {'accepted': permitted,
            'operations': [{'kind': 'apply', 'buff': buff,
                            'duration_seconds': None, 'stacks': 1}] if permitted else []}


def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS, 'reference.c7.ore_finish':
            {'callable': ore_finish, 'version': '1.0.0'}}
