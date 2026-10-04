"""Independent arithmetic for an explicit subset of chapter08 source rules."""
import math


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('A finite numeric input is required')
    return value


def frames(seconds, quantum):
    seconds, quantum = number(seconds), number(quantum)
    if seconds < 0 or quantum <= 0:
        raise ValueError('Nonnegative seconds and positive quantum required')
    return math.ceil(round(seconds / quantum, 12))


def expected(definition, inputs, context):
    """Calculate from source parameters/inputs, never from observed outputs."""
    impl = definition['implementation']
    params = definition.get('parameters', {})
    provider = impl.get('provider')
    expression = impl.get('expression')
    if provider == 'reference.c8.dynamic_buff_rate':
        rate = number(inputs['attributes'].get(params['attribute'], 1))
        return 1 / min(number(params['maximum']), max(number(params['minimum']), rate))
    if provider == 'reference.c8.dragon_fire.pipeline':
        now = context['time']
        if type(now) is not int or now < 0:raise ValueError('Strict integer trace time required')
        entries = inputs['target']['components'].get('buffs', {}).get('instances', [])
        def active(identifier):
            return [entry for entry in entries if entry['definition'] == identifier
                    and entry.get('applicability', {}).get('active', True)
                    and (entry['expires_at'] is None or now < entry['expires_at'])]
        parent, child = active(params['timer']), active(params['child'])
        if not parent or len(child) != 1:
            return {'accepted': False, 'amount': 0, 'allocations': [], 'events': []}
        started=child[0]['started_at']
        if type(started) is not int or started<0:raise ValueError('Strict integer child start time required')
        elapsed = (now - started) * number(context['quantum'])
        fraction = min(1, max(0, elapsed / number(params['increase_duration'])))
        return {'accepted': True, 'amount': number(params['base']) + number(params['addition']) * fraction,
                'allocations': [], 'events': []}
    if provider == 'model.field.uniform_trigger':
        bb = inputs['blackboard']
        low, high = number(bb[params['minimum_key']]), number(bb[params['maximum_key']])
        samples = inputs['samples']
        if len(samples) != 1 or not 0 <= number(samples[0]['value']) < 1 or not 0 <= low <= high:
            raise ValueError('One valid uniform sample and ordered interval required')
        return {'enabled': True, 'next_delay_seconds': low + (high - low) * samples[0]['value']}
    if provider in ('reference.c8.talula.start_cooldown', 'reference.c8.bsnake.skills.recovery'):
        q = number(context['quantum'])
        speed = max(number(inputs['attributes']['attack_speed_ratio']), .01)
        total = frames(inputs['recovery_parameters']['seconds'], q)
        if provider == 'reference.c8.talula.start_cooldown':
            speed *= number(params['mapping_speed'])
            busy = max(frames(number(params['source_duration']) / speed, q),
                       frames(number(params['source_delay']) / speed, q))
        else:
            busy = frames(number(params['full_seconds']) / speed, q)
        return max(0, total - busy) * q
    timing = {
        'inputs.timing_parameters.seconds / (params.mapping_speed * max(inputs.attributes.attack_speed_ratio,.01))': ('timing_parameters', True),
        'inputs.duration_parameters.seconds / (params.mapping_speed * max(inputs.attributes.attack_speed_ratio,.01))': ('duration_parameters', True),
        'inputs.timing_parameters.seconds/max(inputs.attributes.attack_speed_ratio,.01)': ('timing_parameters', False),
        'inputs.duration_parameters.seconds/max(inputs.attributes.attack_speed_ratio,.01)': ('duration_parameters', False),
    }
    if expression in timing:
        field, mapping = timing[expression]
        denominator = max(number(inputs['attributes']['attack_speed_ratio']), .01)
        if mapping:
            denominator *= number(params['mapping_speed'])
        return number(inputs[field]['seconds']) / denominator
    if expression in ('inputs.owner.components.resources.mode.current != 2',
                      'inputs.owner.components.resources.mode.current != 3'):
        mode = 2 if expression.endswith('2') else 3
        observed=inputs['owner']['components']['resources']['mode']['current']
        if type(observed) not in (int,float) or not math.isfinite(observed):raise ValueError('Typed finite mode required')
        return observed != mode
    raise KeyError(definition['id'])


def supported(definition):
    if definition.get('kind') not in ('rule', 'calculation_rule'):
        return False
    if definition.get('numeric') not in (None, {'backend':'float','rounding':'half_even'}):
        return False  # Custom numeric profiles require a separate explicit oracle.
    impl = definition.get('implementation', {})
    return impl.get('provider') in {
        'reference.c8.dynamic_buff_rate', 'reference.c8.dragon_fire.pipeline',
        'model.field.uniform_trigger', 'reference.c8.talula.start_cooldown',
        'reference.c8.bsnake.skills.recovery'} or impl.get('expression') in {
        'inputs.timing_parameters.seconds / (params.mapping_speed * max(inputs.attributes.attack_speed_ratio,.01))',
        'inputs.duration_parameters.seconds / (params.mapping_speed * max(inputs.attributes.attack_speed_ratio,.01))',
        'inputs.timing_parameters.seconds/max(inputs.attributes.attack_speed_ratio,.01)',
        'inputs.duration_parameters.seconds/max(inputs.attributes.attack_speed_ratio,.01)',
        'inputs.owner.components.resources.mode.current != 2',
        'inputs.owner.components.resources.mode.current != 3'}
