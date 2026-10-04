"""Actual eightbranch requests exercise modulo7 hint cursor and once countdown."""
import json
from pathlib import Path
from copy import deepcopy
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.chapter08_joint_v4.build_summon_hint_v3 import OUT, build
from tools.chapter08_joint_v4.build_summon_hint_v2 import providers
from tools.chapter08_joint_v4.build_summon_hint_v1 import HINT, COUNTDOWN, SUMMON, TIMER, LOOP
from tools.campaign_ordered_checkpoint import write_ordered, load_bound


def test_source_rebuild_preserves_loop_and_hint_keys():
    assert json.loads(OUT.read_bytes()) == build()


def test_eight_actual_internal_requests_and27s_hint_countdown_CP_head(tmp_path):
    p = json.loads(OUT.read_bytes())
    loop = json.loads(LOOP.read_bytes())
    summon = next(row for row in p['abilities'] if row['id'] == SUMMON)
    summon['cooldown_seconds'] = 0
    summon['initial_cooldown_seconds'] = 0
    summon['activation']['parameters'].pop('auto_when_ready')
    # Explicit controlled schedule tests phase/visual callbacks; native50/75
    # readiness is a separate test and source module fields remain unchanged.
    p['abilities'].append({'id': 'ability/hint/trigger', 'kind': 'ability',
                           'activation': {'mode': 'manual', 'on_start': [
                               {'op': 'trigger_ability', 'target': 12, 'ability': SUMMON}]}, 'timeline': []})
    p['entities'] = [{'id': 'unit/hint/source', 'kind': 'entity', 'components': {
        'spatial': {}, 'resources': deepcopy(p['manifest']['metadata']['resources_required']),
        'abilities': [HINT, COUNTDOWN, SUMMON]}},
        {'id': 'unit/hint/controller', 'kind': 'entity', 'components': {
            'spatial': {}, 'abilities': ['ability/hint/trigger']}}]
    p['entities'][0]['components']['resources']['mode']['initial'] = 1
    # Each primitive device explicitly retires after1s to make reuse observable.
    # No native device SP/attack claim is made by this callback test.
    unit = loop['initial_entities'][0]['definition']
    p['entities'].append({'id': unit, 'kind': 'entity', 'components': {'spatial': {},
        'attributes': {'base': {'max_hp': 6000}}, 'resources': {'hp': {'initial': 6000, 'capacity': 6000, 'role': 'health'}},
        'lifecycle': {'policy': 'policy/ark_lifecycle'}, 'abilities': ['ability/hint/device_retire']}})
    p['abilities'].append({'id': 'ability/hint/device_retire', 'kind': 'ability',
                          'activation': {'mode': 'on_deploy'},
                          'timeline': [{'at_seconds': 1, 'effect': {'op': 'retire', 'target': 'source', 'parameters': {'reason': 'withdrawn'}}}]})
    p['scenarioDraft'] = {'id': 'scene/hint/callbacks', 'ruleset': 'ruleset/ark_standard',
                          'map': {'rows': 9, 'cols': 15}, 'branches': loop['runtime_branch'],
                          'initialEntities': deepcopy(loop['initial_entities']) + [
                              {'definition': 'unit/hint/source', 'instanceAlias': 'boss', 'position': {'row': 0, 'col': 0}},
                              {'definition': 'unit/hint/controller', 'instanceAlias': 'controller', 'position': {'row': 0, 'col': 1}}]}
    reg = providers()
    s = Engine.create(Compiler(providers=reg).compile(p), providers=reg)
    for index in range(8):
        s.submit({'action': 'skill', 'source': 'controller', 'ability': 'ability/hint/trigger'}, at=index * 100)
    s.advance(650)
    f = tmp_path / 'hint650.cp.json'
    pin = write_ordered(f, s.checkpoint())
    r = Engine.restore(s.program, load_bound(f, pin), providers=reg)
    s.advance(900)
    r.advance(900)
    h = replay(s.program, s.export_replay(), providers=reg)
    assert s.checkpoint() == r.checkpoint() == h.checkpoint()
    assert list(s.session.events) == list(r.session.events) == list(h.session.events)
    shown = [event for event in s.session.events if event['type'] == 'source.bsnake.hint.show']
    expected_indices = [1, 2, 3, 4, 5, 6, 0, 1, 1]
    assert [event['payload']['phase_index'] for event in shown] == expected_indices
    assert all(event['payload']['registration_keys'] == loop['native_phase_keys'][event['payload']['phase_index']] for event in shown)
    assert [event['time'] for event in shown][-1] == 1537
    assert s.ctx.resources.current('boss', 'hint_phase') == 1
    assert not [event for event in s.session.events if event['type'] == 'command.rejected']
