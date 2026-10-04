"""Actual compound impact and source retirement with fresh source16/capacity19."""
import pytest
from copy import deepcopy
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter09_elemental_review.test_root_peer_v2 import package


def proof(p,tmp_path):
    program=Compiler().compile(p);s=Engine.create(program,seed=911)
    s.submit({'action':'skill','source':'source','ability':'ability/root/ep/cast'},at=2)
    s.session.advance(40)
    assert s.ctx.resources.current('target','hp')==100
    assert s.ctx.get('target',('runtime','elemental','remaining','fire'))==19
    path=tmp_path/'inflight40.checkpoint.json';pin=write_ordered(path,s.checkpoint())
    r=Engine.restore(program,load_bound(path,pin));s.session.advance(24);r.session.advance(24)
    h=replay(program,s.export_replay());assert s.checkpoint()==r.checkpoint()==h.checkpoint()
    health=[e for e in s.session.events if e['type']=='damage.accepted']
    ep=[e for e in s.session.events if e['type']=='elemental.loss.accepted']
    assert len(health)==len(ep)==1 and health[0]['time']==ep[0]['time']==62
    assert health[0]['id']<ep[0]['id']
    assert s.ctx.resources.current('target','hp')==84
    assert s.ctx.get('target',('runtime','elemental','remaining','fire'))==18
    return s


def test_one_compound_projectile_hp_and_EP_same62_impact_order_CP40_head(tmp_path):
    proof(package(delayed=True),tmp_path)


def test_real_source_retire5_after_launch2_keeps_both16health_and1_EP(tmp_path):
    p=package(delayed=True)
    p['entities'][0]['components']['abilities'].append('ability/root/ep/retire')
    p['abilities'].append({'id':'ability/root/ep/retire','kind':'ability','activation':{'mode':'manual'},
                          'timeline':[{'at':0,'effect':{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}}]})
    p['scenarioDraft']['commands']=[{'at':5,'action':'skill','source':'source','ability':'ability/root/ep/retire'}]
    s=proof(p,tmp_path)
    assert not s.ctx.active('source')
