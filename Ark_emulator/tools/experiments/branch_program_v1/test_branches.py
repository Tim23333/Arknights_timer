from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay


def fixture():
    token={'id':'unit/trap','kind':'entity','components':{'attributes':{'base':{'max_hp':100}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'}},'tags':['trap']}
    advance={'id':'ability/advance','kind':'ability','activation':{'mode':'manual'},
        'timeline':[{'at':2,'effect':{'op':'advance_branch','parameters':{'branch':'test'}}}]}
    source={'id':'unit/source','kind':'entity','components':{'abilities':['ability/advance']}}
    branch={'loop':False,'phases':[{'pre_delay_seconds':0,'actions':[{'delay_seconds':.1,'effects':[
        {'op':'activate_predefined','target':'battle','parameters':{'key':'trapA'}}]}]},
        {'pre_delay_seconds':0,'actions':[{'delay_seconds':0,'effects':[
        {'op':'activate_predefined','target':'battle','parameters':{'key':'trapB'}}]}]}]}
    return {'definitions':[token,advance,source],'scenarioDraft':{'id':'scene/branch','ruleset':'ruleset/ark_standard',
        'objectives':{},'branches':{'test':branch},'initialEntities':[{'definition':'unit/source','instanceAlias':'source'},
            {'definition':'unit/trap','instanceAlias':'trapA','active':False,'registration_key':'trapA'},
            {'definition':'unit/trap','instanceAlias':'trapB','active':False,'registration_key':'trapB'}]}}


def create(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=540)


def test_real_phase_progress_activation_and_cp_replay():
    s=create();s.submit({'action':'skill','source':'source','ability':'ability/advance'},at=0)
    s.advance(4);assert s.ctx.branches.state()['test']['phase']=='running'
    assert not s.ctx.active('trapA');r=Engine.restore(s.program,s.checkpoint())
    s.advance(3);r.advance(3);assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
    assert s.ctx.active('trapA') and not s.ctx.active('trapB') and s.ctx.branches.state()['test']['cursor']==1
    s.submit({'action':'skill','source':'source','ability':'ability/advance'},at=7);s.advance(4)
    assert s.ctx.active('trapB') and s.ctx.branches.state()['test']['cursor']==2
    assert not s.ctx.branches.available('test')


def test_busy_or_exhausted_branch_rejects_without_writes():
    s=create();s.ctx.branches.advance('test',s.session.world.resolve('source'));before=s.checkpoint()
    with pytest.raises(ValueError,match='busy'):s.ctx.branches.advance('test',2)
    assert s.checkpoint()==before
    s.advance(4);s.ctx.branches.advance('test',2);s.advance(1);before=s.checkpoint()
    with pytest.raises(ValueError,match='complete'):s.ctx.branches.advance('test',2)
    assert s.checkpoint()==before


def test_action_failure_atomic_retains_dormant_and_running_phase():
    p=fixture();p['scenarioDraft']['branches']['test']['phases'][0]['actions'][0]['effects'].append(
        {'op':'activate_predefined','target':'battle','parameters':{'key':'trapA'}})
    s=create(p);s.ctx.branches.advance('test',2)
    with pytest.raises(ValueError,match='dormant'):s.advance(4)
    assert not s.ctx.active('trapA') and s.ctx.branches.state()['test']['phase']=='running'
    assert not any(e['type']=='entity.activated' for e in s.session.events)


def test_terminal_cancel_does_not_claim_unexecuted_phase_complete():
    s=create();s.ctx.branches.advance('test',2);s.ctx.state_update(finished=True,result='defeat')
    s.ctx.branches.cancel_terminal();row=s.ctx.branches.state()['test']
    assert row['phase']=='stopped' and row['remaining']==1 and row['cursor']==0
    assert not any(t['kind']=='domain.branch.action' for t in s.session.scheduler.pending)
    s.advance(5);assert not s.ctx.active('trapA')


def test_loop_phase_is_explicit_and_unknown_program_compile_rejected():
    p=fixture();p['definitions'][1]['timeline'][0]['effect']['parameters']['branch']='missing'
    with pytest.raises(ValueError,match='unknown'):Compiler().compile(p)


@pytest.mark.parametrize('field,value',[('generation',True),('phase_index',-1),('action_index',True),('action_index',99)])
def test_invalid_or_undispatched_handler_cannot_activate_or_mutate_phase(field,value):
    s=create();s.ctx.branches.advance('test',2);payload={'branch':'test','generation':1,'phase_index':0,'action_index':0};payload[field]=value
    before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.branches.action(s.session,payload)
    assert s.checkpoint()==before and not s.ctx.active('trapA')


def test_real_delayed_task_cannot_be_invoked_early_from_caller():
    s=create();s.ctx.branches.advance('test',2);before=s.checkpoint()
    with pytest.raises(ValueError,match='actual owned dispatch'):
        s.ctx.branches.action(s.session,{'branch':'test','generation':1,'phase_index':0,'action_index':0})
    assert s.checkpoint()==before


def test_branch_available_activation_condition_rejects_before_cast_after_exhaustion():
    p=fixture();p['definitions'][1]['activation']['condition']="inputs.branches['test'].available"
    s=create(p)
    before=s.checkpoint();assert s.ctx.branches.facts()['test']['available'] is True;assert s.checkpoint()==before
    s.submit({'action':'skill','source':'source','ability':'ability/advance'},at=0)
    s.submit({'action':'skill','source':'source','ability':'ability/advance'},at=7)
    s.submit({'action':'skill','source':'source','ability':'ability/advance'},at=12);s.advance(15)
    assert s.ctx.branches.facts()['test']['available'] is False
    assert any(e['type']=='command.rejected' and e['time']==12 for e in s.session.events)
    assert len([e for e in s.session.events if e['type']=='ability.started'])==2
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
