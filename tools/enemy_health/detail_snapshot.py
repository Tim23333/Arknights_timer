"""Bounded address-only detail plans on the existing isolated v5 channel.

Parsing follows current parent pointers. A new address invalidates the round;
its live bytes are only discovery input for the next freshly guarded capture.
No result bytes survive end(), and no core resident plan is changed.
"""
from collections import OrderedDict
from threading import RLock

MAX_OPERATIONS = 4096
MAX_BYTES = 8 * 1024 * 1024


class DetailSnapshot:
    def __init__(self, channel, requests, guard_address):
        self.channel = channel
        self.seen = {}
        self.values = {}
        self.guard = {}
        self.valid = False
        self.failure_reason = 'plan_cold' if not requests else 'guard_missing'
        self.prefixes = {}
        if requests and guard_address:
            values, self.guard = channel.guarded_transaction_read(
                [('direct', address, size) for address, size in requests],
                guard_address, max_attempts=3)
            self.valid = (self.guard.get('complete') is True
                          and type(self.guard.get('start')) is int
                          and self.guard['start'] == self.guard.get('end')
                          and len(values) == len(requests))
            self.values = dict(zip(requests, values))
            self.failure_reason = ('' if self.valid else
                'cross_frame' if type(self.guard.get('start')) is int
                and type(self.guard.get('end')) is int
                and self.guard['start'] != self.guard['end'] else 'guard_incomplete')
            if any(value is None or len(value) != size
                   for (_, size), value in self.values.items()):
                self.valid = False
                self.failure_reason = 'read_failed'
            prefixes = self.prefixes
            for (address, _), value in self.values.items():
                if value is None:
                    continue
                previous = prefixes.get(address, b'')
                overlap = min(len(previous), len(value))
                if previous[:overlap] != value[:overlap]:
                    self.valid = False
                    self.failure_reason = 'overlap_conflict'
                if len(value) > len(previous):
                    prefixes[address] = value

    @property
    def frame(self):
        return self.guard.get('start') if self.valid else None

    def read(self, requests):
        self.seen.update(dict.fromkeys(requests))
        # Only bytes already captured by this transaction may satisfy a smaller
        # same-address request. Never use live discovery bytes for this reuse.
        for address, size in requests:
            prefix = self.prefixes.get(address)
            if (address, size) not in self.values and prefix is not None and len(prefix) >= size:
                self.values[address, size] = prefix[:size]
        missing = [request for request in requests if request not in self.values]
        if missing:
            self.valid = False
            if not self.failure_reason:
                self.failure_reason = 'plan_miss'
            values = self.channel.batch_read(missing, force_live=True, remember=False)
            self.values.update(zip(missing, values))
        result = [self.values.get(request) for request in requests]
        if any(value is None or len(value) != size
               for (_, size), value in zip(requests, result)):
            self.valid = False
            self.failure_reason = 'read_failed'
        return result


class DetailSnapshotPool:
    """Reader-owned address LRU survives short-lived detail worker threads."""
    def __init__(self):
        self.plans = OrderedDict()
        self._lock = RLock()

    def begin(self, key, channel, guard_address):
        with self._lock:
            requests = self.plans.get(key, ())
        return DetailSnapshot(channel, requests, guard_address)

    def end(self, key, sample):
        requests = tuple(sample.seen)
        with self._lock:
            if len(requests) <= MAX_OPERATIONS and sum(size for _, size in requests) <= MAX_BYTES:
                self.plans[key] = requests
                self.plans.move_to_end(key)
                while len(self.plans) > 128:
                    self.plans.popitem(last=False)
            else:
                self.plans.pop(key, None)
        sample.values.clear()
        sample.prefixes.clear()
        sample.valid = False
