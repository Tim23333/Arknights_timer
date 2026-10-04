"""Exact extension of the pre-lifetime catalog, not a guessed contract count."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'tools/candidates/chapter08_joint_v2/base_contracts.json'
BASE_SHA = '63c8e7838fccea8ebfd5b14678327b0c01cf65c978290b3df0b07abcbd254588'
LIFETIME = {
    'id': 'buff.lifetime_rate', 'kind': 'calculation', 'owner': 'target',
    'inputs': [{'name': name, 'type': kind, 'required': True} for name, kind in (
        ('owner', 'entity_snapshot'), ('source', 'entity_snapshot'), ('instance', 'record'),
        ('clock', 'record'), ('attributes', 'record'), ('parameters', 'record'))],
    'outputType': 'number', 'implementations': ['expression', 'graph', 'provider'],
    'description': 'Explicit dynamic Buff lifetime consumption rate; finite nonnegative runtime checked.',
    'pureEvaluation': True, 'writesStateDirectly': False, 'versionsRequired': True,
    'outputSchema': {'type': 'number'}, 'contractVersion': 1, 'status': 'declared',
}


def assert_catalog_extension(catalog):
    from ark_sim.contracts.models import thaw
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_SHA
    previous = json.loads(BASE.read_bytes())
    actual = thaw(catalog)
    base_contracts = {row['id']: row for row in previous['contracts']}
    actual_contracts = {row['id']: row for row in actual['contracts']}
    assert len(base_contracts) == len(previous['contracts']) == 98
    assert len(actual_contracts) == len(actual['contracts']) == 99
    assert set(actual_contracts) == set(base_contracts) | {'buff.lifetime_rate'}
    assert all(actual_contracts[key] == row for key, row in base_contracts.items())
    assert actual_contracts['buff.lifetime_rate'] == LIFETIME
    assert {key: value for key, value in actual.items() if key != 'contracts'} == {
        key: value for key, value in previous.items() if key != 'contracts'}
