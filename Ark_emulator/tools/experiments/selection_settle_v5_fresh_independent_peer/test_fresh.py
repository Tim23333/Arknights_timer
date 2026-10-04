from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from tools.experiments.selection_settle_independent_peer_v2.test_boundary import callback_fixture,aid
INPUTS=[];CAPTURES=[]
def create(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=55556)
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot()})
def test_settlement_callback_new_stun_controls_are_rechecked_without_accepting_outer_cast():
 p=callback_fixture('nested');p['buffs'].append({'id':'buff/peer/new_control','kind':'buff','selection_flags':{'abnormal_flags':[0]},'control':{'move':False,'attack':False,'abilities':False,'block':False,'interrupt':True}});next(b for b in p['buffs'] if b['id']=='buff/peer/child')['on_remove']=[{'op':'apply_buff','target':'source','buff':'buff/peer/new_control'}]
 s=create(p);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.abilities.start('enemy',aid(p),automatic=True)
 assert s.checkpoint()==before;capture(s,'new_control_rollback')
def test_settlement_callback_health_change_requires_fresh_activation_condition():
 p=callback_fixture('nested');next(b for b in p['buffs'] if b['id']=='buff/peer/child')['on_remove']=[{'op':'modify_resource','target':'source','resource':'hp','delta':-3900}];next(a for a in p['abilities'] if a['id']==aid(p))['activation']['condition']='inputs.resources.hp.current >= 1000'
 s=create(p);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.abilities.start('enemy',aid(p),automatic=True)
 assert s.checkpoint()==before and s.ctx.resources.current('enemy','hp')==4000;capture(s,'fresh_condition_rollback')
def test_allowed_nonblocking_nested_cast_keeps_distinct_ids_owned_tasks_and_nextsequence():
 p=callback_fixture('nested');next(a for a in p['abilities'] if a['id']=='ability/peer/nested')['activation']['parameters']={'blocks_attacks':False}
 s=create(p);outer=s.ctx.abilities.start('enemy',aid(p),automatic=True);casts=s.ctx.get('enemy',('runtime','casts'));capture(s,'nonblocking_nested_kept')
 assert len(casts)==2 and outer=='cast/2/2' and casts['cast/2/1']['ability']=='ability/peer/nested' and casts['cast/2/2']['ability']==aid(p)
 assert s.ctx.get('enemy',('runtime','next_cast_id'))==3
 assert set(casts['cast/2/1']['tasks']).isdisjoint(casts['cast/2/2']['tasks'])
 pending={t['id'] for t in s.session.scheduler.pending};assert all(t in pending for c in casts.values() for t in c['tasks'])
