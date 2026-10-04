"""Owned ability lifecycle effects keep rule scopes and public replay identity."""
import sys
import json
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / 'unpack_work/campaign_c9_ability_clock_v2_candidate')); sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay


def package(seconds=1, rule=None):
    clock = {'op': 'set_ability_cooldown', 'target': 'source', 'ability': 'ability/clock/work', 'duration_seconds': seconds}
    if rule: clock['rules'] = {'ability.recovery': rule}
    return {'schemaVersion': 2, 'abilities': [
        {'id': 'ability/clock/work', 'kind': 'ability', 'activation': {'mode': 'manual'}, 'duration_seconds': 2,
         'timeline': [{'at_seconds': 1, 'effect': {'op': 'emit', 'event': 'clock.work.hit'}}]},
        {'id': 'ability/clock/reset', 'kind': 'ability', 'activation': {'mode': 'manual', 'parameters': {'allow_overlap': True}},
         'timeline': [{'at': 0, 'effect': clock}]},
        {'id': 'ability/clock/interrupt', 'kind': 'ability', 'activation': {'mode': 'manual', 'parameters': {'allow_overlap': True}},
         'timeline': [{'at': 0, 'effect': {'op': 'interrupt_ability', 'target': 'source', 'ability': 'ability/clock/work'}}]}],
        'entities': [{'id': 'unit/clock/owner', 'kind': 'entity', 'components': {'attributes': {'base': {'atk': 7}},
                     'spatial': {}, 'abilities': ['ability/clock/work', 'ability/clock/reset', 'ability/clock/interrupt']}}],
        'scenarioDraft': {'id': 'scene/clock', 'ruleset': 'ruleset/ark_standard', 'map': {'rows': 1, 'cols': 1},
            'initialEntities': [{'definition': 'unit/clock/owner', 'instanceAlias': 'owner'}]}}


def test_current_clock_reset_and_clear_are_exact_public_actions():
    p = package(); s = Engine.create(Compiler().compile(p))
    s.submit({'action': 'skill', 'source': 'owner', 'ability': 'ability/clock/reset'}, at=3); s.advance(4)
    assert s.ctx.get('owner', ('runtime', 'cooldowns', 'ability/clock/work')) == 33
    assert s.snapshot() == replay(s.program, s.export_replay()).snapshot()
    effect = {'op': 'set_ability_cooldown', 'ability': 'ability/clock/work', 'duration_seconds': 0}
    s.ctx.effects.execute('owner', ['owner'], effect)
    assert s.ctx.get('owner', ('runtime', 'cooldowns', 'ability/clock/work')) == 4


def test_custom_recovery_formula_is_effect_owned_and_applied():
    p = package(rule='rule/clock/custom'); p['rules'] = [{'id': 'rule/clock/custom', 'kind': 'rule', 'contract': 'ability.recovery',
        'implementation': {'type': 'expression', 'expression': 'inputs.recovery_parameters.seconds * 2'}}]
    s = Engine.create(Compiler().compile(p)); s.submit({'action': 'skill', 'source': 'owner', 'ability': 'ability/clock/reset'}, at=7); s.advance(8)
    assert s.ctx.get('owner', ('runtime', 'cooldowns', 'ability/clock/work')) == 67


def test_controlled_ability_local_recovery_rule_is_preserved():
    p = package(); p['rules'] = [{'id': 'rule/clock/ability_local', 'kind': 'rule', 'contract': 'ability.recovery',
        'implementation': {'type': 'expression', 'expression': 'inputs.recovery_parameters.seconds * 1.5'}}]
    p['abilities'][0]['rules'] = {'ability.recovery': 'rule/clock/ability_local'}
    s = Engine.create(Compiler().compile(p)); s.submit({'action': 'skill', 'source': 'owner', 'ability': 'ability/clock/reset'}, at=4); s.advance(5)
    assert s.ctx.get('owner', ('runtime', 'cooldowns', 'ability/clock/work')) == 49


def test_interrupt_only_declared_owned_ability_and_cancels_later_hit():
    p = package()
    p['selectors'] = [{'id': 'selector/clock/owner', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'controlled'}]}]
    p['entities'][0]['tags'] = ['controlled']
    p['entities'].append({'id': 'unit/clock/controller', 'kind': 'entity', 'components': {'spatial': {}, 'abilities': ['ability/clock/external_interrupt']}})
    p['abilities'].append({'id': 'ability/clock/external_interrupt', 'kind': 'ability', 'activation': {'mode': 'manual'},
        'selector': 'selector/clock/owner', 'timeline': [{'at': 0, 'effect': {'op': 'interrupt_ability', 'ability': 'ability/clock/work'}}]})
    p['scenarioDraft']['initialEntities'].append({'definition': 'unit/clock/controller', 'instanceAlias': 'controller'})
    s = Engine.create(Compiler().compile(p)); s.submit({'action': 'skill', 'source': 'owner', 'ability': 'ability/clock/work'}, at=0)
    s.submit({'action': 'skill', 'source': 'controller', 'ability': 'ability/clock/external_interrupt'}, at=2); s.advance(35)
    assert not [e for e in s.session.events if e['type'] == 'command.rejected']
    assert not [e for e in s.session.events if e['type'] == 'clock.work.hit']
    assert not s.ctx.get('owner', ('runtime', 'casts'))


@pytest.mark.parametrize('value', [True, -1, float('nan')])
def test_invalid_duration_rejected_before_execution(value):
    with pytest.raises(ValueError): Compiler().compile(package(seconds=value))


def test_wrong_possessed_reference_and_late_formula_fault_roll_back():
    s = Engine.create(Compiler().compile(package())); before = s.checkpoint()
    with pytest.raises(ValueError):
        s.ctx.effects.execute('owner', ['owner'], {'op': 'set_ability_cooldown', 'ability': 'ability/not_owned', 'duration_seconds': 1})
    assert s.checkpoint() == before
    p = package(rule='rule/clock/fault'); p['rules'] = [{'id': 'rule/clock/fault', 'kind': 'rule', 'contract': 'ability.recovery',
        'implementation': {'type': 'expression', 'expression': '1 / 0'}}]
    s = Engine.create(Compiler().compile(p)); before = s.checkpoint()
    with pytest.raises(ValueError):
        s.ctx.effects.execute('owner', ['owner'], p['abilities'][1]['timeline'][0]['effect'])
    assert s.checkpoint() == before


def test_disk_cp_pending_reset_and_public_head(tmp_path):
    s = Engine.create(Compiler().compile(package())); s.submit({'action': 'skill', 'source': 'owner', 'ability': 'ability/clock/reset'}, at=8); s.advance(4)
    path = tmp_path / 'clock.checkpoint.json'; path.write_text(json.dumps(s.checkpoint()), encoding='utf8')
    r = Engine.restore(s.program, json.loads(path.read_bytes())); s.advance(6); r.advance(6)
    assert s.checkpoint() == r.checkpoint() == replay(s.program, s.export_replay()).checkpoint()
