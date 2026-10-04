"""Actual late effect fault on a live recipient after a waiting cast starts."""
import pytest
from tools.experiments.waiting_actions_peer.test_peer_forgery import make, package


def test_actual_periodic_failure_rolls_waiting_cast_and_cleans_context():
    content = package()
    content['buffs'][0]['effects'].append(
        {'op': 'modify_resource', 'target': 3, 'resource': 'absent', 'delta': 1})
    simulation = make(content)
    simulation.advance(28)
    world = simulation.session.world.snapshot()
    events = tuple(simulation.session.events)
    with pytest.raises((ValueError, KeyError)):
        simulation.advance(2)
    assert simulation.session.world.snapshot() == world
    assert tuple(simulation.session.events) == events
    assert simulation.session.current_task is None
    assert not simulation.ctx.waiting_actions._timers
    assert not simulation.ctx.waiting_actions._scopes
    assert not simulation.ctx.get('waiter', ('runtime', 'casts'), {})
