"""Opt-in diagnostics for a single sampled state, not a global log filter.

Owner-scoped instances keep unrelated modules/sessions independent. Callers pass
stable codes, never timestamps, frame numbers or addresses as state keys. Real
events bypass this helper. None means healthy: silent initially, immediate once
on recovery. This does not control acquisition, retries or network heartbeats.
"""
from threading import RLock
from collections import Counter
from time import monotonic
import json

SUMMARY_INTERVAL_SECONDS = 20.0


class DetailReadLog:
    """Bounded per-reader counters; sample churn is not a lifecycle event.

    Counts are field outcomes, not unique entities. Keep at most three bounded
    failure examples per interval, without raw addresses or payload values.
    Flush only on sampling, at most once per 20 seconds.
    """
    def __init__(self, *, clock=monotonic):
        self._clock = clock
        self._lock = RLock()
        self._reported = None
        self._counts = Counter()
        self._examples = []

    def emit(self, sink, domain, states, source_frame, accepted_frame, *, evidence=None):
        if not callable(sink):
            return
        # Closed vocabulary prevents variable error messages growing the map.
        if domain not in ('enemy_detail', 'character_detail', 'request'):
            domain = 'request'
        with self._lock:
            if evidence:
                cause = evidence.get('capture')
                if cause not in ('plan_cold', 'guard_missing', 'cross_frame',
                                 'guard_incomplete', 'read_failed', 'overlap_conflict',
                                 'plan_miss', ''):
                    cause = 'other'
                self._counts[f'{domain}.capture.{cause or "valid"}'] += 1
                failures = {str(key)[:80]: str(record.get('reason', ''))[:80]
                            for key, record in list(states.items())[:32]
                            if record.get('collectionState') == 'unavailable'
                            and record.get('reason') != 'unsupported_in_source'
                            and key != 'enemy_detail.skills'}
                if failures and len(self._examples) < 3:
                    self._examples.append({
                        'domain': domain, 'entity': str(evidence.get('entity', ''))[:96],
                        'capture': cause, 'fields': failures,
                        'sourceFrame': source_frame, 'acceptedFrame': accepted_frame,
                        'guardStart': evidence.get('guardStart'),
                        'guardEnd': evidence.get('guardEnd')})
            if domain != 'request':
                outcome = ('frame_missing' if source_frame is None or accepted_frame is None
                           else 'same_frame' if source_frame == accepted_frame else 'cross_frame')
                self._counts[f'{domain}.{outcome}'] += 1
            for key, record in states.items():
                state = record.get('collectionState')
                reason = record.get('reason')
                label = state if state in ('current', 'not_collected') else reason
                if key == 'enemy_detail.skills' and reason == 'detail_read_failed':
                    # Heavy detail deliberately does not read skills; the WS
                    # projector uses the primary enemy.skill evidence instead.
                    self._counts['enemy_detail.primary_skill_dependency'] += 1
                    continue
                if label not in ('current', 'not_collected', 'frame_inconsistent',
                                 'unsupported_in_source', 'detail_read_failed', 'batch_failed'):
                    label = 'other'
                self._counts[f'{domain}.{label}'] += 1
            now = self._clock()
            if self._reported is not None and now - self._reported < SUMMARY_INTERVAL_SECONDS:
                return
            line = ('[详情采样诊断] 实体帧/字段结果计数 ' + ', '.join(
                f'{key}={value}' for key, value in sorted(self._counts.items()))
                + f'；末次实体帧 {source_frame}->{accepted_frame}')
            if self._examples:
                line += '；失败样本 ' + json.dumps(self._examples, ensure_ascii=False)
            self._examples.clear()
            self._counts.clear()
            self._reported = now
        try:
            sink(line)
        except Exception:
            pass


def report_poll_snapshot(state_log, sink, snapshot):
    """Normalize the known variable-count diagnostic, not arbitrary event text."""
    message = snapshot.get('msg') or ''
    reason = 'invalid_list_count' if message.startswith('List 数据异常 (cnt=') else message
    state_log.emit(sink, reason or None, '轮询: ' + (message or '读取恢复'),
                   scope=snapshot.get('sourceSessionId'))


class StateLog:
    def __init__(self, *, clock=monotonic):
        self._clock = clock
        self._lock = RLock()
        self._scope = None
        self._state = None
        self._started = self._reported = 0.0
        self._repeats = 0

    def observe(self, state, message, *, scope=None):
        """Return a transition/summary line or None, retaining no payload history."""
        with self._lock:
            now = self._clock()
            if scope != self._scope:
                self._scope, self._state, self._repeats = scope, None, 0
            if state != self._state:
                suffix = ''
                if self._state is not None:
                    suffix = (f'（上一状态持续 {now - self._started:.1f}s；'
                              f'上次报告后重复 {self._repeats} 次）')
                self._state = state
                self._started = self._reported = now
                self._repeats = 0
                return message + suffix
            if state is None:
                return None
            self._repeats += 1
            if now - self._reported < SUMMARY_INTERVAL_SECONDS:
                return None
            line = (f'{message}（状态持续 {now - self._started:.1f}s；'
                    f'上次报告后重复 {self._repeats} 次）')
            self._reported, self._repeats = now, 0
            return line

    def emit(self, sink, state, message, *, scope=None):
        """Diagnostics must not turn a successful memory read into a failure."""
        if not callable(sink):
            return
        line = self.observe(state, message, scope=scope)
        if line is not None:
            try:
                sink(line)
            except Exception:
                pass
