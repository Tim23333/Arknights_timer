"""Public eightphase wrap with sourcepositions; primitive actors declared separately."""
import json
from copy import deepcopy
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.chapter08_joint_v4.build_flame_loop_profile_v1 import OUT, build
from tools.campaign_ordered_checkpoint import write_ordered, load_bound


def test_exact_source_loop_true_and_explicit_horizon_not_native_stock():
    profile = json.loads(OUT.read_bytes())
    assert profile == build()
    assert profile['runtime_branch']['bsnake_flame']['loop'] is True
    assert profile['run_horizon_policy']['budgets_are_native_stock'] is False
    assert profile['run_horizon_policy']['conservative_max_requests'] == 21
    assert sum(item['reactivation']['max_activations'] for item in profile['initial_entities']) == 105


def test_eighth_branch_request_wraps_nativephase0_with_fresh_actors_CP_head(tmp_path):
    profile = json.loads(OUT.read_bytes())
    initial = deepcopy(profile['initial_entities'])
    for item in initial:
        item['definition'] = 'unit/loop/primitive'
    p = {'schemaVersion': 2, 'manifest': {'id': 'package/loop/primitive', 'requires': ['preset/ark_standard']},
         'entities': [
             {'id': 'unit/loop/primitive', 'kind': 'entity', 'tags': ['device'], 'components': {
                 'attributes': {'base': {'max_hp': 6000, 'atk': 0}},
                 'resources': {'hp': {'initial': 6000, 'capacity': 6000, 'role': 'health'}},
                 'spatial': {}, 'lifecycle': {'policy': 'policy/ark_lifecycle'}}},
             {'id': 'unit/loop/director', 'kind': 'entity', 'components': {
                 'spatial': {}, 'abilities': ['ability/loop/advance', 'ability/loop/retire']}}],
         'selectors': [{'id': 'selector/loop/device', 'kind': 'selector', 'region': {'type': 'all'},
                        'filters': [{'tag': 'device'}, {'state': 'alive'}]}],
         'abilities': [
             {'id': 'ability/loop/advance', 'kind': 'ability', 'activation': {'mode': 'manual', 'on_start': [
                 {'op': 'advance_branch', 'parameters': {'branch': 'bsnake_flame'}}]}, 'timeline': []},
             {'id': 'ability/loop/retire', 'kind': 'ability', 'selector': 'selector/loop/device',
              'activation': {'mode': 'manual', 'on_start': [{'op': 'retire', 'parameters': {'reason': 'withdrawn'}}]}, 'timeline': []}],
         'scenarioDraft': {'id': 'scene/loop/primitive', 'ruleset': 'ruleset/ark_standard',
                           'map': {'rows': 9, 'cols': 15}, 'branches': profile['runtime_branch'],
                           'initialEntities': initial + [{'definition': 'unit/loop/director', 'instanceAlias': 'director',
                                                          'position': {'row': 0, 'col': 0}}]}}
    s = Engine.create(Compiler().compile(p))
    for index in range(8):
        s.submit({'action': 'skill', 'source': 'director', 'ability': 'ability/loop/advance'}, at=4 * index)
        s.submit({'action': 'skill', 'source': 'director', 'ability': 'ability/loop/retire'}, at=4 * index + 2)
    s.advance(27)
    path = tmp_path / 'loop27.cp.json'
    pin = write_ordered(path, s.checkpoint())
    r = Engine.restore(s.program, load_bound(path, pin))
    s.advance(6)
    r.advance(6)
    h = replay(s.program, s.export_replay())
    assert s.checkpoint() == r.checkpoint() == h.checkpoint()
    assert list(s.session.events) == list(r.session.events) == list(h.session.events)
    activated = [event for event in s.session.events if event['type'] == 'entity.activated']
    assert len(activated) == 40
    last_keys = [event['payload']['registration_key'] for event in activated if event['time'] == 28]
    assert last_keys == profile['native_phase_keys'][0]
    assert s.ctx.branches.state()['bsnake_flame']['cursor'] == 8
    assert not [event for event in s.session.events if event['type'] == 'command.rejected']
