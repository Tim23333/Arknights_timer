"""Fresh native JT8-2 input and public-plan recovery on foundation82db."""
import json
from copy import deepcopy

import pytest
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter08_joint_v4.build_jt82_foundation_v1 import OUT, ROOT, build, providers, sha
from tools.chapter08_joint_v4.build_jt82_foundation_public_v1 import OUT as OVERLAY, COMMANDS
from tools.chapter08_stage_join.inactive_branches_v1 import compose


def test_frozen_source_scene_and_definitions_equal_v6():
    assert sha(OUT) == 'a7b061ea9bcb49f2bd6094a675d4840c224209a0ee645c9bbe32d32ad193146c'
    package = json.loads(OUT.read_bytes())
    assert package == build()
    scene = package['scenarioDraft']
    assert sum(action.get('count', 1) for wave in scene['timeline']['waves']
               for fragment in wave['fragments'] for action in fragment['actions']
               if action['kind'] == 'spawn') == 32
    assert scene['resources']['life']['initial'] == 3
    assert scene['resources']['dp']['initial'] == 10
    assert scene['parameters']['deploy_capacity'] == 9
    assert len(scene['roster']) == 12
    assert len(scene['map']['tile_mechanics']) == 4


def test_public_plan_source_fields_and_durable160_to330_head(tmp_path):
    from tools.campaign_runthrough_progress_v5 import validate_native_overlay
    parent = json.loads(OUT.read_bytes())
    package = json.loads(OVERLAY.read_bytes())
    validate_native_overlay(package, parent, COMMANDS)
    registry = providers()
    program = Compiler(providers=registry).compile(package)
    sim = Engine.create(program, providers=registry, seed=82712)
    for command in json.loads(COMMANDS.read_bytes()):
        if command['at'] < 330:
            sim.submit({key: value for key, value in command.items() if key != 'at'}, at=command['at'])
    sim.advance(160)
    path = tmp_path / 'public160.cp.json'
    pin = write_ordered(path, sim.checkpoint())
    restored = Engine.restore(program, load_bound(path, pin), providers=registry)
    sim.advance(170)
    restored.advance(170)
    head = replay(program, sim.export_replay(), providers=registry)
    assert sim.checkpoint() == restored.checkpoint() == head.checkpoint()
    assert list(sim.session.events) == list(restored.session.events) == list(head.session.events)
    assert len(sim.ctx.periodic_fields.state()['fields']) == 6
    results = [event for event in sim.session.events if event['type'] in ('command.accepted', 'command.rejected')]
    assert len(results) == 2 and all(event['type'] == 'command.accepted' for event in results)
    assert sim.ctx.resources.current('system/battle', 'life') == 99999
    assert not sim.ctx.state()['finished']


@pytest.mark.parametrize('mutation', [
    lambda native: native['waves'][0]['fragments'][0]['actions'][0].update(key='bsnake_flame'),
    lambda native: native['hardPredefines']['tokenInsts'].update(unexpected='token'),
])
def test_declared_dormant_branch_rejects_new_native_triggers(mutation):
    source = ROOT / 'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json'
    native = deepcopy(json.loads(source.read_bytes())['stages']['level_main_08-16']['native_document'])
    mutation(native)
    with pytest.raises(ValueError):
        compose(native, 'level_main_08-16', {}, {}, inactive_profile={
            'native_branches': native['branches'], 'reason': 'Explicit dormant validation fixture',
            'source_consumer_documents': [{}]})
