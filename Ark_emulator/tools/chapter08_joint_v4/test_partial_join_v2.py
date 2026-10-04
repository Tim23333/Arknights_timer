"""Actual joined arbitration executes normal and source skills under one owner."""
import json
from pathlib import Path
from copy import deepcopy
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.chapter08_joint_v4.build_bsnake_partial_join_v1 import OUT, build, providers, BASE
from tools.campaign_ordered_checkpoint import write_ordered, load_bound


def package():
    p = json.loads(OUT.read_bytes())
    loop = json.loads((BASE.parent / 'flame/loop.profile.v3.json').read_bytes())
    # Callback-only dummy definitions ensure summon references compile. Stage
    # admission will replace these with actual source25SP devices.
    p['definitions'].append({'id': 'unit/ch8/flame/level1', 'kind': 'entity', 'components': {'spatial': {}}})
    p['definitions'].append({'id': 'unit/partial/recipient', 'kind': 'entity', 'tags': ['player'],
                             'components': {'attributes': {'base': {'max_hp': 100000, 'atk': 0, 'def': 2713, 'mres': 40}},
                                            'resources': {'hp': {'initial': 100000, 'capacity': 100000, 'role': 'health'}},
                                            'selection_state': {'side': 0, 'motion': 1, 'category': 1, 'unit_type': 1},
                                            'spatial': {}, 'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
    p['scenarioDraft'] = {'id': 'scene/partial/join', 'ruleset': 'ruleset/ark_standard',
                          'map': {'rows': 9, 'cols': 15}, 'branches': loop['runtime_branch'], 'objectives': {},
                          'initialEntities': deepcopy(loop['initial_entities']) + [{'definition': 'unit/ch8/bsnake/cadb87696bef4de2', 'instanceAlias': 'boss',
                                               'position': {'row': 2, 'col': 4}},
                                              {'definition': 'unit/partial/recipient', 'instanceAlias': 'target',
                                               'position': {'row': 2, 'col': 5}}]}
    # Source loop config is retained, no request occurs in mode0 first40s.
    return p


def test_exact_partial_source_join_rebuild():
    assert json.loads(OUT.read_bytes()) == build()


def test_joined_normal_and_ignite_actual_CP500_head(tmp_path):
    p = package()
    reg = providers()
    s = Engine.create(Compiler(providers=reg).compile(p), providers=reg, seed=81321)
    s.advance(500)
    path = tmp_path / 'join500.cp.json'
    pin = write_ordered(path, s.checkpoint())
    r = Engine.restore(s.program, load_bound(path, pin), providers=reg)
    s.advance(700)
    r.advance(700)
    h = replay(s.program, s.export_replay(), providers=reg)
    assert s.checkpoint() == r.checkpoint() == h.checkpoint()
    assert list(s.session.events) == list(r.session.events) == list(h.session.events)
    normal = [event for event in s.session.events if event['type'] == 'damage.accepted'
              and event['payload']['ability'] == 'ability/ch8/bsnake/normal/phase0']
    assert normal and normal[0]['time'] == 31 and normal[0]['payload']['amount'] == 770
    assert s.ctx.resources.current('boss', 'mode') == 0
    assert not [event for event in s.session.events if event['type'] == 'source.bsnake.screen.volley']
    assert any(event['type'] == 'ability.started' and event['payload']['ability'] == 'ability/ch8/bsnake/explode/phase0'
               for event in s.session.events)
