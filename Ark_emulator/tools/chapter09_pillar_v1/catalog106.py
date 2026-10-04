"""Exact prior105 catalog plus the independently specified rebirth-skip contract."""
import json
from pathlib import Path
from ark_sim.contracts import thaw
from ark_sim.rules import DEFAULT_CATALOG

ROOT = Path(__file__).resolve().parents[2]


def test_catalog_exact105_plus_rebirth_skip_and_immutable():
    import pytest
    parent = json.loads((ROOT / 'tools/chapter09_elemental/contracts.parent99.json').read_bytes())
    elements = json.loads((ROOT / 'tools/chapter09_elemental/contracts.elemental6.json').read_bytes())
    expected = {r['id']: r for r in parent['contracts'] + elements}
    actual = thaw(DEFAULT_CATALOG)
    rows = {r['id']: r for r in actual['contracts']}
    assert len(expected) == 105 and len(rows) == 106
    assert {k: v for k, v in actual.items() if k != 'contracts'} == {k: v for k, v in parent.items() if k != 'contracts'}
    assert all(rows[k] == v for k, v in expected.items())
    assert set(rows) == set(expected) | {'lifecycle.rebirth_skip'}
    row = rows['lifecycle.rebirth_skip']
    assert row['owner'] == 'owner' and row['outputType'] == 'boolean'
    assert row['inputs'] == [{'name': 'source', 'type': 'entity_snapshot', 'required': True},
        {'name': 'target', 'type': 'entity_snapshot', 'required': True},
        {'name': 'depletion_event', 'type': 'record', 'required': True},
        {'name': 'clock', 'type': 'record', 'required': True}]
    assert row['pureEvaluation'] is True and row['writesStateDirectly'] is False
    assert row['implementations'] == ['expression', 'graph', 'provider'] and row['contractVersion'] == 1
    with pytest.raises(TypeError):
        DEFAULT_CATALOG['contracts'][-1]['owner'] = 'source'
