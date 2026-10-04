"""Exact prior 99 definitions plus six independently typed elemental contracts."""
import hashlib,json
from pathlib import Path
from ark_sim.contracts import thaw
from ark_sim.rules import DEFAULT_CATALOG

HERE=Path(__file__).parent

def test_catalog_is_exact_previous99_plus_elemental6_and_readonly():
    import pytest
    locks=json.loads((HERE/'catalog.locks.json').read_bytes())
    parent_path=HERE/'contracts.parent99.json';extra_path=HERE/'contracts.elemental6.json'
    assert hashlib.sha256(parent_path.read_bytes()).hexdigest()==locks['parent_sha256']
    assert hashlib.sha256(extra_path.read_bytes()).hexdigest()==locks['elemental_sha256']
    parent=json.loads(parent_path.read_bytes());extra=json.loads(extra_path.read_bytes());actual=thaw(DEFAULT_CATALOG)
    parent_rows={row['id']:row for row in parent['contracts']}
    actual_rows={row['id']:row for row in actual['contracts']}
    assert len(parent_rows)==99 and len(actual_rows)==105
    assert {key:value for key,value in actual.items() if key!='contracts'}=={key:value for key,value in parent.items() if key!='contracts'}
    assert all(actual_rows[key]==value for key,value in parent_rows.items())
    assert len(extra)==6 and set(actual_rows)==set(parent_rows)|{x['id'] for x in extra}
    assert all(actual_rows[row['id']]==row for row in extra)
    with pytest.raises(TypeError):DEFAULT_CATALOG['types']['number']={}
    with pytest.raises(TypeError):DEFAULT_CATALOG['contracts'][-1]['owner']='source'
