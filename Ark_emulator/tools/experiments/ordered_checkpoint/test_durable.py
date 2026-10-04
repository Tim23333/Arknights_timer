"""Preserving values alone is insufficient for exact causal continuation."""
from pathlib import Path
import sys
import json
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m27_event_intern_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.campaign_streaming_evidence import write_canonical


def fixture():
    return {'entities':[{'id':'unit/resource','kind':'entity','components':{'attributes':{'base':{'max_hp':10,'atk':0}},
        'resources':{'hp':{'initial':10,'capacity':10,'role':'health'},'z':{'initial':0,'capacity':10,'recovery_rate':1},'a':{'initial':0,'capacity':10,'recovery_rate':2}},'spatial':{}}}],
        'scenarioDraft':{'id':'scene/resource_order','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'objectives':{},
                         'initialEntities':[{'definition':'unit/resource','instanceAlias':'unit','position':{'row':0,'col':0}}]}}


def test_ordered_disk_checkpoint_exactly_preserves_events_and_iteration(tmp_path):
    program=Compiler().compile(fixture());s=Engine.create(program,seed=31);s.advance(1)
    path=tmp_path/'cp.json';sha=write_ordered(path,s.checkpoint());durable=load_bound(path,sha)
    r=Engine.restore(program,durable);s.advance(3);r.advance(3)
    assert s.snapshot()==r.snapshot()
    assert [key for key in r.ctx.entity('unit')['components']['resources']]==['hp','z','a']


def test_sorted_checkpoint_is_a_real_counterexample_not_an_interner_bug(tmp_path):
    program=Compiler().compile(fixture());s=Engine.create(program,seed=31);s.advance(1)
    path=tmp_path/'cp.json';write_canonical(path,s.checkpoint());r=Engine.restore(program,json.loads(path.read_bytes()));s.advance(1);r.advance(1)
    assert s.ctx.resources.current('unit','z')==r.ctx.resources.current('unit','z')
    assert s.ctx.resources.current('unit','a')==r.ctx.resources.current('unit','a')
    left=[e['payload']['resource'] for e in s.session.events if e['type']=='resource.changed' and e['time']==1]
    right=[e['payload']['resource'] for e in r.session.events if e['type']=='resource.changed' and e['time']==1]
    assert left==['z','a'] and right==['a','z']
    assert s.snapshot()!=r.snapshot()


def test_saved_checkpoint_changed_bytes_rejected(tmp_path):
    path=tmp_path/'cp.json';sha=write_ordered(path,{'z':1,'a':2});path.write_text('{"z":9,"a":2}',encoding='utf8')
    with pytest.raises(ValueError,match='bytes changed'):load_bound(path,sha)
