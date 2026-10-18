"""Bounded worker-local diagnostics, separate from loop Hz and the WS contract.

Accepted means the domain's read and enclosing frame guard succeeded, not that
every individual field is available. Mixed pause/running windows are explicitly
labelled; their wall-time rate must not be reported as a running-only rate.
"""
from collections import Counter
import os
from time import perf_counter

from tools.runtime_log import SUMMARY_INTERVAL_SECONDS


class EffectiveFrameMetrics:
    def __init__(self, *, enabled=None, started=None):
        self.enabled = (os.environ.get('TIMELINE_PROFILE_STAGE_GLOBAL') == '1'
                        if enabled is None else enabled)
        self._started = perf_counter() if started is None else started
        self._identity = None
        self._highwater = {}
        self._clear_window()

    def _clear_window(self):
        self._attempts = 0
        self._identity_changes = 0
        self._modes = Counter()
        self._rejections = Counter()
        self._guard_sources = Counter()
        self._domains = {name: Counter() for name in ('enemy', 'character', 'combined')}

    def observe_guards(self, core_initial, core_final, optional_initial,
                       optional_final, frame):
        """Classify existing guard evidence; never read memory or affect validity.

        Initial guards are captured before parsing can invalidate a plan on a
        topology miss. No device evidence is not itself a cross-frame failure.
        Counts are nonexclusive and independent of the final published batch.
        """
        if not self.enabled:
            return
        for domain, initial, final in (
                ('core', core_initial, core_final),
                ('optional', optional_initial, optional_final)):
            if not initial.get('attempts'):
                self._guard_sources[domain + '.no_device_evidence'] += 1
                continue
            start, end = initial.get('start'), initial.get('end')
            if initial.get('complete') is not True:
                reason = ('device_cross_frame' if type(start) is int
                          and type(end) is int and start != end
                          else 'device_incomplete')
                self._guard_sources[domain + '.' + reason] += 1
            elif final.get('complete') is False:
                self._guard_sources[domain + '.topology_miss'] += 1
            if (initial.get('complete') is True and type(frame) is int
                    and start != frame):
                self._guard_sources[domain + '.core_frame_mismatch'] += 1

    def observe(self, snapshot, *, require_character):
        if not self.enabled:
            return
        identity = (snapshot.get('_history_epoch'), snapshot.get('policy_generation'))
        if identity != self._identity:
            if self._identity is not None:
                self._identity_changes += 1
            self._identity = identity
            self._highwater.clear()
        self._attempts += 1
        paused = snapshot.get('paused_snapshot')
        self._modes['paused' if paused is True else 'running' if paused is False else 'unknown'] += 1
        frame = snapshot.get('fixed_frame')
        has_frame = type(frame) is int and frame >= 0
        consistent = snapshot.get('frame_consistent') is True
        if not has_frame:
            self._rejections['frame_missing'] += 1
        if not consistent:
            self._rejections['frame_inconsistent'] += 1
        enemy_ok = bool(snapshot.get('ok'))
        character_ok = bool(snapshot.get('character_ok'))
        if not enemy_ok:
            self._rejections['enemy_read_failed'] += 1
        if require_character and not character_ok:
            self._rejections['character_read_failed'] += 1
        valid = {'enemy': enemy_ok, 'character': require_character and character_ok,
                 'combined': enemy_ok and (not require_character or character_ok)}
        for domain, success in valid.items():
            if not (success and consistent and has_frame):
                continue
            counts = self._domains[domain]
            counts['accepted'] += 1
            previous = self._highwater.get(domain)
            if previous is not None and frame < previous:
                counts['regressions'] += 1
                continue
            if previous is None or frame > previous:
                self._highwater[domain] = frame
                if paused is False:
                    counts['newFrames'] += 1

    def report(self, *, now=None):
        if not self.enabled:
            return None
        now = perf_counter() if now is None else now
        elapsed = now - self._started
        if elapsed < SUMMARY_INTERVAL_SECONDS:
            return None
        result = {'seconds': round(elapsed, 3), 'attempts': self._attempts,
                  'identityChanges': self._identity_changes,
                  'mode': ('idle' if not self._modes else
                           next(iter(self._modes)) if len(self._modes) == 1 else 'mixed'),
                  'attemptModes': dict(self._modes), 'rejections': dict(self._rejections),
                  'guardSources': dict(self._guard_sources),
                  'domains': {name: {
                      'accepted': counts['accepted'], 'newFrames': counts['newFrames'],
                      'newFrameHz': round(counts['newFrames'] / elapsed, 3),
                      'regressions': counts['regressions']}
                      for name, counts in self._domains.items()}}
        self._started = now
        self._clear_window()
        return result
