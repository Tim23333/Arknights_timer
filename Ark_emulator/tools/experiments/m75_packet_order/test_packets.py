"""M75 authored packet tests use preserved M73 actual failure JSON inputs."""
from pathlib import Path
from copy import deepcopy
import json,sys
import pytest

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m75_periodic_packets_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.kernel.session import ReactionBudgetExceeded
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def fixture(kind='retire_second',callback=True,two=False):
    path=ROOT/'validation/campaign/m73_environment_peer/callback_reproduction'/(kind+'-fixture.json')
    p=json.loads(path.read_text(encoding='utf8'))
    if not callback:
        p['abilities']=[];p['entities'][2]['components']['abilities']=[]
    if two:
        p['scenarioDraft']['map']['tiles'][1]=deepcopy(p['scenarioDraft']['map']['tiles'][0])
    return p

def make(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=73191)
def events(s,kind):return [thaw(e) for e in s.session.events if e['type']==kind]
def stores(s):return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),
    'random':s.session.random.snapshot(),'events':s.session._events.snapshot()}


@pytest.mark.parametrize('kind',['retire_second','move_second'])
def test_preserved_actual_m73_legal_callback_now_prevents_second_packet(kind):
    s=make(fixture(kind));s.session.advance(4)
    assert s.ctx.resources.current('first','hp')==1300
    assert s.ctx.resources.current('second','hp')==2000
    assert [e['payload']['target'] for e in events(s,'damage.accepted')]==[2]
    assert s.ctx.periodic_fields.current('field/1')['sequence']==1


def test_delay0_ability_cascade_completes_before_next_packet():
    p=fixture();p['abilities'][0]['events'][0]['effects']=[{'op':'trigger_ability','target':4,'ability':'ability/peer_cascade'}]
    p['entities'][2]['components']['abilities'].append('ability/peer_cascade')
    p['abilities'].append({'id':'ability/peer_cascade','kind':'ability','activation':{'mode':'manual'},
        'timeline':[{'at_seconds':0,'effect':{'op':'schedule','target':3,'delay_seconds':0,
            'effect':{'op':'move','target':3,'position':{'row':0,'col':1}}}}]})
    s=make(p);s.session.advance(4)
    assert s.ctx.resources.current('second','hp')==2000
    assert s.ctx.get('second',('spatial','position'))=={'row':0,'col':1}
    assert len(events(s,'ability.started'))>=1


def test_two_cells_one_global_fifo_after_each_packet_callback():
    p=fixture(two=True);s=make(p);s.session.advance(4)
    assert [(e['time'],e['payload']['field_uid']) for e in events(s,'field.triggered')]==[(3,'field/1'),(3,'field/2')]
    assert [e['payload']['target'] for e in events(s,'damage.accepted')]==[2,4]
    assert s.ctx.resources.current('second','hp')==2000
    state=s.ctx.periodic_fields.state()
    assert state['packet_queue']==[] and state['packet_dispatch'] is None
    assert all(field['packet_chain'] is None for field in state['fields'].values())


def test_legal_life_resource_callback_finishes_before_remaining_packet_or_draw():
    p=fixture();p['scenarioDraft'].update(resources={'life':{'initial':1,'capacity':1}},
        objectives={'type':'waves','life_resource':'life'})
    p['abilities'][0]['events'][0]['effects']=[{'op':'modify_resource','target':'battle','resource':'life','value':0}]
    s=make(p);s.session.advance(4)
    assert s.ctx.state()['finished'] and s.ctx.state()['result']=='defeat'
    assert s.ctx.resources.current('second','hp')==2000
    assert s.session.random.samples==()
    assert not s.ctx.periodic_fields.current('field/1')['active']
    assert not [t for t in s.session.scheduler.pending if t['kind'].startswith('domain.field.')]


def test_public_host_callback_removes_field_cancels_owned_continuation_without_draw(monkeypatch):
    s=make(fixture(callback=False));original=s.ctx.abilities.notify
    def callback(event,payload,cause=None):
        original(event,payload,cause)
        if event=='damage.accepted' and payload['target']==2:
            s.ctx.periodic_fields.remove(payload['origin']['field_uid'])
    monkeypatch.setattr(s.ctx.abilities,'notify',callback)
    s.session.advance(4)
    assert s.ctx.resources.current('second','hp')==2000
    assert s.session.random.samples==()
    assert not s.ctx.periodic_fields.current('field/1')['active']
    assert not [t for t in s.session.scheduler.pending if t['kind'].startswith('domain.field.')]


def test_failed_queued_callback_atomic_only_its_boundary_retains_completed_packet(monkeypatch,tmp_path):
    p=fixture();p['abilities'][0]['events'][0]['effects']=[{'op':'random','stream':'callback_probe',
        'on_success':[{'op':'modify_resource','target':4,'resource':'missing','delta':1}]}]
    s=make(p);original=s.ctx._react;captured=[]
    def recorder(session,payload):
        if payload['event']=='damage.accepted' and payload['payload']['target']==2:
            captured.append(stores(s))
        return original(session,payload)
    monkeypatch.setattr(s.ctx,'_react',recorder)
    with pytest.raises(ValueError):s.session.advance(4)
    assert len(captured)==1 and stores(s)==captured[0]
    assert s.ctx.resources.current('first','hp')==1300 and s.ctx.resources.current('second','hp')==2000
    assert s.session.random.samples==()
    chain=s.ctx.periodic_fields.current('field/1')['packet_chain']
    assert chain['cursor']==1 and s.ctx.periodic_fields.state()['packet_dispatch'] is not None
    assert s.session._failure['time']==3
    path=tmp_path/'failed-boundary.json';pin=write_ordered(path,s.checkpoint())
    restored=Engine.restore(s.program,load_bound(path,pin))
    assert restored.checkpoint()==s.checkpoint()
    for live in (s,restored):
        with pytest.raises(RuntimeError,match='execution has failed'):live.session.advance(1)


def test_duplicate_pulse_owned_dispatch_seq_prevents_early_or_double_trigger():
    s=make(fixture(callback=False));task=next(t for t in s.session.scheduler.pending if t['kind']=='domain.field.pulse')
    s.session.schedule(task['kind'],task['payload'],task['at'],phase=task['phase'],priority=-1)
    s.session.advance(4)
    assert len(events(s,'field.triggered'))==1 and len(events(s,'damage.accepted'))==2
    assert len(s.session.random.samples)==1


def test_duplicate_packet_payload_rejected_by_actual_dispatch_identity(monkeypatch):
    s=make(fixture(callback=False));original=s.ctx.abilities.notify;copies=[]
    def callback(event,payload,cause=None):
        original(event,payload,cause)
        if event=='field.triggered':
            owner=s.ctx.periodic_fields.state()['packet_dispatch']
            data={key:owner[key] for key in ('uid','generation','token','cursor')}
            copies.append(data)
            before=stores(s);s.ctx.periodic_fields.packet(s.session,data)
            assert stores(s)==before
            s.session.schedule('domain.field.packet',data,s.session.time,phase=owner['phase'],priority=-1)
    monkeypatch.setattr(s.ctx.abilities,'notify',callback)
    s.session.advance(4)
    assert copies and len(events(s,'damage.accepted'))==2 and len(s.session.random.samples)==1


def test_reaction_cycle_hits_existing_budget_without_running_next_packet():
    p=fixture();p['rulesets']=[{'id':'ruleset/peer_budget','kind':'ruleset','extends':'ruleset/ark_standard','reaction_budget':80}]
    p['scenarioDraft']['ruleset']='ruleset/peer_budget'
    p['abilities'][0]['events'][0]['effects']=[{'op':'emit','event':'peer.cycle'}]
    p['abilities'][0]['events'].append({'event':'peer.cycle','effects':[{'op':'emit','event':'peer.cycle'}]})
    s=make(p)
    with pytest.raises(ReactionBudgetExceeded):s.session.advance(4)
    assert s.ctx.resources.current('first','hp')==1300 and s.ctx.resources.current('second','hp')==2000
    assert s.ctx.periodic_fields.state()['packet_phase']<=s.ctx._base_effect_phase+2


def test_ordered_actual_checkpoint_and_replay_keep_owned_task_chain(tmp_path):
    s=make(fixture('move_second',two=True));s.session.advance(2)
    path=tmp_path/'boundary.json';pin=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,pin))
    s.session.advance(20);r.session.advance(20)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
    assert s.checkpoint()==r.checkpoint()


def test_external_same_tick_higher_phase_task_has_deterministic_order():
    snapshots=[]
    for _ in range(2):
        s=make(fixture(callback=False))
        s.session.schedule('domain.effect',{'source':'observer','targets':[3],
            'effect':{'op':'emit','event':'peer.external_marker'}},3,phase=s.ctx._base_effect_phase+2)
        s.session.advance(4)
        snapshots.append(s.snapshot())
    assert snapshots[0]==snapshots[1]
    relevant=[e['type'] for e in snapshots[0]['events'] if e['type'] in ('damage.accepted','peer.external_marker')]
    assert relevant==['damage.accepted','peer.external_marker','damage.accepted']


@pytest.mark.parametrize('action',['remove','finish'])
def test_synchronous_field_triggered_toggle_callback_cannot_recreate_removed_chain(monkeypatch,action):
    s=make(fixture(callback=False,two=True));original=s.ctx.buffs.toggles.pulse
    def callback(event,payload):
        original(event,payload)
        if event=='field.triggered' and payload['field_uid']=='field/1':
            if action=='remove':s.ctx.periodic_fields.remove('field/1')
            else:s.ctx.state_update(finished=True)
    monkeypatch.setattr(s.ctx.buffs.toggles,'pulse',callback)
    s.session.advance(4)
    field=s.ctx.periodic_fields.current('field/1')
    assert field['active'] is False and field['packet_chain'] is None and field['task'] is None and field['due'] is None
    assert field['sequence']==1
    assert s.ctx.resources.current('first','hp')==2000 and s.ctx.resources.current('second','hp')==2000
    assert 'field/1' not in s.ctx.periodic_fields.state().get('packet_queue',[])
    if action=='finish':
        assert s.session.random.samples==()
        assert not [t for t in s.session.scheduler.pending if t['kind'].startswith('domain.field.')]


def test_scheduler_owned_pulse_sync_callback_error_rolls_back_actual_boundary(monkeypatch):
    s=make(fixture(callback=False));original=s.ctx.buffs.toggles.pulse;before=[]
    pulse=s.ctx.periodic_fields.pulse
    # Capture after the real scheduler pops its owned task, before pulse atomic.
    def recorded(session,payload):
        before.append(stores(s));return pulse(session,payload)
    s.session._handlers['domain.field.pulse']=recorded
    def callback(event,payload):
        original(event,payload)
        if event=='field.triggered':
            s.session.random.sample('pulse_sync_failure')
            s.ctx.state_update(kills=17)
            raise ValueError('actual synchronous pulse callback failure')
    monkeypatch.setattr(s.ctx.buffs.toggles,'pulse',callback)
    with pytest.raises(ValueError):s.session.advance(4)
    assert len(before)==1 and stores(s)==before[0]
    assert not events(s,'field.triggered') and s.ctx.periodic_fields.current('field/1')['sequence']==0
    assert s.session._failure['time']==3


def test_duplicate_schedule_rejected_before_rng_or_allocator_consumption():
    s=make(fixture(callback=False));before=stores(s)
    with pytest.raises(ValueError,match='already owns'):s.ctx.periodic_fields.schedule('field/1',1)
    assert stores(s)==before


def test_no_profile_high_numeric_phase_retains_old_backward_reaction_rejection():
    p=fixture(callback=False);mp=p['scenarioDraft']['map'];mp.pop('tile_mechanics')
    for tile in mp['tiles']:
        tile.pop('tileKey',None);tile.pop('blackboard',None)
    s=make(p)
    assert s.ctx.periodic_fields is None and s.ctx.effect_phase==s.ctx._base_effect_phase
    s.session.schedule('domain.effect',{'source':'observer','targets':[3],
        'effect':{'op':'emit','event':'peer.no_profile_high_phase'}},0,phase=99)
    with pytest.raises(ValueError,match='cannot precede'):s.session.advance(1)
    assert not events(s,'peer.no_profile_high_phase')
