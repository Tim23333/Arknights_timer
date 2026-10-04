"""Different literal inputs and mutations verify the source arithmetic audit."""
from copy import deepcopy

import pytest
from tools.trace_audit.chapter08_arithmetic_v1 import expected, frames
from tools.trace_audit.chapter08_stream_v1 import trace_check


def definition(provider, parameters):
    return {'id': 'rule/peer/arithmetic', 'kind': 'rule', 'contract': 'custom',
            'parameters': parameters, 'implementation': {'type': 'provider', 'provider': provider}}


@pytest.mark.parametrize('multiplier,want', [(2, .5), (.5, 2.0), (0, 1000.0), (2000, .001)])
def test_dynamic_rate_clamps_reciprocal_without_damage_inputs(multiplier, want):
    rule = definition('reference.c8.dynamic_buff_rate', {'attribute': 'resist', 'minimum': .001, 'maximum': 1000})
    assert expected(rule, {'attributes': {'resist': multiplier}}, {}) == want


def test_burn_ramp_before_absence_and_at_cap():
    rule = definition('reference.c8.dragon_fire.pipeline',
                      {'timer': 'parent', 'child': 'child', 'base': 17, 'addition': 93, 'increase_duration': 3})
    values = {'target': {'components': {'buffs': {'instances': [
        {'definition': 'parent', 'expires_at': 200},
        {'definition': 'child', 'expires_at': None, 'started_at': 11}]}}}}
    assert expected(rule, values, {'time': 41, 'quantum': 1/30}) == {
        'accepted': True, 'amount': 48.0, 'allocations': [], 'events': []}
    assert expected(rule, values, {'time': 131, 'quantum': 1/30})['amount'] == 110
    assert expected(rule, values, {'time': 200, 'quantum': 1/30})['accepted'] is False
    values['target']['components']['buffs']['instances'][0]['applicability'] = {'active': False}
    assert expected(rule, values, {'time': 41, 'quantum': 1/30})['accepted'] is False


def test_uniform_trigger_uses_sample_and_bounds():
    rule = definition('model.field.uniform_trigger', {'minimum_key': 'lo', 'maximum_key': 'hi'})
    inputs = {'blackboard': {'lo': 3, 'hi': 7}, 'samples': [{'value': .75}]}
    assert expected(rule, inputs, {}) == {'enabled': True, 'next_delay_seconds': 6.0}
    inputs['samples'][0]['value'] = 1
    with pytest.raises(ValueError):
        expected(rule, inputs, {})


def test_bsnake_quantized_start_recovery_with_different_ASPD_and_fraction():
    rule = definition('reference.c8.bsnake.skills.recovery', {'full_seconds': 1.9})
    inputs = {'attributes': {'attack_speed_ratio': 2}, 'recovery_parameters': {'seconds': 7.05}}
    assert frames(.95, 1/30) == 29 and frames(7.05, 1/30) == 212
    assert expected(rule, inputs, {'quantum': 1/30}) == 183 / 30


@pytest.mark.parametrize('mutation', [
    lambda trace: trace['inputs']['attributes'].update(resist=4),
    lambda trace: trace['parameters'].update(maximum=99),
    lambda trace: trace['provider'].update(source_sha256='forged'),
    lambda trace: trace.update(rule_fingerprint='forged'),
    lambda trace: trace.update(runtime_fingerprint='forged'),
    lambda trace: trace.update(raw=False),
])
def test_unchanged_observed_result_cannot_validate_changed_source_or_input(mutation):
    rule = definition('reference.c8.dynamic_buff_rate', {'attribute': 'resist', 'minimum': .001, 'maximum': 1000})
    identity = {'name': 'reference.c8.dynamic_buff_rate', 'source_sha256': 'source'}
    trace = {'rule_id': rule['id'], 'runtime_fingerprint': 'runtime', 'rule_fingerprint': 'rule',
             'parameters': deepcopy(rule['parameters']), 'provider': deepcopy(identity),
             'inputs': {'attributes': {'resist': 2}}, 'context': {}, 'raw': .5, 'value': .5,
             'numeric': {'backend': 'float', 'rounding': 'half_even'}}
    arguments = ({rule['id']: rule}, {rule['id']: 'rule'}, {identity['name']: identity}, 'runtime')
    assert trace_check(trace, *arguments) == .5
    mutation(trace)
    assert trace['value'] == .5
    with pytest.raises(AssertionError):
        trace_check(trace, *arguments)
