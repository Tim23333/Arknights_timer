"""Content-side source policies; generic kernel contains no Cold/Frozen IDs."""
import math
from ark_sim.contracts import thaw


def cold_application(inputs, params, context):
    cold, frozen = params['cold'], params['frozen']
    if {cold, frozen} != set(inputs['allowed']): raise ValueError('Exact source policy Buff set required')
    request = inputs['request']; seconds = request.get('duration_seconds')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0: raise ValueError('Exact source duration must be finite')
    flags = set(inputs['status']['abnormal_flags']); immunes = set(inputs['status'].get('abnormal_immunes', []))
    if 23 in immunes: return {'accepted': False, 'operations': []}
    factor = inputs['attributes'].get('one_minus_status_resistance', 1)
    if type(factor) not in (int, float) or not math.isfinite(factor) or not 0 <= factor <= 1: raise ValueError('Source resistance duration factor outside0..1')
    duration = context.calculate('buff.duration', {'attributes': inputs['attributes'],
        'buff_parameters': {'duration_seconds': seconds, 'status_duration_factor': factor}}, rule_id=params['duration_rule']).value
    selected = frozen if (23 in flags or 16 in flags) and 16 not in immunes else cold
    # Source BSON orders CreateFrozen BEFORE FinishCold. Preserve this to avoid
    # post-remove callbacks inventing a fresh application on a changed incarnation.
    ops = [{'kind': 'apply', 'buff': selected, 'duration_seconds': duration, 'stacks': 1}]
    for instance in inputs['instances']:
        if instance['definition'] in (cold, frozen) and instance['definition'] != selected:
            ops.append({'kind': 'remove', 'buff': instance['definition'], 'instance': instance['id'], 'generation': instance['generation']})
    return {'accepted': True, 'operations': ops}


def frozen_request(inputs, params, context):
    effect = thaw(inputs['effect'])
    if 16 in inputs['states']['target_selection_state']['abnormal_flags']:
        effect['scale'] = effect.get('scale', 1) * params['atk_scale']
    return {'accepted': True, 'effect': effect, 'effects': [], 'events': []}


def freeze_recovery(inputs, params, context):
    if inputs['configured_frozen']: return True
    now = inputs['time']
    return any(i['definition'] == params['frozen'] and (i['expires_at'] is None or now < i['expires_at'])
               and i.get('applicability', {}).get('active', True) and i.get('applicability', {}).get('control', True)
               for i in inputs['owner']['components'].get('buffs', {}).get('instances', []))


def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS, 'reference.c6.cold_application': {'callable': cold_application, 'version': '1.0.0'},
            'reference.c6.frozen_atkscale': {'callable': frozen_request, 'version': '1.0.0'},
            'reference.c6.frozen_recovery': {'callable': freeze_recovery, 'version': '1.0.0'}}
