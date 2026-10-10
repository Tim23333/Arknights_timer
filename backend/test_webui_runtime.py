"""Real Qt/HTTP bridge tests; no game process or emulator is read.

Run --serve for browser QA against the actual window/controller with source
workers disabled. This is deliberately an unavailable-data test, not fake game
telemetry. Temporary preferences and output stay on the repository's D: volume.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import ExitStack, contextmanager
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings, QEvent
from backend import desktop_app
from backend.app.services.webui_runtime import WebUiRuntime
from backend.app.services.websocket_api import WebSocketApi


class WebUiRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.app.setQuitOnLastWindowClosed(False)
        test_root = Path(__file__).resolve().parents[1] / "UsedMD"
        test_root.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix="webui-test-", dir=test_root)
        self.stack = ExitStack()
        options_class = desktop_app.CustomOptions
        settings = QSettings(str(Path(self.directory.name) / "qt.ini"), QSettings.Format.IniFormat)
        self.stack.enter_context(patch.object(desktop_app, "CustomOptions", lambda: options_class(Path(self.directory.name) / "options.json")))
        self.stack.enter_context(patch.object(desktop_app, "QSettings", lambda *args: settings))
        for method in ("_start_hook_server", "_start_websocket_api", "_start_workers", "_start_timers"):
            self.stack.enter_context(patch.object(desktop_app.CoachWindow, method, lambda self: None))
        self.window = desktop_app.CoachWindow()
        # Isolate both disk logging and the background persistence owner. Qt
        # deleteLater used by this fixture is not the application's closeEvent.
        self.window._diagnostic_logger = desktop_app.DiagnosticLogManager(Path(self.directory.name) / 'logs')
        self.stack.callback(self.window._diagnostic_logger.close)
        self.stack.callback(self.window._departure_history.close)
        self.window._websocket_api = WebSocketApi(False, "test", policy_provider=self.window._field_policy.snapshot)
        self.window._websocket_api.publish_timer({"connected": False, "configured": False, "message": "QA: source workers disabled"})
        self.runtime = WebUiRuntime(self.window, port=0)
        self.url = self.runtime.start()

    def tearDown(self):
        self.runtime.stop()
        self.window._mini_hotkey_timer.stop()
        self.window._theme_timer.stop()
        self.window.deleteLater()
        # processEvents() alone does not deliver DeferredDelete outside exec().
        # Dispose the QObject-owned HTTP bridge before restoring test patches.
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.stack.close()
        self.directory.cleanup()

    def request(self, path, data=None):
        request = Request(self.url + path, data=json.dumps(data).encode() if data is not None else None,
                          headers={"Content-Type": "application/json"} if data is not None else {})
        def read_response():
            with urlopen(request, timeout=6) as response:
                return json.load(response)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(read_response)
            deadline = time.monotonic() + 7
            while not future.done() and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.005)
            return future.result(timeout=1)

    def test_real_window_registry_and_unavailable_clock(self):
        policy = self.request("api/policy")
        self.assertGreater(len(policy["registry"]), 150)
        self.assertIn("enemy.hp", policy["fields"])
        state = self.request("api/state")
        self.assertFalse(state["clock"]["connected"])
        self.assertIsNone(state["clock"].get("gameTime"))

    def test_sse_clock_updates_without_qt_processing_or_external_ws(self):
        # ROOT CAUSE: /api/state polling waited for Qt's 100ms refresh plus the
        # complete entity response. A paused Qt loop must not delay this channel.
        with urlopen(self.url + 'api/stream/clock', timeout=2) as response:
            def read_packet():
                while line := response.readline():
                    if line.startswith(b'data: '):
                        return json.loads(line[6:])
                self.fail('SSE closed without a snapshot')
            self.assertEqual(response.headers['Content-Type'], 'text/event-stream; charset=utf-8')
            first = read_packet()
            self.assertFalse(first['data']['connected'])
            self.window._websocket_api.publish_timer({'connected': True, 'game_time': 2, 'frame_count': 60})
            packet = read_packet()
            self.assertGreater(packet['sequence'], first['sequence'])
            self.assertEqual(packet['data']['fixedFrame'], 60)
            self.assertEqual(packet['data']['gameTime'], 2)
            self.assertFalse(self.window._websocket_api.status_snapshot()['enabled'])

    def test_rng_update_cannot_reformat_an_unpublished_enemy_value(self):
        from tools.enemy_health.enemy_reader import EnemyInfo
        enemy = EnemyInfo(0x1000)
        enemy.hp, enemy.max_hp = 123, 500
        enemy.field_states['enemy.hp'] = {'collectionState': 'current'}
        snapshot = {'ok': True, 'fixed_frame': 100, 'enemies': [enemy], 'characters': []}
        self.window._webui_runtime_snapshot = snapshot
        self.window._websocket_api.publish_runtime(snapshot)
        self.runtime.refresh()
        # Another producer must not reinterpret mutable scanner objects as a
        # new accepted enemy batch. Only a new enemies revision permits this.
        enemy.hp = 99
        self.window._websocket_api.publish_rng({})
        self.runtime.refresh()
        self.assertEqual(self.runtime.state()['enemies']['items'][0]['columns']['hp'], '123.00/500.00')

    def test_webui_hp_and_sp_columns_keep_successful_values_and_zero(self):
        from tools.enemy_health.enemy_reader import EnemyInfo
        from tools.character_status.character_reader import CharacterInfo
        enemy = EnemyInfo(0x1000)
        enemy.hp, enemy.max_hp = 123.25, 500.0
        character = CharacterInfo(addr=0x2000, hp=1631.0, max_hp=1631.0, sp=0.0, max_sp=15)
        enemy.field_states['enemy.hp'] = {'collectionState': 'current'}
        character.field_states = {'character.hp': {'collectionState': 'current'},
                                  'character.sp': {'collectionState': 'current'}}
        snapshot = {'ok': True, 'character_ok': True, 'frame_consistent': True,
                    'fixed_frame': 100, 'enemies': [enemy], 'characters': [character]}
        self.window._webui_runtime_snapshot = snapshot
        self.window._websocket_api.publish_runtime(snapshot)
        self.runtime.refresh()
        state = self.request('api/state')
        self.assertEqual(state['enemies']['items'][0]['columns']['hp'], '123.25/500.00')
        self.assertEqual(state['characters']['items'][0]['columns']['hp'], '1631.00/1631.00')
        self.assertEqual(state['characters']['items'][0]['columns']['sp'], '0.00/15.00')
        self.assertEqual(state["clock"]["fieldStates"]["battle.gameTime"]["collectionState"], "unavailable")
        self.assertIn("/v2/game", state["service"]["ws"]["gameUrl"])

    def test_policy_command_executes_on_qt_thread_and_persists(self):
        policy = self.request("api/policy")
        result = self.request("api/policy", {"generation": policy["generation"], "fields": {"enemy.name": {"publish": False}}})
        self.assertFalse(result["fields"]["enemy.name"]["publish"])
        self.assertFalse(self.window._field_policy.snapshot().enabled("enemy.name", "publish"))
        self.assertTrue((Path(self.directory.name) / "options.json").is_file())

    def test_precision_and_detail_close_are_real_commands(self):
        result = self.request("api/command", {"action": "precision", "params": {"kind": "enemy", "places": 4}})
        self.assertTrue(result["accepted"])
        self.assertEqual(self.window._enemy_dec["default"], 4)
        result = self.request("api/command", {"action": "detail", "params": {"kind": "enemy", "id": None}})
        self.assertTrue(result["accepted"])

    def test_manual_auto_address_runs_once_without_enabling_persistent_setting(self):
        # ROOT CAUSE: the existing auto-address checkbox is a persistent retry
        # mode. A one-shot toolbar action must start the same guest locator
        # without silently changing that mode or spawning duplicate workers.
        with patch.object(desktop_app, 'GuestAddressWorker') as worker_class, \
             patch.object(self.window, '_connect_scan_worker'):
            result = self.request('api/command', {'action': 'auto-address-once', 'params': {}})
            self.assertTrue(result['accepted'])
            self.assertTrue(self.window._guest_addressing_active)
            self.assertFalse(self.window.chk_auto_addressing.isChecked())
            self.assertFalse(self.window._custom_options.get('auto_addressing', 'enabled'))
            worker_class.return_value.start.assert_called_once_with()
            with self.assertRaises(HTTPError) as failure:
                self.request('api/command', {'action': 'auto-address-once', 'params': {}})
            self.assertEqual(failure.exception.code, 400)
            failure.exception.close()
        self.window._guest_worker = None
        self.window._guest_addressing_active = False

    def test_manual_auto_address_failure_preserves_existing_auto_mode(self):
        # A failed manual retry must not turn off the user's persistent mode
        # or discard a clock already adopted by an earlier successful scan.
        self.window.chk_auto_addressing.blockSignals(True)
        self.window.chk_auto_addressing.setChecked(True)
        self.window.chk_auto_addressing.blockSignals(False)
        self.window._auto_addressing_enabled = True
        self.window._custom_options.set('auto_addressing', 'enabled', True)
        old_clock = object()
        self.window._guest_clock = old_clock
        self.window._on_guest_addressed(self.window._guest_addressing_gen, False,
                                        '测试失败', None, once=True)
        self.assertTrue(self.window.chk_auto_addressing.isChecked())
        self.assertTrue(self.window._auto_addressing_enabled)
        self.assertTrue(self.window._custom_options.get('auto_addressing', 'enabled'))
        self.assertIs(self.window._guest_clock, old_clock)
        self.window._guest_clock = None

    def test_character_overview_merges_retired_history_and_obeys_policy(self):
        # ROOT CAUSE: the WebUI overview was raw JSON and omitted the desktop
        # reader's retired-operator history. Reuse its peak merge, not a sum of
        # duplicated instances; collection/display remain independently gated.
        from tools.character_status.character_reader import CharacterInfo
        self.window._field_policy.commit({'character.healing_total': {'display': True}})
        live = CharacterInfo(addr=10, cid='char_a', name='甲', damage_total=100, healing_total=5)
        live.field_states = {f'character.{key}': {'collectionState': 'current'}
                             for key in ('damage_total', 'healing_total')}
        history = CharacterInfo(addr=0, cid='char_a', name='甲', damage_total=90, healing_total=7)
        retired = CharacterInfo(addr=0, cid='char_b', name='乙', damage_total=20, healing_total=0)
        for item in (history, retired):
            item.field_states = {f'character.{key}': {'collectionState': 'historical'}
                                 for key in ('damage_total', 'healing_total')}
        token = CharacterInfo(addr=11, cid='token_a', name='召唤物', is_token=True, damage_total=999)
        self.window._character_stats_history = [history, retired]
        self.window._webui_runtime_snapshot = {'characters': [live, token]}
        self.window._websocket_api.publish_runtime({'ok': True, 'character_ok': True,
            'frame_consistent': True, 'fixed_frame': 100, 'characters': [live, token]})
        self.runtime.refresh()
        overview = self.request('api/state')['characterOverview']
        self.assertTrue(overview['available'])
        self.assertEqual(len(overview['rows']), 2)
        self.assertEqual(overview['rows'][0]['damage'], 100)
        self.assertEqual(overview['rows'][0]['healing'], 7)
        self.assertEqual(overview['rows'][1]['damage'], 20)
        self.window._field_policy.commit({'character.healing_total': {'display': False}})
        # Supply a fresh-generation envelope after policy invalidation.
        self.window._webui_runtime_snapshot = {'characters': [live, token]}
        self.window._websocket_api.publish_runtime({'ok': True, 'character_ok': True,
            'policy_generation': self.window._field_policy.snapshot().generation,
            'frame_consistent': True, 'fixed_frame': 101, 'characters': [live, token]})
        self.runtime.refresh()
        overview = self.request('api/state')['characterOverview']
        self.assertFalse(overview['healingAvailable'])
        self.assertIsNone(overview['rows'][0]['healing'])

    def test_character_overview_does_not_revive_unverified_retired_metric(self):
        from tools.character_status.character_reader import CharacterInfo
        self.window._field_policy.commit({'character.healing_total': {'display': True}})
        retired = CharacterInfo(addr=0, cid='char_b', name='乙', damage_total=20, healing_total=7)
        retired.field_states = {
            'character.damage_total': {'collectionState': 'unavailable'},
            'character.healing_total': {'collectionState': 'historical'}}
        self.window._character_stats_history = [retired]
        self.window._webui_runtime_snapshot = {'characters': []}
        self.window._websocket_api.publish_runtime({'ok': True, 'character_ok': True,
            'frame_consistent': True, 'fixed_frame': 100, 'characters': []})
        self.runtime.refresh()
        overview = self.request('api/state')['characterOverview']
        self.assertTrue(overview['available'])
        self.assertEqual(overview['rows'][0]['name'], '乙')
        self.assertIsNone(overview['rows'][0]['damage'])
        self.assertEqual(overview['rows'][0]['healing'], 7)

    def test_character_overview_cannot_revive_values_after_stop(self):
        self.window._websocket_api.invalidate_domains(('characters',), 'source_stopped')
        self.runtime.refresh()
        overview = self.request('api/state')['characterOverview']
        self.assertFalse(overview['available'])
        self.assertEqual(overview['rows'], [])

    def test_character_overview_missing_read_evidence_is_not_zero_or_stale_value(self):
        from tools.character_status.character_reader import CharacterInfo
        missing = CharacterInfo(addr=10, cid='char_a', name='甲', damage_total=123)
        failed = CharacterInfo(addr=11, cid='char_b', name='乙', damage_total=456,
            field_states={'character.damage_total': {'collectionState': 'unavailable'}})
        self.window._webui_runtime_snapshot = {'characters': [missing, failed]}
        self.window._websocket_api.publish_runtime({'ok': True, 'character_ok': True,
            'frame_consistent': True, 'fixed_frame': 100, 'characters': [missing, failed]})
        self.runtime.refresh()
        overview = self.request('api/state')['characterOverview']
        self.assertEqual(len(overview['rows']), 2)
        self.assertIsNone(overview['rows'][0]['damage'])
        self.assertIsNone(overview['rows'][1]['damage'])

    def test_character_overview_name_and_global_total_follow_local_display_policy(self):
        from tools.character_status.character_reader import CharacterInfo
        self.window._field_policy.commit({'character.name': {'display': False}})
        live = CharacterInfo(addr=10, cid='char_a', name='甲', damage_total=123,
            field_states={'character.damage_total': {'collectionState': 'current'}})
        summary = CharacterInfo(addr=0, is_global_damage_summary=True, global_total_damage=321,
            field_states={'character.global_total_damage': {'collectionState': 'current'}})
        snapshot = {'ok': True, 'character_ok': True, 'frame_consistent': True,
            'fixed_frame': 100, 'characters': [live], 'global_damage_summary': summary}
        self.window._webui_runtime_snapshot = snapshot
        self.window._websocket_api.publish_runtime(snapshot)
        self.runtime.refresh()
        overview = self.request('api/state')['characterOverview']
        self.assertEqual(overview['rows'][0]['name'], '干员 1')
        self.assertEqual(overview['rows'][0]['damage'], 123)
        self.assertEqual(overview['globalTotal'], 321)
        self.window._field_policy.commit({'character.global_total_damage': {'display': False}})
        self.window._websocket_api.publish_runtime(snapshot)
        self.runtime.refresh()
        self.assertIsNone(self.request('api/state')['characterOverview']['globalTotal'])

    def test_damage_quick_switch_uses_existing_collection_policy_and_real_checkbox(self):
        policy = self.request('api/policy')
        self.assertFalse(self.window.chk_unattributed_damage.isChecked())
        result = self.request('api/policy', {'generation': policy['generation'],
            'fields': {'character.unattributed_damage': {'collect': True}}})
        self.assertTrue(result['fields']['character.unattributed_damage']['collect'])
        self.assertTrue(self.window.chk_unattributed_damage.isChecked())
        result = self.request('api/policy', {'generation': result['generation'],
            'fields': {'character.unattributed_damage': {'collect': False},
                       'character.global_total_damage': {'collect': False}}})
        self.assertFalse(result['fields']['character.global_total_damage']['collect'])
        self.assertFalse(self.window.chk_unattributed_damage.isChecked())

    def test_active_planned_enemy_attributes_reach_local_http(self):
        from tools.enemy_health.enemy_reader import EnemyInfo, EnemyReader
        reader = EnemyReader(mc=SimpleNamespace())
        reader.set_capture_policy(self.window._field_policy.snapshot())
        enemy = EnemyInfo(0x2000)
        reader._copy_plan_metadata(enemy, {'roster_id': 1, 'spawn_order': 1}, 'active')
        enemy.eid, enemy.name = 'enemy_test', '测试敌人'
        enemy.hp, enemy.max_hp = 21000, 28000
        enemy.attributes = {0: 28000, 1: 500}
        reader._stamp_fields(enemy, 100)
        snapshot = {'ok': True, 'character_ok': True, 'frame_consistent': True,
                    'fixed_frame': 100, 'enemies': [enemy]}
        self.window._webui_runtime_snapshot = snapshot
        self.window._websocket_api.publish_runtime(snapshot)
        self.runtime.refresh()
        row = self.request('api/state')['enemies']['items'][0]
        self.assertEqual(row['hp'], 21000)
        self.assertEqual(row['maxHp'], 28000)
        self.assertEqual(row['attributes']['1'], 500)
        self.assertEqual(row['fieldStates']['enemy.hp']['collectionState'], 'current')
        self.assertEqual(row['columns']['attr_1'], '500.00')

    def test_global_total_column_reaches_http_without_unattributed_tracking(self):
        from tools.character_status.character_reader import CharacterInfo
        live = CharacterInfo(addr=10, cid='char_a', name='甲', damage_total=123,
            global_total_damage=321, unattributed_tracking_enabled=False,
            field_states={f'character.{key}': {'collectionState': 'current'}
                          for key in ('damage_total', 'global_total_damage')})
        snapshot = {'ok': True, 'character_ok': True, 'frame_consistent': True,
                    'fixed_frame': 100, 'characters': [live]}
        self.window._webui_runtime_snapshot = snapshot
        self.window._websocket_api.publish_runtime(snapshot)
        self.runtime.refresh()
        row = self.request('api/state')['characters']['items'][0]
        self.assertEqual(row['globalDamageSummary'], 321)
        self.assertEqual(row['columns']['global_total_damage'], '321.00')
        self.assertFalse(self.window.chk_unattributed_damage.isChecked())

    def test_one_toast_duration_update_preserves_other_levels(self):
        self.window._custom_options.set("toast", "duration_ms", {"info": 111, "warn": 12345, "error": 999})
        self.request("api/command", {"action": "setting", "params": {"section": "toast", "key": "duration_ms", "value": {"info": 222}}})
        durations = self.window._custom_options.get("toast")["duration_ms"]
        self.assertEqual(durations["info"], 222)
        self.assertEqual(durations["warn"], 12345)

    def test_both_doc_sources_are_readable(self):
        self.assertIn("选择 ADB", self.request("api/docs/guide")["markdown"])
        doc = self.request("api/docs/api")["markdown"]
        self.assertIn("enemy.checkpoint_countdown", doc)
        self.assertIn("/v2/game", doc)

    def test_queued_enemy_wake_cannot_restore_current_values_after_stop(self):
        # A Qt signal can already be queued when stop invalidates the source.
        # While the worker is still unwinding, its saved snapshot must not be
        # consumed again and replace the unavailable envelope with an old frame.
        api = self.window._websocket_api
        api.invalidate_domains(("enemies", "characters"), "source_stopped")
        with patch.object(self.window, "_on_enemy_snapshot") as consume:
            self.window._enemy_poll = SimpleNamespace(
                isInterruptionRequested=lambda: True,
                take_latest_snapshot=lambda: {"ok": True, "fixed_frame": 100})
            try:
                self.window._on_enemy_snapshot_ready({})
                consume.assert_not_called()
            finally:
                self.window._enemy_poll = None
        state = api.local_snapshot()
        self.assertEqual(state["enemies"]["meta"]["collectionState"], "unavailable")
        self.assertEqual(state["enemies"]["items"], [])

    def test_selected_detail_reaches_local_http_without_ws_clients(self):
        # UI-selected heavy data uses the worker's detail_enemy key, independent
        # from external detail subscription tasks. The WS service remains off.
        detail = SimpleNamespace(addr=123, eid="enemy_review", name="QA",
                                 buffs=[{"name": "QA buff"}], raw_attributes={1: 10},
                                 attributes={1: 10}, field_states={})
        self.window._websocket_api.publish_runtime({
            "ok": True, "character_ok": True, "frame_consistent": True,
            "enemies": [], "characters": [], "fixed_frame": 100,
            "detail_enemy": detail})
        self.runtime.refresh()
        state = self.request("api/state")
        self.assertFalse(state["service"]["ws"]["enabled"])
        self.assertEqual(state["enemy_detail"]["items"][0]["buffs"], [{"name": "QA buff"}])

    def test_adb_switch_during_scan_is_rejected_before_preferences_write(self):
        # Only file validation is simulated; the real HTTP/Qt bridge executes the
        # scan guard. No process, reader switch or preference file is touched.
        with patch("pathlib.Path.is_file", return_value=True), \
                patch.object(self.window, "_adb_scan_is_running", return_value=True), \
                patch("tools.enemy_health.memcore.save_adb_config") as persist, \
                patch.object(self.window, "_activate_adb_path") as activate:
            with self.assertRaises(HTTPError) as failure:
                self.request("api/command", {"action": "adb", "params": {
                    "path": "D:/unused/adb.exe", "serial": "test-device"}})
            self.assertEqual(failure.exception.code, 400)
            failure.exception.close()
            persist.assert_not_called()
            activate.assert_not_called()

    def test_adb_detection_is_a_pollable_job_not_a_blocking_http_request(self):
        # ROOT CAUSE: the Web UI only edited two strings and had no equivalent
        # of the desktop emulator discovery/device picker. Slow process and ADB
        # calls must not run on the Qt thread or outlive a synchronous RPC.
        with patch("tools.enemy_health.memcore.find_running_emulator_adbs", return_value=[]):
            result = self.request("api/command", {"action": "adb-detect", "params": {}})
            self.assertIn("id", result)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                job = self.request("api/command", {"action": "adb-job", "params": {"id": result["id"]}})
                if job["status"] != "running":
                    break
            self.assertEqual(job["status"], "error")
            self.assertIn("未", job["message"])

    def adb_command(self, action, **params):
        return self.request("api/command", {"action": action, "params": params})

    def test_webui_receives_backend_toasts_and_auto_refresh_progress(self):
        self.window._toast.show('自动刷新完成', semantic='success')
        self.runtime.refresh()
        state = self.request('api/state')
        self.assertEqual(state['notifications']['items'][-1]['text'], '自动刷新完成')
        self.assertIn('autoRefresh', state['service'])
        with patch.object(self.window, '_wait_guest_ready_then_refresh'):
            self.adb_command('setting', section='auto_detect_stage_change', key='enabled', value=True)
            self.assertTrue(self.window.chk_auto_refresh.isChecked())
            self.assertEqual(self.request('api/state')['service']['autoRefresh']['state'], 'waiting_source')

    def test_webui_log_read_has_cursor_and_export_preserves_all_lines(self):
        self.runtime.diagnostics.logger.log('下载验证行')
        result = self.adb_command('logs-read', after=0, limit=100)
        self.assertIn('sessionId', result)
        self.assertIsInstance(result['items'], list)
        result = self.adb_command('logs-export', format='text')
        job = self.wait_log_job(result)
        self.assertEqual(job['status'], 'done')
        self.assertIn('url', job['result'])
        with urlopen(self.runtime.server.url.rstrip('/') + job['result']['url']) as response:
            self.assertEqual(response.status, 200)
            self.assertIn('attachment', response.headers['Content-Disposition'])
            self.assertIn('下载验证行', response.read().decode('utf-8'))
        with self.assertRaises(HTTPError) as failure:
            urlopen(self.runtime.server.url + 'api/logs/download?id=../options.json')
        self.assertEqual(failure.exception.code, 404)
        failure.exception.close()

    def wait_log_job(self, job):
        deadline = time.monotonic() + 3
        while job['status'] == 'running' and time.monotonic() < deadline:
            job = self.adb_command('logs-job', id=job['id'])
        self.assertNotEqual(job['status'], 'running')
        return job

    def wait_adb_job(self, job, timeout=3):
        deadline = time.monotonic() + timeout
        while job['status'] in {'running', 'stopping'} and time.monotonic() < deadline:
            job = self.adb_command('adb-job', id=job['id'])
        self.assertNotIn(job['status'], {'running', 'stopping'}, job)
        return job

    @contextmanager
    def adb_io(self, rows=None):
        # Only external I/O and the reader-replacement boundary are mocked.
        # Tests still exercise the real HTTP, Qt queue and job lifecycle.
        with ExitStack() as stack:
            probe = stack.enter_context(patch('tools.enemy_health.memcore.probe_adb_executable', return_value=(True, 'ADB version test')))
            query = stack.enter_context(patch('tools.enemy_health.memcore.query_adb_devices', return_value=rows if rows is not None else [{'serial': 'device-a', 'state': 'device'}]))
            persist = stack.enter_context(patch('tools.enemy_health.memcore.save_adb_config', return_value=True))
            activate = stack.enter_context(patch.object(self.window, '_activate_adb_path', return_value=True))
            yield SimpleNamespace(probe=probe, query=query, persist=persist, activate=activate)

    def test_adb_detect_and_device_refresh_do_not_switch_or_save(self):
        candidate = {'adb_path': 'D:/emulator/adb.exe', 'process_name': 'MuMu', 'process_path': 'D:/emulator/MuMu.exe'}
        with self.adb_io() as io, patch('tools.enemy_health.memcore.find_running_emulator_adbs', return_value=[candidate]):
            job = self.wait_adb_job(self.adb_command('adb-detect', path='', serial=''))
            self.assertEqual(job['status'], 'done')
            self.assertEqual(job['result']['candidates'][0]['process_name'], 'MuMu')
            self.assertEqual(job['result']['serial'], 'device-a')
            self.assertEqual(job['result']['devices'][0]['state'], 'device')
            job = self.wait_adb_job(self.adb_command('adb-devices', path=candidate['adb_path'], serial='manual-address'))
            self.assertEqual(job['result']['serial'], 'manual-address')
            io.query.assert_called_with(os.path.normpath(candidate['adb_path']), connect_known=True, connect_serial='manual-address')
            io.activate.assert_not_called()
            io.persist.assert_not_called()

    def test_adb_invalid_version_never_queries_or_switches(self):
        with self.adb_io() as io:
            io.probe.return_value = (False, '执行 adb version 超时')
            job = self.wait_adb_job(self.adb_command('adb', path='D:/unused/adb.exe', serial='device-a'))
            self.assertEqual(job['status'], 'error')
            self.assertIn('超时', job['message'])
            io.query.assert_not_called()
            io.activate.assert_not_called()
            io.persist.assert_not_called()

    def test_adb_offline_unauthorized_empty_and_ambiguous_devices_rejected(self):
        for rows, serial in [([], ''), ([{'serial': 'a', 'state': 'offline'}], 'a'),
                             ([{'serial': 'a', 'state': 'unauthorized'}], 'a'),
                             ([{'serial': 'a', 'state': 'device'}, {'serial': 'b', 'state': 'device'}], ''),
                             ([{'serial': 'a', 'state': 'device'}], 'offline-target')]:
            with self.subTest(rows=rows, serial=serial), self.adb_io(rows) as io:
                job = self.wait_adb_job(self.adb_command('adb', path='D:/unused/adb.exe', serial=serial))
                self.assertEqual(job['status'], 'error')
                io.activate.assert_not_called()
                io.persist.assert_not_called()

    def test_adb_single_online_device_autofills_and_persists_after_switch(self):
        order = []
        with self.adb_io() as io:
            io.activate.side_effect = lambda *args: order.append(('activate', args)) or True
            io.persist.side_effect = lambda *args: order.append(('save', args)) or True
            job = self.wait_adb_job(self.adb_command('adb', path='D:/unused/adb.exe', serial=''))
            self.assertEqual(job['status'], 'done')
            self.assertTrue(job['result']['persisted'])
            self.assertEqual([item[0] for item in order], ['activate', 'save'])
            self.assertEqual(order[0][1][1], 'device-a')

    def test_adb_failed_activation_does_not_persist_and_save_failure_is_visible(self):
        with self.adb_io() as io:
            io.activate.return_value = False
            job = self.wait_adb_job(self.adb_command('adb', path='D:/unused/adb.exe', serial='device-a'))
            self.assertEqual(job['status'], 'error')
            io.persist.assert_not_called()
        with self.adb_io() as io:
            io.persist.return_value = False
            job = self.wait_adb_job(self.adb_command('adb', path='D:/unused/adb.exe', serial='device-a'))
            self.assertEqual(job['status'], 'done')
            self.assertFalse(job['result']['persisted'])
            self.assertIn('保存失败', job['message'])

    def test_adb_slow_query_keeps_http_clock_responsive_and_cancel_ignores_late_result(self):
        entered, release = threading.Event(), threading.Event()
        def slow_query(*args, **kwargs):
            entered.set()
            release.wait(3)
            return [{'serial': 'device-a', 'state': 'device'}]
        with self.adb_io() as io:
            io.query.side_effect = slow_query
            try:
                job = self.adb_command('adb', path='D:/unused/adb.exe', serial='device-a')
                self.assertTrue(entered.wait(1))
                self.assertIn('clock', self.request('api/state'))
                cancelled = self.adb_command('adb-cancel', id=job['id'])
                self.assertEqual(cancelled['status'], 'cancelled')
                with self.assertRaises(HTTPError) as failure:
                    self.adb_command('adb-devices', path='D:/unused/adb.exe', serial='')
                self.assertEqual(failure.exception.code, 400)
                failure.exception.close()
            finally:
                release.set()
                self.runtime.adb_selection._thread.join(1)
                self.app.processEvents()
            io.activate.assert_not_called()
            io.persist.assert_not_called()
            self.assertEqual(self.adb_command('adb-job', id=job['id'])['status'], 'cancelled')

    def test_adb_source_change_during_validation_rejects_old_result(self):
        release = threading.Event()
        with self.adb_io() as io:
            def changed_query(*args, **kwargs):
                # The device changed on the owner while an I/O result was in
                # flight. Only the result is simulated; epoch validation is real.
                release.wait(3)
                return [{'serial': 'device-a', 'state': 'device'}]
            io.query.side_effect = changed_query
            try:
                job = self.adb_command('adb', path='D:/unused/adb.exe', serial='device-a')
                self.window._source_epoch += 1
            finally:
                release.set()
            job = self.wait_adb_job(job)
            self.assertEqual(job['status'], 'error')
            io.activate.assert_not_called()
            io.persist.assert_not_called()

    def test_adb_waits_for_old_monitors_and_restores_auto_refresh(self):
        self.window._auto_refresh_enabled = True
        with self.adb_io() as io, patch.object(self.window, '_stop_enemy_poll', side_effect=[False, True]):
            job = self.wait_adb_job(self.adb_command('adb', path='D:/unused/adb.exe', serial='device-a'))
            self.assertEqual(job['status'], 'done')
            self.assertTrue(self.window._auto_refresh_enabled)
            io.activate.assert_called_once()

    def test_adb_cancel_while_stopping_restores_preference_but_never_switches(self):
        self.window._auto_refresh_enabled = True
        with self.adb_io() as io, patch.object(self.window, '_stop_enemy_poll', return_value=False):
            job = self.adb_command('adb', path='D:/unused/adb.exe', serial='device-a')
            deadline = time.monotonic() + 3
            while job['status'] == 'running' and time.monotonic() < deadline:
                job = self.adb_command('adb-job', id=job['id'])
            self.assertEqual(job['status'], 'stopping')
            self.assertFalse(self.window._auto_refresh_enabled)
            with self.assertRaises(HTTPError) as failure:
                self.adb_command('enemy-scan')
            failure.exception.close()
            self.assertEqual(self.adb_command('adb-cancel', id=job['id'])['status'], 'cancelled')
            self.assertTrue(self.window._auto_refresh_enabled)
            io.activate.assert_not_called()
            io.persist.assert_not_called()

    def test_adb_shutdown_while_validation_is_pending_never_applies(self):
        release = threading.Event()
        with self.adb_io() as io:
            def query(*args, **kwargs):
                release.wait(3)
                return [{'serial': 'device-a', 'state': 'device'}]
            io.query.side_effect = query
            try:
                job = self.adb_command('adb', path='D:/unused/adb.exe', serial='device-a')
                self.window._closing = True
            finally:
                release.set()
            job = self.wait_adb_job(job)
            self.assertEqual(job['status'], 'cancelled')
            io.activate.assert_not_called()
            io.persist.assert_not_called()

    def test_adb_stopping_timeout_never_switches_and_only_requests_stop_once(self):
        # A genuinely owned old poll worker is not released, simulating a slow
        # socket unwind. Let the real 15 s stop deadline expire; no fake clock.
        old_poll = SimpleNamespace()
        self.window._enemy_poll = old_poll
        try:
            with self.adb_io() as io, patch.object(self.window, '_stop_enemy_poll', return_value=False) as stop:
                job = self.wait_adb_job(self.adb_command('adb', path='D:/unused/adb.exe', serial='device-a'), timeout=17)
                self.assertEqual(job['status'], 'error')
                self.assertIn('尚未完全退出', job['message'])
                stop.assert_called_once()
                io.activate.assert_not_called()
                io.persist.assert_not_called()
        finally:
            self.window._enemy_poll = None

    def test_adb_rechecks_shutdown_and_source_epoch_while_old_worker_is_stopping(self):
        for change in ('closing', 'epoch'):
            with self.subTest(change=change):
                self.window._enemy_poll = SimpleNamespace()
                try:
                    with self.adb_io() as io, patch.object(self.window, '_stop_enemy_poll', return_value=False):
                        job = self.adb_command('adb', path='D:/unused/adb.exe', serial='device-a')
                        deadline = time.monotonic() + 3
                        while job['status'] == 'running' and time.monotonic() < deadline:
                            job = self.adb_command('adb-job', id=job['id'])
                        self.assertEqual(job['status'], 'stopping')
                        if change == 'closing':
                            self.window._closing = True
                        else:
                            self.window._source_epoch += 1
                        job = self.wait_adb_job(job)
                        self.assertEqual(job['status'], 'cancelled' if change == 'closing' else 'error')
                        io.activate.assert_not_called()
                        io.persist.assert_not_called()
                finally:
                    self.window._enemy_poll = None
                    self.window._closing = False

    def test_adb_local_picker_is_async_cancelable_and_does_not_apply(self):
        from PySide6.QtWidgets import QFileDialog
        with patch.object(QFileDialog, 'open') as open_picker, self.adb_io() as io:
            job = self.adb_command('adb-browse', path='D:/unused/adb.exe', serial='')
            self.assertEqual(job['status'], 'running')
            open_picker.assert_called_once()
            # ROOT CAUSE: rapid cancellation/deletion of Qt 6.9.2's Windows
            # native asynchronous dialog logged cleanupThread failed to finish
            # in the source app. The widget picker avoids that helper thread.
            self.assertTrue(self.runtime.adb_selection._dialog.testOption(QFileDialog.Option.DontUseNativeDialog))
            self.runtime.adb_selection._dialog.fileSelected.emit('D:/selected/adb.exe')
            job = self.adb_command('adb-job', id=job['id'])
            self.assertEqual(job['status'], 'done')
            self.assertEqual(Path(job['result']['path']), Path('D:/selected/adb.exe'))
            self.runtime.adb_selection._dialog.accept()
            job = self.adb_command('adb-browse', path='', serial='')
            self.assertEqual(self.adb_command('adb-cancel', id=job['id'])['status'], 'cancelled')
            self.assertIsNone(self.runtime.adb_selection._dialog)
            io.activate.assert_not_called()
            io.persist.assert_not_called()

    def test_adb_rejects_stale_job_and_invalid_types(self):
        for action, params in [('adb-job', {'id': 'expired'}), ('adb-cancel', {'id': 'expired'}),
                               ('adb-devices', {'path': [], 'serial': ''}),
                               ('adb-devices', {'path': 'adb.exe', 'serial': 'a' * 257})]:
            with self.subTest(action=action), self.assertRaises(HTTPError) as failure:
                self.adb_command(action, **params)
            self.assertEqual(failure.exception.code, 400)
            failure.exception.close()


if __name__ == "__main__":
    if "--serve" in sys.argv:
        fixture = WebUiRuntimeTests()
        fixture.setUp()
        print(json.dumps({"url": fixture.url, "mode": "real-window-no-source-workers"}), flush=True)
        try:
            fixture.app.exec()
        finally:
            fixture.tearDown()
    else:
        unittest.main()
