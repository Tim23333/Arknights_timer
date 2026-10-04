"""Production enemy score binding consumes bird taunt without changing player aim."""
import json

from ark_sim import Compiler, Engine
from tools.build_m8_enemy_targeting import ROOT, SCORE, build


def scene(revised=True):
    path = ROOT/'packages/campaign/mainline_models/level_main_00-10.m8_roster.json'
    data = build(path) if revised else json.loads(path.read_bytes())
    data['entities'] += [{'id': 'unit/taunt_probe_player', 'kind': 'entity', 'tags': ['player', 'ground'],
        'components': {'attributes': {'base': {'max_hp': 10000}}, 'spatial': {},
            'resources': {'hp': {'initial': 10000, 'capacity': 10000, 'role': 'health'}}}}]
    data['selectors'].append({'id': 'selector/taunt_probe', 'kind': 'selector', 'region': {'type': 'all'},
        'filters': [{'tag': 'player'}, {'state': 'alive'}], 'limit': 1})
    enemy = next(e for e in data['entities'] if 'enemy' in e.get('tags', []))
    # Actor and all score bindings are imported from actual production content.
    # An inert probe ability exposes a selector, without changing the score.
    data['abilities'].append({'id': 'ability/taunt_probe', 'kind': 'ability', 'activation': {'mode': 'manual'},
        'selector': 'selector/taunt_probe', 'timeline': []})
    enemy['components']['abilities'] = ['ability/taunt_probe']
    data['scenarioDraft'].update(id='scenario/production_enemy_taunt', waves=[], objectives={}, initialEntities=[
        {'definition': enemy['id'], 'instanceAlias': 'enemy', 'position': {'row': 4, 'col': 4}},
        {'definition': 'unit/taunt_probe_player', 'instanceAlias': 'near', 'position': {'row': 4, 'col': 5}},
        {'definition': 'unit/support_night_bird', 'instanceAlias': 'bird', 'position': {'row': 4, 'col': 6}}])
    return data


def selected(sim):
    return sim.ctx.spatial.select('enemy', 'selector/taunt_probe')


def test_old_default_ignores_taunt_and_production_wrapper_selects_bird():
    old = Engine.create(Compiler().compile(scene(False)))
    assert selected(old) == [old.session.world.resolve('near')]
    new = Engine.create(Compiler().compile(scene()))
    assert selected(new) == [new.session.world.resolve('bird')]


def test_declared_blocker_priority_precedes_taunt_then_retirement_removes_bird():
    sim = Engine.create(Compiler().compile(scene()))
    sim.ctx.set('near', ('runtime', 'blocked_by'), sim.session.world.resolve('enemy'))
    assert selected(sim) == [sim.session.world.resolve('near')]
    sim.ctx.set('near', ('runtime', 'blocked_by'), None)
    sim.ctx.lifecycle.retire('bird', 'withdrawn')
    assert selected(sim) == [sim.session.world.resolve('near')]


def test_only_enemy_definitions_receive_targeting_rule_and_pending_scope_is_retained():
    source = ROOT/'packages/campaign/mainline_models/level_main_00-10.m8_roster.json'
    old = json.loads(source.read_bytes()); new = build(source)
    old_units = {e['id']: e for e in old['entities']}
    for entity in new['entities']:
        if 'enemy' in entity.get('tags', []):
            assert entity['rules']['targeting.score'] == SCORE
        else:
            assert entity.get('rules', {}) == old_units[entity['id']].get('rules', {})
    assert new['manifest']['metadata']['m8_enemy_targeting']['formal_stage_approved'] is False
    assert 'dynamic taunt modifiers/effective attribute score adapter' in new['manifest']['metadata']['m8_enemy_targeting']['model_gaps']
