"""Original eightpopup publicacks and exact Opera AV-node times persist in CP."""
import json
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.chapter08_joint_v4.build_stage_controls_v1 import OUT, build
from tools.campaign_ordered_checkpoint import write_ordered, load_bound


def scene(control):
    p = json.loads(OUT.read_bytes())
    p['scenarioDraft'] = {'id': 'scene/stage_controls/source', 'ruleset': 'ruleset/ark_standard',
                          'map': {'rows': 1, 'cols': 1}, 'objectives': {},
                          'timeline': {'policy': 'managed_clear', 'negative_timeout_policy': 'wait_for_clear',
                                       'waves': [{'max_wait_seconds': -1, 'fragments': [{'actions': [
                                           {'kind': 'control', 'definition': control}]}]}]}}
    return p


def test_exact_source_controls_rebuild():
    assert json.loads(OUT.read_bytes()) == build()


def test_eight_real_external_ack_steps_and_blocker3tenths_CP_head(tmp_path):
    s = Engine.create(Compiler().compile(scene('control/ch8/source/story/main_08-17')))
    s.advance(1)
    initial = [event for event in s.session.events if event['type'] == 'control.awaiting_ack']
    assert len(initial) == 1
    control = initial[0]['payload']['control']
    for index in range(8):
        s.submit({'action': 'control_ack', 'control': control, 'step': 2 * index + 1}, at=index + 1)
    s.advance(4)
    path = tmp_path / 'story5.cp.json'
    pin = write_ordered(path, s.checkpoint())
    r = Engine.restore(s.program, load_bound(path, pin))
    s.advance(15)
    r.advance(15)
    h = replay(s.program, s.export_replay())
    assert s.checkpoint() == r.checkpoint() == h.checkpoint()
    assert list(s.session.events) == list(r.session.events) == list(h.session.events)
    assert len([event for event in s.session.events if event['type'] == 'source.story.popup.observed']) == 8
    assert len([event for event in s.session.events if event['type'] == 'command.accepted']) == 8
    assert not [event for event in s.session.events if event['type'] == 'command.rejected']
    assert [event['time'] for event in s.session.events if event['type'] == 'control.completed'] == [17]


def test_Opera_color0_audio6_camera9_and_completion90_no_battle_rng_CP_head(tmp_path):
    s = Engine.create(Compiler().compile(scene('control/ch8/source/opera/blast_effect_x')), seed=81827)
    random_before = s.session.random.snapshot()
    s.advance(7)
    path = tmp_path / 'opera7.cp.json'
    pin = write_ordered(path, s.checkpoint())
    r = Engine.restore(s.program, load_bound(path, pin))
    s.advance(85)
    r.advance(85)
    h = replay(s.program, s.export_replay())
    assert s.checkpoint() == r.checkpoint() == h.checkpoint()
    assert list(s.session.events) == list(r.session.events) == list(h.session.events)
    nodes = [(event['time'], event['payload']['node_class'].split('.')[-1]) for event in s.session.events
             if event['type'] == 'source.opera.node.observed']
    assert nodes == [(0, 'ColorGrading'), (6, 'GlobalAudio'), (9, 'CameraShake')]
    assert [event['time'] for event in s.session.events if event['type'] == 'source.opera.completed'] == [90]
    assert s.session.random.snapshot() == random_before
    assert not [event for event in s.session.events if event['type'] in ('damage.accepted', 'projectile.launched', 'entity.created')]
