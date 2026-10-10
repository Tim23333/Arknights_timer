"""Deployment scan/poll data obey read validity, policy and history boundaries."""
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt

from backend import desktop_app
from backend.app.field_policy import PolicyStore
from backend.app.services.websocket_api import WebSocketApi
from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader


def test_initial_scan_binds_policy_before_locating_and_reading():
    store = PolicyStore()
    policy = store.commit({key: {'collect': False} for key in (
        'deploy.events', 'deploy.journal', 'stage.squad', 'stage.stage')})
    mc = Mock(connect=Mock(return_value=1))
    reader = DeployTrackerReader(mc)
    reader._read_log_list = Mock()
    reader._read_squad = Mock()
    reader.get_battle_state = Mock(return_value={})
    reader.is_battle_active = Mock(return_value=True)
    seen = []

    def locate():
        assert reader._capture_policy is policy
        reader._publish_stage_info({'stageId': 'test-stage'})
        return True

    reader.locate = locate
    worker = desktop_app.DeployScanWorker('unused', '127.0.0.1:16384', policy=policy)
    worker.stage.connect(seen.append, Qt.ConnectionType.DirectConnection)
    with patch.object(desktop_app, 'MemCore', return_value=mc), \
         patch.object(desktop_app, 'DeployTrackerReader', return_value=reader):
        worker.run()
    reader._read_log_list.assert_not_called()
    reader._read_squad.assert_not_called()
    assert seen == []
    assert reader._stage_info['stageId'] == 'test-stage'
    assert worker.initial_state['policy_generation'] == policy.generation
    assert 'events' not in worker.initial_state and 'squad' not in worker.initial_state


def test_failed_header_reaches_poll_and_ws_as_unavailable():
    store = PolicyStore()
    reader = DeployTrackerReader(Mock())
    reader._logs_list_addr = 0x1000
    reader._read = Mock(return_value=None)
    reader.is_chain_valid = Mock(return_value=True)
    worker = desktop_app.DeployPollWorker(reader, interval=0, policy_provider=store.snapshot)
    packets = []
    worker.isInterruptionRequested = lambda: bool(packets)
    worker.snapshot.connect(lambda *packet: packets.append(packet), Qt.ConnectionType.DirectConnection)
    worker.run()
    events, battle, chain_ok = packets[0]
    assert chain_ok and events == []
    assert battle['collection_state'] == 'unavailable'
    assert '列表头' in battle['reason']
    api = WebSocketApi(enabled=False, app_version='test', policy_provider=store.snapshot)
    api.publish_deploy(events, {}, [], [], metadata=battle)
    payload = api.local_snapshot()['deploy']
    assert payload['meta']['collectionState'] == 'unavailable'
    assert 'events' not in payload and 'journal' not in payload
    api.publish_deploy([], {}, [], [], metadata={'collection_state': 'current'})
    assert api.local_snapshot()['deploy']['events'] == []


def test_failed_poll_keeps_final_history_and_does_not_clear_desktop_rows():
    old = [{'timestamp': 1.5, 'charId': 'char_test'}]
    holder = SimpleNamespace(_deploy_events=old, _deploy_seen=1,
        lbl_deploy_status=Mock(), deploy_table=Mock(), _cache_current_deploy=Mock(),
        _websocket_api=Mock())
    desktop_app.CoachWindow._on_deploy_snapshot(holder, [],
        {'collection_state': 'unavailable', 'reason': 'read_failed'}, True)
    assert holder._deploy_events is old and holder._deploy_seen == 1
    holder._cache_current_deploy.assert_not_called()
    holder.deploy_table.setRowCount.assert_not_called()


def test_old_generation_initial_result_is_not_relabelled_or_cached():
    store = PolicyStore()
    old = store.snapshot()
    current = store.commit({'deploy.events': {'collect': False}})
    reader = Mock()
    holder = SimpleNamespace(btn_deploy_scan=Mock(), lbl_deploy_status=Mock(),
        _field_policy=store, _cache_current_deploy=Mock(),
        _start_deploy_poll=Mock(return_value=True), _on_auto_refresh_step_done=Mock())
    desktop_app.CoachWindow._on_deploy_scan_done(holder, reader, '', {
        'policy_generation': old.generation, 'journalEvents': ['old'],
        'squad': ['old'], 'stage': {'stageId': 'old'}})
    assert holder._deploy_journal == [] and holder._deploy_squad == []
    assert holder._deploy_stage_info == {}
    reader.set_capture_policy.assert_called_once_with(current)
    holder._cache_current_deploy.assert_not_called()
    holder._start_deploy_poll.assert_called_once()


def test_old_generation_early_stage_cannot_republish_after_policy_change():
    store = PolicyStore()
    worker = SimpleNamespace(capture_policy=store.snapshot(), _source_epoch=1)
    store.commit({'stage.stage': {'collect': False}})
    holder = SimpleNamespace(_field_policy=store, _deploy_scan=worker,
        _source_epoch=1, _closing=False, _on_deploy_stage=Mock())
    desktop_app.CoachWindow._on_deploy_stage_from_worker(holder, worker, {'stageId': 'old'})
    holder._on_deploy_stage.assert_not_called()
