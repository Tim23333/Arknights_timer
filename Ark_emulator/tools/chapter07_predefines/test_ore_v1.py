"""Independent operands for pinned ore source, with explicit pending timing."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter07_predefines.policies_v1 import providers

ROOT = Path(__file__).resolve().parents[2]
ABILITY = 'ability/ch7/predefined/ore/pulse'


def package():
    p = json.loads((ROOT / 'packages/campaign/chapter07_predefines_consumer/ore.module.v2.json').read_bytes())
    p['buffs'] += [{'id': 'buff/ch7/source/ore_listener', 'kind': 'buff'},
                   {'id': 'buff/ch7/source/ore_immune', 'kind': 'buff'}]
    p['behaviors'] = [{'id': 'machine/ore/test', 'kind': 'behavior',
                            'initial': 'mode0', 'states': {'mode0': {}, 'mode1': {}}}]
    units = [('ally', 0, [], 1, 1), ('enemy', 1, [], 2, 3),
             ('immune', 1, ['buff/ch7/source/ore_immune'], 3, 2),
             ('listener', 1, ['buff/ch7/source/ore_listener'], 2, 1)]
    p['scenarioDraft'] = {'id': 'scene/ore/test', 'ruleset': 'ruleset/ark_standard',
        'map': {'rows': 5, 'cols': 5}, 'objectives': {},
        'initialEntities': [{'definition': p['entities'][0]['id'], 'instanceAlias': 'ore',
                             'position': {'row': 2, 'col': 2}}]}
    for name, side, buffs, row, col in units:
        definition = {'id': 'unit/ore/test/' + name, 'kind': 'entity', 'components': {
            'attributes': {'base': {'max_hp': 5000, 'atk': 13, 'def': 997, 'mres': 90}},
            'resources': {'hp': {'initial': 5000, 'capacity': 5000, 'role': 'health'}},
            'selection_state': {'side': side, 'category': 1, 'motion': 1, 'unit_type': 2},
            'spatial': {}, 'buffs': {'initial': buffs},
            'behavior': {'machine': 'machine/ore/test', 'state': 'mode0'},
            'lifecycle': {'policy': 'policy/ark_lifecycle'}}}
        p['entities'].append(definition)
        p['scenarioDraft']['initialEntities'].append({'definition': definition['id'],
            'instanceAlias': name, 'position': {'row': row, 'col': col}})
    return p


def make(p=None):
    registry = providers()
    return Engine.create(Compiler(providers=registry).compile(p or package()),
                         seed=7125, providers=registry)


def test_real_sp7_fixed_predelay_and_both_sides_true_damage_listener_immune():
    s = make()
    s.advance(210)
    assert not any(e['type'] == 'ability.started' for e in s.session.events)
    s.advance(25)
    starts = [e for e in s.session.events if e['type'] == 'ability.started']
    packets = [e for e in s.session.events if e['type'] == 'damage.accepted']
    assert len(starts) == 1 and len(packets) == 3
    assert all(e['time'] == starts[0]['time'] + 19 for e in packets)
    assert all(e['payload']['amount'] == 500 for e in packets)
    assert {e['payload']['target'] for e in packets} == {
        s.session.world.resolve(n) for n in ('ally', 'enemy', 'listener')}
    assert s.ctx.resources.current('immune', 'hp') == 5000
    assert s.ctx.get('listener', ('behavior', 'state')) == 'mode1'
    assert s.ctx.get('enemy', ('behavior', 'state')) == 'mode0'
    assert all(e['payload']['source'] == s.session.world.resolve('ore') for e in packets)
    assert all(e['payload']['damage_flags']['source_attack_type'] == 'NONE' for e in packets)
    assert s.ctx.spatial.grid.tile(2, 2)['passableMask'] == 2


def test_actual_cp_before_pulse_and_public_head(tmp_path):
    s = make()
    s.advance(210)
    file = tmp_path / 'before_pulse.json'
    pin = write_ordered(file, s.checkpoint())
    r = Engine.restore(s.program, load_bound(file, pin), providers=providers())
    s.advance(270)
    r.advance(270)
    assert s.checkpoint() == r.checkpoint() == replay(s.program, s.export_replay(), providers=providers()).checkpoint()


@pytest.mark.parametrize('field,value', [('camouflage', True), ('category', 2)])
def test_source_selector_still_excludes_camo_and_nonunit(field, value):
    p = package()
    p['entities'][1]['components']['selection_state'][field] = value
    s = make(p)
    s.advance(235)
    assert s.ctx.resources.current('ally', 'hp') == 5000


def test_targetfree_is_explicitly_ignored_in_native_source_config():
    p = package()
    p['entities'][1]['components']['selection_state']['target_free'] = True
    s = make(p)
    s.advance(235)
    assert s.ctx.resources.current('ally', 'hp') == 4500
