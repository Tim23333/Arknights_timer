"""Actual source5000/12000 collapse branches and owned ruin lifecycle."""
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_c9_foundation_v7_candidate'
sys.path.insert(0, str(RUNTIME)); sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter09_pillar_v1.build_payload import build, providers


def fixture(direction='right', enemy_motion=1, free=False, hp=20000):
    p = build()
    p['entities'].extend([
        {'id': 'unit/pillar/enemy', 'kind': 'entity', 'tags': ['enemy'], 'components': {
            'attributes': {'base': {'max_hp': hp, 'atk': 0, 'def': 9999, 'mres': 99}},
            'resources': {'hp': {'role': 'health', 'initial': hp, 'capacity': hp}}, 'spatial': {},
            'selection_state': {'side': 1, 'motion': enemy_motion, 'category': 1, 'unit_type': 2, 'target_free': free},
            'lifecycle': {'policy': 'policy/ark_lifecycle'}}},
        {'id': 'unit/pillar/player', 'kind': 'entity', 'tags': ['player'], 'components': {
            'attributes': {'base': {'max_hp': 1000, 'atk': 0, 'def': 0, 'mres': 0}},
            'resources': {'hp': {'role': 'health', 'initial': 1000, 'capacity': 1000}}, 'spatial': {},
            'selection_state': {'side': 0, 'motion': 1, 'category': 1, 'unit_type': 1, 'target_free': True},
            'lifecycle': {'policy': 'policy/ark_lifecycle'}}}])
    offset = {'right': (0, 1), 'left': (0, -1), 'up': (-1, 0), 'down': (1, 0)}[direction]
    r, c = 2, 3; dr, dc = offset
    p['scenarioDraft'] = {'id': 'scene/pillar/payload', 'ruleset': 'ruleset/ark_standard',
        'map': {'rows': 5, 'cols': 7}, 'initialEntities': [
            {'definition': 'unit/ch9/pillar/body', 'instanceAlias': 'pillar', 'position': {'row': r, 'col': c}},
            {'definition': 'unit/pillar/enemy', 'instanceAlias': 'enemy', 'position': {'row': r + dr, 'col': c + dc}},
            {'definition': 'unit/pillar/player', 'instanceAlias': 'player', 'position': {'row': r + 2 * dr, 'col': c + 2 * dc}}]}
    return p


def create(direction='right', **options):
    program = Compiler(providers=providers()).compile(fixture(direction, **options))
    sim = Engine.create(program, providers=providers(), seed=90315)
    sim.submit({'action': 'skill', 'source': 'pillar', 'ability': 'ability/ch9/pillar/collapse_' + direction}, at=2)
    return sim


@pytest.mark.parametrize('direction', ['right', 'left', 'up', 'down'])
def test_four_source_directions_true12000_stun10_withdraw_and_two_ruins(direction):
    sim = create(direction)
    native_passability = sim.ctx.spatial.grid.tile(2, 3)['passableMask']
    sim.advance(47)
    assert sim.ctx.resources.current('enemy', 'hp') == 20000
    sim.advance(1)
    assert sim.ctx.resources.current('enemy', 'hp') == 8000
    assert sim.ctx.get('player', ('runtime', 'state')) == 'withdrawn'
    assert sim.ctx.get('pillar', ('runtime', 'state')) == 'dead'
    ruins = [e for e in sim.session.world.entities() if e['definition_id'] == 'unit/ch9/pillar/ruin']
    assert len(ruins) == 2 and all(sim.ctx.resources.current(e['id'], 'hp') == 100 for e in ruins)
    assert sim.ctx.buffs.controls('enemy')['move'] is False
    row = next(b for b in sim.ctx.get('enemy', ('buffs', 'instances')) if b['definition'] == 'buff/ch9/pillar/stun10')
    assert row['expires_at'] == 347
    assert any(e['time'] == 47 and e['type'] == 'buff.applied'
               and e['payload'].get('buff') == 'buff/ch9/pillar/stun10' for e in sim.session.events)
    for e in ruins:
        pos = e['components']['spatial']['position']; tile = sim.ctx.spatial.grid.tile(pos['row'], pos['col'])
        assert tile['buildableType'] == 0 and tile['passableMask'] == native_passability
        assert tile['physicalHeight'] == pytest.approx(.4)


def test_ground_and_flying_enemies_receive_same_true_packet():
    sim = create(enemy_motion=2); sim.advance(48)
    assert sim.ctx.resources.current('enemy', 'hp') == 8000


def test_target_free_enemy_is_rejected_but_player_is_withdrawn():
    sim = create(free=True); sim.advance(48)
    assert sim.ctx.resources.current('enemy', 'hp') == 20000
    assert sim.ctx.get('player', ('runtime', 'state')) == 'withdrawn'


def test_late_enemy_membership_reads_current_position_at_collapse():
    sim = create(); sim.ctx.set('enemy', ('spatial', 'position'), {'row': 0, 'col': 0}); sim.advance(46)
    sim.ctx.set('enemy', ('spatial', 'position'), {'row': 2, 'col': 4}); sim.advance(2)
    assert sim.ctx.resources.current('enemy', 'hp') == 8000


def test_ruin_has_no_fixed_lifetime_and_death_removes_owned_terrain():
    sim = create(); sim.advance(400)
    ruins = [e for e in sim.session.world.entities() if e['definition_id'] == 'unit/ch9/pillar/ruin']
    assert len(ruins) == 2 and all(sim.ctx.active(e['id']) for e in ruins)
    target = ruins[0]['id']; pos = thaw(ruins[0]['components']['spatial']['position'])
    sim.ctx.lifecycle.retire(target, 'dead')
    assert sim.ctx.spatial.grid.tile(pos['row'], pos['col'])['buildableType'] == 1


def test_actual_disk_cp_before_collapse_head_and_post_collapse_resume(tmp_path):
    sim = create(); sim.advance(30)
    cp = tmp_path / 'collapse.checkpoint.json'; cp.write_text(json.dumps(sim.checkpoint()), encoding='utf8')
    restored = Engine.restore(sim.program, json.loads(cp.read_bytes()), providers=providers())
    sim.advance(40); restored.advance(40)
    assert sim.checkpoint() == restored.checkpoint()
    assert sim.snapshot() == replay(sim.program, sim.export_replay(), providers=providers()).snapshot()


def test_source_ruin_blocks_three_route_movers_and_fourth_is_unblocked():
    data = fixture()
    data['scenarioDraft']['initialEntities'] = [{'definition': 'unit/ch9/pillar/ruin',
        'instanceAlias': 'ruin', 'position': {'row': 2, 'col': 3}}]
    enemy = next(e for e in data['entities'] if e['id'] == 'unit/pillar/enemy')
    enemy['components']['attributes']['base']['block_cost'] = 1
    enemy['components']['attributes']['base']['move_speed'] = 1
    for i in range(4):
        data['scenarioDraft']['initialEntities'].append({'definition': enemy['id'], 'instanceAlias': 'mover' + str(i),
            'position': {'row': 2, 'col': 3}, 'route': {'motionMode': 'WALK', 'endPosition': {'row': 2, 'col': 6}}})
    sim = Engine.create(Compiler(providers=providers()).compile(data), providers=providers())
    sim.ctx.spatial.blocking()
    blocker = sim.session.world.resolve('ruin')
    assert [sim.ctx.spatial.blocked_by('mover' + str(i)) for i in range(4)] == [blocker, blocker, blocker, None]
    sim.ctx.lifecycle.retire('ruin', 'dead'); sim.ctx.spatial.blocking()
    assert all(sim.ctx.spatial.blocked_by('mover' + str(i)) is None for i in range(4))
