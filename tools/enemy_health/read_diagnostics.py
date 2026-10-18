"""Opt-in read accounting; no cached values and no transport decisions.

Repeated addresses are observations, NOT permission to remove reads: structural
checks and separate guarded transactions must continue to read independently.
Only aggregate counts leave this object; bounded address keys die each round.
"""
from collections import Counter
from threading import Lock
import os
import sys


class ReadDiagnostics:
    def __init__(self, max_keys=8192):
        self._limit = max_keys
        self._seen = set()
        self._counts = Counter()
        self._lock = Lock()
        self._last_report = None
        self._origins = {}
        self._first_miss_origins = Counter()
        self._missed_domains = set()

    def miss(self, category, requests, results=None, *, origin=None):
        """Bounded caller aggregation, only for misses; never retain frames."""
        if not requests:
            return
        if origin is None:
            frame = sys._getframe(1)
            parts = []
            try:
                for _ in range(8):
                    if frame is None:
                        break
                    filename = os.path.basename(frame.f_code.co_filename)
                    if filename not in ('memcore.py', 'optional_memory.py', 'memory.py'):
                        parts.append(f'{filename}:{frame.f_code.co_name}:{frame.f_lineno}')
                        if len(parts) == 2:
                            break
                    frame = frame.f_back
            finally:
                del frame
            origin = ' <- '.join(parts) or 'unknown'
        key = category + ':' + origin
        with self._lock:
            # First observed miss, NOT proof of the first invalidating read:
            # the device guard may already have failed before Python parsing.
            # Keep a separate budget so cascading origins cannot crowd it out.
            if category in ('core', 'optional') and category not in self._missed_domains:
                self._missed_domains.add(category)
                if (key in self._first_miss_origins
                        or len(self._first_miss_origins) < min(64, self._limit)):
                    self._first_miss_origins[key] += 1
                else:
                    self._counts['first_miss_origin_overflow'] += 1
            if key not in self._origins:
                if len(self._origins) >= min(64, self._limit):
                    self._counts['miss_origin_overflow'] += len(requests)
                    return
                self._origins[key] = {'calls': 0, 'requests': 0, 'bytes': 0, 'failed': 0}
            row = self._origins[key]
            row['calls'] += 1
            row['requests'] += len(requests)
            row['bytes'] += sum(size for _, size in requests)
            if results is not None:
                row['failed'] += sum(
                    index >= len(results) or results[index] is None
                    or len(results[index]) != size
                    for index, (_, size) in enumerate(requests))

    def _snapshot(self):
        result = dict(self._counts)
        if self._origins:
            result['miss_origins'] = {key: dict(value) for key, value in self._origins.items()}
        if self._first_miss_origins:
            result['first_miss_origins'] = dict(self._first_miss_origins)
        return result

    def record(self, category, requests):
        with self._lock:
            self._counts[category + '.calls'] += 1
            batch = set()
            for address, size in requests:
                request = (address, size)
                key = (category, address, size)
                self._counts[category + '.requests'] += 1
                self._counts[category + '.bytes'] += max(0, size)
                if request in batch:
                    self._counts[category + '.batch_duplicates'] += 1
                if key in self._seen:
                    self._counts[category + '.round_repeats'] += 1
                elif len(self._seen) < self._limit:
                    self._seen.add(key)
                else:
                    self._counts['tracking_overflow'] += 1
                # Each call is bounded by the transport request limit.
                if len(batch) < self._limit:
                    batch.add(request)

    def new_round(self):
        with self._lock:
            self._seen.clear()
            self._missed_domains.clear()
            self._counts['rounds'] += 1

    def transaction(self, category, attempts=0, cross_frame=False):
        """Completed commands only; attempts are device executions, not RPCs."""
        with self._lock:
            self._counts[category + '.calls'] += 1
            self._counts[category + '.attempts'] += attempts
            self._counts[category + '.cross_frame'] += int(cross_frame)

    def snapshot(self):
        with self._lock:
            return self._snapshot()

    def report_due(self, now):
        with self._lock:
            if self._last_report is None:
                self._last_report = now
            if now - self._last_report < 20:
                return None
            self._last_report = now
            result = self._snapshot()
            self._counts.clear()
            self._origins.clear()
            self._first_miss_origins.clear()
            return result
