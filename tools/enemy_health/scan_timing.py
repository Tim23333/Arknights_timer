"""Scan-only timing; never adds work to the realtime frame loop."""
from contextlib import contextmanager
from time import perf_counter
from functools import wraps


@contextmanager
def scan_phase(log, name):
    started = perf_counter()
    try:
        yield
    finally:
        log(f'[扫描计时] {name}: {perf_counter() - started:.3f}s')


def timed_scan(name):
    """Decorate cold paths only. Exceptions and return values are unchanged."""
    def decorate(method):
        @wraps(method)
        def measured(self, *args, **kwargs):
            log = getattr(self, 'log', None)
            # Qt SignalInstance reports callable(), but requires .emit().
            log = getattr(log, 'emit', log)
            if not callable(log):
                log = print
            with scan_phase(log, name):
                return method(self, *args, **kwargs)
        return measured
    return decorate
