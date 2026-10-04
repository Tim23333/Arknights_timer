"""Exact native44 stage compilation and actual eightACK public prefix."""
import json
from pathlib import Path
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.chapter08_joint_v4.build_jt83_draft_v2 import OUT, build, providers
from tools.control_driver.public_ack_v2 import PublicAckDriver
from tools.campaign_ordered_checkpoint import write_ordered, load_bound


def test_exact_native_draft_rebuild_birth44_and_original_resources():
    p = json.loads(OUT.read_bytes())
    assert p == build()
    scene = p['scenarioDraft']
    assert sum(action.get('count', 1) for wave in scene['timeline']['waves'] for fragment in wave['fragments']
               for action in fragment['actions'] if action['kind'] == 'spawn') == 44
    assert scene['resources']['dp']['initial'] == 15 and scene['resources']['life']['initial'] == 3
    assert scene['parameters']['deploy_capacity'] == 9 and len(scene['roster']) == 12
    assert len(scene['initialEntities']) == 10 and scene['branches']['bsnake_flame']['loop'] is True
    assert scene['map']['rows'] == 9 and scene['map']['cols'] == 15
    assert len(scene['timeline']['waves']) == 4


def test_actual_source_prefix_external8dialogues_and_midack_CP10_head(tmp_path):
    reg = providers()
    p = json.loads(OUT.read_bytes())
    program = Compiler(providers=reg).compile(p)
    s = Engine.create(program, providers=reg, seed=83831)
    driver = PublicAckDriver(s)
    driver.advance_to(10)
    path = tmp_path / 'jt83_story10.cp.json'
    pin = write_ordered(path, s.checkpoint())
    saved_driver = driver.checkpoint()
    r = Engine.restore(program, load_bound(path, pin), providers=reg)
    continuation = PublicAckDriver(r, saved_driver)
    driver.advance_to(120)
    continuation.advance_to(120)
    h = replay(program, s.export_replay(), providers=reg)
    assert s.checkpoint() == r.checkpoint() == h.checkpoint()
    assert list(s.session.events) == list(r.session.events) == list(h.session.events)
    assert driver.checkpoint() == continuation.checkpoint()
    assert len(driver.submitted) == 8
    assert len([event for event in s.session.events if event['type'] == 'source.story.popup.observed']) == 8
    assert all(command['type'] == 'command.accepted' for command in s.session.events
               if command['type'] in ('command.accepted', 'command.rejected'))
    assert not s.ctx.state()['finished']
