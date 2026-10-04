from pathlib import Path
import json
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];INPUTS=[]


def fixture():
    p=json.loads((ROOT/'validation/campaign/m73_environment_peer/callback_reproduction/retire_second-fixture.json').read_bytes())
    p['abilities'][0]['events'][0]['effects']=[{'op':'emit','event':'peer.boundary_marker'}];return p


def make(p):INPUTS.append(p);return Engine.create(Compiler().compile(p),seed=75991)
def events(s,kind):return [e for e in s.session.events if e['type']==kind]


def test_field_triggered_public_reaction_can_remove_second_before_first_damage():
    p=fixture();p['abilities'][0]['events']=[{'event':'field.triggered','effects':[{'op':'retire','target':3,'parameters':{'reason':'withdrawn'}}]}]
    s=make(p);s.advance(5)
    assert [(e['payload']['target'],e['payload']['amount']) for e in events(s,'damage.accepted')]==[(2,700)]
    assert s.ctx.resources.current('second','hp')==2000


@pytest.mark.parametrize('flag',[9,17])
def test_damage_reaction_apply_half_open_flag_excludes_second_then_reenters(flag,tmp_path):
    p=fixture();p['buffs']=[{'id':'buff/hidden','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_flags':[flag]}}]
    p['abilities'][0]['events'][0]['effects']=[{'op':'apply_buff','target':3,'buff':'buff/hidden'}]
    s=make(p);s.advance(5);assert s.ctx.resources.current('second','hp')==2000
    path=tmp_path/'cp.json';pin=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,pin));s.advance(33);r.advance(33)
    # Every next trigger still has a fresh callback which hides the second.
    assert s.ctx.resources.current('second','hp')==2000
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_in_callback_checkpoint_rejected_and_valid_idle_boundary_saved_reload(monkeypatch,tmp_path):
    p=fixture();s=make(p);original=s.ctx._react;rejected=[]
    def capture(session,payload):
        original(session,payload)
        if payload['event']=='damage.accepted' and payload['payload']['target']==2 and not rejected:
            with pytest.raises(RuntimeError,match='between advance'):s.checkpoint()
            rejected.append(True)
    monkeypatch.setattr(s.ctx,'_react',capture);s.advance(5)
    assert rejected
    path=tmp_path/'idle.json';pin=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,pin))
    s.advance(15);r.advance(15)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
    assert len(events(r,'damage.accepted'))==4
    assert [e['time'] for e in events(r,'field.triggered')]==[3,18]


def test_unrelated_field_error_keeps_only_already_committed_packet_boundary():
    p=fixture();p['abilities'][0]['events'][0]['effects']=[{'op':'random','stream':'peer','on_success':[{'op':'modify_resource','target':3,'resource':'does_not_exist','delta':2}]}]
    s=make(p)
    with pytest.raises(ValueError):s.advance(5)
    assert s.ctx.resources.current('first','hp')==1300 and s.ctx.resources.current('second','hp')==2000
    assert s.session.random.samples==() and s.ctx.periodic_fields.state()['packet_dispatch'] is not None
    with pytest.raises(RuntimeError):s.advance(1)
