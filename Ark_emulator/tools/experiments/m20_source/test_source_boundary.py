"""Generic dormant-source isolation and opt-in actor revival; API scope explicit."""
from copy import deepcopy
import pytest
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from tools.experiments.m20.test_dormant import fixture


def active_target(p):
    p['entities'].append({'id': 'unit/target', 'kind': 'entity', 'tags': ['enemy'], 'components': {
        'attributes': {'base': {'max_hp': 100, 'atk': 0, 'def': 0, 'mres': 0}},
        'resources': {'hp': {'initial': 100, 'capacity': 100, 'role': 'health'}, 'sp': {'initial': 0, 'capacity': 50}}, 'spatial': {}}})
    p['scenarioDraft']['initialEntities'].append({'definition': 'unit/target', 'instanceAlias': 'target', 'position': {'row': 0, 'col': 2}})


@pytest.mark.parametrize('effect', [
    {'op': 'modify_resource', 'resource': 'sp', 'delta': 3},
    {'op': 'damage', 'damage_type': 'physical', 'scale': 1},
    {'op': 'random', 'stream': 'imp', 'on_success': [{'op': 'modify_resource', 'resource': 'sp', 'delta': 3}]},
    {'op': 'schedule', 'delay_seconds': 1, 'effect': {'op': 'modify_resource', 'resource': 'sp', 'delta': 3}},
])
def test_never_activated_source_cannot_affect_active_actor_or_consume_rng(effect):
    p = fixture(); active_target(p); sim = Engine.create(Compiler().compile(p)); ref = sim.ctx.state()['predefined_registry']['native-npc']
    before = sim.session.random.snapshot(); tasks = tuple(sim.session.scheduler.pending)
    sim.ctx.effects.execute(ref, ['target'], effect)
    assert sim.ctx.resources.current('target', 'hp') == 100 and sim.ctx.resources.current('target', 'sp') == 2
    assert sim.session.random.snapshot() == before
    # Domain observation reaction is permitted; no delayed effect or random work.
    assert not any(t['kind'] == 'domain.effect' for t in sim.session.scheduler.pending if t not in tasks)
    assert not [e for e in sim.session.events if e['type'] in {'damage.accepted', 'random.branch'}]
    assert len([e for e in sim.session.events if e['type'] == 'effect.source_inactive_rejected']) == 1


def test_previously_activated_registered_actor_revives_as_operational_instance():
    p = fixture(); p['scenarioDraft'].pop('scheduledEffects')
    p['rules'] = [{'id': 'rule/revive', 'kind': 'calculation_rule', 'extends': 'rule/ark_lifecycle_death',
        'parameters': {'resource': 'hp', 'threshold': 0, 'revive': True, 'revive_value': 50}}]
    p['entities'][0]['components']['lifecycle']['rules'] = {'lifecycle.death': 'rule/revive'}
    sim = Engine.create(Compiler().compile(p)); ref = sim.ctx.state()['predefined_registry']['native-npc']
    # A direct lifecycle query must not initialize a dormant template.
    before = sim.checkpoint(); sim.ctx.lifecycle.check(ref, {})
    assert first_difference(before, sim.checkpoint()) is None
    sim.ctx.lifecycle.activate_predefined('native-npc'); sim.ctx.lifecycle.retire(ref, 'dead')
    assert not sim.ctx.active(ref)
    sim.ctx.resources.adjust(ref, 'hp', value=0)
    assert sim.ctx.alive(ref) and sim.ctx.active(ref) and sim.ctx.resources.current(ref, 'hp') == 50
    assert sim.ctx.state()['predefined_registry']['native-npc'] == ref
    restored = Engine.restore(sim.program, sim.checkpoint())
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
