"""Queue copy-on-write keeps public isolation and nested rollback intact."""
import pytest

from ark_sim.contracts import Intent
from ark_sim.kernel import Session
from ark_sim.kernel.scheduler import Scheduler


def test_fork_has_independent_task_index_heap_and_identity_allocators():
    queue = Scheduler(); queue.schedule('old', {'nested': [1]}, 10)
    before = queue.snapshot(); fork = queue.fork()
    assert fork.cancel(1) is None
    assert fork.schedule('new', {}, 20) == 2
    assert queue.snapshot() == before
    assert queue.next_task_id == 2
    assert fork.next_task_id == 3
    assert queue.pop()['kind'] == 'old'
    assert fork.pop()['kind'] == 'new'


def test_fork_input_and_public_views_cannot_mutate_shared_stored_payload():
    payload = {'nested': [1]}
    queue = Scheduler(); queue.schedule('old', payload, 10)
    fork = queue.fork(); payload['nested'].append(99)
    assert queue.peek()['payload']['nested'] == (1,)
    with pytest.raises((TypeError, AttributeError)):
        fork.peek()['payload']['nested'].append(2)
    checkpoint = fork.snapshot(); checkpoint['tasks'][0]['payload']['nested'].append(3)
    assert queue.snapshot()['tasks'][0]['payload']['nested'] == [1]
    assert fork.snapshot()['tasks'][0]['payload']['nested'] == [1]


def test_internal_commit_does_not_snapshot_queue_and_failed_batch_is_atomic(monkeypatch):
    session = Session(); actor = session.world.create('unit/a', {'value': 0}, alias='actor')
    task = session.schedule('old', {'long': list(range(100))}, 30)
    before = session.snapshot()
    def forbidden():
        raise AssertionError('internal commit must not serialize queue')
    with monkeypatch.context() as scoped:
        scoped.setattr(session.scheduler, 'snapshot', forbidden)
        with pytest.raises(KeyError):
            session.commit([Intent('set', actor, ('value',), 1), Intent('cancel', data={'task_id': task}),
                Intent('schedule', data={'kind': 'new', 'at': 40, 'payload': {}}),
                Intent('cancel', data={'task_id': 999})])
    assert session.snapshot() == before


def test_nested_savepoint_rolls_back_pop_cancel_and_new_schedule():
    session = Session(); session.schedule('old', {}, 10)
    with session.atomic():
        second = session.schedule('outer', {}, 20)
        outer = session.snapshot()
        with pytest.raises(RuntimeError, match='inner'):
            with session.atomic():
                assert session.scheduler.pop()['kind'] == 'old'
                session.cancel(second)
                session.schedule('inner', {}, 0)
                raise RuntimeError('inner')
        assert session.snapshot() == outer
    assert [t['kind'] for t in session.scheduler.pending] == ['old', 'outer']


def test_successful_inner_commit_is_rolled_back_by_outer_failure():
    session = Session(); session.schedule('old', {}, 10); before = session.snapshot()
    with pytest.raises(RuntimeError, match='outer'):
        with session.atomic():
            session.cancel(1)
            with session.atomic():
                session.commit([Intent('schedule', data={'kind': 'inner', 'at': 20, 'payload': {}})])
                session.emit('inner.event', {})
            raise RuntimeError('outer')
    assert session.snapshot() == before


def test_checkpoint_restore_and_same_time_order_preserve_sequences():
    queue = Scheduler(['first', 'last'])
    queue.schedule('b', {}, 10, phase='last')
    queue.schedule('a', {}, 10, phase='first')
    queue.schedule('c', {}, 10, phase='last')
    fork = queue.fork(); restored = Scheduler(); restored.restore(fork.snapshot())
    assert [fork.pop()['kind'] for _ in range(3)] == ['a', 'b', 'c']
    assert [restored.pop()['kind'] for _ in range(3)] == ['a', 'b', 'c']
    assert len(queue.pending) == 3


@pytest.mark.parametrize('payload', [{'x': float('nan')}, {'x': object()}])
def test_new_fork_tasks_still_validate_entire_payload(payload):
    fork = Scheduler().fork(); before = fork.snapshot()
    with pytest.raises((ValueError, TypeError)):
        fork.schedule('bad', payload, 0)
    assert fork.snapshot() == before
