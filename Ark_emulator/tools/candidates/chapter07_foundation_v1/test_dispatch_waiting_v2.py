"""Dispatch identity is detached and waiting callback failures leave no grant."""
from copy import deepcopy
import pytest

from ark_sim.kernel.session import Session
from tools.experiments.waiting_actions_peer.test_peer_forgery import make, package


def test_current_task_detached_and_cleared_after_callback_failure():
    session = Session()
    seen = []

    def fail(s, payload):
        actual = s.current_task
        seen.append(actual)
        actual['payload']['value'] = 999
        assert s.current_task['payload']['value'] == 7
        with s.atomic():
            assert s.current_task['id'] == 1
            raise ValueError('actual handler fault')

    session.register_handler('probe.failure', fail)
    session.schedule('probe.failure', {'value': 7}, 0)
    with pytest.raises(ValueError, match='actual handler fault'):
        session.advance(1)
    assert seen[0]['id'] == 1 and session.current_task is None
    assert not session.scheduler.pending


def test_waiting_periodic_late_failure_rolls_cast_and_clears_private_scopes():
    content = package()
    content['buffs'][0]['effects'].append(
        {'op': 'modify_resource', 'target': 'self', 'resource': 'absent', 'delta': 1})
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


def test_owned_buff_rebind_really_invalidates_existing_waiting_cast():
    content = package()
    content['buffs'][0]['stacking'] = {
        'mode': 'refresh', 'identity': ['definition', 'target'], 'max_stacks': 1}
    simulation = make(content)
    simulation.advance(30)
    before = deepcopy(simulation.ctx.get('waiter', ('buffs', 'instances'))[0])
    simulation.ctx.buffs.apply('controller', 'waiter', 'buff/peer/timer')
    after = simulation.ctx.get('waiter', ('buffs', 'instances'))[0]
    assert after['id'] == before['id'] and after['generation'] > before['generation']
    assert after['source'] != before['source']
    simulation.advance(5)
    assert not any(e['type'] == 'peer.wait.impact' for e in simulation.session.events)


def test_direct_effect_with_copied_waiting_cast_cannot_invoke_a_private_scope():
    simulation = make()
    simulation.advance(30)
    cast = deepcopy(next(iter(simulation.ctx.get('waiter', ('runtime', 'casts')).values())))
    before = simulation.checkpoint()
    simulation.ctx.effects.execute('waiter', [2],
        {'op': 'emit', 'event': 'probe.borrowed'}, cast=cast)
    assert simulation.checkpoint() == before
