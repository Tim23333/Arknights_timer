"""Forked queues bound tombstones without changing task order or allocators."""
from ark_sim.contracts import Intent
from ark_sim.kernel import Session


def test_many_future_schedule_cancel_transactions_leave_no_inactive_records():
    session = Session()
    for _ in range(200):
        task = session.commit([Intent('schedule', data={'kind': 'future', 'at': 1000000, 'payload': {}})])[0]
        session.commit([Intent('cancel', data={'task_id': task})])
    assert not session.scheduler.pending
    assert not session.scheduler._heap
    assert session.scheduler.next_task_id == 201


def test_compaction_preserves_live_stable_order_while_replacing_far_future_jobs():
    session = Session()
    a = session.schedule('live.a', {}, 5, priority=1)
    b = session.schedule('live.b', {}, 5, priority=0)
    c = session.schedule('live.c', {}, 5, priority=1)
    for _ in range(500):
        task = session.schedule('cancelled.future', {}, 1000000)
        session.cancel(task)
    assert len(session.scheduler._heap) <= 64
    assert [session.scheduler.pop()['id'] for _ in range(3)] == [b, a, c]


def test_cancel_compaction_inside_failed_atomic_restores_pending_order_and_ids():
    session = Session()
    session.schedule('old', {}, 10)
    before = session.snapshot()
    try:
        with session.atomic():
            session.cancel(1)
            for _ in range(100):
                task = session.schedule('new', {}, 20)
                session.cancel(task)
            raise RuntimeError('fail')
    except RuntimeError:
        pass
    assert session.snapshot() == before
    assert session.scheduler.pop()['kind'] == 'old'
