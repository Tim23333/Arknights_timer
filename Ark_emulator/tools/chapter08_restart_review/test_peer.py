from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
ATTACK='ability/peer/long';OTHER='ability/peer/other'
def restart(state='b'):
 return {'op':'restart_behavior','target':2,'state':state,'parameters':{'abilities':[ATTACK],'reset_attack_clock':True,'initial_cooldowns':{ATTACK:.11},'reason':'independent boundary'}}
def package(exit_effects=None,enter_effects=None):
 return {'schemaVersion':2,'manifest':{'id':'package/peer/restart','requires':['preset/ark_standard']},'behaviors':[{'id':'behavior/peer/machine','kind':'behavior','initial':'a','states':{'a':{'on_exit':exit_effects or []},'b':{'on_enter':enter_effects or []}}}], 'entities':[{'id':'unit/peer/actor','kind':'entity','components':{'spatial':{},'behavior':{'machine':'behavior/peer/machine'},'abilities':[ATTACK,OTHER]}},{'id':'unit/peer/director','kind':'entity','components':{'spatial':{},'abilities':['ability/peer/restart']}}],'abilities':[{'id':ATTACK,'kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':.5,'effect':{'op':'emit','event':'peer.long.packet'}}]},{'id':OTHER,'kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':.6,'effect':{'op':'emit','event':'peer.other.packet'}}]},{'id':'ability/peer/restart','kind':'ability','activation':{'mode':'manual','on_start':[restart()]},'timeline':[]}],'scenarioDraft':{'id':'scene/peer/restart','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':2},'initialEntities':[{'definition':'unit/peer/actor','instanceAlias':'actor','position':{'row':0,'col':0}},{'definition':'unit/peer/director','instanceAlias':'director','position':{'row':0,'col':1}}]}}
def make(p=None):
 p=p or package();INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=81981)
def capture(s,name):CAPTURES.append({'case':name,'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'replay':s.export_replay()})
def test_public_restart_cancels_only_declared_cast_quantizes_clock_and_disk_head(tmp_path):
 s=make();s.submit({'action':'skill','source':'actor','ability':ATTACK},at=0);s.submit({'action':'skill','source':'director','ability':'ability/peer/restart'},at=3);s.advance(2)
 pin=write_ordered(tmp_path/'restart2.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'restart2.json',pin));s.advance(20);r.advance(20);h=replay(s.program,s.export_replay());capture(s,'public');assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 assert s.ctx.get('actor',('behavior','state'))=='b' and s.ctx.get('actor',('behavior','restart_generation'))==1
 assert s.ctx.get('actor',('runtime','cooldowns',ATTACK))==7 and not any(e['type']=='peer.long.packet' for e in s.session.events)
 assert len([e for e in s.session.events if e['type']=='behavior.restarted'])==1
def test_finite_owned_set_leaves_foreign_cast_tasks_intact():
 s=make();s.ctx.abilities.start('actor',OTHER);s.ctx.effects.execute('director',[2],restart());s.advance(20);capture(s,'unlisted');assert any(e['type']=='peer.other.packet' for e in s.session.events)
@pytest.mark.parametrize('mutation',['unknown_state','foreign_ability','bool_clock','bool_generation'])
def test_invalid_request_rejects_without_world_journal_tasks_or_rng_changes(mutation):
 s=make();s.advance(1);e=restart()
 if mutation=='unknown_state':e['state']='absent'
 elif mutation=='foreign_ability':e['parameters']['abilities']=['ability/peer/restart'];e['parameters']['initial_cooldowns']={}
 elif mutation=='bool_clock':e['parameters']['initial_cooldowns'][ATTACK]=True
 else:s.ctx.set('actor',('behavior','restart_generation'),True)
 before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.effects.execute('director',[2],e)
 capture(s,mutation);assert s.checkpoint()==before and not getattr(s.ctx.behavior,'_restart_busy',set())
@pytest.mark.parametrize('where',['exit','enter'])
def test_retirement_callback_stops_later_effects_and_clock_commit(where):
 actions=[{'op':'retire','target':'self','reason':'independent callback'},{'op':'emit','event':'peer.after.retire'}];s=make(package(exit_effects=actions if where=='exit' else None,enter_effects=actions if where=='enter' else None));s.ctx.effects.execute('director',[2],restart());capture(s,where)
 assert not s.ctx.active('actor') and not any(e['type'] in ('peer.after.retire','behavior.restarted') for e in s.session.events)
 assert s.ctx.get('actor',('runtime','cooldowns',ATTACK)) is None and not getattr(s.ctx.behavior,'_restart_busy',set())
def test_recursive_callback_rolls_back_cancelled_cast_events_tasks_and_busy_scope():
 s=make(package(exit_effects=[restart()]));s.ctx.abilities.start('actor',ATTACK);before=s.checkpoint()
 with pytest.raises(ValueError,match='Recursive restart'):s.ctx.effects.execute('director',[2],restart())
 capture(s,'recursive');assert s.checkpoint()==before and not getattr(s.ctx.behavior,'_restart_busy',set())
def test_late_callback_failure_rolls_back_prior_transition_and_resource_changes():
 s=make(package(enter_effects=[{'op':'emit','event':'peer.before.fault'},{'op':'modify_resource','resource':'missing','amount':1}]));s.ctx.abilities.start('actor',ATTACK);before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.effects.execute('director',[2],restart())
 capture(s,'latefault');assert s.checkpoint()==before and not getattr(s.ctx.behavior,'_restart_busy',set())
