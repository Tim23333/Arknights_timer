"""Audit sealed event bytes with source-bound independent chapter08 arithmetic."""
import hashlib
import json
from collections import Counter
from pathlib import Path

from tools.trace_audit.chapter08_arithmetic_v1 import expected, supported


def exact(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return list(left) == list(right) and all(exact(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(exact(a, b) for a, b in zip(left, right))
    return left == right


def trace_check(trace, definitions, rule_fingerprints, provider_identities, runtime):
    identifier = trace['rule_id']
    definition = definitions[identifier]
    assert supported(definition)
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


def audit(reference, definitions, rule_fingerprints, provider_identities, runtime):
    selected = {key: value for key, value in definitions.items() if supported(value)}
    count = 0
    digest = hashlib.sha256()
    counts, pending = Counter(), Counter()
    failures, samples = [], {}
    with Path(reference['path']).open('rb') as stream:
        for line in stream:
            if count >= reference['count']:
                break
            digest.update(line)
            count += 1
            event = json.loads(line)
            if event['type'] != 'calculation':
                continue
            trace = event['payload'].get('trace', {})
            identifier = trace.get('rule_id')
            if identifier not in selected:
                pending[str(identifier)] += 1
                continue
            try:
                assert event['payload']['rule_id'] == identifier
                assert exact(event['payload']['value'], trace['value']), 'Event and trace result differ'
                result = trace_check(trace, selected, rule_fingerprints, provider_identities, runtime)
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
            'all_intermediate_fields_verified': False, 'client_verified': False,
            'scope': 'Explicit source-bound arithmetic subset only; no claim for omitted rules, packet outcomes or full stage'}
