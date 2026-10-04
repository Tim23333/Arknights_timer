"""Public two defeats drive first28s screen and realHP0 final screen."""
import json
from copy import deepcopy
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.chapter08_joint_v4.build_bsnake_four_modes_v1 import OUT, build, BASE, FINAL
from tools.chapter08_joint_v4.build_bsnake_partial_join_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered, load_bound


def package():
    p = json.loads(OUT.read_bytes())
    loop = json.loads((BASE.parent / 'flame/loop.profile.v3.json').read_bytes())
    p['definitions'] += [
        {'id': 'unit/ch8/flame/level1', 'kind': 'entity', 'components': {'spatial': {}}},
        {'id': 'unit/fourmode/director', 'kind': 'entity', 'components': {'spatial': {}, 'abilities': ['ability/fourmode/kill']}},
        {'id': 'ability/fourmode/kill', 'kind': 'ability', 'activation': {'mode': 'manual', 'on_start': [
            {'op': 'instant_kill', 'target': 12, 'parameters': {'cause': 'source_fourmode', 'skip_rebirth': False}}]}, 'timeline': []},
    ]
    p['scenarioDraft'] = {'id': 'scene/fourmode/source', 'ruleset': 'ruleset/ark_standard', 'objectives': {},
                          'map': {'rows': 9, 'cols': 15}, 'branches': loop['runtime_branch'],
                          'initialEntities': deepcopy(loop['initial_entities']) + [
                              {'definition': 'unit/ch8/bsnake/cadb87696bef4de2', 'instanceAlias': 'boss', 'position': {'row': 4, 'col': 10}},
                              {'definition': 'unit/fourmode/director', 'instanceAlias': 'director', 'position': {'row': 0, 'col': 0}}]}
    return p


def test_exact_source_fourmode_rebuild():
    assert json.loads(OUT.read_bytes()) == build()


def test_two_public_defeats_restore37500_then_true0_final70launch_onceDeath_CP1600_head(tmp_path):
    reg = providers()
    s = Engine.create(Compiler(providers=reg).compile(package()), providers=reg, seed=81897)
    s.submit({'action': 'skill', 'source': 'director', 'ability': 'ability/fourmode/kill'}, at=1)
    s.submit({'action': 'skill', 'source': 'director', 'ability': 'ability/fourmode/kill'}, at=1500)
    s.advance(152)
    assert s.ctx.resources.current('boss', 'hp') == 37500 and s.ctx.resources.current('boss', 'mode') == 2
    s.advance(840)
    assert s.ctx.resources.current('boss', 'hp') == 37500 and s.ctx.resources.current('boss', 'mode') == 1
    s.advance(608)
    assert s.ctx.resources.current('boss', 'hp') == 0 and not s.ctx.active('boss') and s.ctx.alive('boss')
    path = tmp_path / 'fourmode1600.cp.json'
    pin = write_ordered(path, s.checkpoint())
    r = Engine.restore(s.program, load_bound(path, pin), providers=reg)
    s.advance(51)
    r.advance(51)
    assert s.ctx.resources.current('boss', 'hp') == 0 and s.ctx.active('boss') and s.ctx.resources.current('boss', 'mode') == 3
    s.advance(850)
    r.advance(850)
    h = replay(s.program, s.export_replay(), providers=reg)
    assert s.checkpoint() == r.checkpoint() == h.checkpoint()
    assert list(s.session.events) == list(r.session.events) == list(h.session.events)
    assert not s.ctx.alive('boss') and s.ctx.resources.current('boss', 'hp') == 0
    volleys = [event['time'] for event in s.session.events if event['type'] == 'source.bsnake.screen.volley']
    assert volleys == list(range(211, 752, 60)) + list(range(1710, 2251, 60))
    assert len([event for event in s.session.events if event['type'] == 'projectile.launched']) == 140
    ended = [event for event in s.session.events if event['type'] == 'entity.terminal.completed']
    assert len(ended) == 1 and ended[0]['time'] == 2490 and ended[0]['payload']['reason'] == 'owned_buff_finished'
    assert len([event for event in s.session.events if event['type'] == 'combat.kill' and event['payload']['target'] == 12]) == 1
