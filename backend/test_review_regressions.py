"""Regressions for callbacks, first deployment snapshot and empty detail publication."""
import os
import threading
import json
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QCoreApplication, QEvent, QThread
from PySide6.QtWidgets import QApplication

from backend import desktop_app
from backend.app.services.websocket_api import WebSocketApi


def test_reader_callbacks_survive_scan_worker_deletion():
    app = QApplication.instance() or QApplication([])
    reader = SimpleNamespace(mc=SimpleNamespace(adb_serial='offline', package='offline'),
                             planned_count=0, enemy_addrs=[], connect=lambda: 1,
                             bootstrap=lambda force: True)
    worker = desktop_app.EnemyScanWorker(reader)
    worker.run()
    worker.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    reader.log('read error after scan worker deletion')
    assert reader.progress is None


def test_first_deployment_state_is_read_in_worker_thread():
    app = QApplication.instance() or QApplication([])
    called = []
    class Reader:
        def __init__(self, mc): pass
        def set_status_callback(self, cb): pass
        def set_stage_callback(self, cb): pass
        def locate(self): return True
        def get_state(self):
            called.append(QThread.currentThread() is not app.thread())
            return {'squad': [{'charName': 'offline'}]}
        def close(self): pass
    mc = SimpleNamespace(connect=lambda: 1, close=lambda: None)
    with patch.object(desktop_app, 'MemCore', return_value=mc), patch.object(desktop_app, 'DeployTrackerReader', Reader):
        worker = desktop_app.DeployScanWorker('offline')
        worker.start()
        assert worker.wait(2000)
    assert called == [True]
    assert worker.initial_state['squad'][0]['charName'] == 'offline'


def test_main_thread_deployment_result_does_not_read_reader():
    class Control:
        def setEnabled(self, *args): pass
        def setText(self, *args): pass
    class Reader:
        def get_state(self): raise AssertionError('GUI must not perform memory I/O')
        def set_capture_policy(self, policy): pass
    policy = SimpleNamespace(generation=1)
    holder = SimpleNamespace(btn_deploy_scan=Control(), btn_deploy_export=Control(),
                             lbl_deploy_status=Control(), _deploy_stage_info={}, _deploy_events=[],
                             _auto_refresh_step=None, _toast=None,
                             _field_policy=SimpleNamespace(snapshot=lambda: policy),
                             _provider=SimpleNamespace(peek_frame_count=lambda: None),
                             _attach_deploy_frames=lambda *args: [],
                             _cache_current_deploy=lambda *args: None,
                             _start_deploy_poll=lambda: True,
                             _on_auto_refresh_step_done=lambda *args: None)
    desktop_app.CoachWindow._on_deploy_scan_done(holder, Reader(), '', {'squad': ['snapshot']})
    assert holder._deploy_squad == ['snapshot']


def test_last_character_withdrawal_publishes_empty_details():
    requests = lambda: {'enemy_detail': {'rateHz': 0},
                        'character_detail': {'rateHz': 5, 'scopeAll': True}}
    worker = desktop_app.EnemyPollWorker(object(), detail_request_provider=requests)
    character = SimpleNamespace(addr=101, unique_id=7, cid='offline', name='offline', data_ptr=0)
    worker._external_character_details = {101: character}
    worker._external_detail_revision = 1
    worker._external_detail_due = float('inf')
    api = WebSocketApi(enabled=False, app_version='test')
    first = {'ok': True, 'frame_consistent': True, 'characters': [character], 'enemies': []}
    worker._append_external_details(first)
    api.publish_runtime(first)
    second = {'ok': True, 'frame_consistent': True, 'characters': [], 'enemies': []}
    worker._append_external_details(second)
    api.publish_runtime(second)
    assert second['external_detail_revision'] == 2
    assert api._snapshots['character_detail']['items'] == []


def test_new_session_accepts_same_detail_revision_from_new_worker():
    api = WebSocketApi(enabled=False, app_version='test')
    snapshot = {'external_detail_revision': 1, 'external_character_details': [], 'external_enemy_details': []}
    api.publish_runtime(snapshot)
    api.begin_session()
    api.publish_runtime(snapshot)
    assert 'character_detail' in api._snapshots


def test_packaging_manifest_matches_embedded_runtime_subset(tmp_path):
    from backend.build_exe import _runtime_bundle_manifest
    bundle = tmp_path / 'game_data'
    bundle.mkdir()
    original = {'schema_version': 1, 'files': {
        'catalogs/char_names.json': {'sha256': 'runtime'},
        'reference/pc_x64/dump.cs': {'sha256': 'reference'},
        'README.md': {'sha256': 'guide'}}}
    (bundle / 'manifest.json').write_text(json.dumps(original))
    generated = _runtime_bundle_manifest(bundle, tmp_path / 'backend')
    embedded = json.loads(generated.read_text(encoding='utf-8'))
    assert embedded['files'] == {'catalogs/char_names.json': {'sha256': 'runtime'}}
    assert json.loads((bundle / 'manifest.json').read_text()) == original


def test_desktop_starts_without_forced_windows_elevation():
    calls = []
    application = SimpleNamespace(setWindowIcon=lambda icon: None,
                                  exec=lambda: calls.append('event_loop'))
    window = SimpleNamespace(show=lambda: calls.append('show'))
    factory = SimpleNamespace(instance=lambda: application)
    with patch.object(desktop_app, 'TEST_BUILD', False), \
         patch.object(desktop_app, '_is_admin', return_value=False), \
         patch.object(desktop_app, 'QApplication', factory), \
         patch.object(desktop_app, 'CoachWindow', return_value=window), \
         patch.object(desktop_app.ctypes.windll.shell32, 'ShellExecuteW') as elevate:
        desktop_app.main()
    assert calls == ['show', 'event_loop']
    elevate.assert_not_called()
