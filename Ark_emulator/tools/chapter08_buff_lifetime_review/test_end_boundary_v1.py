from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from tools.chapter08_buff_lifetime_review.test_joint_peer_v2 import package,INPUTS,CAPTURES,REGISTRY,command,removed,packets,capture
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from ark_sim.tools.replay import replay
def inner(inputs,params,context):
 assert context['time']==inputs['clock']['time'] and context['seconds']==inputs['clock']['time']*inputs['clock']['quantum']
 return 1 if context['time']<3 else 2
def nested(inputs,params,context):return context.calculate('buff.lifetime_rate',inputs,rule_id='rule/peer/inner_time').value
def late_fault(inputs,params,context):
 if inputs['clock']['time']==1 and inputs['instance'].get('lifetime_clock',{}).get('due')==2:raise ValueError('peer boundary latefault')
 return 1
def test_nested_rate_clock_context_and_segmented_advance_match_continuous_cp_head(tmp_path):
 p=package();p['rules'][0]['implementation']={'type':'provider','provider':'peer.nested_time'};p['rules'][0]['dependencies']=['rule/peer/inner_time'];p['rules'].append({'id':'rule/peer/inner_time','kind':'rule','contract':'buff.lifetime_rate','implementation':{'type':'provider','provider':'peer.inner_time'}});INPUTS.append(deepcopy(p));reg={**REGISTRY,'peer.nested_time':nested,'peer.inner_time':inner};program=Compiler(providers=reg).compile(p);a=Engine.create(program,providers=reg);b=Engine.create(program,providers=reg)
 for s in (a,b):command(s,'install',0)
 a.advance(2)
 for _ in range(2):b.advance(1)
 assert a.checkpoint()==b.checkpoint();pin=write_ordered(tmp_path/'nested2.json',a.checkpoint());r=Engine.restore(program,load_bound(tmp_path/'nested2.json',pin),providers=reg);a.advance(6);r.advance(6)
 for _ in range(6):b.advance(1)
 h=replay(program,a.export_replay(),providers=reg);capture(a,'nested_segmented');assert a.checkpoint()==b.checkpoint()==r.checkpoint()==h.checkpoint() and removed(a)==[5] and packets(a)==[2,4]
def test_late_second_clock_failure_rolls_back_first_clock_and_all_boundary_traces():
 p=package();evil=deepcopy(p['buffs'][0]);evil['id']='buff/peer/second_clock';evil['lifetime']['rule']='rule/peer/boundary_fault';evil['modifiers']=[];p['buffs'].append(evil);p['rules'].append({'id':'rule/peer/boundary_fault','kind':'rule','contract':'buff.lifetime_rate','implementation':{'type':'provider','provider':'peer.boundary_fault'}});p['abilities'][0]['activation']['on_start'].append({'op':'apply_buff','target':2,'buff':'buff/peer/second_clock'});INPUTS.append(deepcopy(p));reg={**REGISTRY,'peer.boundary_fault':late_fault};program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg);command(s,'install',0)
 with pytest.raises(ValueError,match='peer boundary latefault'):s.advance(2)
 capture(s,'late_boundary_fault');rows=s.ctx.get('owner',('buffs','instances'));assert len(rows)==2 and all(b['lifetime_clock']['last_time']==1 and abs(b['lifetime_clock']['remaining_seconds']-5/30)<1e-12 for b in rows)
 assert not [e for e in s.session.events if e['time']==2 and e['type']=='calculation'] and s.session.current_task is None
