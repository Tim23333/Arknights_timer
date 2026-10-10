"""Bounded single-battle departure history, not a recording of live frames.

The Qt owner observes already accepted snapshots. A single coalescing writer
owns disk IO and atomic replacement. Restoration is a presentation-side copy:
it cannot resurrect recycled pointers or mutate the memory reader's roster.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time

from ..field_policy import FIELD_REGISTRY, collection_record
from ..storage_paths import data_root
from tools.enemy_health.enemy_reader import EnemyInfo


# Only public basic snapshot fields are durable. Pointer chains and asynchronous
# detail objects never cross this boundary. Nested paths share containers but not
# policy ownership; disabling one field must not resurrect it on re-enable.
_FIELD_PATHS = {
    'name': ('name',), 'code': ('code',), 'eid': ('eid',),
    'hp': ('hp', 'max_hp'), 'pos': ('pos_x', 'pos_y'),
    'precise_pos': ('precise_pos_x', 'precise_pos_y', 'precise_pos_valid'),
    'action_state': ('state_id', 'action.state_id', 'action.state_name'),
    'action_phase': tuple('action.' + key for key in (
        'name', 'phase', 'detail', 'elapsed_frames', 'skill_name', 'ready_skills', 'clock_source')),
    'remaining_time': tuple('action.' + key for key in ('remaining', 'remaining_frames', 'remaining_kind')),
    'next_action': tuple('action.' + key for key in (
        'next_action', 'next_action_detail', 'next_action_confidence', 'next_action_lane',
        'next_action_candidates', 'next_action_rule', 'next_action_rule_detail',
        'next_action_rule_confidence', 'next_action_rule_candidates')),
    'abnormal_status': ('abnormal_flags', 'abnormal_combos', 'status_timers'),
    'immune_status': ('abnormal_immunes', 'abnormal_combo_immunes'),
    'shield': ('shield', 'special_shield'), 'es': ('es',),
    'skill': ('skills', 'skills_detail'), 'ep_break': ('ep_break_recovery',),
    'intent_end': ('pathing.intent_end',), 'current_route': ('pathing.route',),
    'next_waypoint': ('pathing.next_waypoint',),
    'next_checkpoint': ('pathing.next_checkpoint',),
    'checkpoint_countdown': ('pathing.checkpoint_countdown',),
    'end_reason': ('end_reason',), 'end_frame': ('end_frame',),
    'finish_reason': ('finish_reason',),
}
for _index in (1, 2, 3, 4, 5):
    _FIELD_PATHS[('ep_sanity', 'ep_water', 'ep_fire', 'ep_dark', 'ep_anger')[_index - 1]] = (
        f'ep_remaining.{_index}',)
for _spec in FIELD_REGISTRY.values():
    if _spec.domain == 'enemy' and _spec.id.startswith('enemy.attr_'):
        _attribute_index = int(_spec.id.rsplit('_', 1)[1])
        _mirror = {0: 'max_hp', 1: 'atk', 2: 'def_', 3: 'res', 6: 'mspd', 7: 'aspd'}.get(_attribute_index)
        _FIELD_PATHS[_spec.id.split('.', 1)[1]] = (
            (f'attributes.{_attribute_index}', _mirror) if _mirror
            else (f'attributes.{_attribute_index}',))


def _value_at(enemy, path):
    parts = path.split('.')
    value = getattr(enemy, parts[0], None)
    for part in parts[1:]:
        if not isinstance(value, dict):
            return None
        value = value.get(int(part) if part.isdigit() else part)
    return value


def _safe_value(value):
    """Normalize JSON-safe historical values, dropping nested address metadata.

    Before: {1: 3.0, 'cursorAddress': 123, 'bad': float('nan')}
    After: {'1': 3.0, 'bad': None}
    """
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()
                if not any(word in str(key).lower() for word in ('address', 'pointer', '_ptr'))
                and str(key).lower() != 'addr' and not str(key).lower().endswith('_addr')}
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    return None


def _set_value(enemy, path, value):
    parts = path.split('.')
    value = copy.deepcopy(value)
    if len(parts) == 1:
        setattr(enemy, parts[0], value)
        return
    target = getattr(enemy, parts[0])
    target[int(parts[1]) if parts[1].isdigit() else parts[1]] = value


class DepartureHistory:
    """Restore only validated same-battle, planned departed basic snapshots.

    Use from the snapshot owner after frame/generation validation. Identity and
    live witnesses come from the sampling worker, never from a later global
    clock lookup. Unknown identity postpones restoration and file replacement.
    Runtime summons without stable plan identity are intentionally not restored.
    """
    SCHEMA = 1
    MAX_BYTES = 16 * 1024 * 1024
    MAX_RECORDS = 10000

    def __init__(self, path: Path | None = None, log=lambda _message: None):
        self.path = Path(path) if path is not None else data_root() / 'cache' / 'current_battle.json'
        self.log = log
        self._identity = None
        self._records = {}
        self._loaded = self._load()
        self._last_frame = None
        self._last_signature = None
        self._observed_signatures = {}
        self._revision = 0
        self._document = None
        self._last_queued = 0.0
        self._blocked_identity = None
        self._minimum_epoch = 0
        self._condition = threading.Condition()
        self._pending = None
        self._closed = False
        self._thread = threading.Thread(target=self._write_loop, name='departure-history', daemon=True)
        self._thread.start()

    def _load(self):
        try:
            if not self.path.exists():
                return None
            if self.path.stat().st_size > self.MAX_BYTES:
                raise ValueError('文件过大')
            payload = json.loads(self.path.read_text(encoding='utf-8'))
            if (not isinstance(payload, dict) or payload.get('schema') != self.SCHEMA
                    or not isinstance(payload.get('records'), list)
                    or len(payload['records']) > self.MAX_RECORDS):
                raise ValueError('格式或版本不匹配')
            checksum = payload.pop('checksum', None)
            canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')
            if checksum != hashlib.sha256(canonical).hexdigest():
                raise ValueError('完整性校验失败')
            # Malformed records cannot reach attribute assignment on a live model.
            for record in payload['records']:
                if (not isinstance(record, dict) or type(record.get('roster_id')) is not int
                        or not isinstance(record.get('eid'), str)
                        or not isinstance(record.get('fields'), dict)
                        or not isinstance(record.get('erased', []), list)
                        or any(key not in FIELD_REGISTRY for key in record.get('erased', []))):
                    raise ValueError('离场记录格式错误')
                for field_id, saved in record['fields'].items():
                    key = field_id.split('.', 1)[-1]
                    if (field_id not in FIELD_REGISTRY or key not in _FIELD_PATHS
                            or not isinstance(saved, dict) or not isinstance(saved.get('state'), dict)
                            or not isinstance(saved.get('values'), dict)
                            or any(path not in _FIELD_PATHS[key] for path in saved['values'])):
                        raise ValueError('历史字段格式错误')
            return payload
        except (OSError, ValueError, TypeError, RecursionError) as error:
            self.log(f'[离场缓存] 读取失败，忽略缓存：{error}')
            return None

    def invalidate(self, source_epoch=None):
        """Invalidate on the timer's underlying battle-reset event, even if auto scan is off.

        Remember the old identity until the reader locates new objects. An old
        worker cannot repopulate the file after reset. A queued tombstone replaces
        the last battle atomically; there is no unlink/write race.
        """
        self._blocked_identity = self._identity if source_epoch is None else None
        if source_epoch is not None:
            self._minimum_epoch = source_epoch
        self._identity = None
        self._loaded = None
        self._records = {}
        self._last_signature = None
        self._observed_signatures = {}
        self._last_frame = None
        self._document = None
        self._queue({'schema': self.SCHEMA, 'identity': None, 'records': []})

    @staticmethod
    def capture_identity(reader, snapshot):
        """Capture process/battle provenance while the sampling worker owns the reader.

        Linux boot ID plus process start ticks distinguishes reused PIDs. Battle
        object addresses distinguish concurrent allocations; a matching live
        entity witness is additionally required before disk history restoration.
        No extra memory or ADB reads occur in the frame loop.
        """
        mc = getattr(reader, 'mc', None)
        birth = getattr(mc, 'process_instance', None)
        level_id = getattr(reader, 'plan_level_id', '')
        if (not birth or not getattr(reader, 'bc_addr', 0)
                or not getattr(reader, 'sched_addr', 0) or not level_id):
            snapshot['_history_identity'] = None
            return
        parts = (getattr(mc, 'adb_serial', ''), mc.package, mc.pid, birth,
                 reader.bc_addr, reader.sched_addr, level_id)
        snapshot['_history_identity'] = hashlib.sha256(repr(parts).encode()).hexdigest()
        snapshot['_history_witnesses'] = [hashlib.sha256(repr((
            enemy.addr, enemy.eid, enemy.id_ptr, enemy.data_ptr)).encode()).hexdigest()
            for enemy in snapshot.get('enemies', ())
            if enemy.lifecycle == 'active' and enemy.alive and enemy.addr and enemy.eid]

    def discard_disabled(self, policy):
        """Erase disabled capture fields immediately, including dormant disk restoration."""
        changed = False
        sources = (list(self._records.values()) + (self._loaded or {}).get('records', [])
                   + (self._document or {}).get('records', []))
        for record in sources:
            for field_id in list(record['fields']):
                if not policy.enabled(field_id):
                    del record['fields'][field_id]
                    erased = record.setdefault('erased', [])
                    if field_id not in erased:
                        erased.append(field_id)
                    changed = True
        if changed:
            self._last_signature = None
            self._observed_signatures = {}
            self._revision += 1
            if self._loaded is not None:
                self._queue(copy.deepcopy(self._loaded))
            elif self._document is not None:
                self._queue(copy.deepcopy(self._document))

    def observe(self, snapshot, policy):
        """Merge historical copies into one accepted snapshot and coalesce durable updates."""
        self.discard_disabled(policy)
        frame = snapshot.get('fixed_frame')
        identity = snapshot.get('_history_identity')
        witnesses = set(snapshot.get('_history_witnesses') or ())
        if (not snapshot.get('ok') or not snapshot.get('frame_consistent')
                or snapshot.get('state') != 2 or type(frame) is not int or frame < 0
                or snapshot.get('_history_epoch', 0) < self._minimum_epoch
                or not identity or identity == self._blocked_identity):
            return
        if identity != self._identity:
            self._identity = identity
            self._records = {}
            self._last_frame = None
            self._last_signature = None
            self._observed_signatures = {}
        if self._last_frame is not None and frame < self._last_frame:
            # Also reject same-ID replays when the owner missed a timer reset.
            self._records = {}
            self._loaded = None
            self._last_signature = None
        self._last_frame = frame
        if self._loaded is not None:
            previous = self._loaded
            saved_frame = previous.get('frame')
            if previous.get('identity') != identity or type(saved_frame) is not int or frame < saved_frame:
                self._loaded = None
            elif not witnesses.intersection(previous.get('witnesses') or ()):
                # Wait for continuity evidence; don't destroy a potentially valid
                # old file just because every previous live witness has departed.
                return
            else:
                self._records = {record['roster_id']: record for record in previous['records']}
                self._loaded = None
                self.log(f'[离场缓存] 已验证同局，恢复 {len(self._records)} 条计划敌人历史')

        enemies = list(snapshot.get('enemies') or ())
        for index, enemy in enumerate(enemies):
            if not enemy.planned or enemy.lifecycle != 'departed':
                continue
            saved = self._records.get(enemy.roster_id)
            restored = (saved and saved['eid'] == enemy.eid and enemy.source_frame is None
                    and enemy.end_frame is None and not enemy.end_reason)
            if restored:
                enemies[index] = enemy = self._restore(saved, enemy, frame, policy)
            # Late attachment placeholders have identity but no observed terminal
            # metadata or successful live sample. They must not overwrite history.
            if not restored and (enemy.source_frame is not None or enemy.end_frame is not None):
                observed = (id(enemy), enemy.source_frame, enemy.end_frame,
                            enemy.end_reason, enemy.finish_reason, policy.generation)
                if self._observed_signatures.get(enemy.roster_id) != observed:
                    self._records[enemy.roster_id] = self._encode(enemy, policy)
                    self._observed_signatures[enemy.roster_id] = observed
                    self._revision += 1
        snapshot['enemies'] = enemies
        signature = (policy.generation, self._revision)
        now = time.monotonic()
        if signature != self._last_signature or now - self._last_queued >= 15:
            self._last_signature = signature
            self._last_queued = now
            self._document = {'schema': self.SCHEMA, 'identity': identity, 'frame': frame,
                              'witnesses': sorted(witnesses),
                              'records': copy.deepcopy(list(self._records.values())[:self.MAX_RECORDS])}
            self._queue(copy.deepcopy(self._document))

    def _encode(self, enemy, policy):
        fields = {}
        erased = list(self._records.get(enemy.roster_id, {}).get('erased', []))
        for field_id, state in enemy.field_states.items():
            key = field_id.split('.', 1)[-1]
            if (key in _FIELD_PATHS and policy.enabled(field_id) and field_id not in erased
                    and state.get('collectionState') in ('current', 'historical', 'static')):
                values = {path: _safe_value(_value_at(enemy, path)) for path in _FIELD_PATHS[key]}
                numeric = ('hp', 'max_hp', 'pos_x', 'pos_y', 'precise_pos_x', 'precise_pos_y',
                           'atk', 'def_', 'res', 'mspd', 'aspd', 'shield', 'special_shield', 'es')
                if any((path in numeric or path.startswith('attributes.'))
                       and (type(value) not in (int, float) or not math.isfinite(value))
                       for path, value in values.items()):
                    # Invalid numeric readings are not successful historical
                    # values. In particular NaN -> null must not later reach the
                    # desktop's numeric formatting as a supposedly valid HP.
                    continue
                fields[field_id] = {'state': _safe_value(state), 'values': values}
        return {'roster_id': enemy.roster_id, 'eid': enemy.eid,
                'source_frame': enemy.source_frame, 'fields': fields, 'erased': erased}

    def _restore(self, saved, placeholder, frame, policy):
        enemy = EnemyInfo(0)  # Frozen history must never trigger a recycled-object read.
        for key in ('eid', 'name', 'code', 'roster_id', 'spawn_order', 'wave_index',
                    'fragment_index', 'action_index', 'spawn_index', 'route_index',
                    'planned', 'spawn_kind', 'spawn_source', 'is_summon',
                    'spawn_frame', 'spawn_eta', 'spawn_condition'):
            setattr(enemy, key, getattr(placeholder, key))
        enemy.lifecycle = 'departed'
        enemy.alive = False
        enemy.source_frame = saved.get('source_frame')
        enemy.policy_generation = policy.generation
        for field_id, spec in FIELD_REGISTRY.items():
            if spec.domain != 'enemy':
                continue
            stored = saved['fields'].get(field_id)
            if policy.enabled(field_id) and stored:
                for path, value in stored['values'].items():
                    _set_value(enemy, path, value)
                enemy.field_states[field_id] = dict(stored['state'],
                    collectionState=('static' if stored['state'].get('collectionState') == 'static' else 'historical'),
                    latestKnownFrame=frame, generation=policy.generation, reason='restored_history')
                if spec.group == 'pathing':
                    enemy.pathing['sample_frame'] = stored['state'].get('sourceFrame')
            else:
                current = placeholder.field_states.get(field_id, {})
                if (policy.enabled(field_id) and (spec.group == 'identity'
                        or field_id in ('enemy.life_status', 'enemy.spawn_wait'))
                        and current.get('collectionState') in ('current', 'static', 'historical')):
                    enemy.field_states[field_id] = dict(current)
                else:
                    enemy.field_states[field_id] = collection_record(None, frame, policy.generation,
                        'unavailable' if policy.enabled(field_id) else 'not_collected',
                        'historical_source_unavailable' if policy.enabled(field_id) else 'capture_disabled')
        enemy.pathing.update(available=False, historical=True, reason='departed')
        return enemy

    def _queue(self, payload):
        with self._condition:
            if self._closed:
                return
            self._pending = payload  # One latest job, never an unbounded frame queue.
            self._condition.notify()

    def _write_loop(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._pending is not None or self._closed)
                if self._pending is None:
                    return
                payload, self._pending = self._pending, None
            # Unique staging file: separate application instances must not unlink
            # each other's in-flight atomic replacement. Final cache stays one file.
            temporary = self.path.with_name(f'.{self.path.name}.{os.getpid()}.{id(self)}.tmp')
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')
                encoded = json.dumps(dict(payload, checksum=hashlib.sha256(canonical).hexdigest()),
                                     ensure_ascii=False, allow_nan=False).encode('utf-8')
                if len(encoded) > self.MAX_BYTES:
                    raise ValueError('离场缓存超过大小上限')
                with temporary.open('wb') as output:
                    output.write(encoded)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.path)
            except (OSError, ValueError, TypeError) as error:
                self.log(f'[离场缓存] 写入失败，实时采集继续：{error}')
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def close(self, timeout=2.0):
        """Flush the latest job; bounded waiting keeps Qt shutdown responsive."""
        with self._condition:
            self._closed = True
            self._condition.notify()
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
