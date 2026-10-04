"""Production-package damage paths, without the old fixture-only arts override."""
import json

import pytest

from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_m8_damage_integration import ROOT, build, patch


def scene(revised=True, mres=0, damage_type='arts'):
    source = ROOT/'packages/campaign/mainline_models/level_main_00-10.m7.json'
    data = build(source) if revised else json.loads(source.read_bytes())
    data['scenarioDraft'].update(id='scenario/m8_damage_probe', waves=[], initialEntities=[
        {'definition': 'unit/char_202_demkni', 'instanceAlias': 'saria', 'position': {'row': 4, 'col': 4},
            'facing': 'right', 'components': {'resources': {'sp': {'initial': 80}}}},
        {'definition': 'unit/char_180_amgoat', 'instanceAlias': 'eyja', 'position': {'row': 3, 'col': 4}},
        {'definition': 'unit/m8_damage_enemy', 'instanceAlias': 'enemy', 'position': {'row': 4, 'col': 5}}])
    data['scenarioDraft']['objectives'] = {}
    # Independent endpoint fixture uses final stats/talents and final aura,
    # suppressing unrelated attack loops; its packet has no damage.pipeline override.
    for unit in data['entities']:
        if unit['id'] == 'unit/char_202_demkni':
            unit['components']['abilities'] = ['ability/demkni_s3']
        elif unit['id'] == 'unit/char_180_amgoat':
            unit['components']['abilities'] = ['ability/m8_damage_probe']
    data['entities'].append({'id': 'unit/m8_damage_enemy', 'kind': 'entity', 'tags': ['enemy', 'ground'],
        'components': {'attributes': {'base': {'max_hp': 100000, 'def': 100, 'mres': mres, 'move_speed': 0, 'arts_factor': 1}},
            'resources': {'hp': {'initial': 100000, 'capacity': 100000, 'role': 'health'}},
            'spatial': {}, 'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
    data['selectors'].append({'id': 'selector/m8_damage_probe', 'kind': 'selector',
        'region': {'type': 'all'}, 'filters': [{'tag': 'enemy'}, {'state': 'alive'}], 'limit': 1})
    data['abilities'].append({'id': 'ability/m8_damage_probe', 'kind': 'ability', 'activation': {'mode': 'manual'},
        'selector': 'selector/m8_damage_probe', 'timeline': [{'at': 0, 'effect': {'op': 'damage', 'damage_type': damage_type}}]})
    return data


def damage(sim, kind='arts'):
    before = sim.ctx.resources.current('enemy', 'hp')
    sim.ctx.effects.execute('eyja', ['enemy'], {'op': 'damage', 'damage_type': kind})
    return before-sim.ctx.resources.current('enemy', 'hp')


def activate(sim):
    sim.ctx.abilities.start('saria', 'ability/demkni_s3')


def test_old_production_defect_is_reproduced_and_new_packet_is_amplified():
    old = Engine.create(Compiler().compile(scene(revised=False)))
    activate(old)
    assert old.ctx.attributes.value('enemy', 'arts_factor') == 1.55
    assert damage(old) == pytest.approx(809.4)
    revised = Engine.create(Compiler().compile(scene()))
    assert damage(revised) == pytest.approx(809.4)
    activate(revised)
    assert damage(revised) == pytest.approx(1254.57)


@pytest.mark.parametrize('kind,expected', [('arts', 1254.57), ('physical', 709.4), ('true', 809.4)])
def test_only_arts_is_scaled_on_actual_default_damage_pipeline(kind, expected):
    sim = Engine.create(Compiler().compile(scene()))
    activate(sim)
    assert damage(sim, kind) == pytest.approx(expected)


def test_mres_precedes_multiplier_and_outside_aura_has_no_bonus():
    sim = Engine.create(Compiler().compile(scene(mres=50)))
    activate(sim)
    assert damage(sim) == pytest.approx(627.285)  # 809.4*.5*1.55
    sim.ctx.set('enemy', ('spatial', 'position'), {'row': 0, 'col': 0})
    sim.ctx.buffs.reconcile()
    assert damage(sim) == pytest.approx(404.7)


def test_fragility_and_arts_taken_are_distinct_groups_not_max_or_double_scaled():
    sim = Engine.create(Compiler().compile(scene()))
    activate(sim)
    sim.ctx.buffs.apply('saria', 'enemy', 'buff/support_lisa_s3_member')
    assert damage(sim) == pytest.approx(1756.398)  # 809.4*1.55*1.4
    assert damage(sim, 'true') == pytest.approx(1133.16)  # fragile remains, arts hook does not


def test_duplicate_arts_hooks_take_highest_once_and_removal_restores_unscaled():
    sim = Engine.create(Compiler().compile(scene()))
    activate(sim)
    sim.ctx.buffs.apply('saria', 'enemy', 'buff/demkni_member')
    assert damage(sim) == pytest.approx(1254.57)
    sim.ctx.buffs.remove('enemy', 'buff/demkni_member')
    # Removing the owning emitter prevents immediate aura reattachment.
    sim.ctx.buffs.remove('saria', 'buff/demkni_emitter')
    assert damage(sim) == pytest.approx(809.4)


def test_selected_skill_and_plain_packet_commands_replay_with_real_aura():
    program = Compiler().compile(scene())
    sim = Engine.create(program)
    sim.submit({'action': 'skill', 'source': 'saria', 'ability': 'ability/demkni_s3'}, at=0)
    sim.submit({'action': 'skill', 'source': 'eyja', 'ability': 'ability/m8_damage_probe'}, at=2)
    sim.advance(1)
    restored = Engine.restore(program, sim.checkpoint())
    sim.advance(3); restored.advance(3)
    assert sim.ctx.resources.current('enemy', 'hp') == pytest.approx(100000-1254.57)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(sim.snapshot(), replay(program, sim.export_replay()).snapshot()) is None


def test_custom_pipeline_health_allocation_is_scaled_without_spending_extra_shield():
    data = scene()
    enemy = next(e for e in data['entities'] if e['id'] == 'unit/m8_damage_enemy')
    enemy['components']['resources']['shield'] = {'initial': 5, 'capacity': 5}
    data['rules'].append({'id': 'rule/m8_custom_allocation', 'kind': 'calculation_rule', 'contract': 'damage.pipeline',
        'implementation': {'type': 'graph', 'nodes': [{'id': 'result', 'expression': "{'accepted': True, 'amount': 10, 'allocations': [{'target': 'target', 'resource': 'hp', 'delta': -10}, {'target': 'target', 'resource': 'shield', 'delta': -1}], 'events': []}"}], 'output': 'nodes.result'}})
    data['abilities'][-1]['timeline'][0]['effect']['rules'] = {'damage.pipeline': 'rule/m8_custom_allocation'}
    sim = Engine.create(Compiler().compile(data))
    activate(sim)
    sim.ctx.effects.execute('eyja', ['enemy'], {'op': 'damage', 'damage_type': 'arts',
        'rules': {'damage.pipeline': 'rule/m8_custom_allocation'}})
    assert sim.ctx.resources.current('enemy', 'hp') == 99984.5
    assert sim.ctx.resources.current('enemy', 'shield') == 4


def test_all_twelve_selected_skill_metadata_matches_real_native_config():
    data = build(ROOT/'packages/campaign/mainline_models/level_main_00-10.m7.json')
    abilities = {a['id']: a for a in data['abilities']}
    actors = [e for e in data['entities'] if 'campaign_roster' in e.get('tags', [])]
    assert len(actors) == 12
    for actor in actors:
        meta = actor['metadata']
        ability = abilities[meta['selected_skill_ability']]
        assert ability['metadata']['native_skill_id'] == meta['selected_skill_native_id'] == meta['config']['skill_id']
    assert data['manifest']['metadata']['complete_operator_count'] == 0
    assert data['manifest']['metadata']['m8_damage_integration']['formal_stage_approved'] is False
    with pytest.raises(ValueError, match='already patched'):
        patch(data)
