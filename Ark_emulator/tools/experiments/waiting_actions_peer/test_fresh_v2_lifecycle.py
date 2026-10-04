from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from tools.experiments.waiting_actions_peer.test_peer_targeted import package,make,capture,events,INPUTS,CAPTURES

def test_foreign_source_timer_never_leases_waiting_owners_ability():
 p=package();p['entities'][0]['components']['buffs']['initial']=[];s=make(p);s.ctx.buffs.apply(3,2,'buff/peer/timer')
 with pytest.raises(ValueError):s.advance(45)
 capture(s,'actual_foreign_timer');assert not events(s,'peer.wait.impact')

def test_removed_finish_job_prevents_forged_waiting_world_state_from_authorizing_timer():
 s=make();s.advance(2);state=s.ctx.get('waiter',('runtime','rebirth'));s.session.cancel(state['task']);s.advance(33);capture(s,'cancelled_real_finishjob');assert not events(s,'peer.wait.impact')

def test_wrong_finish_job_due_no_lease_even_if_phase_and_generation_still_match():
 s=make();s.advance(2);state=s.ctx.get('waiter',('runtime','rebirth'));s.ctx.set('waiter',('runtime','rebirth','due_at'),state['due_at']+1);s.advance(33);capture(s,'wrong_finish_due');assert not events(s,'peer.wait.impact')

def test_actual_waiting_activation_late_callback_failure_rolls_back_meter_cast_and_scope():
 p=package();p['entities'][1]['components']['resources']={'meter':{'initial':0,'capacity':10},'hp':{'initial':101,'capacity':101,'role':'health'}};p['rules'].append({'id':'rule/peer/explode','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':'1/0'}],'output':'nodes.result'}});p['abilities'][0]['activation']['on_start']=[{'op':'modify_resource','target':3,'resource':'meter','delta':1},{'op':'damage','target':3,'damage_type':'true','scale':1,'rules':{'damage.pipeline':'rule/peer/explode'}}];s=make(p);s.advance(29)
 with pytest.raises(Exception):s.advance(1)
 capture(s,'waiting_callback_fault');assert s.ctx.resources.current('controller','meter')==0 and s.ctx.resources.current('waiter','hp')==0 and not s.ctx.active('waiter') and not s.ctx.get('waiter',('runtime','casts')) and not s.ctx.waiting_actions._scopes
 assert not [e for e in events(s,'ability.started') if e['payload']['ability']=='ability/peer/wait']

def test_actual_public_retire_waiting_owner_cancels_inflight_and_owned_finishjob():
 p=package();p['abilities'].append({'id':'ability/peer/retire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}]},'timeline':[]});p['entities'][1]['components']['abilities'].append('ability/peer/retire');s=make(p);s.submit({'action':'skill','source':'controller','ability':'ability/peer/retire'},at=30);s.advance(105);capture(s,'real_waiting_retired');assert not s.ctx.active('waiter') and not events(s,'peer.wait.impact') and s.ctx.get('waiter',('runtime','rebirth','phase'))=='cancelled'

def test_public_terminal_life_zero_cancels_waiting_cast_and_future_restore():
 p=package();p['scenarioDraft']['resources']={'life':{'initial':1,'capacity':1}};p['scenarioDraft']['objectives']={'life_resource':'life'};p['abilities'].append({'id':'ability/peer/end','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'modify_resource','target':1,'resource':'life','value':0}]},'timeline':[]});p['entities'][1]['components']['abilities'].append('ability/peer/end');s=make(p);s.submit({'action':'skill','source':'controller','ability':'ability/peer/end'},at=30);s.advance(105);capture(s,'terminal_waiting');assert s.ctx.state()['finished'] and not events(s,'peer.wait.impact') and s.ctx.resources.current('waiter','hp')==0 and s.ctx.get('waiter',('runtime','rebirth','phase'))=='cancelled'
