"""Lateeffectphase rate changes sampled at finaltick boundary, source arithmetic."""
import json
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_buff_lifetime_review.test_peer_v3 import package,make,command,removed,packets

def test_initialrate2_restore1_at150_reversescounter765_not764(tmp_path):
    p=package();p['buffs'][0]['duration_seconds']=30.5;p['buffs'][0]['interval_seconds']=1
    p['rules'][0]['implementation']['expression']='1 / inputs.attributes.clock_multiplier'
    p['entities'][0]['components']['attributes']['base']['clock_multiplier']=1
    p['buffs'][1]['modifiers']=[{'attribute':'clock_multiplier','layer':'final_ratio','value':-.5}]
    p['entities'][0]['components']['buffs']={'initial':['buff/peer/fast']}
    p['abilities'].append({'id':'ability/peer/restore','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'remove_buff','target':2,'buff':'buff/peer/fast'}]},'timeline':[]});p['entities'][1]['components']['abilities'].append('ability/peer/restore')
    s=make(p);command(s,'install',0);command(s,'restore',150);s.advance(151);cp=tmp_path/'reverse151.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h));s.advance(629);r.advance(629);head=replay(s.program,s.export_replay())
    assert s.checkpoint()==r.checkpoint()==head.checkpoint() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    assert removed(s)==[765] and packets(s)==list(range(30,751,30))

def test_rate_change_on_exactexpiry_cannot_resurrect_old_nominaltime():
    p=package();p['buffs'][0]['duration_seconds']=2/30;p['buffs'][0]['interval_seconds']=1/30
    s=make(p);command(s,'install',0);command(s,'pause',2);s.advance(4)
    assert removed(s)==[2] and packets(s)==[1]
