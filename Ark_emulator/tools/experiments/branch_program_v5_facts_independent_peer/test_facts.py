from copy import deepcopy
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.experiments.branch_program_v3_independent_peer_v2.test_peer import fixture
INPUTS=[];CAPTURES=[]
def create(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=5108)
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot()})
def test_facts_are_pure_and_mutating_returned_nested_records_cannot_mutate_world():
 s=create(fixture());before=s.checkpoint();facts=s.ctx.branches.facts();assert facts['peer']['available'] is True
 facts['peer']['cursor']=999;facts['peer']['tasks'].append('fake');facts['peer']['action_tasks']['fake']={'consumed':True}
 assert s.checkpoint()==before and s.ctx.branches.facts()['peer']['cursor']==0
 s.ctx.branches.advance('peer',2);before=s.checkpoint();facts=s.ctx.branches.facts();assert facts['peer']['available'] is False
 facts['peer']['action_tasks']['0']['consumed']=True;facts['peer']['tasks'].clear();assert s.checkpoint()==before
 capture(s,'facts_readonly')
def test_auto_condition_consumes_available_and_does_not_emit_exhausted_empty_cast():
 p=fixture();advance=next(a for a in p['definitions'] if a['id']=='ability/peer/advance');advance['activation']['condition']='inputs.branches.peer.available';advance['activation']['parameters']={'auto_when_ready':True,'auto_only':True}
 s=create(p);s.advance(10);capture(s,'available_condition_exhaustion')
 starts=[e for e in s.session.events if e['type']=='ability.started'];assert [e['time'] for e in starts]==[0,5]
 assert s.ctx.branches.facts()['peer']['cursor']==2 and s.ctx.branches.facts()['peer']['available'] is False
 assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
