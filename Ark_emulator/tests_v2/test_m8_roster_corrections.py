"""Receiver shield on canonical actors, with native defense and talent SP preserved."""
import json
import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_m8_roster_corrections import ROOT, build


def scene(initial_sp=0, damage_type='true', revised=True):
    path = ROOT/'packages/campaign/mainline_models/level_main_00-10.m8_damage.json'
    data = build(path) if revised else json.loads(path.read_bytes())
    data['scenarioDraft'].update(id='scenario/canonical_liskam_shield_probe', waves=[], objectives={}, initialEntities=[
        {'definition': 'unit/char_107_liskam', 'instanceAlias': 'liskam', 'position': {'row': 4, 'col': 4},
            'tags': ['fixture_target'], 'components': {'resources': {'sp': {'initial': initial_sp}}}},
        {'definition': 'unit/char_128_plosis', 'instanceAlias': 'friend', 'position': {'row': 4, 'col': 5},
            'components': {'resources': {'sp': {'initial': 0}}}},
        {'definition': 'unit/canonical_shield_probe_enemy', 'instanceAlias': 'attacker', 'position': {'row': 0, 'col': 0}}])
    data['entities'].append({'id': 'unit/canonical_shield_probe_enemy', 'kind': 'entity', 'tags': ['enemy'],
        'components': {'attributes': {'base': {'atk': 100, 'max_hp': 100000, 'def': 0, 'mres': 0}},
            'resources': {'hp': {'initial': 100000, 'capacity': 100000, 'role': 'health'}}, 'spatial': {},
            'abilities': ['ability/canonical_shield_probe']}})
    data['selectors'].append({'id': 'selector/canonical_shield_probe', 'kind': 'selector', 'region': {'type': 'all'},
        'filters': [{'tag': 'fixture_target'}, {'state': 'alive'}], 'limit': 1})
    data['abilities'].append({'id': 'ability/canonical_shield_probe', 'kind': 'ability',
        'activation': {'mode': 'manual'}, 'selector': 'selector/canonical_shield_probe',
        'timeline': [{'at': 0, 'effect': {'op': 'damage', 'damage_type': damage_type}}]})
    return data


def hit(sim, at):
    sim.submit({'action': 'skill', 'source': 'attacker', 'ability': 'ability/canonical_shield_probe'}, at=at)


@pytest.mark.parametrize('kind,unshielded', [('physical', 5), ('arts', 90), ('true', 100)])
def test_canonical_s1_blocks_once_without_legacy_effect_pipeline(kind, unshielded):
    old = Engine.create(Compiler().compile(scene(18, kind, revised=False)))
    hit(old, 1); old.advance(2)
    assert old.ctx.resources.current('liskam', 'shield_charge') == 1
    assert old.ctx.resources.current('liskam', 'hp') == 3124-unshielded
    sim = Engine.create(Compiler().compile(scene(18, kind)))
    hit(sim, 1); hit(sim, 3); sim.advance(2)
    assert sim.ctx.resources.current('liskam', 'shield_charge') == 0
    assert sim.ctx.resources.current('liskam', 'hp') == 3124
    assert sim.ctx.resources.current('friend', 'sp') == 0
    sim.advance(2)
    assert sim.ctx.resources.current('liskam', 'hp') == 3124-unshielded
    assert sim.ctx.resources.current('liskam', 'sp') == 0  # active S1 freeze
    assert sim.ctx.resources.current('friend', 'sp') == 1


def test_base_defense_one_plus_talent_self_one_and_adjacent_ally_one():
    sim = Engine.create(Compiler().compile(scene()))
    hit(sim, 1); sim.advance(2)
    assert sim.ctx.resources.current('liskam', 'sp') == 2
    assert sim.ctx.resources.current('friend', 'sp') == 1
    assert sim.ctx.resources.current('liskam', 'hp') == 3024


def test_nine_hits_pay_eighteen_then_block_tenth_and_command_replay_is_exact():
    program = Compiler().compile(scene())
    sim = Engine.create(program)
    for at in range(1, 11):
        hit(sim, at)
    sim.advance(6)
    restored = Engine.restore(program, sim.checkpoint())
    sim.advance(6); restored.advance(6)
    assert sim.ctx.resources.current('liskam', 'hp') == 3124-9*100
    assert sim.ctx.resources.current('liskam', 'sp') == 0
    assert sim.ctx.resources.current('liskam', 'shield_charge') == 0
    assert sim.ctx.resources.current('friend', 'sp') == 9
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None


def test_unused_shield_and_defense_end_at_half_open_eight_second_boundary():
    sim = Engine.create(Compiler().compile(scene(18, 'true')))
    hit(sim, 240)
    sim.advance(240)
    assert sim.ctx.attributes.value('liskam', 'def') == 1462
    assert sim.ctx.resources.current('liskam', 'shield_charge') == 1
    sim.advance(1)
    assert sim.ctx.attributes.value('liskam', 'def') == 731
    assert sim.ctx.resources.current('liskam', 'shield_charge') == 0
    assert sim.ctx.resources.current('liskam', 'hp') == 3024
    assert sim.ctx.resources.current('liskam', 'sp') == 2


def test_source_integration_preserves_full_roster_and_both_sp_sources():
    data = build(ROOT/'packages/campaign/mainline_models/level_main_00-10.m8_damage.json')
    units = [e for e in data['entities'] if 'campaign_roster' in e.get('tags', [])]
    assert len(units) == 12
    unit = next(e for e in units if e['id'] == 'unit/char_107_liskam')
    assert unit['components']['resources']['sp']['recovery']['amount'] == 1
    talent = next(b for b in data['buffs'] if b['id'] == 'buff/talent_liskam_hit')
    assert [e['delta'] for e in talent['events'][0]['effects']] == [1, 1]
    meta = data['manifest']['metadata']['m8_liskam_receiver_integration']
    assert meta['formal_stage_approved'] is False and meta['complete_operator'] is False
    assert meta['native_block_template']['native_method_bodies_recovered'] is False
