"""Interactions between registered actors and retained attached projectiles."""
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.experiments.m21.test_projectile_integration import base


def test_C4_retired_registered_attachment_still_blasts_at_stored_point():
    p = base(normal=False, targets=((3, 4), (3, 5)))
    target = next(e for e in p['scenarioDraft']['initialEntities'] if e.get('instanceAlias') == 'target0')
    target.update(active=False, registration_key='registered-target')
    p['scenarioDraft']['scheduledEffects'] = [{'at': 0, 'effect': {'op': 'activate_predefined', 'target': 'battle', 'parameters': {'key': 'registered-target'}}}]
    sim = Engine.create(Compiler().compile(p), seed=2101)
    sim.submit({'action': 'skill', 'source': 'w', 'ability': 'ability/chapter01_w_c4_0'}, at=0)
    sim.submit({'action': 'withdraw', 'source': 'target0'}, at=50)
    sim.advance(100); checkpoint = sim.checkpoint(); sim.advance(15)
    assert not sim.ctx.active('target0') and not sim.ctx.alive('target0')
    assert sim.ctx.resources.current('target0', 'hp') == 5000
    assert sim.ctx.resources.current('target1', 'hp') == 4254
    assert len([e for e in sim.session.events if e['type'] == 'area.resolved']) == 1
    restored = Engine.restore(sim.program, checkpoint); restored.advance(15)
    assert first_difference(sim.snapshot(), restored.snapshot()) is None
    assert first_difference(tuple(sim.session.events), tuple(restored.session.events)) is None
    replayed = replay(sim.program, sim.export_replay())
    assert first_difference(sim.snapshot(), replayed.snapshot()) is None
    assert first_difference(tuple(sim.session.events), tuple(replayed.session.events)) is None

