"""An optional guarded batch, sharing transport but not the core resident plan.

Only addresses are retained between samples. Values are freshly read each time;
new topology invalidates this batch alone, never the enemy/character batch.
"""
from .memory import MemoryAccess, ReadFailure


class OptionalMemoryAccess(MemoryAccess):
    def __init__(self, memory, channel):
        super().__init__(memory, channel)
        self._requests = ()
        self._seen = {}
        self._values = {}
        self._pending_values = None
        self._active = False
        self.guard = {}

    def begin_sample(self, guard_address):
        self._seen = {}
        self._values = {}
        self._pending_values = None
        self.guard = {'complete': False}
        self._active = True
        if not self._requests or not guard_address:
            return
        queue = getattr(self.channel, 'queue_optional_capture', None)
        if callable(queue) and queue(self._requests, guard_address,
                                     self._accept_capture):
            return
        values, self.guard = self.channel.guarded_transaction_read(
            [('direct', address, size) for address, size in self._requests],
            guard_address, max_attempts=1)
        # Keep the gap before the core device read free of result indexing.
        # These are this round's owned bytes, never a cross-round value cache.
        self._pending_values = values

    def _accept_capture(self, values, guard):
        self._pending_values = values
        self.guard = guard

    def end_sample(self):
        # Bounded by the transport's transaction limit. Oversized demand fails
        # locally instead of uploading an invalid plan on the next round.
        self._requests = tuple(self._seen)[:8192]
        self._values = {}
        self._pending_values = None
        self._active = False

    def read_many(self, requests, *, structural_check=False):
        if not requests:
            return []
        diagnostics = getattr(self.channel, 'read_diagnostics', None)
        if structural_check or not self._active:
            if diagnostics is not None:
                diagnostics.record('optional.structural' if structural_check
                                   else 'optional.unplanned', requests)
            values = self.channel.batch_read(requests, force_live=True, remember=False)
        else:
            if self._pending_values is not None:
                self._values = dict(zip(self._requests, self._pending_values))
                self._pending_values = None
            self._seen.update(dict.fromkeys(requests))
            missing = [request for request in requests if request not in self._values]
            if diagnostics is not None:
                diagnostics.record('optional.plan_miss', missing)
                diagnostics.record('optional.plan_hit', [
                    request for request in requests if request in self._values])
            if missing:
                self.guard = {**self.guard, 'complete': False}
                fresh = self.channel.batch_read(missing, force_live=True, remember=False)
                if diagnostics is not None:
                    diagnostics.miss('optional', missing, fresh)
                self._values.update(zip(missing, fresh))
            values = [self._values.get(request) for request in requests]
        if len(values) != len(requests) or any(
            value is None or len(value) != size
            for (_, size), value in zip(requests, values)
        ):
            raise ReadFailure()
        return values
