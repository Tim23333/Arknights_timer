"""An append-only causal event journal with local identities."""
from threading import RLock
from collections.abc import Mapping
import math
import sys

from ._data import clone, integer, name, readonly
from .interning import PayloadInterner
from .journal import DiskEventRecords
from ark_sim.contracts.models import FrozenMapping, FrozenTuple, freeze


def freeze_event_payload(value, memo=None, active=None):
    """Validate JSON and detach mutable nodes, retaining immutable DAG aliases.

    Public FrozenMapping construction does not validate JSON. Its children
    must therefore pass the same validation as ordinary input containers.
    Memo lifetime is one emission: no historical cache or rollback state.
    """
    kind = type(value)
    if value is None or kind in (str, bool, int):
        digit_limit = sys.get_int_max_str_digits() if kind is int else 0
        if digit_limit and value.bit_length() * .30103 + 1 > digit_limit:
            # Preserve the JSON serializer's configured large-integer limit.
            import json
            json.dumps(value)
        return value
    if isinstance(value, str):
        return str.__str__(value)
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return freeze_event_payload(int.__int__(value))
    if isinstance(value, float):
        number = float.__float__(value)
        if not math.isfinite(number):
            raise ValueError("Event payload must contain finite JSON numbers")
        return number
    if not isinstance(value, (Mapping, list, tuple)):
        raise ValueError(f"Event payload must be JSON data, got {kind.__name__}")
    memo = {} if memo is None else memo
    active = set() if active is None else active
    identity = id(value)
    if identity in active:
        raise ValueError("Event payload cannot contain a container cycle")
    if identity in memo:
        return memo[identity]
    active.add(identity)
    try:
        if isinstance(value, Mapping):
            if any(not isinstance(key, str) for key in value):
                raise ValueError("Event payload object keys must be strings")
            items = {str.__str__(key): freeze_event_payload(child, memo, active) for key, child in value.items()}
            unchanged = kind is FrozenMapping and all(type(key) is str for key in value) and all(items[key] is child for key, child in value.items())
            result = value if unchanged else freeze(items)
        else:
            items = [freeze_event_payload(child, memo, active) for child in value]
            unchanged = kind is FrozenTuple and all(new is old for new, old in zip(items, value))
            result = value if unchanged else freeze(items)
        memo[identity] = result
        return result
    finally:
        active.remove(identity)


class EventLog:
    def __init__(self, lock=None):
        self._lock = lock or RLock()
        self._payload_interner = PayloadInterner()
        self._records = []
        self._next_id = 1

    def emit(self, event_type, payload, time, cause=None):
        with self._lock:
            name(event_type, "event type")
            integer(time, "event time", 0)
            if cause is not None:
                integer(cause, "cause event ID", 1)
                if cause >= self._next_id:
                    raise ValueError(f"Cause event does not exist: {cause}")
            payload = freeze_event_payload(payload)
            if not isinstance(self._records, DiskEventRecords):
                payload = self._payload_interner.intern(payload)
            event_id = self._next_id
            self._records.append(readonly({"id": event_id, "type": event_type, "payload": payload,
                                          "time": time, "cause": cause}))
            self._next_id += 1
            return event_id

    @property
    def records(self):
        with self._lock:
            return tuple(self._records)

    def iter_records(self, start=0):
        """Read a stable immutable slice without cloning historical payloads."""
        with self._lock:
            integer(start, "event journal start", 0)
            return iter(tuple(self._records[start:]))

    def enable_disk(self, path):
        with self._lock:
            records = DiskEventRecords(path)
            for record in self._records:
                records.append(record)
            self._records = records
            self._payload_interner.clear()

    def export_jsonl(self, path):
        with self._lock:
            if not isinstance(self._records, DiskEventRecords):
                raise RuntimeError("Direct byte export requires an enabled event journal")
            return self._records.export(path)

    def snapshot(self, event_reference=False):
        with self._lock:
            if event_reference:
                if not isinstance(self._records, DiskEventRecords):
                    raise RuntimeError("Event reference checkpoint requires an enabled journal")
                return {"reference": self._records.reference(), "next_id": self._next_id}
            return clone({"records": list(self._records), "next_id": self._next_id})

    def restore(self, data):
        with self._lock:
            if "reference" in data:
                records = DiskEventRecords.from_reference(data["reference"])
                data = {"records": records, "next_id": data["next_id"]}
            else:
                data = freeze_event_payload(data)
                records = data["records"]
            try:
                previous = 0
                previous_time = 0
                for record in data["records"]:
                    record = freeze_event_payload(record)
                    if not isinstance(record, Mapping) or not {"id", "type", "payload", "time", "cause"}.issubset(record):
                        raise ValueError("Event checkpoint lacks required fields")
                    event_id = integer(record["id"], "event ID", 1)
                    if event_id != previous + 1:
                        raise ValueError("Event IDs must be contiguous and ordered")
                    name(record["type"], "event type")
                    integer(record["time"], "event time", 0)
                    if record["time"] < previous_time:
                        raise ValueError("Event times must be nondecreasing")
                    cause = record["cause"]
                    if cause is not None:
                        integer(cause, "cause event ID", 1)
                        if cause >= event_id:
                            raise ValueError("Cause must refer to an earlier event")
                    previous = event_id
                    previous_time = record["time"]
                next_id = integer(data["next_id"], "next event ID", 1)
                if next_id != previous + 1:
                    raise ValueError("Invalid next event ID")
                # Restore owns a fresh cache; no live session/factory cache is reused.
                self._payload_interner.clear()
                self._records = records if isinstance(records, DiskEventRecords) else [readonly({**dict(record), "payload": self._payload_interner.intern(record["payload"])}) for record in records]
                self._next_id = next_id
            except BaseException:
                if isinstance(records,DiskEventRecords):records.discard()
                raise
