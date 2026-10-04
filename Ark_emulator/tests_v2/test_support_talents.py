"""Actual support models: source guards, residence clocks, live aura and heal cadence."""
from copy import deepcopy
import json
import pytest
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_campaign_support_talents import ROOT, OUTPUT, build, mon3tr_model_fixture, cannon_model_fixture


@pytest.fixture(scope='module')
def package():
    return json.loads(OUTPUT.read_bytes())


def only(data, name, injured=0):
    value = deepcopy(data)
    value['scenarioDraft']['initialEntities'] = [x for x in value['scenarioDraft']['initialEntities'] if x['instanceAlias'] == name]
    value['scenarioDraft']['initialEntities'] += [{'definition': 'unit/support_injured', 'instanceAlias': 'ally' + str(i),
        'position': {'row': 7, 'col': 8}} for i in range(injured)]
    return value


def events(sim, kind):
    return [x for x in sim.session.events if x['type'] == kind]


def test_rebuild_and_all_applicable_talents_are_recorded_without_complete_claim(package):
    assert build() == package
    evidence = package['manifest']['metadata']['source_evidence']
    assert len(evidence['operators']) == 6
    assert sum(len(x['selected_talents']) for x in evidence['operators'].values()) == 11
    assert package['manifest']['metadata']['official_unit_complete'] is False
    with pytest.raises(ValueError, match='complete.*unsupported'):
        build(require_complete=True)
    Compiler().compile(package)


def test_saria_residence_twenty_seconds_caps_at_five_and_new_instance_resets(package):
    data = only(package, 'demkni')
    sim = Engine.create(Compiler().compile(data))
    atk, defense = sim.ctx.attributes.value('demkni', 'atk'), sim.ctx.attributes.value('demkni', 'def')
    sim.advance(599)
    assert sim.ctx.attributes.value('demkni', 'atk') == atk
    sim.advance(1)
    assert sim.ctx.attributes.value('demkni', 'atk') == pytest.approx(atk * 1.05)
    sim.advance(2400)
    assert sim.ctx.attributes.value('demkni', 'atk') == pytest.approx(atk * 1.25)
    assert sim.ctx.attributes.value('demkni', 'def') == pytest.approx(defense * 1.20)
    sim.advance(300)
    assert sim.ctx.attributes.value('demkni', 'atk') == pytest.approx(atk * 1.25)
    fresh = Engine.create(Compiler().compile(data))
    assert fresh.ctx.attributes.value('demkni', 'atk') == atk


def test_night_base_res_aura_moves_and_source_retirement_cleans_members(package):
    sim = Engine.create(Compiler().compile(only(package, 'cgbird', 1)))
    assert sim.ctx.attributes.value('ally0', 'mres') == 25
    sim.ctx.movement.displace('ally0', 'ally0', {'position': {'row': 0, 'col': 0}}, {})
    assert sim.ctx.attributes.value('ally0', 'mres') == 10
    sim.ctx.movement.displace('ally0', 'ally0', {'position': {'row': 7, 'col': 8}}, {})
    assert sim.ctx.attributes.value('ally0', 'mres') == 25
    sim.ctx.lifecycle.retire(sim.session.world.resolve('cgbird'), 'withdrawn')
    assert sim.ctx.attributes.value('ally0', 'mres') == 10


@pytest.mark.parametrize('name', ['plosis', 'cgbird'])
def test_sustained_heal_selects_three_injured_and_repeats_native_model_interval(package, name):
    data = only(package, name, 4)
    actor = next(x for x in data['entities'] if x['id'] == 'unit/support_' + name)
    actor['components']['resources']['sp']['initial'] = actor['components']['resources']['sp']['capacity']
    sim = Engine.create(Compiler().compile(data))
    sim.submit({'action': 'skill', 'source': name, 'ability': 'ability/support_' + name + '_skill'})
    sim.advance(28 if name == 'cgbird' else 8)
    first = events(sim, 'healing.accepted')
    assert len(first) == 3
    assert all(x['payload']['target'] != sim.session.world.resolve(name) for x in first)
    assert sim.ctx.resources.current(name, 'sp') == 0
    sim.advance(86 if name == 'cgbird' else 23)
    assert len(events(sim, 'healing.accepted')) == 6
    targets = {x['payload']['target'] for x in events(sim, 'healing.accepted')}
    assert len(targets) == 4  # fourth injured actor is selected after first packet changes health ranking.
    if name == 'plosis':
        assert sim.ctx.attributes.value(name, 'attack_interval') == pytest.approx(.75)
    else:
        assert sim.ctx.attributes.value('ally0', 'mres') == pytest.approx(62.5)


def test_sustained_mode_half_open_end_and_checkpoint_replay(package):
    data = only(package, 'plosis', 3)
    actor = next(x for x in data['entities'] if x['id'] == 'unit/support_plosis')
    actor['components']['resources']['sp']['initial'] = 100
    program = Compiler().compile(data)
    sim = Engine.create(program)
    sim.submit({'action': 'skill', 'source': 'plosis', 'ability': 'ability/support_plosis_skill'})
    sim.advance(1100)
    restored = Engine.restore(program, sim.checkpoint())
    sim.advance(101)
    restored.advance(101)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None
    assert sim.ctx.resources.current('plosis', 'mode') == 0
    assert sim.ctx.attributes.value('plosis', 'attack_interval') == 2.85
    assert all(e['time'] < 1200 for e in events(sim, 'healing.accepted'))


def test_highest_only_sp_aura_profession_and_retirement_change_real_recovery(package):
    data = deepcopy(package)
    data['scenarioDraft']['initialEntities'] = [x for x in data['scenarioDraft']['initialEntities'] if x['instanceAlias'] in ('plosis', 'lisa', 'demkni')]
    sim = Engine.create(Compiler().compile(data))
    assert sim.ctx.attributes.value('lisa', 'sp_recovery_rate') == pytest.approx(1.4)
    assert sim.ctx.attributes.value('demkni', 'sp_recovery_rate') == pytest.approx(1.3)
    initial_lisa_sp = sim.ctx.resources.current('lisa', 'sp')
    sim.advance(30)
    assert sim.ctx.resources.current('lisa', 'sp') == pytest.approx(initial_lisa_sp + 1.4)
    assert sim.ctx.resources.current('demkni', 'sp') == pytest.approx(1.3)
    sim.ctx.lifecycle.retire(sim.session.world.resolve('lisa'), 'withdrawn')
    sim.advance(30)
    assert sim.ctx.resources.current('demkni', 'sp') == pytest.approx(2.6)
    sim.ctx.lifecycle.retire(sim.session.world.resolve('plosis'), 'withdrawn')
    sim.advance(30)
    assert sim.ctx.resources.current('demkni', 'sp') == pytest.approx(3.6)


def test_saria_heal_sp_only_own_packets_freezes_recipient_and_skips_no_sp(package):
    data = deepcopy(package)
    data['scenarioDraft']['initialEntities'] = [x for x in data['scenarioDraft']['initialEntities'] if x['instanceAlias'] in ('demkni', 'plosis')]
    data['scenarioDraft']['initialEntities'].append({'definition': 'unit/support_injured', 'instanceAlias': 'without_sp', 'position': {'row': 7, 'col': 8}})
    selector = {'id': 'selector/heal_sp_review', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'plosis'}], 'limit': 1}
    ability = {'id': 'ability/heal_sp_review', 'kind': 'ability', 'parameters': {'healing': True},
        'activation': {'mode': 'manual'}, 'selector': selector['id'], 'timeline': [{'at': 0, 'effect': {'op': 'heal', 'scale': .001}}]}
    data['selectors'].append(selector)
    data['abilities'].append(ability)
    for actor in data['entities']:
        if actor['id'] in ('unit/support_demkni', 'unit/support_plosis'):
            actor['components']['abilities'].append(ability['id'])
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.resources.adjust('plosis', 'sp', value=0)
    sim.ctx.resources.adjust('plosis', 'hp', delta=-20)
    sim.ctx.abilities.start('demkni', ability['id'])
    sim.advance(1)
    assert sim.ctx.resources.current('plosis', 'sp') == pytest.approx(1 + 1.3/30)
    previous = sim.ctx.resources.current('plosis', 'sp')
    sim.ctx.abilities.start('plosis', ability['id'])
    sim.advance(1)
    assert sim.ctx.resources.current('plosis', 'sp') == previous  # its own manual probe also freezes time recovery.
    # Use a genuine ongoing selected skill to freeze its SP.
    sim.ctx.resources.adjust('plosis', 'sp', value=100)
    sim.ctx.abilities.start('plosis', 'ability/support_plosis_skill')
    sim.ctx.abilities.start('demkni', ability['id'])
    sim.advance(1)
    assert sim.ctx.resources.current('plosis', 'sp') == 0
    attack = sim.ctx.attributes.value('demkni', 'atk')
    sim.ctx.effects.execute('demkni', ['without_sp'], {'op': 'heal', 'scale': 1})
    assert sim.ctx.resources.current('without_sp', 'hp') == 100 + attack


def test_saria_emission_time_recipient_freeze_survives_same_tick_finish(package):
    data = only(package, 'demkni')
    data['scenarioDraft']['initialEntities'].append({'definition': 'unit/support_plosis', 'instanceAlias': 'plosis',
        'position': {'row': 7, 'col': 8}})
    data['selectors'].append({'id': 'selector/saria_freeze_review', 'kind': 'selector', 'region': {'type': 'all'},
        'filters': [{'tag': 'plosis'}], 'limit': 1})
    data['abilities'] += [{'id': 'ability/saria_freeze_heal_review', 'kind': 'ability', 'parameters': {'healing': True},
        'activation': {'mode': 'manual'}, 'selector': 'selector/saria_freeze_review', 'timeline': [{'at': 1, 'effect': {'op': 'heal', 'scale': .001}}]},
        {'id': 'ability/recipient_freeze_hold_review', 'kind': 'ability', 'activation': {'mode': 'manual'},
            'duration_seconds': 1/30, 'timeline': []}]
    for actor in data['entities']:
        if actor['id'] == 'unit/support_demkni':
            actor['components']['abilities'].append('ability/saria_freeze_heal_review')
        elif actor['id'] == 'unit/support_plosis':
            actor['components']['abilities'].append('ability/recipient_freeze_hold_review')
            actor['components']['resources']['sp']['initial'] = 0
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.resources.adjust('plosis', 'hp', delta=-10)
    # Queue the heal effect before the recipient finish, at the identical time.
    sim.ctx.abilities.start('demkni', 'ability/saria_freeze_heal_review')
    sim.ctx.abilities.start('plosis', 'ability/recipient_freeze_hold_review')
    sim.advance(2)
    heal = events(sim, 'healing.accepted')[0]
    finish = next(x for x in events(sim, 'ability.finished') if x['payload']['ability'] == 'ability/recipient_freeze_hold_review')
    assert heal['time'] == finish['time'] == 1
    assert heal['id'] < finish['id']
    assert sim.ctx.resources.current('plosis', 'sp') == 0


def test_night_magic_dodge_real_rng_accepts_physical_without_draw(package):
    data = only(package, 'cgbird', 1)
    actor = next(x for x in data['entities'] if x['id'] == 'unit/support_cgbird')
    actor['components']['resources']['sp']['initial'] = actor['components']['resources']['sp']['capacity']
    sim = Engine.create(Compiler().compile(data), seed=23)
    sim.ctx.abilities.start('cgbird', 'ability/support_cgbird_skill')
    sim.ctx.resources.adjust('ally0', 'hp', value=10000)
    before = deepcopy(sim.session.random.snapshot())
    sim.ctx.effects.execute('cgbird', ['ally0'], {'op': 'damage', 'damage_type': 'physical', 'amount': 10})
    assert sim.session.random.snapshot() == before
    before = deepcopy(sim.session.random.snapshot())
    for _ in range(12):
        sim.ctx.effects.execute('cgbird', ['ally0'], {'op': 'damage', 'damage_type': 'arts', 'amount': 10})
    assert sim.session.random.snapshot() != before
    assert events(sim, 'damage.rejected')
    assert events(sim, 'damage.accepted')


def lisa_scene(package, second=False):
    data = only(package, 'lisa')
    data['scenarioDraft']['initialEntities'].append({'definition': 'unit/support_enemy', 'instanceAlias': 'victim', 'position': {'row': 7, 'col': 8}})
    if second:
        data['scenarioDraft']['initialEntities'].append({'definition': 'unit/support_lisa', 'instanceAlias': 'lisa2', 'position': {'row': 7, 'col': 7}, 'facing': 'right'})
    return data


def test_sluggish_fragile_live_condition_overlap_highest_and_exit(package):
    sim = Engine.create(Compiler().compile(lisa_scene(package, second=True)))
    effect = {'op': 'damage', 'damage_type': 'true', 'scale': 0, 'additions': 100}
    sim.ctx.effects.execute('lisa', ['victim'], effect)
    assert events(sim, 'damage.accepted')[-1]['payload']['amount'] == 100
    sim.ctx.buffs.apply('lisa', 'victim', 'buff/support_sluggish')
    sim.ctx.effects.execute('lisa', ['victim'], effect)
    assert events(sim, 'damage.accepted')[-1]['payload']['amount'] == pytest.approx(120)
    sim.ctx.lifecycle.retire(sim.session.world.resolve('lisa2'), 'withdrawn')
    sim.ctx.effects.execute('lisa', ['victim'], effect)
    assert events(sim, 'damage.accepted')[-1]['payload']['amount'] == pytest.approx(120)
    sim.ctx.movement.displace('victim', 'victim', {'position': {'row': 0, 'col': 0}}, {})
    sim.ctx.effects.execute('lisa', ['victim'], effect)
    assert events(sim, 'damage.accepted')[-1]['payload']['amount'] == 100


def test_ineligible_hook_modifier_does_not_ghost_amplify_active_fragility(package):
    data = lisa_scene(package)
    data['buffs'].append({'id': 'buff/ghost_fragile_review', 'kind': 'buff',
        'modifiers': [{'attribute': 'fragile_factor', 'layer': 'fragility', 'value': .8}],
        'damage_hooks': [{'phase': 'after', 'rule': 'rule/support_fragility_s3', 'group': 'fragility', 'priority': .8, 'condition': 'False'}]})
    data['scenarioDraft']['dependencies'] = ['buff/ghost_fragile_review']
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.buffs.apply('lisa', 'victim', 'buff/support_sluggish')
    sim.ctx.buffs.apply('lisa', 'victim', 'buff/ghost_fragile_review')
    sim.ctx.effects.execute('lisa', ['victim'], {'op': 'damage', 'damage_type': 'true', 'scale': 0, 'additions': 100})
    assert events(sim, 'damage.accepted')[-1]['payload']['amount'] == pytest.approx(120)


def test_suzu_s3_double_delta_half_open_slow_and_fragility(package):
    data = lisa_scene(package)
    actor = next(x for x in data['entities'] if x['id'] == 'unit/support_lisa')
    actor['components']['resources']['sp']['initial'] = actor['components']['resources']['sp']['capacity']
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.abilities.start('lisa', 'ability/support_lisa_s3')
    assert sim.ctx.attributes.value('victim', 'move_speed') == pytest.approx(.2, abs=1e-6)
    sim.ctx.effects.execute('lisa', ['victim'], {'op': 'damage', 'damage_type': 'true', 'scale': 0, 'additions': 100})
    assert events(sim, 'damage.accepted')[-1]['payload']['amount'] == pytest.approx(140)
    sim.advance(1050)
    sim.advance(1)
    assert sim.ctx.attributes.value('victim', 'move_speed') == 1
    sim.ctx.effects.execute('lisa', ['victim'], {'op': 'damage', 'damage_type': 'true', 'scale': 0, 'additions': 100})
    assert events(sim, 'damage.accepted')[-1]['payload']['amount'] == 100


def test_overlapping_suzu_s3_slows_once_and_regenerates_without_heal_events(package):
    data = lisa_scene(package, second=True)
    actor = next(x for x in data['entities'] if x['id'] == 'unit/support_lisa')
    actor['components']['resources']['sp']['initial'] = actor['components']['resources']['sp']['capacity']
    data['scenarioDraft']['initialEntities'].append({'definition': 'unit/support_injured', 'instanceAlias': 'patient', 'position': {'row': 7, 'col': 8}})
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.abilities.start('lisa', 'ability/support_lisa_s3')
    sim.ctx.abilities.start('lisa2', 'ability/support_lisa_s3')
    assert sim.ctx.attributes.value('victim', 'move_speed') == pytest.approx(.2, abs=1e-6)
    sim.ctx.effects.execute('lisa', ['victim'], {'op': 'damage', 'damage_type': 'true', 'scale': 0, 'additions': 100})
    assert events(sim, 'damage.accepted')[-1]['payload']['amount'] == pytest.approx(140)
    sim.advance(31)
    assert sim.ctx.resources.current('patient', 'hp') == pytest.approx(100 + 2 * actor['components']['attributes']['base']['atk'] * .2)
    assert events(sim, 'regeneration.accepted')
    assert not events(sim, 'healing.accepted')


def test_fragile_mixed_allocations_scale_health_only_and_preserve_events(package):
    data = lisa_scene(package)
    enemy = next(x for x in data['entities'] if x['id'] == 'unit/support_enemy')
    enemy['components']['resources']['shield_charge'] = {'initial': 1, 'capacity': 1}
    data['rules'].append({'id': 'rule/support_mixed_alloc_probe', 'kind': 'calculation_rule', 'contract': 'damage.pipeline',
        'implementation': {'type': 'graph', 'nodes': [{'id': 'result', 'expression':
            "{'accepted':True,'amount':100,'allocations':[{'target':'target','resource':'shield_charge','amount':1},{'target':'target','resource':'hp','amount':100}],'events':[{'type':'support.alloc.probe','payload':{}}]}"}], 'output': 'nodes.result'}})
    data['scenarioDraft']['dependencies'] = ['rule/support_mixed_alloc_probe']
    sim = Engine.create(Compiler().compile(data))
    sim.ctx.buffs.apply('lisa', 'victim', 'buff/support_sluggish')
    sim.ctx.effects.execute('lisa', ['victim'], {'op': 'damage', 'damage_type': 'true',
        'rules': {'damage.pipeline': 'rule/support_mixed_alloc_probe'}})
    assert sim.ctx.resources.current('victim', 'shield_charge') == 0
    assert sim.ctx.resources.current('victim', 'hp') == pytest.approx(99880)
    assert events(sim, 'damage.accepted')[-1]['payload']['amount'] == pytest.approx(120)
    assert len(events(sim, 'support.alloc.probe')) == 1


def token(sim):
    return next(x['id'] for x in sim.session.world.entities() if x['definition_id'] == 'unit/kalts_mon3tr_model')


def test_default_token_exact_mapping_payload_and_source_hash_guards():
    import base64, hashlib
    from tools.extract_campaign_support_token_sources import build as source_build, OUTPUT as token_output
    data = json.loads(token_output.read_bytes())
    assert source_build() == data
    native = data['tokens']['token_10002_kalts_mon3tr']
    raw = base64.b64decode(native['skeletons']['single']['payload_base64'])
    assert hashlib.sha256(raw).hexdigest() == native['skeletons']['single']['payload_sha256']
    assert [m['exact_bindings']['single']['events'][0]['frame'] for m in native['modes']] == [7, 11, 20]
    assert native['skeletons']['single']['native_name'] == 'token_10002_kalts_mon3tr.skel'
    assert data['source_version_matches_local'] is False


def test_mon3tr_real_auto_normal_windup_repeat_and_manual_command_rejection():
    sim = Engine.create(Compiler().compile(mon3tr_model_fixture()))
    sim.submit({'action': 'skill', 'source': 'host', 'ability': 'ability/kalts_summon'})
    sim.advance(7)
    assert sim.ctx.resources.current('enemy', 'hp') == 100000
    sim.advance(1)
    assert sim.ctx.resources.current('enemy', 'hp') == 100000 - 1345 * .05
    assert [x['time'] for x in events(sim, 'damage.accepted') if x['payload']['ability'] == 'ability/mon3tr_normal_probe'] == [7]
    checkpoint = sim.checkpoint()
    with pytest.raises(ValueError, match='Automatic-only'):
        sim.ctx.abilities.start(token(sim), 'ability/mon3tr_normal_probe')
    assert sim.checkpoint() == checkpoint
    sim.advance(60)
    assert [x['time'] for x in events(sim, 'damage.accepted') if x['payload']['ability'] == 'ability/mon3tr_normal_probe'] == [7, 67]


def test_mon3tr_s3_automatic_true_packet_uses_source_frame_twenty_and_live_curve():
    sim = Engine.create(Compiler().compile(mon3tr_model_fixture()))
    sim.submit({'action': 'skill', 'source': 'host', 'ability': 'ability/kalts_summon'})
    sim.advance(8)
    sim.ctx.resources.adjust('host', 'sp', value=15)
    sim.submit({'action': 'skill', 'source': 'host', 'ability': 'ability/kalts_host_s3'})
    sim.advance(72)
    assert not [x for x in events(sim, 'damage.accepted') if x['payload']['ability'] == 'ability/mon3tr_true_probe']
    sim.advance(1)
    packets = [x for x in events(sim, 'damage.accepted') if x['payload']['ability'] == 'ability/mon3tr_true_probe']
    assert [x['time'] for x in packets] == [80]  # next_attack60 + source f20, preserving declared model cadence clock.
    assert packets[0]['payload']['amount'] == pytest.approx(1345 * (1 + 2.6 * (1 - 2.4 / 20)))


@pytest.mark.parametrize('retired', [False, True])
def test_mon3tr_death_native_value_stun_and_withdraw_exclusion(retired):
    sim = Engine.create(Compiler().compile(mon3tr_model_fixture()))
    sim.submit({'action': 'skill', 'source': 'host', 'ability': 'ability/kalts_summon'})
    sim.advance(1)
    uid = token(sim)
    if retired:
        sim.ctx.lifecycle.retire(uid, 'withdrawn')
        assert sim.ctx.resources.current('enemy', 'hp') == 100000
        assert sim.ctx.buffs.controls('enemy')['attack'] is True
    else:
        sim.ctx.resources.adjust(uid, 'hp', value=0)
        sim.advance(1)
        assert sim.ctx.resources.current('enemy', 'hp') == 98800
        assert events(sim, 'damage.accepted')[-1]['payload']['source'] == uid
        assert sim.ctx.buffs.controls('enemy')['attack'] is False
        assert sim.ctx.buffs.controls('enemy')['move'] is False
        sim.advance(90)
        sim.advance(1)
        assert sim.ctx.buffs.controls('enemy')['attack'] is True


def test_mon3tr_automatic_source_clock_checkpoint_and_replay():
    program = Compiler().compile(mon3tr_model_fixture())
    sim = Engine.create(program)
    sim.submit({'action': 'skill', 'source': 'host', 'ability': 'ability/kalts_summon'})
    sim.advance(3)
    restored = Engine.restore(program, sim.checkpoint())
    sim.advance(68)
    restored.advance(68)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None


def birds(sim):
    return [x['id'] for x in sim.session.world.entities() if x['definition_id'] == 'unit/support_night_bird']


def test_night_bird_two_cards_dp_and_failed_third_are_atomic(package):
    sim = Engine.create(Compiler().compile(only(package, 'cgbird')))
    for _ in range(2):
        sim.submit({'action': 'skill', 'source': 'cgbird', 'ability': 'ability/support_night_bird'})
        sim.advance(1)
    assert len(birds(sim)) == 2
    assert sim.ctx.resources.current('cgbird', 'bird_cards') == 0
    assert sim.ctx.resources.current('system/battle', 'dp') == 10
    checkpoint = sim.checkpoint()
    with pytest.raises(ValueError, match='insufficient resource'):
        sim.ctx.abilities.start('cgbird', 'ability/support_night_bird')
    assert sim.checkpoint() == checkpoint
    assert not [x for x in events(sim, 'ability.started') if x['payload']['source'] in birds(sim)]
    assert all(sim.ctx.attributes.value(uid, 'block_count') == 0 for uid in birds(sim))


def test_bird_heal_free_tick_selfloss_and_owner_retire_cleanup(package):
    sim = Engine.create(Compiler().compile(only(package, 'cgbird')))
    sim.submit({'action': 'skill', 'source': 'cgbird', 'ability': 'ability/support_night_bird'})
    sim.advance(30)
    uid = birds(sim)[0]
    assert sim.ctx.resources.current(uid, 'hp') == 5326
    sim.advance(1)
    assert sim.ctx.resources.current(uid, 'hp') == pytest.approx(5326 * .97)
    before = sim.ctx.resources.current(uid, 'hp')
    sim.ctx.effects.execute('cgbird', [uid], {'op': 'heal', 'scale': 1})
    assert sim.ctx.resources.current(uid, 'hp') == before
    assert events(sim, 'healing.rejected')[-1]['payload']['reason'] == 'resource_healing_disabled'
    sim.ctx.lifecycle.retire(sim.session.world.resolve('cgbird'), 'withdrawn')
    assert not sim.ctx.alive(uid)


def test_bird_taunt_pure_model_selection_no_attack_and_checkpoint(package):
    data = only(package, 'cgbird', 1)
    data['scenarioDraft']['initialEntities'].append({'definition': 'unit/support_enemy', 'instanceAlias': 'attacker', 'position': {'row': 7, 'col': 10}})
    enemy = next(x for x in data['entities'] if x['id'] == 'unit/support_enemy')
    enemy['rules']['targeting.score'] = 'rule/support_taunt_score'
    data['scenarioDraft']['dependencies'] = ['rule/support_taunt_score']
    data['selectors'].append({'id': 'selector/bird_taunt_review', 'kind': 'selector', 'region': {'type': 'all'},
        'filters': [{'tag': 'player'}, {'state': 'alive'}], 'limit': 1})
    data['scenarioDraft']['dependencies'].append('selector/bird_taunt_review')
    program = Compiler().compile(data)
    sim = Engine.create(program)
    sim.submit({'action': 'skill', 'source': 'cgbird', 'ability': 'ability/support_night_bird'})
    sim.advance(12)
    restored = Engine.restore(program, sim.checkpoint())
    sim.advance(25)
    restored.advance(25)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None
    assert sim.ctx.spatial.select('attacker', 'selector/bird_taunt_review') == birds(sim)


@pytest.mark.parametrize('cause', ['hp_drop', 'enemy_true_damage'])
def test_bird_real_health_exhaustion_retires_without_owner_retreat(package, cause):
    data = only(package, 'cgbird')
    data['scenarioDraft']['initialEntities'].append({'definition': 'unit/support_enemy', 'instanceAlias': 'enemy',
        'position': {'row': 7, 'col': 9}})
    sim = Engine.create(Compiler().compile(data))
    sim.submit({'action': 'skill', 'source': 'cgbird', 'ability': 'ability/support_night_bird'})
    sim.advance(1)
    uid = birds(sim)[0]
    if cause == 'hp_drop':
        # The next source-backed 3% pulse is enough to exhaust this injured bird.
        sim.ctx.resources.adjust(uid, 'hp', value=100)
        sim.advance(30)
    else:
        sim.ctx.effects.execute('enemy', [uid], {'op': 'damage', 'damage_type': 'true', 'scale': 0, 'additions': 6000})
    assert sim.ctx.alive('cgbird') is True
    assert sim.ctx.resources.current(uid, 'hp') == 0
    assert sim.ctx.alive(uid) is False
    assert sim.ctx.get(uid, ('runtime', 'state')) == 'dead'
    assert events(sim, 'entity.died')[-1]['payload']['target'] == uid


def test_cannon_default_loop_packet_waits_for_real_projectile_travel():
    data = cannon_model_fixture()
    # Isolate the packet/travel amount from the historical armor-minimum fixture.
    next(x for x in data['entities'] if x['id'] == 'unit/weedy_force_probe')['components']['attributes']['base']['def'] = 0
    sim = Engine.create(Compiler().compile(data))
    sim.submit({'action': 'skill', 'source': 'weedy', 'ability': 'ability/campaign_weedy_deploy_cannon'})
    sim.advance(2)
    assert [x['time'] for x in events(sim, 'projectile.launched')] == [1]
    assert not events(sim, 'damage.accepted')
    sim.advance(3)
    assert events(sim, 'damage.accepted')[0]['time'] == 4
    assert events(sim, 'damage.accepted')[0]['payload']['amount'] == 561
    assert events(sim, 'damage.accepted')[0]['payload']['ability'] == 'ability/support_cannon_normal'


def test_integration_patch_ids_and_selected_overrides_do_not_replace_native_stats(package):
    meta = package['manifest']['metadata']
    assert len(meta['unit_patches']) == 6
    assert all(k.startswith('unit/char_') for k in meta['unit_patches'])
    for patch in meta['unit_patches'].values():
        assert patch['attributes_merge_policy'] == 'setdefault'
        assert set(patch['attributes']) == {'sp_recovery_rate'}
        assert 'hp' not in patch['resources']
        assert patch['time_resource_patch']['preserve_selector_and_freeze'] is True
    assert {'ability/plosis_s2_first_packet', 'ability/cgbird_s3', 'ability/lisa_s3'} <= set(meta['skill_definition_overrides'])
    assert set(meta['token_definition_overrides']) == {'unit/kalts_mon3tr_model', 'unit/campaign_weedy_cannon', 'unit/support_night_bird'}
    assert meta['token_definition_overrides']['unit/support_night_bird']['components']['deployable']['capacity'] == 0
