"""Actual ranged definitions under explicit isolated actor configurations."""
from copy import deepcopy
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_chapter01_ranged_projectiles import build


def fixture(kind):
    p = build('level_main_01-11')
    caster = 'unit/enemy_1028_mocock' if kind == 'mocock' else 'unit/ch1_predefined_adnach_e0_l20'
    ability = 'ability/enemy_1028_mocock/ch1_model_normal' if kind == 'mocock' else 'ability/ch1_predefined_adnach_normal'
    actor = next(e for e in p['entities'] if e['id'] == caster)
    selected = next(a for a in p['abilities'] if a['id'] == ability); selected['activation']['mode'] = 'manual'
    selected.setdefault('parameters', {})['blocks_attacks'] = False
    victim_tags = ['player', 'ground'] if kind == 'mocock' else ['enemy', 'ground']
    for name in ('victim', 'decoy'):
        p['entities'].append({'id': 'unit/'+name, 'kind': 'entity', 'tags': victim_tags, 'components': {
            'attributes': {'base': {'max_hp': 1000, 'atk': 0, 'def': 30, 'mres': 0}},
            'resources': {'hp': {'initial': 1000, 'capacity': 1000, 'role': 'health'}}, 'spatial': {},
            'lifecycle': {'policy': 'policy/ark_lifecycle'}, 'abilities': ['ability/victim_move'] if name == 'victim' else []}})
    p['abilities'].append({'id': 'ability/victim_move', 'kind': 'ability', 'activation': {'mode': 'manual', 'on_start': [
        {'op': 'move', 'target': 'source', 'position': {'row': 2, 'col': 4}},
        {'op': 'spawn', 'definition': 'unit/decoy', 'position': {'row': 2, 'col': 2}}]}, 'timeline': []})
    p['entities'].append({'id': 'unit/director', 'kind': 'entity', 'tags': ['system_probe'], 'components': {'spatial': {}, 'abilities': ['ability/give_atk']}})
    p['buffs'].append({'id': 'buff/extra_atk', 'kind': 'buff', 'modifiers': [{'attribute': 'atk', 'layer': 'flat', 'value': 100}]})
    p['abilities'].append({'id': 'ability/give_atk', 'kind': 'ability', 'activation': {'mode': 'manual', 'on_start': [
        {'op': 'apply_buff', 'target': 2, 'buff': 'buff/extra_atk'}]}, 'timeline': []})
    p['scenarioDraft'] = {'id': 'scenario/actual_ranged_'+kind, 'ruleset': 'ruleset/ark_standard',
        'map': {'rows': 5, 'cols': 6}, 'resources': {'dp': {'initial': 50, 'capacity': 99}}, 'objectives': {},
        'initialEntities': [{'definition': caster, 'instanceAlias': 'caster', 'position': {'row': 2, 'col': 1}, 'facing': 'right'},
            {'definition': 'unit/victim', 'instanceAlias': 'victim', 'position': {'row': 2, 'col': 2}},
            {'definition': 'unit/director', 'instanceAlias': 'director', 'position': {'row': 0, 'col': 0}}],
        'metadata': {'test_scope': 'isolated actual ranged ability with synthetic target/director and manual activation', 'whole_stage': False}}
    return p, ability


def roundtrip(sim):
    checkpoint = sim.checkpoint(); restored = Engine.restore(sim.program, checkpoint); sim.advance(2); restored.advance(2)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(tuple(sim.session.events), tuple(restored.session.events)) is None
    replayed = replay(sim.program, sim.export_replay())
    assert first_difference(sim.snapshot(), replayed.snapshot()) is None
    assert first_difference(tuple(sim.session.events), tuple(replayed.session.events)) is None


def test_mocock_keeps_capture_tracks_moving_target_and_ignores_new_nearer_decoy():
    p, ability = fixture('mocock'); sim = Engine.create(Compiler().compile(p), seed=2201)
    sim.submit({'action': 'skill', 'source': 'caster', 'ability': ability}, at=0)
    sim.submit({'action': 'skill', 'source': 'victim', 'ability': 'ability/victim_move'}, at=23)
    sim.advance(29)
    assert not [e for e in sim.session.events if e['type'] == 'damage.accepted']
    sim.advance(15)
    hits = [e for e in sim.session.events if e['type'] == 'damage.accepted']
    assert len(hits) == 1 and hits[0]['payload']['target'] == sim.session.world.resolve('victim')
    assert hits[0]['time'] > 28
    assert sim.ctx.resources.current(next(e['id'] for e in sim.session.world.entities() if e['definition_id'] == 'unit/decoy'), 'hp') == 1000
    projectile = next(iter(sim.ctx.get('system/battle', ('projectiles', 'instances')).values()))
    assert projectile['hit_count'] == 1 and not projectile['jobs']
    roundtrip(sim)


def test_actual_crossbow_speed_ten_and_live_atk_after_launch():
    p, ability = fixture('crossbow'); sim = Engine.create(Compiler().compile(p), seed=2202)
    sim.submit({'action': 'skill', 'source': 'caster', 'ability': ability}, at=0)
    sim.submit({'action': 'skill', 'source': 'director', 'ability': 'ability/give_atk'}, at=10)
    sim.advance(13)
    assert [e['time'] for e in sim.session.events if e['type'] == 'projectile.launched'] == [9]
    hits = [e for e in sim.session.events if e['type'] == 'damage.accepted']
    assert [(e['time'], e['payload']['amount']) for e in hits] == [(12, 269)]
    assert sim.ctx.resources.current('victim', 'hp') == 731
    roundtrip(sim)

