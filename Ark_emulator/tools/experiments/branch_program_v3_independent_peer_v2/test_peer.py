from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[];CALLS=[]
def fixture(loop=False,victory=False,fault=False):
 source={'id':'unit/peer/source','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'abilities':['ability/peer/advance','ability/peer/lose'],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 trap={'id':'unit/peer/trap','kind':'entity','tags':['trap'],'components':{'attributes':{'base':{'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 abilities=[{'id':'ability/peer/advance','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'advance_branch','parameters':{'branch':'peer'}}]},'timeline':[]},{'id':'ability/peer/lose','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'modify_resource','target':'battle','resource':'life','value':0}]},'timeline':[]}]
 effect={'op':'activate_predefined','target':'battle','parameters':{'key':'alpha'}}
 effects=[effect]
 if fault:effects.append({'op':'random','target':'battle','stream':'branch_peer_fault','on_success':[{'op':'modify_resource','target':3,'resource':'missing','delta':1}]})
 phases=[{'pre_delay_seconds':.1,'actions':[{'delay_seconds':1/30,'effects':effects}]},{'pre_delay_seconds':0,'actions':[{'delay_seconds':0,'effects':[{'op':'activate_predefined','target':'battle','parameters':{'key':'beta'}}]}]}]
 if loop:phases=[{'pre_delay_seconds':.1,'actions':[{'delay_seconds':0,'effects':[{'op':'emit','target':'battle','event':'peer.loop'}]}]}]
 return {'manifest':{'requires':['preset/ark_standard']},'definitions':[source,trap,*abilities],'scenarioDraft':{'id':'scene/peer/branches','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':5},'branches':{'peer':{'loop':loop,'phases':phases}},'objectives':{'type':'waves','life_resource':'life'} if victory else {'life_resource':'life'},'waves':[],'resources':{'life':{'initial':99999,'capacity':99999},'dp':{'initial':25,'capacity':99}},'initialEntities':[{'definition':source['id'],'instanceAlias':'source','position':{'row':0,'col':0}},{'definition':trap['id'],'instanceAlias':'alpha','position':{'row':0,'col':2},'active':False,'registration_key':'alpha'},{'definition':trap['id'],'instanceAlias':'beta','position':{'row':1,'col':3},'active':False,'registration_key':'beta'}]}}
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=5107)
def row(s):return s.ctx.branches.state()['peer']
def ev(s,t):return [thaw(e) for e in s.session.events if e['type']==t]
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'commands':s.export_replay()})
def payload():return {'branch':'peer','generation':1,'phase_index':0,'action_index':0}
@pytest.mark.parametrize('field,value',[('generation',True),('phase_index',True),('phase_index',1),('action_index',-1),('action_index',99)])
def test_strict_payload_and_wrong_phase_or_action_fail_without_world_writes(field,value):
 s=make(fixture());s.ctx.branches.advance('peer',2);p=payload();p[field]=value;before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.branches.action(s.session,p)
 assert s.checkpoint()==before;CALLS.append({'case':'typed','payload':p});capture(s,'typed_'+field+'_'+str(value))
def test_undispatched_owned_payload_is_rejected_while_job_is_still_pending():
 s=make(fixture());s.ctx.branches.advance('peer',2);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.branches.action(s.session,payload())
 assert s.checkpoint()==before;capture(s,'early_direct_call')
@pytest.mark.parametrize('foreign',[False,True])
def test_canceling_owned_job_cannot_turn_caller_or_foreign_task_into_owned_dispatch(foreign):
 s=make(fixture());s.ctx.branches.advance('peer',2);owned=row(s)['tasks'][0];s.session.cancel(owned);CALLS.append({'op':'cancel','task':owned,'foreign':foreign})
 if foreign:s.session.schedule('domain.branch.action',payload(),4,phase=s.ctx.effect_phase)
 rejected=False
 if foreign:
  try:s.advance(5)
  except ValueError:rejected=True
 else:
  s.advance(4);before=s.checkpoint()
  try:s.ctx.branches.action(s.session,payload())
  except ValueError:rejected=True
 capture(s,'forged_dispatch_'+str(foreign));assert rejected and not s.ctx.active('alpha') and row(s)['cursor']==0 and row(s)['remaining']==1
def test_accepted_battle_owned_phase_survives_requester_withdraw_as_explicit_policy(tmp_path):
 s=make(fixture());s.submit({'action':'skill','source':'source','ability':'ability/peer/advance'},at=0);s.submit({'action':'withdraw','source':'source'},at=1);s.advance(2);h=write_ordered(tmp_path/'pending.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'pending.json',h));s.advance(3);r.advance(3)
 assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot();capture(s,'source_exit_policy')
 assert not s.ctx.active('source') and s.ctx.active('alpha') and row(s)['cursor']==1
 before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.branches.advance('peer',2)
 assert s.checkpoint()==before
def test_busy_exhausted_and_explicit_loop_progress_are_actual_public_events(tmp_path):
 s=make(fixture());s.submit({'action':'skill','source':'source','ability':'ability/peer/advance'},at=0);s.submit({'action':'skill','source':'source','ability':'ability/peer/advance'},at=1);s.submit({'action':'skill','source':'source','ability':'ability/peer/advance'},at=5);s.submit({'action':'skill','source':'source','ability':'ability/peer/advance'},at=7);s.advance(3)
 h=write_ordered(tmp_path/'phase.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'phase.json',h));s.advance(5);r.advance(5);assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot();capture(s,'busy_exhausted')
 assert row(s)['cursor']==2 and not s.ctx.branches.available('peer');assert len(ev(s,'command.rejected'))==2
 s=make(fixture(loop=True))
 for t in [0,4,8]:s.submit({'action':'skill','source':'source','ability':'ability/peer/advance'},at=t)
 s.advance(12);capture(s,'loop_three');assert row(s)['cursor']==3 and row(s)['generation']==3 and len(ev(s,'peer.loop'))==3 and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_terminal_real_life_command_cancels_without_claiming_phase_done(tmp_path):
 p=fixture();p['scenarioDraft']['objectives']['type']='waves';p['definitions'][0]['tags']=['enemy'];s=make(p);s.submit({'action':'skill','source':'source','ability':'ability/peer/advance'},at=0);s.submit({'action':'skill','source':'source','ability':'ability/peer/lose'},at=2);s.advance(3);capture(s,'terminal_cancel')
 assert s.ctx.state()['finished'] and row(s)['phase']=='stopped' and row(s)['cursor']==0 and row(s)['remaining']==1 and not s.ctx.active('alpha')
 assert not [t for t in s.session.scheduler.pending if t['kind']=='domain.branch.action'];assert not ev(s,'branch.phase_finished')
 h=write_ordered(tmp_path/'terminal.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'terminal.json',h));assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_real_action_failure_after_activation_and_rng_restores_boundary_partition():
 s=make(fixture(fault=True));s.submit({'action':'skill','source':'source','ability':'ability/peer/advance'},at=0);old=s.ctx.branches.action;before=[]
 def handler(session,p):
  before.append({'world':session.world.snapshot(),'scheduler':session.scheduler.snapshot(),'random':session.random.snapshot(),'events':session._events.snapshot()});return old(session,p)
 s.session._handlers['domain.branch.action']=handler
 with pytest.raises(ValueError):s.advance(5)
 after={'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'random':s.session.random.snapshot(),'events':s.session._events.snapshot()};assert after==before[0] and not s.ctx.active('alpha') and row(s)['phase']=='running';capture(s,'fault_atomic')
def test_victory_waits_for_running_branch_actual_activation_then_idle_completion():
 s=make(fixture(victory=True));s.submit({'action':'skill','source':'source','ability':'ability/peer/advance'},at=0);s.advance(4);assert not s.ctx.state()['finished'] and row(s)['phase']=='running'
 s.advance(3);capture(s,'victory_pending');assert s.ctx.active('alpha') and row(s)['cursor']==1 and s.ctx.state()['finished'] and s.ctx.state()['result']=='victory'
