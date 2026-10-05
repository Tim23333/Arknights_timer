"""Exact frozen prior106 table plus the new pure finite depletion protocol."""
import json
from pathlib import Path
from ark_sim.contracts import thaw
from ark_sim.rules import DEFAULT_CATALOG

ROOT = Path(__file__).resolve().parents[2]


def test_catalog_exact106_plus_depletion_and_immutable():
    import pytest
    parent = json.loads((ROOT / 'tools/chapter09_pillar_channel_joint_v3/contracts.parent106.json').read_bytes())
    actual = thaw(DEFAULT_CATALOG)
    expected = {row['id']: row for row in parent['contracts']}
    rows = {row['id']: row for row in actual['contracts']}
    assert len(expected) == 106 and len(rows) == 107
    assert {k: v for k, v in actual.items() if k != 'contracts'} == {k: v for k, v in parent.items() if k != 'contracts'}
    assert all(rows[key] == row for key, row in expected.items())
    assert set(rows) == set(expected) | {'resource.depletion'}
    assert rows['resource.depletion'] == {
        'id': 'resource.depletion', 'kind': 'policy', 'owner': 'owner',
        'inputs': [
            {'name': 'source', 'type': 'entity_snapshot', 'required': True},
            {'name': 'target', 'type': 'entity_snapshot', 'required': True},
            {'name': 'request', 'type': 'record', 'required': True},
            {'name': 'state', 'type': 'record', 'required': True},
            {'name': 'clock', 'type': 'record', 'required': True},
            {'name': 'parameters', 'type': 'value_map', 'required': True}],
        'outputType': 'record', 'implementations': ['expression', 'graph', 'provider'],
        'description': 'Pure exact-zero owner health defer/finish/none plan selecting finite declared stages and action keys; actual health/source delivery only.',
        'pureEvaluation': True, 'writesStateDirectly': False, 'versionsRequired': True,
        'outputSchema': {'type': 'record'}, 'contractVersion': 1, 'status': 'declared'}
    with pytest.raises(TypeError):
        DEFAULT_CATALOG['contracts'][-1]['owner'] = 'source'
