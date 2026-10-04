from pathlib import Path
import copy
import pytest
from ark_sim.kernel.session import Session
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def build_session():
    s=Session(seed=84101)
    def boundary(session):session.emit('boundary.observed',{'current':session.time})
    s.add_boundary_system(boundary);return s


def test_every_step_boundary_order_segmented_exact_and_zero_advance_no_callback():
    a=build_session();b=build_session();a.advance(3)
    for _ in range(3):b.advance(1)
    assert a.checkpoint()==b.checkpoint()
    assert [e['time'] for e in a.events]==[1,2,3]
    before=a.checkpoint();a.advance(0);assert a.checkpoint()==before


def test_boundary_does_not_dispatch_next_frame_pending_command():
    s=build_session();s.register_handler('probe',lambda session,payload:session.emit('task.ran',{}));s.schedule('probe',{},3,phase=0);s.advance(3)
    assert not [e for e in s.events if e['type']=='task.ran']
    assert any(task['at']==3 for task in s.scheduler.pending)
    s.advance(1);assert len([e for e in s.events if e['type']=='task.ran'])==1


@pytest.mark.parametrize('value',[False,1,None,'true'])
def test_checkpoint_signature_rejects_wrong_boundary_registration(value):
    s=build_session();s.advance(1);cp=s.checkpoint();cp['systems'][0]['boundary']=value;before=s.checkpoint()
    with pytest.raises(ValueError):s.restore(cp)
    assert s.checkpoint()==before


def test_failure_rolls_only_observer_writes_and_blocks_failed_session():
    s=Session(seed=84101);s.world.create('unit/raw',{},alias='raw');s.register_handler('probe',lambda session,payload:None)
    boundary_states=[]
    def bad(session):
        boundary_states.append((session.world.snapshot(),session.scheduler.snapshot(),session.random.snapshot(),session._events.snapshot()))
        session.random.sample('peer');session.emit('probe.transient',{});session.schedule('probe',{},5)
        raise ValueError('bad observer')
    s.add_boundary_system(bad)
    with pytest.raises(ValueError):s.advance(1)
    actual=(s.world.snapshot(),s.scheduler.snapshot(),s.random.snapshot(),s._events.snapshot())
    assert actual==boundary_states[0] and s.time==1 and s._failure['time']==1
    with pytest.raises(RuntimeError):s.advance(1)


def test_public_source_immune_sleep_commands_disk_checkpoint_and_replay(tmp_path):
    from tools.experiments.m84_boundary_settle.test_live import fixture
    p=fixture();unit=p['entities'][0];unit['components']['abilities']=['ability/immune','ability/sleep']
    p['abilities']=[{'id':'ability/'+name,'kind':'ability','activation':{'mode':'manual','parameters':{'blocks_attacks':False},
        'on_start':[{'op':'apply_buff','target':'source','buff':'buff/'+buff}]},'timeline':[]} for name,buff in [('immune','immune_combo'),('sleep','sleep')]]
    s=Engine.create(Compiler().compile(p),seed=84101);s.submit({'action':'skill','source':'t','ability':'ability/immune'},at=0);s.submit({'action':'skill','source':'t','ability':'ability/sleep'},at=1)
    s.session.advance(3);assert not s.ctx.buffs.controls('t')['attack'];path=tmp_path/'cp.json';pin=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,pin));s.session.advance(3);r.session.advance(3)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
