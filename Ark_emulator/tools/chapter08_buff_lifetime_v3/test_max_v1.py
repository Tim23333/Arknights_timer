"""Actual maxstack dynamic remaining clock, shorter and longer application."""
from copy import deepcopy
from tools.chapter08_buff_lifetime_review.test_peer_v3 import package,make,command,removed,packets
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def proof(tmp_path,seconds,end):
    p=package('max');p['rules'].append({'id':'rule/peer/shortduration','kind':'rule','contract':'buff.application',
        'parameters':{'seconds':seconds},'implementation':{'type':'expression','expression':"{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/timer','duration_seconds':params.seconds,'stacks':1}]}"}})
    p['abilities'].append({'id':'ability/peer/reapply','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'buff_application','target':2,'allowed':['buff/peer/timer'],'application_rule':'rule/peer/shortduration'}]},'timeline':[]});p['entities'][1]['components']['abilities'].append('ability/peer/reapply')
    s=make(p);command(s,'install',0);s.submit({'action':'skill','source':'director','ability':'ability/peer/reapply'},at=3)
    s.advance(2);path=tmp_path/'max2.cp.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,h));s.advance(end-2);r.advance(end-2);head=replay(s.program,s.export_replay())
    assert s.checkpoint()==r.checkpoint()==head.checkpoint() and list(s.session.events)==list(r.session.events)==list(head.session.events);return s

def test_shorter_new1tick_keeps_previousremaining3tick_expiry6(tmp_path):
    s=proof(tmp_path,1/30,9);assert removed(s)==[6] and packets(s)==[2,5]

def test_longer_new8tick_extends_maxexpiry11(tmp_path):
    s=proof(tmp_path,8/30,14);assert removed(s)==[11] and packets(s)==[2,5,7,9]
