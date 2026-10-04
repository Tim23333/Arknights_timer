import json,sys
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3]
from tools.experiments.m94_independent_cross_peer.test_cross import lasso_fixture,FROST
INPUTS=[];CAPTURES=[]
def ev(s,t):return [thaw(e) for e in s.session.events if e['type']==t]
def create(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=940494)
def link(s):return next(iter(s.ctx.attachments.state()['instances'].values()))
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'commands':s.export_replay()})
def fixture_boundary():
 p=lasso_fixture();p['buffs'].extend([{'id':'buff/peer/immune3','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_immunes':[0]}},{'id':'buff/peer/atk3','kind':'buff','duration_seconds':.1,'modifiers':[{'attribute':'atk','layer':'flat','value':13}]}])
 p['entities'][1]['components']['buffs']={'initial':['buff/peer/immune3','buff/m86/chen_source_stun']};p['entities'][2]['components']['buffs']={'initial':['buff/peer/atk3']}
 p['entities'][2]['components']['abilities'].append('ability/peer/probe');p['abilities'].append({'id':'ability/peer/probe','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'damage','target':2,'damage_type':'true','scale':1}]},'timeline':[]})
 return p
def test_actual_native_stun_at_exact_immunity_expiry_control_attrs_agree_without_dispatching_due_public_command(tmp_path):
 s=create(fixture_boundary());s.submit({'action':'skill','source':'director','ability':'ability/peer/probe'},at=3)
 s.advance(2);assert s.ctx.buffs.controls('victim')['attack'] is True;assert s.ctx.spatial.selection_state('victim',DEFAULT_STATE)['abnormal_flags']==[]
 h=write_ordered(tmp_path/'before.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'before.json',h));s.advance(1);r.advance(1)
 assert s.session.time==3 and s.ctx.buffs.controls('victim')['attack'] is False and s.ctx.spatial.selection_state('victim',DEFAULT_STATE)['abnormal_flags']==[0]
 assert s.ctx.get('director',('attributes','modifiers'))==[];assert not ev(s,'damage.accepted')
 assert any(t['at']==3 and t['kind']=='domain.command' for t in s.session.scheduler.pending)
 before=s.checkpoint();s.ctx.buffs.controls('victim');s.ctx.spatial.selection_state('victim',DEFAULT_STATE);assert s.checkpoint()==before
 assert s.checkpoint()==r.checkpoint();assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
 s.advance(1);r.advance(1);assert ev(s,'damage.accepted')[0]['payload']['amount']==1
 assert s.checkpoint()==r.checkpoint();assert s.snapshot()==replay(s.program,s.export_replay()).snapshot();capture(s,'native_stun_exact3')

@pytest.mark.parametrize('dead_target,expected',[(2,'cast_interrupted'),(3,'target_invalid')])
def test_public_zero_delay_callback_remove_restore_then_true_damage_death_owned_chain_exact_disk_and_replay(dead_target,expected,tmp_path):
 p=lasso_fixture();buff=p['definitions'][0]['target_buff'];director=p['entities'][2];director['components']['abilities'].append('ability/peer/cascade')
 p['abilities'].append({'id':'ability/peer/cascade','kind':'ability','activation':{'mode':'manual'},'timeline':[],'events':[{'event':'damage.accepted','condition':'inputs.payload.source == 2','effects':[{'op':'remove_buff','target':3,'buff':buff},{'op':'apply_buff','target':3,'buff':buff},{'op':'schedule','target':dead_target,'delay_seconds':0,'effect':{'op':'damage','target':dead_target,'damage_type':'true','scale':100000}}]}]})
 s=create(p);s.advance(28);h=write_ordered(tmp_path/'flight.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'flight.json',h));s.advance(7);r.advance(7)
 capture(s,'remove_restore_death_'+str(dead_target));assert s.checkpoint()==r.checkpoint();assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
 x=link(s);assert not x['active'] and x['reason']==expected and type(x['generation']) is int and type(x['active']) is bool
 assert type(x['source']) is int and type(x['target']) is int and isinstance(x['owned_buffs'],list) and all(isinstance(uid,str) for uid in x['owned_buffs'])
 assert not s.ctx.active(dead_target);assert len([e for e in ev(s,'damage.accepted') if e['payload']['source']==2])==1
 assert len(ev(s,'attachment.finished'))==1;assert not [t for t in s.session.scheduler.pending if t['kind']=='domain.attachment.step']
 if dead_target==2:
  rows=s.ctx.get('victim',('buffs','instances'));assert len(rows)==1 and rows[0]['definition']==buff and rows[0]['source']==s.session.world.resolve('director')
 else:assert not s.ctx.get('victim',('buffs','instances'))
