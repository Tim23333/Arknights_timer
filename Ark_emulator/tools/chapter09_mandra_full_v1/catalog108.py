"""Exact prior107 plus source/target/instance Buff sample, immutable catalog."""
import json
from pathlib import Path
import pytest
from ark_sim.contracts import thaw
from ark_sim.rules import DEFAULT_CATALOG
ROOT=Path(__file__).resolve().parents[2]


def test_catalog_exact107_plus_capture_and_immutable():
    parent=json.loads((ROOT/'tools/chapter09_mandra_full_v1/contracts.parent107.json').read_bytes())
    actual=thaw(DEFAULT_CATALOG);old={r['id']:r for r in parent['contracts']};rows={r['id']:r for r in actual['contracts']}
    assert len(old)==107 and len(rows)==108
    assert {k:v for k,v in actual.items() if k!='contracts'}=={k:v for k,v in parent.items() if k!='contracts'}
    assert all(rows[k]==v for k,v in old.items())
    assert set(rows)==set(old)|{'buff.capture'}
    assert rows['buff.capture']=={
        'id':'buff.capture','kind':'policy','owner':'owner',
        'inputs':[{'name':'source','type':'entity_snapshot','required':True},
                  {'name':'target','type':'entity_snapshot','required':True},
                  {'name':'instance','type':'record','required':True},
                  {'name':'clock','type':'record','required':True},
                  {'name':'parameters','type':'value_map','required':True}],
        'description':'Pure finite Buff blackboard sample from original source/target snapshots and instance generation, persisted by owned Buff application only.',
        'pureEvaluation':True,'writesStateDirectly':False,'versionsRequired':True,
        'outputSchema':{'type':'record'},'contractVersion':1,'status':'declared',
        'outputType':'record','implementations':['expression','graph','provider']}
    with pytest.raises(TypeError):DEFAULT_CATALOG['contracts'][-1]['owner']='source'
