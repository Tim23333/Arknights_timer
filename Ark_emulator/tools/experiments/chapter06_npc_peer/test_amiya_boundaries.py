import json
from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter06_npcs.amiya_policy import providers
from tools.experiments.chapter06_npc_peer.test_peer_v2_final import fixture as own_generic_fixture
ROOT=Path(__file__).resolve().parents[3];INPUTS=[];CAPTURES=[]
def fixture(state=None,tag='ground'):
 old=own_generic_fixture(state,tag);p=json.loads((ROOT/'packages/campaign/chapter06_npcs/amiya.v3.model.json').read_bytes());p['entities'].append(old['entities'][-1]);p['scenarioDraft']=deepcopy(old['scenarioDraft']);p['scenarioDraft']['initialEntities'][0].update(definition=p['entities'][0]['id'],registration_key='char_002_amiya');p['controls']=old['controls'];p['controls'][0]['steps'][1]['effects'][0]['parameters']['key']='char_002_amiya'
 p['scenarioDraft']['initialEntities'][1]['components']={'attributes':{'base':{'mres':25}}}
 return p
def ev(s,t):return [e for e in s.session.events if e['type']==t]
def make(p):INPUTS.append(deepcopy(p));reg=providers();return Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=6468)
def capture(s,k):CAPTURES.append({'case':k,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()})
def test_hidden_activation_single_real_payload_no_native_sp_and_disk_head(tmp_path):
 s=make(fixture());s.submit({'action':'control_ack','control':'native_activation','step':0},at=20);s.advance(19);assert not ev(s,'ability.started') and not ev(s,'projectile.launched')
 cp=tmp_path/'amiya_hidden.json';h=write_ordered(cp,s.checkpoint());reg=providers();r=Engine.restore(s.program,load_bound(cp,h),providers=reg);s.advance(61);r.advance(61);head=replay(s.program,s.export_replay(),providers=reg);capture(s,'single_action_payload')
 assert s.checkpoint()==r.checkpoint()==head.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(head.session.events))
 hits=ev(s,'damage.accepted');launches=ev(s,'projectile.launched');assert len(hits)==len(launches)==1 and hits[0]['payload']['amount']==408
 assert 'sp' not in s.ctx.get('native_actor',('resources',)) and s.ctx.get('native_actor',('abilities',))==['ability/ch6/npc/amiya_normal']
 assert not s.session.random.snapshot()['samples']
@pytest.mark.parametrize('state',[{'target_free':True},{'camouflage':True}])
def test_actual_selector_zero_ignore_rejects_unselectable_target(state):
 s=make(fixture(state));s.submit({'action':'control_ack','control':'native_activation','step':0},at=20);s.advance(80);capture(s,'ineligible_'+repr(state));assert not ev(s,'ability.started') and not ev(s,'damage.accepted')
def test_native_motion_three_accepts_air_without_visual_damage_copies():
 s=make(fixture(tag='flying'));s.submit({'action':'control_ack','control':'native_activation','step':0},at=20);s.advance(80);capture(s,'air_allowed');assert len(ev(s,'damage.accepted'))==1 and ev(s,'damage.accepted')[0]['payload']['amount']==408

@pytest.mark.parametrize('case',['withdraw_source','kill_target'])
def test_real_emitted_payload_lifetime_boundary_with_public_command_disk_head(case,tmp_path):
 p=fixture();effect={'op':'retire','target':'native_actor','parameters':{'reason':'withdrawn'}} if case=='withdraw_source' else {'op':'modify_resource','target':'target','resource':'hp','value':0}
 p['abilities'].append({'id':'ability/peer/lifetime','kind':'ability','activation':{'mode':'manual','on_start':[effect]},'timeline':[]})
 p['entities'].append({'id':'unit/peer/controller','kind':'entity','components':{'attributes':{'base':{'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'abilities':['ability/peer/lifetime']}})
 p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer/controller','instanceAlias':'controller','position':{'row':0,'col':0}})
 s=make(p);s.submit({'action':'control_ack','control':'native_activation','step':0},at=20);s.submit({'action':'skill','source':'controller','ability':'ability/peer/lifetime'},at=41);s.advance(40)
 assert len(ev(s,'projectile.launched'))==1 and not ev(s,'damage.accepted')
 cp=tmp_path/(case+'.json');h=write_ordered(cp,s.checkpoint());reg=providers();r=Engine.restore(s.program,load_bound(cp,h),providers=reg);s.advance(20);r.advance(20);head=replay(s.program,s.export_replay(),providers=reg);capture(s,case)
 assert s.checkpoint()==r.checkpoint()==head.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(head.session.events))
 if case=='withdraw_source':assert not s.ctx.active('native_actor') and len(ev(s,'damage.accepted'))==1 and ev(s,'damage.accepted')[0]['payload']['amount']==408
 else:assert not s.ctx.active('target') and not ev(s,'damage.accepted')
