"""Scenario-owned blocking dispatch; entity bindings cannot select this contract."""
from collections.abc import Mapping


def blocking(inputs, parameters, context):
    from tools.chapter09_ruin_v2.build import blocking as squared_radius
    blocker = inputs['blocker']
    spec = parameters['ruin']
    if blocker['definition_id'] == spec['definition']:
        return squared_radius(inputs, {'radius_squared': spec['radius_squared']}, context)
    value = context.calculate('blocking.eligibility', inputs, rule_id=parameters['base_rule']).value
    if not isinstance(value, Mapping) or set(value) != {'accepted', 'reason'}:
        raise ValueError('Base blocking rule must return accepted/reason')
    return dict(value)


def providers():
    from tools.chapter09_stage_assembly_v1.providers_v5 import providers as base
    return {**base(), 'reference.ch9.scenario_blocking': {
        'callable': blocking, 'version': 'scenario-owned-native-obstacle-radius-v1'}}
