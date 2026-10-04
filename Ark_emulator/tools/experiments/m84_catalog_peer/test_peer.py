import sys,copy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m84_boundary_settle_v2_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.kernel.session import Session
from ark_sim.tools.replay import replay
from ark_sim.domains.selection import DEFAULT_STATE
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def fixture():
 p={'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/boundary/subject','kind':'entity','tags':['enemy','focus'],'components':{'spatial':{},'selection_state':{'side':1},'attributes':{'base':{'max_hp':10000,'atk':20,'def':0,'mres':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'}}},{'id':'unit/boundary/director','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'atk':10}},'abilities':['ability/boundary/apply','ability/boundary/damage']}}],
 'selectors':[{'id':'selector/boundary/subject','kind':'selector','region':{'type':'all'},'filters':[{'tag':'focus'}],'limit':1}],
 'rules':[{'id':'rule/boundary/active','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'12 not in inputs.status.abnormal_flags'}},{'id':'rule/boundary/sleep','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'0 in inputs.status.abnormal_combos'}}],
 'buffs':[{'id':'buff/boundary/immune','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_combo_immunes':[0]}},{'id':'buff/boundary/sleep','kind':'buff','control_rule':'rule/boundary/sleep','selection_flags':{'abnormal_combos':[0]},'control':{'attack':False,'move':False,'abilities':False,'block':False}},{'id':'buff/boundary/silent','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_flags':[12]}},{'id':'buff/boundary/mixed','kind':'buff','active_rule':'rule/boundary/active','modifiers':[{'attribute':'atk','layer':'flat','value':13}],'selection_flags':{'abnormal_flags':[9],'abnormal_immunes':[16]}}],
 'abilities':[{'id':'ability/boundary/apply','kind':'ability','selector':'selector/boundary/subject','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/boundary/'+name} for name in ['immune','sleep','mixed','silent']]},'timeline':[]},{'id':'ability/boundary/damage','kind':'ability','selector':'selector/boundary/subject','activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'true'}]},'timeline':[]}],
 'scenarioDraft':{'id':'scene/peer/boundary','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':2,'cols':4},'initialEntities':[{'definition':'unit/boundary/subject','instanceAlias':'subject','position':{'row':0,'col':0}},{'definition':'unit/boundary/director','instanceAlias':'director','position':{'row':1,'col':3}}]}};return p

def make():
 s=Engine.create(Compiler().compile(fixture()),seed=840070);s.submit({'action':'skill','source':'director','ability':'ability/boundary/apply'},at=0);s.submit({'action':'skill','source':'director','ability':'ability/boundary/damage'},at=3);return s

def test_exact_three_boundary_mixed_state_control_agree_and_command_at_three_not_run():
 s=make();s.advance(3);state=s.ctx.spatial.selection_state('subject',DEFAULT_STATE);assert state['abnormal_flags']==[9] and state['abnormal_immunes']==[16] and state['abnormal_combos']==[0];assert not s.ctx.buffs.controls('subject')['attack'] and s.ctx.resources.current('subject','hp')==10000
 # Attribute observations have a trace, so this test is separate from replay.
 assert s.ctx.attributes.value('subject','atk')==33;before=s.checkpoint()
 for _ in range(5):s.ctx.spatial.selection_state('subject',DEFAULT_STATE);s.ctx.buffs.controls('subject')
 assert s.checkpoint()==before;s.advance(1);assert s.ctx.resources.current('subject','hp')==9990

def test_actual_public_commands_disk_checkpoint_exact_boundary_and_segmentation_replay(tmp_path):
 s=make();s.advance(2);h=write_ordered(tmp_path/'boundary.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'boundary.json',h));s.advance(2);r.advance(1);assert not r.ctx.buffs.controls('subject')['attack'];r.advance(1)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_zero_advance_and_multiple_observer_order_do_not_dispatch_new_clock_tasks():
 s=Session(seed=840071);s.register_handler('task',lambda sess,p:sess.emit('task.ran',p));s.schedule('task',{'at':3},3,phase=0)
 s.add_boundary_system(lambda sess:sess.emit('observer.first',{'time':sess.time}));s.add_boundary_system(lambda sess:sess.emit('observer.second',{'time':sess.time}));before=s.checkpoint();s.advance(0);assert before==s.checkpoint();s.advance(3)
 assert [(e['time'],e['type']) for e in s.events]==[(t,n) for t in [1,2,3] for n in ['observer.first','observer.second']];assert any(t['at']==3 for t in s.scheduler.pending)
 s.advance(1);assert len([e for e in s.events if e['type']=='task.ran'])==1

@pytest.mark.parametrize('bad',[False,[],{},1,'true',None])
def test_wrong_checkpoint_boundary_registration_is_atomic(bad):
 s=Session(seed=840072);s.add_boundary_system(lambda sess:None);s.advance(1);original=s.checkpoint();badcp=copy.deepcopy(original);badcp['systems'][0]['boundary']=bad
 with pytest.raises((ValueError,TypeError)):s.restore(badcp)
 assert s.checkpoint()==original

def test_observer_failure_rolls_its_world_rng_events_tasks_but_clock_failure_is_retained():
 s=Session(seed=840073);ref=s.world.create('unit/raw',{'credit':0});s.register_handler('later',lambda sess,p:None);at_boundary=[]
 from ark_sim.contracts import Intent
 def bad(sess):
  at_boundary.append((sess.world.snapshot(),sess.random.snapshot(),sess.scheduler.snapshot(),sess._events.snapshot()));sess.commit([Intent('set',ref,('credit',),4)]);sess.random.sample('peer');sess.emit('transient',{});sess.schedule('later',{},5);raise ValueError('observer failure')
 s.add_boundary_system(bad)
 with pytest.raises(ValueError):s.advance(1)
 assert (s.world.snapshot(),s.random.snapshot(),s.scheduler.snapshot(),s._events.snapshot())==at_boundary[0] and s.time==1 and s._failure['time']==1
 with pytest.raises(RuntimeError):s.advance(1)

@pytest.mark.parametrize('bad',[None,{},1])
def test_bad_registration_rejects_before_reserving_sequence_or_checkpoint_mutation(bad):
 s=Session(seed=840074);before=s.checkpoint()
 with pytest.raises(TypeError):s.add_boundary_system(bad)
 assert s.checkpoint()==before

def test_boundary_budget_counts_observers_and_failure_does_not_run_unentered_second_callback():
 s=Session(seed=840075);s.reaction_budget=1;s.add_boundary_system(lambda sess:sess.emit('first.completed',{}));s.add_boundary_system(lambda sess:sess.emit('second.must_not_run',{}))
 with pytest.raises(Exception,match='budget'):s.advance(1)
 assert s.time==1 and [e['type'] for e in s.events]==['first.completed'] and s._failure['time']==1
 with pytest.raises(RuntimeError):s.advance(1)

def test_real_expiry_stabilization_cycle_rolls_observer_mutations_and_clears_private_guards():
 p=fixture();p['rules'][0]['implementation']['expression']='12 in inputs.status.abnormal_flags or 9 not in inputs.status.abnormal_flags';p['abilities'][0]['activation']['on_start']=[{'op':'apply_buff','buff':'buff/boundary/'+name} for name in ['immune','sleep','silent','mixed']];s=Engine.create(Compiler().compile(p),seed=840076);s.session.reaction_budget=64;s.submit({'action':'skill','source':'director','ability':'ability/boundary/apply'},at=0)
 record=[];observer=next(row for row in s.session._systems if row.get('boundary'));old=observer['callback']
 def capture(sess):
  if sess.time==3:record.append((sess.world.snapshot(),sess.random.snapshot(),sess.scheduler.snapshot(),sess._events.snapshot()))
  return old(sess)
 observer['callback']=capture
 with pytest.raises(ValueError,match='budget'):s.advance(3)
 assert s.session.time==3 and record and (s.session.world.snapshot(),s.session.random.snapshot(),s.session.scheduler.snapshot(),s.session._events.snapshot())==record[0]
 assert not s.ctx.buffs.applicability._busy and not s.ctx.buffs.applicability._requested
 with pytest.raises(RuntimeError):s.advance(1)
