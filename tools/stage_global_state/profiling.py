"""Opt-in, bounded hot-path timings. No values or addresses are recorded.

Set TIMELINE_PROFILE_STAGE_GLOBAL=1 before launch. Inclusive durations are not
additive (sample contains map/wave); disabling leaves only a direct call.
"""
from collections import defaultdict, deque
import json
import os
from time import perf_counter
from tools.runtime_log import SUMMARY_INTERVAL_SECONDS


class StageProfiler:
    def __init__(self):
        self.enabled = os.environ.get('TIMELINE_PROFILE_STAGE_GLOBAL') == '1'
        self.samples = defaultdict(lambda: deque(maxlen=256))
        self.last_report = perf_counter()

    def call(self, name, callback):
        if not self.enabled:
            return callback()
        started = perf_counter()
        try:
            return callback()
        finally:
            self.samples[name].append((perf_counter() - started) * 1000)

    def report(self, log):
        if not self.enabled or not callable(log) or perf_counter() - self.last_report < SUMMARY_INTERVAL_SECONDS:
            return
        self.last_report = perf_counter()
        summary = {}
        for key, samples in self.samples.items():
            values = sorted(samples)
            summary[key] = {'n':len(values), **{label:round(values[min(len(values)-1,int(len(values)*p))],3)
                for label,p in (('p50',.5),('p95',.95),('p99',.99))}}
        try:
            log('[stage-profile-ms] ' + json.dumps(summary, separators=(',', ':')))
        except Exception:
            pass  # Diagnostics cannot interrupt acquisition.
        self.samples.clear()
