"""Actual Mephi HP-rate aura and Heal33 author probes on frozen M94."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter05.mephi.build_module import build, UID, AID, MEMBER, EMITTER, HS, AS

ROOT = Path(__file__).resolve().parents[3]
REGEN = ROOT/'packages/campaign/chapter05_units/regenerating/model.json'


def char(alias, hp=1000, maximum=10000, col=1, side=1, motion=1, category=1, rate=0, **flags):
    return {'alias': alias, 'hp': hp, 'maximum': maximum, 'col': col, 'side': side, 'motion': motion,
            'category': category, 'rate': rate, 'flags': flags}


def fixture_package(chars=(), *, regen=(), mephi_hp=28000, mephi_active=True, mephi_activate=None,
                    source_retire=None, route=False, extra_effects=(), second_mephi=False, kill_at=None):
    p = build(); g = json.loads(REGEN.read_bytes())
    initial = [{'definition': UID, 'instanceAlias': 'mephi', 'position': {'row': 0, 'col': 0},
                'components': {'resources': {'hp': {'initial': mephi_hp}}}}]
    if not mephi_active: initial[0].update(active=False, registration_key='mephi_key')
    if route: initial[0]['route'] = {'motionMode': 'WALK', 'startPosition': {'row': 0, 'col': 0},
                                   'endPosition': {'row': 0, 'col': 15}, 'checkpoints': []}
    if second_mephi: initial.append({'definition': UID, 'instanceAlias': 'mephi2', 'position': {'row': 1, 'col': 0}})
    for c in chars:
        did = 'unit/test/mephi/'+c['alias']
        hp_spec = {'initial': c['hp'], 'capacity_attribute': 'max_hp', 'role': 'health', 'parameters': {'healing_allowed': c['flags'].get('healing_allowed', True)}}
        if c['rate']:
            hp_spec.update(recovery={'mode': 'continuous'}, recovery_rule='rule/ch5/regen/hp_recovery', parameters={'pause_at_full': True})
        state = {'side': c['side'], 'motion': c['motion'], 'category': c['category'], 'unit_type': 2}
        state.update({k: v for k, v in c['flags'].items() if k not in ('healing_allowed', 'mutant')})
        p['entities'].append({'id': did, 'kind': 'entity', 'tags': ['probe_char']+(['mutant'] if c['flags'].get('mutant') else []),
            'components': {'attributes': {'base': {'max_hp': c['maximum'], 'atk': 0, 'def': 999, 'mres': 100,
                'move_speed': 0, 'block_count': 0, 'hp_recovery_per_sec': c['rate']}},
                'resources': {'hp': hp_spec}, 'spatial': {}, 'selection_state': state,
                'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
        initial.append({'definition': did, 'instanceAlias': c['alias'], 'position': {'row': 0, 'col': c['col']}})
    for native, alias, hp, col in regen:
        u = next(u for u in g['entities'] if u['metadata']['native_reference']['id'] == native)
        initial.append({'definition': u['id'], 'instanceAlias': alias, 'position': {'row': 0, 'col': col},
                        'components': {'resources': {'hp': {'initial': hp}}}})
    if kill_at is not None:
        p['selectors'].append({'id': 'selector/test/mephi_kill', 'kind': 'selector', 'region': {'type': 'all'},
                              'filters': [{'tag': 'boss'}, {'state': 'alive'}], 'limit': 1})
        p['abilities'].append({'id': 'ability/test/mephi_kill', 'kind': 'ability', 'selector': 'selector/test/mephi_kill',
            'activation': {'mode': 'manual'}, 'timeline': [{'at': 0, 'effect': {'op': 'damage', 'damage_type': 'physical', 'scale': 1}}]})
        p['entities'].append({'id': 'unit/test/mephi_killer', 'kind': 'entity', 'tags': ['player'],
            'components': {'attributes': {'base': {'max_hp': 5000, 'atk': 50000, 'def': 0, 'mres': 0, 'block_count': 0}},
                'resources': {'hp': {'initial': 5000, 'capacity': 5000, 'role': 'health'}}, 'spatial': {},
                'selection_state': {'side': 0, 'motion': 1, 'category': 1, 'unit_type': 1},
                'abilities': ['ability/test/mephi_kill'], 'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
        initial.append({'definition': 'unit/test/mephi_killer', 'instanceAlias': 'killer', 'position': {'row': 2, 'col': 49}})
    effects = list(deepcopy(extra_effects))
    if mephi_activate is not None:
        effects.append({'at': mephi_activate, 'effect': {'op': 'activate_predefined', 'target': 'battle', 'parameters': {'key': 'mephi_key'}}})
    if source_retire is not None:
        effects.append({'at': source_retire, 'effect': {'op': 'retire', 'target': 2, 'parameters': {'reason': 'dead'}}})
    p['scenarioDraft'] = {'id': 'scene/ch5/mephi/author_probe', 'ruleset': 'ruleset/ark_standard', 'objectives': {},
        'map': {'rows': 3, 'cols': 50}, 'initialEntities': initial, 'scheduledEffects': effects}
    return p, g


def fixture(*args, **kwargs):
    p, g = fixture_package(*args, **kwargs)
    s = Engine.create(Compiler().compile(p, packages=[g]), seed=5510)
    if kwargs.get('kill_at') is not None:
        s.submit({'action': 'skill', 'source': 'killer', 'ability': 'ability/test/mephi_kill'}, at=kwargs['kill_at'])
    return s


def hp(s, alias): return s.ctx.resources.current(alias, 'hp')
def rate(s, alias): return s.ctx.attributes.value(alias, 'hp_recovery_per_sec')
def members(s, alias): return [b for b in s.ctx.get(alias, ('buffs', 'instances'), []) if b['definition'] == MEMBER]
def heals(s): return [e for e in s.session.events if e['type'] == 'healing.accepted']


def test_exact_core_native_shared_heal_and_no_fabricated_skill_sp():
    assert implementation_digest() == 'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'
    p = build(); e = p['manifest']['metadata']['source_evidence']
    assert e['resolved_DB']['attributes']['maxHp'] == 28000 and e['resolved_DB']['attributes']['atk'] == 500
    assert e['mode']['nodes']['_combat']['path_id'] == e['mode']['nodes']['_attack']['path_id']
    assert len(p['abilities']) == 1 and len(p['entities'][0]['components']['resources']) == 1
    assert e['native_selector']['_maxNum'] == 3 and e['native_selector']['_postFilter'] == 3
    assert e['native_aura']['_buffs'][0]['attributes']['attributeModifiers'][0]['attributeType'] == 13


def test_real_aura_doubles_both_native_regenerators_globally_before_first_tick():
    s = fixture(regen=[('enemy_1044_zomstr', 'zomstr', 1000, 30), ('enemy_1043_zomsbr', 'zomsbr', 1000, 31)])
    assert rate(s, 'zomstr') == 400 and rate(s, 'zomsbr') == 160
    assert len(members(s, 'zomstr')) == len(members(s, 'zomsbr')) == 1
    s.session.advance(30)
    assert hp(s, 'zomstr') == pytest.approx(1400, abs=1e-8)
    assert hp(s, 'zomsbr') == pytest.approx(1160, abs=1e-8)
    assert heals(s) == []  # Out of heal radius, but global actual rate multiplier operates.


def test_untagged_qualified_positive_rate_also_doubles_and_zero_remains_zero():
    s = fixture([char('untagged', col=30, rate=40), char('zero', col=31)])
    assert rate(s, 'untagged') == 80 and rate(s, 'zero') == 0
    assert len(members(s, 'untagged')) == len(members(s, 'zero')) == 1
    s.session.advance(30)
    assert hp(s, 'untagged') == pytest.approx(1080, abs=1e-8) and hp(s, 'zero') == 1000


def test_native_mutants_receive_both_real_500_heal_and_doubled_continuous_rate():
    s = fixture(regen=[('enemy_1044_zomstr', 'zomstr', 1000, 10), ('enemy_1043_zomsbr', 'zomsbr', 1000, 11)])
    s.session.advance(34)
    assert [(e['time'], e['payload']['target'], e['payload']['amount']) for e in heals(s)] == [
        (33, s.session.world.resolve('zomstr'), 500), (33, s.session.world.resolve('zomsbr'), 500)]
    assert hp(s, 'zomstr') == pytest.approx(1953.3333333333333, abs=1e-8)
    assert hp(s, 'zomsbr') == pytest.approx(1681.3333333333333, abs=1e-8)


def test_late_real_native_regenerator_joins_existing_aura_before_first_tick():
    gen = json.loads(REGEN.read_bytes())
    uid = next(u['id'] for u in gen['entities'] if u['metadata']['native_reference']['id'] == 'enemy_1044_zomstr')
    p, gen = fixture_package()
    p['scenarioDraft']['dependencies'] = [uid]
    s = Engine.create(Compiler().compile(p, packages=[gen]), seed=5510)
    s.session.advance(20)
    s.ctx.lifecycle.create(uid, {'row': 0, 'col': 30}, alias='late', component_overrides={'resources': {'hp': {'initial': 1000}}})
    assert rate(s, 'late') == 400 and len(members(s, 'late')) == 1
    s.session.advance(30)
    assert hp(s, 'late') == pytest.approx(1400, abs=1e-8) and heals(s) == []


def test_source_reconcile_does_not_duplicate_one_owned_member():
    s = fixture([char('friend', col=30, rate=40)])
    before = members(s, 'friend')[0]['id']
    for _ in range(5): s.ctx.buffs.reconcile()
    assert len(members(s, 'friend')) == 1 and members(s, 'friend')[0]['id'] == before and rate(s, 'friend') == 80


def test_reference_two_source_stacking_and_detach_only_one_parent():
    s = fixture([char('friend', col=30, rate=40)], second_mephi=True)
    assert len(members(s, 'friend')) == 2 and rate(s, 'friend') == 120
    s.ctx.lifecycle.retire('mephi', 'dead')
    assert len(members(s, 'friend')) == 1 and rate(s, 'friend') == 80
    s.ctx.lifecycle.retire('mephi2', 'dead')
    assert members(s, 'friend') == [] and rate(s, 'friend') == 40


@pytest.mark.parametrize('changes,eligible', [({'motion': 2}, True), ({'motion': 0}, False),
    ({'category': 2}, False), ({'category': 4}, False), ({'side': 0, 'mutant': True}, False),
    ({'side': 2}, False), ({'target_free': True}, False), ({'ally_target_free': True}, False),
    ({'camouflage': True}, False), ({'heal_free': True}, True), ({'abnormal_flags': [0]}, True)])
def test_aura_actual_native_mask_and_declared_status_qualification(changes, eligible):
    c = char('friend', col=30, rate=40)
    for key in ('side', 'category', 'motion'):
        if key in changes: c[key] = changes[key]
    c['flags'].update({k: v for k, v in changes.items() if k not in ('side', 'category', 'motion')})
    s = fixture([c]); assert bool(members(s, 'friend')) is eligible
    assert rate(s, 'friend') == (80 if eligible else 40)
    s.session.advance(30)
    assert hp(s, 'friend') == pytest.approx(1080 if eligible else 1040, abs=1e-8)


def test_full_source_all_full_has_no_heal_and_can_walk():
    s = fixture([char('full', hp=10000)], route=True)
    s.session.advance(35)
    assert heals(s) == [] and not s.ctx.get('mephi', ('runtime', 'casts'))
    assert s.ctx.get('mephi', ('spatial', 'position'))['col'] > 0


def test_legacy_player_without_selection_state_never_becomes_boss_ally():
    p, g = fixture_package([char('operator')])
    unit = next(u for u in p['entities'] if u['id'] == 'unit/test/mephi/operator')
    unit['tags'] = ['player']
    del unit['components']['selection_state']
    s = Engine.create(Compiler().compile(p, packages=[g]), seed=5510)
    s.session.advance(34)
    assert members(s, 'operator') == [] and hp(s, 'operator') == 1000 and heals(s) == []


def test_actual_heal33_has_no_early_packet_and_repeats_every180_ticks():
    s = fixture([char('friend')])
    s.session.advance(33); assert hp(s, 'friend') == 1000 and heals(s) == []
    s.session.advance(1); assert hp(s, 'friend') == 1500
    s.session.advance(180)
    assert [(e['time'], e['payload']['amount']) for e in heals(s)] == [(33, 500), (213, 500)]
    assert hp(s, 'friend') == 2000


def test_three_lowest_injured_ratios_once_each_not_duplicate_combat_and_attack():
    s = fixture([char('a', hp=6000), char('b', hp=1000, col=2), char('c', hp=3000, col=3), char('d', hp=2000, col=4)])
    s.session.advance(34)
    assert [e['payload']['target'] for e in heals(s)] == [s.session.world.resolve(a) for a in ('b', 'd', 'c')]
    assert [hp(s, a) for a in ('a', 'b', 'c', 'd')] == [6000, 1500, 3500, 2500]


def test_source_may_heal_self_and_saturation_uses_remaining_headroom():
    s = fixture(mephi_hp=27990)
    s.session.advance(34)
    assert hp(s, 'mephi') == 28000
    assert [(e['time'], e['payload']['target'], e['payload']['amount']) for e in heals(s)] == [(33, s.session.world.resolve('mephi'), 10)]


@pytest.mark.parametrize('changes', [{'side': 0}, {'side': 2}, {'category': 2}, {'target_free': True},
    {'ally_target_free': True}, {'heal_free': True}, {'camouflage': True}, {'healing_allowed': False}])
def test_heal_qualifies_injured_allies_and_respects_native_status_flags(changes):
    c = char('noheal')
    for key in ('side', 'category', 'motion'):
        if key in changes: c[key] = changes[key]
    c['flags'].update({k: v for k, v in changes.items() if k not in ('side', 'category', 'motion')})
    s = fixture([c]); s.session.advance(34)
    assert hp(s, 'noheal') == 1000 and heals(s) == []


@pytest.mark.parametrize('motion', [1, 2])
def test_heal_both_source_motion_masks(motion):
    s = fixture([char('friend', motion=motion)]); s.session.advance(34)
    assert hp(s, 'friend') == 1500


@pytest.mark.parametrize('col,expected', [(20, 1500), (20.0001, 1000)])
def test_db_scaled_radius20_inclusive_boundary(col, expected):
    s = fixture([char('friend', col=col)]); s.session.advance(34)
    assert hp(s, 'friend') == expected


def test_hp_ratio_ties_are_stable_id_not_taunt_or_distance():
    s = fixture([char('far', col=19), char('near', col=1), char('mid', col=10), char('fourth', col=2)])
    s.session.advance(34)
    assert [e['payload']['target'] for e in heals(s)] == [s.session.world.resolve(a) for a in ('far', 'near', 'mid')]
    assert hp(s, 'fourth') == 1000


def test_beginning_capture_does_not_retarget_new_low_ratio_during_windup():
    effects = [{'at': 10, 'effect': {'op': 'modify_resource', 'target': 3, 'resource': 'hp', 'value': 1}}]
    s = fixture([char('a', hp=6000), char('b', hp=1000, col=2), char('c', hp=3000, col=3), char('d', hp=2000, col=4)], extra_effects=effects)
    s.session.advance(34)
    assert [e['payload']['target'] for e in heals(s)] == [s.session.world.resolve(a) for a in ('b', 'd', 'c')]
    assert hp(s, 'a') == 1


def test_dead_captured_target_is_skipped_without_retargeting_fourth():
    effects = [{'at': 10, 'effect': {'op': 'retire', 'target': 3, 'parameters': {'reason': 'dead'}}}]
    s = fixture([char('a'), char('b', col=2), char('c', col=3), char('d', col=4)], extra_effects=effects)
    s.session.advance(34)
    assert not s.ctx.alive('a')
    assert [e['payload']['target'] for e in heals(s)] == [s.session.world.resolve(a) for a in ('b', 'c')]
    assert hp(s, 'd') == 1000


def test_source_death_detaches_real_rate_aura_and_cancels_pending_heal():
    s = fixture([char('inrange')], regen=[('enemy_1044_zomstr', 'zomstr', 1000, 30),
        ('enemy_1043_zomsbr', 'zomsbr', 1000, 31)], source_retire=15)
    s.session.advance(15); assert rate(s, 'zomstr') == 400
    s.session.advance(1); assert not s.ctx.alive('mephi')
    assert members(s, 'zomstr') == [] and rate(s, 'zomstr') == 200 and rate(s, 'zomsbr') == 80
    s.session.advance(18)
    assert heals(s) == [] and hp(s, 'inrange') == 1000
    assert hp(s, 'zomstr') == pytest.approx(1326.6666666666667, abs=1e-8)


def test_initial_dormant_source_has_no_aura_or_heal_before_exact_activation():
    s = fixture([char('friend')], regen=[('enemy_1044_zomstr', 'zomstr', 1000, 30)], mephi_active=False, mephi_activate=20)
    s.session.advance(20); assert rate(s, 'zomstr') == 200 and members(s, 'zomstr') == []
    s.session.advance(1); assert rate(s, 'zomstr') == 400 and len(members(s, 'zomstr')) == 1
    s.session.advance(33)
    assert [(e['time'], e['payload']['amount']) for e in heals(s)] == [(53, 500)]


def test_actual_damage_hp_death_removes_aura_and_pending_heal():
    s = fixture([char('friend')], regen=[('enemy_1044_zomstr', 'zomstr', 1000, 30),
        ('enemy_1043_zomsbr', 'zomsbr', 1000, 31)], kill_at=10)
    s.session.advance(11)
    damage = [e for e in s.session.events if e['type'] == 'damage.accepted']
    # The 49800 physical packet credits only the remaining 28000 HP.
    assert [(e['time'], e['payload']['amount']) for e in damage] == [(10, 28000)]
    assert hp(s, 'mephi') == 0 and not s.ctx.alive('mephi') and not s.ctx.state()['finished']
    assert rate(s, 'zomstr') == 200 and rate(s, 'zomsbr') == 80 and members(s, 'zomstr') == []
    s.session.advance(23)
    assert heals(s) == [] and hp(s, 'friend') == 1000
    assert hp(s, 'zomstr') == pytest.approx(1300, abs=1e-8)
    assert hp(s, 'zomsbr') == pytest.approx(1120, abs=1e-8)


def test_injured_trigger_stops_motion_purely_and_does_not_emit_fake_heals():
    s = fixture([char('friend')], route=True); s.session.advance(33)
    assert s.ctx.get('mephi', ('spatial', 'position')) == {'row': 0, 'col': 0}
    assert heals(s) == []


@pytest.mark.parametrize('source_retire', [None, 15])
def test_durable_cp_and_replay_restore_pending_heal_owned_members_and_rates(tmp_path, source_retire):
    s = fixture([char('friend')], regen=[('enemy_1044_zomstr', 'zomstr', 1000, 30),
        ('enemy_1043_zomsbr', 'zomsbr', 1000, 31)], source_retire=source_retire)
    s.session.advance(10)
    path = tmp_path/'actual.mephi.json'; pin = write_ordered(path, s.checkpoint())
    restored = Engine.restore(s.program, load_bound(path, pin))
    s.session.advance(50); restored.session.advance(50)
    repeated = replay(s.program, s.export_replay())
    assert s.snapshot() == restored.snapshot() == repeated.snapshot()
    assert [rate(sim, 'zomstr') for sim in (s, restored, repeated)] == [400 if source_retire is None else 200]*3


def test_public_damage_command_cp_replay_preserves_source_death_and_rate_boundary(tmp_path):
    s = fixture([char('friend')], regen=[('enemy_1044_zomstr', 'zomstr', 1000, 30),
        ('enemy_1043_zomsbr', 'zomsbr', 1000, 31)], kill_at=10)
    s.session.advance(5)
    path = tmp_path/'actual.damage_command.json'; pin = write_ordered(path, s.checkpoint())
    restored = Engine.restore(s.program, load_bound(path, pin))
    s.session.advance(55); restored.session.advance(55)
    repeated = replay(s.program, s.export_replay())
    assert s.snapshot() == restored.snapshot() == repeated.snapshot()
    assert hp(s, 'mephi') == 0 and heals(s) == []
    assert hp(s, 'zomstr') == pytest.approx(1473.3333333333333, abs=1e-8)
    assert hp(s, 'zomsbr') == pytest.approx(1189.3333333333333, abs=1e-8)
