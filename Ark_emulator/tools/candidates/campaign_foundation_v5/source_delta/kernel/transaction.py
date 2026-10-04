"""Validate a complete intent batch before exposing any state change."""
from collections.abc import Mapping

from ark_sim.contracts.models import Intent

from .events import EventLog
from .world import World


def commit(session, intents):
    """Run on isolated stores, then publish under the session execution lock."""
    intents = tuple(intents)
    world = session.world._fork_validated()
    scheduler = session.scheduler.fork()
    events = EventLog()
    # Stage only new records. Cause validation needs the contiguous next ID,
    # and no intent can rewrite historical events. Commit appends this batch
    # after every store has validated; rollback discards it without touching
    # history. Cost depends on the new batch, not the journal's total length.
    events._next_id = session._events._next_id
    results = []
    for index, intent in enumerate(intents):
        if isinstance(intent, Mapping):
            intent = Intent(**intent)
        if not isinstance(intent, Intent):
            raise TypeError(f"Intent {index} is neither Intent nor a mapping")
        data = intent.data
        if intent.op == "create":
            result = world.create(data["definition_id"], data["components"],
                                  data.get("tags", ()), data.get("alias"))
        elif intent.op == "set":
            world.set(intent.entity_id, intent.path, intent.value)
            result = None
        elif intent.op == "delete":
            world.delete(intent.entity_id)
            result = None
        elif intent.op == "emit":
            result = events.emit(data["type"], data.get("payload", {}), session.time, data.get("cause"))
        elif intent.op == "schedule":
            session._validate_schedule(data["at"], data.get("phase", 0), data.get("priority", 0), scheduler)
            result = scheduler.schedule(data["kind"], data.get("payload", {}), data["at"],
                                        data.get("phase", 0), data.get("priority", 0), now=session.time)
        elif intent.op == "cancel":
            task_id = data.get("task_id", intent.entity_id)
            scheduler.cancel(task_id)
            result = None
        else:
            raise ValueError(f"Unknown intent operation at index {index}: {intent.op}")
        results.append(result)
    # Disk IO can fail: append/rollback the new batch before publishing stores.
    session._events._records.extend(events._records)
    # All validation happens above. Adoption cannot invoke user code or fail validation.
    session.world._adopt_validated(world, preserve_views=True)
    session.scheduler._tasks = scheduler._tasks
    session.scheduler._heap = scheduler._heap
    session.scheduler._next_id = scheduler._next_id
    session.scheduler._next_seq = scheduler._next_seq
    session._events._next_id = events._next_id
    return tuple(results)
