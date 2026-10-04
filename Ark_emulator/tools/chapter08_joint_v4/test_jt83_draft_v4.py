"""Newest exact stage fields and real eight external ACKs with recovery."""
import json

from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.chapter08_joint_v4.build_jt83_draft_v4 import OUT, build, providers
from tools.chapter08_joint_v4.build_jt83_public_v3 import OUT as OVERLAY, COMMANDS
from tools.control_driver.public_ack_v2 import PublicAckDriver
from tools.campaign_ordered_checkpoint import write_ordered, load_bound


def test_native_stage_rebuild_and_life_only_overlay():
    from tools.campaign_runthrough_progress_v5 import validate_native_overlay
    package = json.loads(OUT.read_bytes())
    assert package == build()
    scene = package['scenarioDraft']
    assert sum(action.get('count', 1) for wave in scene['timeline']['waves']
               for fragment in wave['fragments'] for action in fragment['actions']
               if action['kind'] == 'spawn') == 44
    assert scene['resources']['dp']['initial'] == 15 and scene['resources']['life']['initial'] == 3
    assert scene['parameters']['deploy_capacity'] == 9 and len(scene['roster']) == 12
    assert len(scene['initialEntities']) == 10 and scene['branches']['bsnake_flame']['loop'] is True
    assert scene['map']['rows'] == 9 and scene['map']['cols'] == 15
    assert len(scene['timeline']['waves']) == 4
    validate_native_overlay(json.loads(OVERLAY.read_bytes()), package, COMMANDS)


def test_real_eight_ACKs_CP10_driver_and_head120(tmp_path):
    registry = providers()
    program = Compiler(providers=registry).compile(json.loads(OUT.read_bytes()))
    sim = Engine.create(program, providers=registry, seed=83841)
    driver = PublicAckDriver(sim)
    driver.advance_to(10)
    path = tmp_path / 'story10.cp.json'
    pin = write_ordered(path, sim.checkpoint())
    restored = Engine.restore(program, load_bound(path, pin), providers=registry)
    resumed = PublicAckDriver(restored, driver.checkpoint())
    driver.advance_to(120)
    resumed.advance_to(120)
    head = replay(program, sim.export_replay(), providers=registry)
    assert sim.checkpoint() == restored.checkpoint() == head.checkpoint()
    assert list(sim.session.events) == list(restored.session.events) == list(head.session.events)
    assert driver.checkpoint() == resumed.checkpoint()
    assert len(driver.submitted) == 8
    assert len([event for event in sim.session.events if event['type'] == 'source.story.popup.observed']) == 8
    assert all(event['type'] == 'command.accepted' for event in sim.session.events
               if event['type'] in ('command.accepted', 'command.rejected'))
    assert not sim.ctx.state()['finished']
