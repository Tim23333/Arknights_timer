"""Author golden probes for exact C5 regeneration content on frozen M94.

Expected numbers are independent constants. Fixtures vary HP/attack speed only
to expose the real resource clock and combat boundaries; shipped stats stay raw.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import pytest
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter05.build_regenerating_units import build

ROOT = Path(__file__).resolve().parents[3]
CASES = [('enemy_1044_zomstr', 6000, 500, 130, 200, 26, 90),
         ('enemy_1043_zomsbr', 2500, 250, 100, 80, 12, 54)]
PARAM = pytest.mark.parametrize('native,hp,atk,defense,regen,frame,interval', CASES)


def fixture_package(native, *, initial_hp=1000, dormant=False, activate_at=None, blocked=False, speed=1):
    p = build()
    u = next(u for u in p['entities'] if u['metadata']['native_reference']['id'] == native)
    enemy = {'definition': u['id'], 'instanceAlias': 'enemy', 'position': {'row': 0, 'col': 0},
             'components': {'resources': {'hp': {'initial': initial_hp}}, 'attributes': {'base': {'attack_speed_ratio': speed}}}}
    if dormant: enemy.update(active=False, registration_key='regen_enemy')
    if blocked:
        enemy['route'] = {'motionMode': 'WALK', 'startPosition': {'row': 0, 'col': 0},
                          'endPosition': {'row': 0, 'col': 4}, 'checkpoints': []}
    p['entities'].append({'id': 'unit/regen_probe', 'kind': 'entity', 'tags': ['player'],
        'components': {'spatial': {}, 'attributes': {'base': {'max_hp': 10000, 'atk': 230 if native == 'enemy_1044_zomstr' else 200,
            'def': 100, 'mres': 0, 'block_count': 1 if blocked else 0}},
            'resources': {'hp': {'initial': 10000, 'capacity': 10000, 'role': 'health'}},
            'lifecycle': {'policy': 'policy/ark_lifecycle'}, 'abilities': ['ability/regen_probe_damage'],
            'deployable': {'base_cost': 0, 'capacity': 1, 'cooldown_seconds': 0, 'terrain': 'ground'}}})
    p['selectors'].append({'id': 'selector/regen_probe_enemy', 'kind': 'selector', 'region': {'type': 'all'},
        'filters': [{'tag': 'enemy'}, {'state': 'alive'}], 'limit': 1})
    p['abilities'].append({'id': 'ability/regen_probe_damage', 'kind': 'ability', 'selector': 'selector/regen_probe_enemy',
        'activation': {'mode': 'manual'}, 'timeline': [{'at': 0, 'effect': {'op': 'damage', 'damage_type': 'physical', 'scale': 1}}]})
    scene = {'id': 'scene/ch5/regen_probe', 'ruleset': 'ruleset/ark_standard', 'objectives': {},
             'map': {'rows': 1, 'cols': 5}, 'roster': ['unit/regen_probe'],
             'resources': {'dp': {'initial': 10, 'capacity': 10}}, 'initialEntities': [enemy]}
    if not blocked:
        scene['initialEntities'].append({'definition': 'unit/regen_probe', 'instanceAlias': 'probe', 'position': {'row': 0, 'col': 4}})
    if activate_at is not None:
        scene['scheduledEffects'] = [{'at': activate_at, 'effect': {'op': 'activate_predefined', 'target': 'battle', 'parameters': {'key': 'regen_enemy'}}}]
    p['scenarioDraft'] = scene
    return p


def fixture(native, **kwargs):
    p = fixture_package(native, **kwargs)
    sim = Engine.create(Compiler().compile(p), seed=5501)
    if kwargs.get('blocked'): sim.submit({'action': 'deploy', 'definition': 'unit/regen_probe', 'alias': 'blocker', 'position': {'row': 0, 'col': 0}}, at=0)
    return sim


def current(s): return s.ctx.resources.current('enemy', 'hp')


def gains(s):
    eid = s.session.world.resolve('enemy')
    return [e for e in s.session.events if e['type'] == 'resource.changed' and e['payload']['target'] == eid
            and e['payload']['resource'] == 'hp' and e['payload']['delta'] > 0]


def hit(s, at=0): s.submit({'action': 'skill', 'source': 'probe', 'ability': 'ability/regen_probe_damage'}, at=at)


def test_exact_frozen_runtime_and_module_isolated_from_plain_variants():
    assert implementation_digest() == 'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'
    p = build()
    assert {u['metadata']['native_reference']['id'] for u in p['entities']} == {'enemy_1044_zomstr', 'enemy_1043_zomsbr'}
    plain = json.loads((ROOT/'packages/campaign/chapter05_units/ordinary.reference_model.json').read_bytes())
    assert {u['id'] for u in plain['entities']}.isdisjoint(u['id'] for u in p['entities'])
    assert {r['id'] for r in plain['rules']}.isdisjoint(r['id'] for r in p['rules'])
    for u, expected in zip(sorted(p['entities'], key=lambda u: u['metadata']['native_reference']['id']), reversed(CASES)):
        native, hp, atk, defense, regen, frame, interval = expected
        assert u['metadata']['native_reference']['id'] == native
        attrs = u['components']['attributes']['base']
        assert (attrs['max_hp'], attrs['atk'], attrs['def'], attrs['hp_recovery_per_sec']) == (hp, atk, defense, regen)
        assert u['components']['resources']['hp']['initial'] == hp
        assert 'mutant' in u['tags']
        assert 'recovery_rate' not in u['components']['resources']['hp']  # One effective-attribute driver, no duplicate static driver.


@pytest.mark.parametrize('native,ticks,expected', [('enemy_1044_zomstr', 1, 1006.6666666666666),
    ('enemy_1044_zomstr', 30, 1200), ('enemy_1044_zomstr', 60, 1400),
    ('enemy_1043_zomsbr', 1, 1002.6666666666666), ('enemy_1043_zomsbr', 30, 1080), ('enemy_1043_zomsbr', 60, 1160)])
def test_explicit_continuous_numeric_clock(native, ticks, expected):
    s = fixture(native)
    s.session.advance(ticks)
    assert current(s) == pytest.approx(expected, abs=1e-8)
    assert len(gains(s)) == ticks


@pytest.mark.parametrize('native,cap', [('enemy_1044_zomstr', 6000), ('enemy_1043_zomsbr', 2500)])
def test_saturation_fractional_headroom_full_pause_and_resume_after_damage(native, cap):
    s = fixture(native, initial_hp=cap-.25)
    s.session.advance(1)
    assert current(s) == cap
    assert gains(s)[0]['payload']['delta'] == .25
    s.session.advance(30)
    assert len(gains(s)) == 1
    hit(s, at=31)
    s.session.advance(1)
    assert current(s) == cap-100
    s.session.advance(1)
    assert current(s) == pytest.approx(5906.666666666667 if cap == 6000 else 2402.6666666666665)


@pytest.mark.parametrize('native,expected', [('enemy_1044_zomstr', 1100), ('enemy_1043_zomsbr', 980)])
def test_damage_does_not_reset_or_freeze_permanent_recovery(native, expected):
    s = fixture(native)
    hit(s, at=0)
    s.session.advance(30)
    damage = [e for e in s.session.events if e['type'] == 'damage.accepted']
    assert [(e['time'], e['payload']['amount']) for e in damage] == [(0, 100)]
    assert current(s) == pytest.approx(expected, abs=1e-8)
    assert len(gains(s)) == 30


@PARAM
def test_dormant_has_no_gain_and_activation_begins_on_exact_tick(native, hp, atk, defense, regen, frame, interval):
    s = fixture(native, dormant=True, activate_at=30)
    s.session.advance(30)
    assert current(s) == 1000 and gains(s) == [] and not s.ctx.active('enemy')
    s.session.advance(1)
    assert s.ctx.active('enemy')
    assert current(s) == pytest.approx(1006.6666666666666 if regen == 200 else 1002.6666666666666)
    assert gains(s)[0]['time'] == 30
    s.session.advance(29)
    assert current(s) == pytest.approx(1200 if regen == 200 else 1080, abs=1e-8)


@PARAM
def test_temporary_inactive_gate_has_no_catch_up(native, hp, atk, defense, regen, frame, interval):
    s = fixture(native)
    s.ctx.set('enemy', ('runtime', 'active'), False)
    s.session.advance(300)
    assert s.ctx.alive('enemy') and current(s) == 1000 and gains(s) == []
    s.ctx.set('enemy', ('runtime', 'active'), True)
    s.session.advance(30)
    assert current(s) == pytest.approx(1200 if regen == 200 else 1080, abs=1e-8)


@PARAM
def test_killed_enemy_never_regenerates_or_resurrects(native, hp, atk, defense, regen, frame, interval):
    s = fixture(native, initial_hp=50)
    hit(s)
    s.session.advance(1)
    deaths = [e for e in s.session.events if e['type'] == 'entity.died']
    assert len(deaths) == 1 and current(s) == 0 and not s.ctx.alive('enemy')
    death_id = deaths[0]['id']
    s.session.advance(300)
    assert current(s) == 0 and not s.ctx.active('enemy')
    assert not [e for e in gains(s) if e['id'] > death_id]


@pytest.mark.parametrize('native,initial', [('enemy_1044_zomstr', 93.33333333333333), ('enemy_1043_zomsbr', 97.33333333333333)])
def test_exact_lethal_boundary_after_same_tick_recovery(native, initial):
    s = fixture(native, initial_hp=initial)
    hit(s)
    s.session.advance(1)
    assert current(s) == 0 and not s.ctx.alive('enemy')
    s.session.advance(30)
    assert current(s) == 0


def test_four_variant_composition_keeps_plain_recovery_absent():
    p = build()
    plain = json.loads((ROOT/'packages/campaign/chapter05_units/ordinary.reference_model.json').read_bytes())
    all_units = p['entities'] + plain['entities']
    p['scenarioDraft'] = {'id': 'scene/ch5/four_variants', 'ruleset': 'ruleset/ark_standard', 'objectives': {},
        'map': {'rows': 1, 'cols': 5}, 'initialEntities': [{'definition': u['id'], 'instanceAlias': 'u'+str(i),
            'position': {'row': 0, 'col': i}, 'components': {'resources': {'hp': {'initial': 1000}}}} for i, u in enumerate(all_units)]}
    s = Engine.create(Compiler().compile(p, packages=[plain]), seed=5502)
    s.session.advance(30)
    results = {u['metadata']['native_reference']['id']: s.ctx.resources.current('u'+str(i), 'hp') for i, u in enumerate(all_units)}
    assert results == pytest.approx({'enemy_1044_zomstr': 1200, 'enemy_1043_zomsbr': 1080,
                                    'enemy_1037_lunsbr': 1000, 'enemy_1030_wteeth': 1000}, abs=1e-8)


@pytest.mark.parametrize('native,expected', [('enemy_1044_zomstr', 1240), ('enemy_1043_zomsbr', 1120)])
def test_effective_recovery_attribute_is_consumed_not_stale_constant(native, expected):
    s = fixture(native)
    s.ctx.set('enemy', ('attributes', 'modifiers'), [{'attribute': 'hp_recovery_per_sec', 'layer': 'flat', 'value': 40}])
    s.session.advance(30)
    assert current(s) == pytest.approx(expected, abs=1e-8)


@pytest.mark.parametrize('native,speed,end,expected', [
    ('enemy_1044_zomstr', 1, 118, [(27, 400), (117, 400)]),
    ('enemy_1043_zomsbr', 1, 68, [(13, 150), (67, 150)]),
    ('enemy_1044_zomstr', 2, 60, [(14, 400), (59, 400)]),
    ('enemy_1043_zomsbr', 2, 41, [(7, 150), (34, 150)]),
    ('enemy_1044_zomstr', .5, 234, [(53, 400), (233, 400)]),
    ('enemy_1043_zomsbr', .5, 134, [(25, 150), (133, 150)]),
])
def test_actual_blocked_attack_source_frames_interval_damage_and_parallel_regeneration(native, speed, end, expected):
    s = fixture(native, blocked=True, speed=speed)
    s.session.advance(end)
    assert s.ctx.spatial.blocked_by('enemy') == s.session.world.resolve('blocker')
    hits = [e for e in s.session.events if e['type'] == 'damage.accepted']
    assert [(e['time'], e['payload']['amount']) for e in hits] == expected
    assert current(s) == pytest.approx(1000 + (200 if native.endswith('zomstr') else 80)*end/30, abs=1e-8)


@PARAM
def test_durable_cp_and_public_replay_cover_activation_incoming_damage_and_fractional_clock(native, hp, atk, defense, regen, frame, interval, tmp_path):
    s = fixture(native, dormant=True, activate_at=20)
    hit(s, at=30)
    s.session.advance(17)
    cp = tmp_path/'actual.saved.json'; pin = write_ordered(cp, s.checkpoint())
    restored = Engine.restore(s.program, load_bound(cp, pin))
    s.session.advance(43); restored.session.advance(43)
    assert current(s) == pytest.approx(1166.6666666666667 if regen == 200 else 1006.6666666666667, abs=1e-8)
    assert s.snapshot() == restored.snapshot() == replay(s.program, s.export_replay()).snapshot()


@PARAM
def test_attack_inflight_saved_cp_and_replay_are_identical(native, hp, atk, defense, regen, frame, interval, tmp_path):
    s = fixture(native, blocked=True)
    s.session.advance(2)
    cp = tmp_path/'actual.attack.json'; pin = write_ordered(cp, s.checkpoint())
    restored = Engine.restore(s.program, load_bound(cp, pin))
    s.session.advance(frame); restored.session.advance(frame)
    assert s.snapshot() == restored.snapshot() == replay(s.program, s.export_replay()).snapshot()


@PARAM
def test_dead_state_survives_real_saved_cp_and_replay_without_regeneration(native, hp, atk, defense, regen, frame, interval, tmp_path):
    s = fixture(native, initial_hp=50)
    hit(s)
    s.session.advance(1)
    assert not s.ctx.alive('enemy') and not s.ctx.state()['finished']
    cp = tmp_path/'actual.dead.json'; pin = write_ordered(cp, s.checkpoint())
    restored = Engine.restore(s.program, load_bound(cp, pin))
    s.session.advance(30); restored.session.advance(30)
    repeated = replay(s.program, s.export_replay())
    assert current(s) == current(restored) == current(repeated) == 0
    assert not any(sim.ctx.active('enemy') for sim in (s, restored, repeated))
    assert s.snapshot() == restored.snapshot() == repeated.snapshot()
