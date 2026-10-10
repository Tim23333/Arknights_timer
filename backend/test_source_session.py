"""Late source results must not cross game/device sessions at equal policy generation."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from backend.desktop_app import CoachWindow


class SourceSessionTests(unittest.TestCase):
    def test_reset_invalidates_sources_even_when_auto_refresh_is_off(self):
        api = Mock()
        window = SimpleNamespace(_closing=False, _source_epoch=4,
            _websocket_api=api, _auto_refresh_enabled=False,
            _webui_runtime_snapshot={'enemies': ['old']},
            lbl_enemy_status=Mock(), lbl_character_status=Mock(),
            lbl_rng_status=Mock(), lbl_deploy_status=Mock())
        CoachWindow._on_game_time_reset_main(window)
        self.assertEqual(window._source_epoch, 5)
        self.assertEqual(window._webui_runtime_snapshot, {})
        api.begin_session.assert_called_once()
        self.assertEqual(api.invalidate_domains.call_args.args[1], 'session_changed')
        self.assertIn('rng', api.invalidate_domains.call_args.args[0])
        window.lbl_enemy_status.setText.assert_called_once()

    def test_old_scan_result_is_discarded_before_adoption(self):
        worker = SimpleNamespace(_source_epoch=3, result=(object(), 'old'),
                                 wait=Mock(), deleteLater=Mock())
        window = SimpleNamespace(_source_epoch=4, _deploy_scan=worker,
            _closing=False, _auto_refresh_stopping_step=None,
            _scan_worker_attr=CoachWindow._scan_worker_attr,
            _discard_scan_result=Mock(), _on_deploy_scan_done=Mock(), btn_deploy_scan=Mock())
        CoachWindow._on_scan_worker_finished(window, 'deploy', worker)
        window._discard_scan_result.assert_called_once_with('deploy', worker.result)
        window._on_deploy_scan_done.assert_not_called()
        self.assertIsNone(window._deploy_scan)
        window.btn_deploy_scan.setEnabled.assert_called_once_with(True)

    def test_old_enemy_poll_cannot_publish_after_reset(self):
        poll = SimpleNamespace(_source_epoch=1, isInterruptionRequested=lambda: False,
                               take_latest_snapshot=Mock(return_value={'ok': True}))
        window = SimpleNamespace(_source_epoch=2, _enemy_poll=poll,
                                 _on_enemy_snapshot=Mock())
        CoachWindow._on_enemy_snapshot_ready(window, {})
        poll.take_latest_snapshot.assert_not_called()
        window._on_enemy_snapshot.assert_not_called()

    def test_old_deploy_poll_cannot_publish_after_reset(self):
        poll = SimpleNamespace(_source_epoch=1, isInterruptionRequested=lambda: False)
        window = SimpleNamespace(_source_epoch=2, _deploy_poll=poll, _closing=False,
                                 _on_deploy_snapshot=Mock())
        CoachWindow._on_deploy_snapshot_from_worker(window, poll, ['old'], {}, True)
        window._on_deploy_snapshot.assert_not_called()

    def test_old_rng_service_cannot_publish_after_reset(self):
        svc = Mock()
        svc.snapshot.side_effect = RuntimeError('Old source must not be queried')
        window = SimpleNamespace(_source_epoch=2, _rng_source_epoch=1, _rng_svc=svc,
            _field_policy=SimpleNamespace(snapshot=lambda: None),
            rng_pred_spin=SimpleNamespace(value=lambda: 1))
        CoachWindow._on_rng_tick(window)
        svc.set_capture_policy.assert_not_called()
        svc.snapshot.assert_not_called()

    def test_old_rng_status_cannot_restore_live_label_after_reset(self):
        window = SimpleNamespace(_closing=False, _source_epoch=2, _rng_source_epoch=1,
                                 _rng_svc=Mock(), lbl_rng_status=Mock())
        CoachWindow._on_rng_runtime_status(window, 'old source monitoring')
        window.lbl_rng_status.setText.assert_not_called()

    def test_early_stage_callback_cannot_republish_old_stage(self):
        worker = SimpleNamespace(_source_epoch=1)
        window = SimpleNamespace(_source_epoch=2, _deploy_scan=worker,
                                 _closing=False, _on_deploy_stage=Mock())
        CoachWindow._on_deploy_stage_from_worker(window, worker, {'stageId': 'old'})
        window._on_deploy_stage.assert_not_called()

    def test_scan_connection_captures_source_epoch(self):
        worker = SimpleNamespace(finished=Mock())
        window = SimpleNamespace(_source_epoch=7, _on_scan_worker_finished=Mock())
        CoachWindow._connect_scan_worker(window, 'deploy', worker)
        self.assertEqual(worker._source_epoch, 7)
        window._source_epoch = 8
        worker.finished.connect.call_args.args[0]()
        window._on_scan_worker_finished.assert_called_once_with('deploy', worker)

    def test_successful_adb_switch_advances_epoch_and_invalidates_battle(self):
        api = Mock()
        window = SimpleNamespace(_source_epoch=4, _websocket_api=api,
            _cache_current_deploy=Mock(), _cache_rng_from_service=Mock(),
            _stop_enemy_poll=Mock(return_value=True), _on_rng_stop=Mock(return_value=True),
            _stop_deploy_poll=Mock(return_value=True), _deploy_reader=None,
            _enemy_reader=Mock(), _enemy_detail_dialog=None, _character_detail_dialog=None,
            _global_damage_detail_dialog=None, _character_overview_dialog=None,
            _sync_battle_cache_controls=Mock(), _update_adb_button=Mock(), _battle_cache=Mock())
        for key in ('chk_enemy_precise_position', 'enemy_table', 'enemy_progress',
                    'btn_enemy_scan', 'lbl_enemy_status', 'character_table',
                    'btn_character_scan', 'lbl_character_status', 'rng_pred_table',
                    'rng_hist_table', 'rng_trivial_pred_table', 'rng_trivial_hist_table',
                    'lbl_rng_info', 'lbl_rng_trivial_info', 'lbl_rng_status',
                    'deploy_table', 'btn_deploy_export', 'lbl_deploy_status'):
            setattr(window, key, Mock())
        for key in ('_enemy_last', '_enemy_rows', '_enemy_row_lifecycle',
                    '_enemy_row_spawn_wait', '_bar_colors', '_skill_lines',
                    '_enemy_cell_state', '_enemy_bar_state', '_enemy_detail_state',
                    '_character_last', '_character_rows', '_character_bar_colors',
                    '_character_skill_lines', '_character_cell_state',
                    '_character_bar_state', '_character_stats_history'):
            setattr(window, key, [])
        with patch('backend.desktop_app.EnemyReader', return_value=Mock()):
            CoachWindow._activate_adb_path(window, 'test-adb', 'test-device')
        self.assertEqual(window._source_epoch, 5)
        api.begin_session.assert_called_once()
        self.assertEqual(api.invalidate_domains.call_args.args[1], 'adb_changed')
        self.assertIn('battle', api.invalidate_domains.call_args.args[0])
        window._cache_current_deploy.assert_called_once_with(final_reason='adb_switched')

    def test_incomplete_adb_stop_does_not_start_new_session(self):
        api = Mock()
        window = SimpleNamespace(_source_epoch=4, _websocket_api=api,
            _cache_current_deploy=Mock(), _cache_rng_from_service=Mock(),
            _stop_enemy_poll=Mock(return_value=False))
        with patch('backend.desktop_app.QMessageBox.information'):
            CoachWindow._activate_adb_path(window, 'test-adb')
        self.assertEqual(window._source_epoch, 4)
        api.begin_session.assert_not_called()


if __name__ == '__main__':
    unittest.main()
