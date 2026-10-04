"""Audit sealed event bytes with source-bound independent chapter08 arithmetic."""
import hashlib
import math
import json
from collections import Counter
from pathlib import Path

from tools.trace_audit.chapter08_arithmetic_v2 import expected, supported


def exact(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return list(left) == list(right) and all(exact(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(exact(a, b) for a, b in zip(left, right))
    return left == right


def trace_check(trace, definitions, rule_fingerprints, provider_identities, runtime, event=None, expected_quantum=None):
    identifier = trace['rule_id']
    definition = definitions[identifier]
    assert supported(definition)
    contract=definition['contract'];version=definition.get('contractVersion',1)
    assert type(trace['contract_version']) is int and trace['contract_version']==version, 'Contract version differs'
    assert type(trace['calculation_id']) is str and trace['calculation_id']==contract, 'Calculation contract differs'
    context=trace['context'];time=context['time'];quantum=context['quantum']
    assert type(time) is int and time>=0, 'Trace time must be strict integer'
    assert type(quantum) in (int,float) and math.isfinite(quantum) and quantum>0, 'Trace quantum must be finite positive'
    assert type(expected_quantum) in (int,float) and math.isfinite(expected_quantum) and expected_quantum>0 and quantum==expected_quantum, 'Bound runtime quantum differs or missing'
    assert type(context['seconds']) in (int,float) and math.isfinite(context['seconds']) and context['seconds']==time*quantum, 'Clock seconds differs'
    for identity_key in ('source_id','target_id','owner_id'):
        identity=context.get(identity_key)
        assert identity is None or (type(identity) is int and identity>0), 'Context actor identity has invalid shape'
    for name in ('clock',):
        if name in trace['inputs']:
            clock=trace['inputs'][name]
            assert type(clock['time']) is int and clock['time']==time and type(clock['quantum']) in (int,float) and clock['quantum']==quantum, 'Input clock differs'
    if event is not None:
        temporal_rate=(definition['contract']=='buff.lifetime_rate' and definition['implementation'].get('provider')=='reference.c8.dynamic_buff_rate')
        # Source Buff lifetime boundary samples the previous interval before
        # current-time pruning. Both same-tick application and next-boundary
        # publication are explicit supported contexts; other rules stay same-time.
        event_times=(time,time+1) if temporal_rate else (time,)
        assert event['type']=='calculation' and type(event['time']) is int and event['time'] in event_times, 'Event clock differs'
        payload=event['payload']
        assert payload['calculation_id']==contract and payload['rule_id']==identifier and exact(payload['value'],trace['value']), 'Event calculation/result binding differs'
        for key in ('source','target'):
            identity=payload.get(key);bound=context.get(key+'_id')
            assert (identity is None or (type(identity) is int and identity>0)) and exact(identity,bound), 'Event actor binding differs'

    assert trace['runtime_fingerprint'] == runtime, 'Rule runtime differs'
    assert trace['rule_fingerprint'] == rule_fingerprints[identifier], 'Source rule differs'
    assert exact(trace['parameters'], definition.get('parameters', {})), 'Source parameters differ'
    impl = definition['implementation']
    if impl['type'] == 'provider':
        assert exact(trace['provider'], provider_identities[impl['provider']]), 'Provider source differs'
    else:
        stage = next(stage for stage in trace['stages'] if stage['id'] == 'expression')
        assert stage['expression'] == impl['expression'], 'Expression source differs'
    result = expected(definition, trace['inputs'], trace['context'])
    assert exact(result, trace['raw']) and exact(result, trace['value']), 'Independent result differs'
    assert trace['numeric'] == {'backend': 'float', 'rounding': 'half_even'}
    return result


def audit(reference, definitions, rule_fingerprints, provider_identities, runtime, expected_quantum):
    selected = {key: value for key, value in definitions.items() if supported(value)}
    count = 0
    digest = hashlib.sha256()
    counts, pending = Counter(), Counter()
    cached_pending=Counter()
    failures, samples = [], {}
    with Path(reference['path']).open('rb') as stream:
        for line in stream:
            if count >= reference['count']:
                break
            digest.update(line)
            count += 1
            event = json.loads(line)
            if event['type'] != 'calculation':
                if event['type']=='calculation.cached':cached_pending[str(event['payload'].get('rule_id'))]+=1
                continue
            trace = event['payload'].get('trace', {})
            identifier = trace.get('rule_id')
            if identifier not in selected:
                pending[str(identifier)] += 1
                continue
            try:
                assert event['payload']['rule_id'] == identifier
                assert exact(event['payload']['value'], trace['value']), 'Event and trace result differ'
                result = trace_check(trace, selected, rule_fingerprints, provider_identities, runtime, event=event, expected_quantum=expected_quantum)
                counts[identifier] += 1
                samples.setdefault(identifier, {'event': event['id'], 'time': event['time'],
                                                'independent_value': result})
            except Exception as error:
                failures.append({'event': event['id'], 'rule': identifier,
                                 'type': type(error).__name__, 'reason': str(error)})
    assert count == reference['count'] and digest.hexdigest() == reference['sha256'], 'Sealed journal prefix differs'
    return {'passed_subset': not failures and bool(counts), 'sealed_prefix_verified': True,
            'event_count': count, 'journal_sha': digest.hexdigest(),
            'checked_rules': dict(counts), 'independent_examples': samples,
            'failures': failures, 'uncovered_calculation_counts': dict(pending),
            'cached_calculation_pending_counts':dict(cached_pending),
            'all_intermediate_fields_verified': False, 'client_verified': False,
            'scope': 'Explicit source-bound arithmetic subset only; no claim for omitted rules, packet outcomes or full stage'}
