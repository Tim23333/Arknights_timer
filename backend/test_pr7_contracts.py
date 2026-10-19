"""PR7 regression boundaries: owned samples, lifecycle and presentation."""
import json
import time
from unittest.mock import Mock

import pytest

from backend.app.services import public_json
from backend.app.services.frontend_presentation import FrontendPresentation
from backend.app.services.websocket_api import WebSocketApi
from tools.enemy_health.battle_lifecycle import LifecycleTracker
from tools.enemy_health.detail_snapshot import DetailSnapshot, DetailSnapshotPool


@pytest.mark.parametrize('payload', (
    {'zero': 0, 'false': False, 'empty': [], 'unknown': None},
    {'name': '琴柳', 'value': 0.125},
    {'large': 2 ** 80},
))
@pytest.mark.parametrize('accelerated', (True, False))
def test_json_acceleration_and_fallback_preserve_text_values(monkeypatch, payload, accelerated):
    if not accelerated:
        monkeypatch.setattr(public_json, '_orjson', None)
    encoded = public_json.encode_sanitized(payload)
    assert isinstance(encoded, str)
    assert json.loads(encoded) == payload


def state(battle=(1, 2), *, ready=True, transiting=False, target='level_1'):
    return dict(battle=battle, ready=ready, transiting=transiting,
                source='level_1', target=target)


def test_lifecycle_unknown_does_not_fabricate_exit_or_readiness():
    tracker = LifecycleTracker()
    assert tracker.observe(state()) == []
    assert tracker.observe(state()) == ['ready']
    assert tracker.observe(None) == []
    assert tracker.active == (1, 2) and not tracker.ready
    assert tracker.observe(state()) == []
    assert not tracker.ready
    assert tracker.observe(state()) == []
    assert tracker.ready


def test_same_level_new_instance_exits_once_and_requires_stable_readiness():
    tracker = LifecycleTracker()
    tracker.observe(state()); tracker.observe(state())
    assert tracker.observe(state((3, 4))) == ['exit']
    assert not tracker.ready
    assert tracker.observe(state((3, 4))) == ['ready']
    assert tracker.observe(state((3, 4))) == []
    assert tracker.observe(state((3, 4), ready=False, transiting=True, target='battle_finish')) == ['exit']
    assert tracker.observe(state((3, 4), ready=False, transiting=True, target='battle_finish')) == []


@pytest.mark.parametrize('values,guard,reason', (
    ([None], {'complete': True, 'start': 1, 'end': 1}, 'read_failed'),
    ([b'x'], {'complete': True, 'start': 1, 'end': 1}, 'read_failed'),
    ([b'abcd'], {'complete': True, 'start': 1, 'end': 2}, 'cross_frame'),
    ([b'abcd'], {'complete': False, 'start': 1, 'end': 1}, 'guard_incomplete'),
    ([], {'complete': True, 'start': 1, 'end': 1}, 'guard_incomplete'),
))
def test_detail_incomplete_or_cross_frame_capture_is_never_current(values, guard, reason):
    channel = Mock()
    channel.guarded_transaction_read.return_value = (values, guard)
    snapshot = DetailSnapshot(channel, [(100, 4)], 99)
    assert not snapshot.valid and snapshot.frame is None
    assert snapshot.failure_reason == reason


def test_detail_discovery_bytes_cannot_become_current_or_survive_a_round():
    channel = Mock()
    channel.batch_read.return_value = [b'old!']
    pool = DetailSnapshotPool()
    cold = pool.begin('entity', channel, 99)
    assert cold.read([(100, 4)]) == [b'old!']
    assert not cold.valid and cold.frame is None
    pool.end('entity', cold)
    assert not cold.values and not cold.prefixes
    channel.guarded_transaction_read.return_value = ([b'new!'], {'complete': True, 'start': 2, 'end': 2})
    warm = pool.begin('entity', channel, 99)
    assert warm.valid and warm.frame == 2
    assert warm.read([(100, 4)]) == [b'new!']
    pool.end('entity', warm)


def test_detail_same_address_prefix_conflict_is_rejected():
    channel = Mock()
    channel.guarded_transaction_read.return_value = (
        [b'abcdefgh', b'xxxx'], {'complete': True, 'start': 2, 'end': 2})
    snapshot = DetailSnapshot(channel, [(100, 8), (100, 4)], 99)
    assert not snapshot.valid and snapshot.failure_reason == 'overlap_conflict'


def test_desktop_and_multiple_web_pages_can_consume_together():
    presentation = FrontendPresentation()
    assert presentation.native_active and presentation.web_active
    assert presentation.page_status('first', now=0)['active']
    assert presentation.page_status('second', now=1)['active']
    assert presentation.stream_allowed('first', now=2)
    assert presentation.stream_allowed('second', now=2)
    assert presentation.status() == {'mode': 'shared'}
    assert presentation.native_active and presentation.web_active
    assert not presentation.stream_allowed('x' * 129)


def test_accepted_public_snapshot_is_independent_of_producer_mutation():
    api = WebSocketApi(False, 'test')
    events = [{'timestamp': 1.0, 'op': 0, 'charId': 'char_test'}]
    api.publish_deploy(events, {}, [], [])
    events[0]['op'] = 2
    events.append({'timestamp': 2.0, 'op': 1})
    accepted = api.local_snapshot()['deploy']['events']
    assert len(accepted) == 1 and accepted[0]['op'] == 0


def test_close_retry_is_cancelled_when_qt_owner_is_destroyed():
    from PySide6.QtCore import QObject, QEvent
    from PySide6.QtWidgets import QApplication
    from backend.desktop_app import CoachWindow
    app = QApplication.instance() or QApplication([])
    owner = QObject()
    owner._closing = True
    owner._close_retry_pending = False
    closed = owner.close = Mock()
    CoachWindow._schedule_close_retry(owner)
    owner.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    time.sleep(.3)
    app.processEvents()
    closed.assert_not_called()
