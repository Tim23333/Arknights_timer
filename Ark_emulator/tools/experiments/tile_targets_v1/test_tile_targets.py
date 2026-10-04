from copy import deepcopy
import pytest
from ark_sim import Compiler, Engine
from ark_sim.domains.tile_targets import query
from ark_sim.tools.replay import replay


def package():
    actor = {'id': 'unit/source', 'kind': 'entity', 'components': {
        'attributes': {'base': {'max_hp': 100}},
        'resources': {'hp': {'initial': 100, 'capacity': 100, 'role': 'health'}},
        'lifecycle': {'policy': 'policy/ark_lifecycle'}, 'abilities': ['ability/seal']}, 'tags': ['enemy']}
    ally = deepcopy(actor)
    ally['id'] = 'unit/ally'; ally['tags'] = ['player']; ally['components']['abilities'] = []
    ally['components']['deployable'] = {'cost': 0, 'terrain': 1}
    token = {'id': 'unit/token', 'kind': 'entity', 'components': {
        'tile_occupancy': {'blocks_deployment': True, 'exclusive': True, 'targetable': False, 'withdrawable': False}}, 'tags': ['token']}
    selector = {'eligibility_expression': 'inputs.tile.buildableType == 1', 'parameters': {},
        'limit': 2, 'selection': 'uniform_without_replacement', 'stream': 'tile-test'}
    effect = {'op': 'spawn_on_tiles', 'definition': 'unit/token', 'parameters': {
        'cells': 'captured', 'recheck': False, 'occupant_expression': "'player' in inputs.candidate.tags",
        'occupant_parameters': {}, 'instant_kill': {'cause': 'sealed', 'skip_rebirth': False},
        'on_owner_retire': 'retain'}}
    skill = {'id': 'ability/seal', 'kind': 'ability', 'tile_selector': selector,
        'activation': {'mode': 'manual', 'parameters': {'requires_targets': True}},
        'timeline': [{'at': 3, 'effect': effect}]}
    return {'definitions': [actor, ally, token, skill], 'scenarioDraft': {
        'id': 'scene/tile', 'ruleset': 'ruleset/ark_standard', 'objectives': {}, 'roster': ['unit/ally'],
        'resources': {'dp': {'initial': 10, 'capacity': 99}},
        'map': {'rows': 1, 'cols': 3, 'tiles': [
            {'buildableType': 0, 'passableMask': 1},
            {'buildableType': 1, 'passableMask': 1},
            {'buildableType': 1, 'passableMask': 1}]},
        'initialEntities': [{'definition': 'unit/source', 'instanceAlias': 'source', 'position': {'row': 0, 'col': 0}},
            {'definition': 'unit/ally', 'instanceAlias': 'ally', 'position': {'row': 0, 'col': 1}}]}}


def simulation(p=None):
    return Engine.create(Compiler().compile(p or package()), seed=731)


def test_query_is_read_only_and_real_cast_selection_checkpoint_and_replay():
    s = simulation(); ability = s.program.definitions['ability/seal']
    before = s.snapshot()
    assert query(s.ctx, 'source', ability['tile_selector']) == [{'row': 0, 'col': 1}, {'row': 0, 'col': 2}]
    assert s.snapshot() == before
    s.submit({'action': 'skill', 'source': 'source', 'ability': 'ability/seal', 'at': 0})
    s.advance(1)
    casts = s.ctx.get('source', ('runtime', 'casts'))
    cast = next(iter(casts.values()))
    assert len(cast['tile_targets']) == 2
    restored = Engine.restore(s.program, s.checkpoint())
    s.advance(4); restored.advance(4)
    assert s.snapshot() == restored.snapshot()
    assert not s.ctx.alive('ally')
    tokens = [e for e in s.session.world.entities() if e['definition_id'] == 'unit/token']
    assert len(tokens) == 2
    assert all(not s.ctx.selectable(t['id']) and not s.ctx.effect_target_available(t['id']) for t in tokens)
    assert s.ctx.spatial.grid.passable(0, 1)
    assert s.ctx.spatial.grid.tile(0, 1)['buildableType'] == 1
    assert not any(e['type'] == 'damage.dealt' for e in s.session.events)
    assert s.snapshot() == replay(s.program, s.export_replay()).snapshot()


def test_occupancy_blocks_public_deployment_retains_after_owner_retire():
    s = simulation(); s.ctx.abilities.start('source', 'ability/seal'); s.advance(4)
    s.ctx.lifecycle.retire('source', 'withdrawn')
    assert len([e for e in s.session.world.entities() if e['definition_id'] == 'unit/token' and s.ctx.active(e['id'])]) == 2
    s.submit({'action': 'deploy', 'entity': 'unit/ally', 'position': {'row': 0, 'col': 2}, 'at': 4})
    s.advance(5)
    rejected = [e for e in s.session.events if e['type'] == 'command.rejected']
    assert rejected and 'occupied' in rejected[-1]['payload']['reason']
    token = next(e['id'] for e in s.session.world.entities() if e['definition_id'] == 'unit/token' and e['components']['spatial']['position']['col'] == 2)
    s.ctx.lifecycle.retire(token, 'removed')
    from ark_sim.domains.deployment import prepare
    assert prepare(s.ctx, 'unit/ally', {'row': 0, 'col': 2})['position'] == {'row': 0, 'col': 2}


def test_failed_cost_no_random_consumption_and_invalid_expression_rolls_back():
    p = package(); skill = next(x for x in p['definitions'] if x['id'] == 'ability/seal')
    skill['activation']['costs'] = [{'resource': 'hp', 'amount': 1000}]
    s = simulation(p); before = s.snapshot()
    with pytest.raises(ValueError, match='insufficient'):
        s.ctx.abilities.start('source', 'ability/seal')
    assert s.snapshot() == before
    p = package(); skill = next(x for x in p['definitions'] if x['id'] == 'ability/seal')
    skill['tile_selector']['eligibility_expression'] = '1'
    s = simulation(p); before = s.snapshot()
    with pytest.raises(ValueError, match='strict boolean'):
        s.ctx.abilities.start('source', 'ability/seal')
    assert s.snapshot() == before


def test_exclusive_occupancy_create_failure_is_atomic_and_no_token_terrain_rewrite():
    s = simulation(); first = s.ctx.lifecycle.create('unit/token', {'row': 0, 'col': 2})
    before = s.snapshot()
    with pytest.raises(ValueError, match='already contains'):
        s.ctx.lifecycle.create('unit/token', {'row': 0, 'col': 2})
    assert s.snapshot() == before
    assert s.ctx.active(first)
    assert s.ctx.spatial.grid.passable(0, 2)
    s.submit({'action':'withdraw', 'source':first}, at=0); s.advance(1)
    assert s.ctx.active(first)
    assert any(e['type']=='command.rejected' and e['payload']['reason']=='entity is not manually withdrawable'
               for e in s.session.events)


def test_recheck_changed_eligibility_skips_without_new_draws():
    p = package(); effect = next(x for x in p['definitions'] if x['id'] == 'ability/seal')['timeline'][0]['effect']
    effect['parameters']['recheck'] = True
    skill = next(x for x in p['definitions'] if x['id'] == 'ability/seal')
    skill['tile_selector']['eligibility_expression'] = 'inputs.tile.buildableType == 1 and not inputs.deployment_blocked'
    s = simulation(p); s.ctx.abilities.start('source', 'ability/seal')
    s.ctx.lifecycle.create('unit/token', {'row': 0, 'col': 2})
    s.advance(4)
    assert len([e for e in s.session.world.entities() if e['definition_id'] == 'unit/token']) == 1
    assert any(e['type'] == 'tile.effect_rejected' for e in s.session.events)


def test_later_cell_failure_rolls_back_earlier_kill_and_token():
    s = simulation(); s.ctx.abilities.start('source', 'ability/seal')
    cast = next(iter(s.ctx.get('source', ('runtime', 'casts')).values()))
    first, second = cast['tile_targets']
    s.ctx.lifecycle.create('unit/token', second)
    before = s.snapshot()
    ability = s.program.definitions['ability/seal']; effect = ability['timeline'][0]['effect']
    with pytest.raises(ValueError, match='already contains'):
        s.ctx.effects.execute(s.session.world.resolve('source'), [], effect, ability=ability, cast=cast)
    assert s.snapshot() == before
    assert s.ctx.alive('ally')


def test_dormant_exclusive_token_cannot_activate_over_existing_token():
    s = simulation(); dormant = s.ctx.lifecycle.create('unit/token', {'row':0,'col':2},
        active=False, registration_key='dormant')
    s.ctx.lifecycle.create('unit/token', {'row':0,'col':2})
    before = s.snapshot()
    with pytest.raises(ValueError, match='already contains'):
        s.ctx.lifecycle.activate_predefined('dormant')
    assert s.snapshot() == before
    assert not s.ctx.active(dormant)


def test_active_cast_captured_cells_cannot_be_modified_by_effect_caller():
    s=simulation();s.ctx.abilities.start('source','ability/seal')
    cast=deepcopy(next(iter(s.ctx.get('source',('runtime','casts')).values())))
    cast['tile_targets']=[{'row':0,'col':0}]
    ability=s.program.definitions['ability/seal'];before=s.checkpoint()
    with pytest.raises(ValueError,match='original captured'):
        s.ctx.effects.execute('source',[],ability['timeline'][0]['effect'],ability=ability,cast=cast)
    assert s.checkpoint()==before and s.ctx.alive('ally')
