"""Frozen M7 storage algorithms for M8 comparisons, never a battle runtime."""
from collections.abc import Mapping
from ark_sim.kernel.events import EventLog
from ark_sim.kernel._data import clone, readonly, integer, name


def legacy_compact_trace(value):
    if isinstance(value, Mapping):
        result = {}
        for key, child in value.items():
            if key in ('source_snapshot', 'target_snapshots', 'launch_snapshot', 'launch_target_snapshots'):
                continue
            if key == 'context' and isinstance(child, Mapping):
                result[key] = {name: legacy_compact_trace(item) for name, item in child.items()
                    if name not in ('source', 'target', 'owner', 'entity_states')}
                for name in ('source', 'target', 'owner'):
                    if isinstance(child.get(name), Mapping):
                        result[key][name + '_id'] = child[name].get('id')
            else:
                result[key] = legacy_compact_trace(child)
        return result
    if isinstance(value, (list, tuple)):
        return [legacy_compact_trace(child) for child in value]
    return value


class LegacyEventLog(EventLog):
    def emit(self, event_type, payload, time, cause=None):
        with self._lock:
            name(event_type, 'event type');integer(time, 'event time', 0)
            if cause is not None:
                integer(cause, 'cause event ID', 1)
                if cause >= self._next_id:
                    raise ValueError(f'Cause event does not exist: {cause}')
            payload = clone(payload)
            identity = self._next_id;self._next_id += 1
            self._records.append(readonly({'id': identity, 'type': event_type, 'payload': payload, 'time': time, 'cause': cause}))
            return identity
