import os
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
)

from backend.desktop_app import (
    CoachWindow,
    RNG_EXPORT_HISTORY_LEN,
    RNG_HISTORY_LEN,
    _build_rng_export_payload,
)
from backend.app.battle_session_cache import BattleSessionCache


def _role_snapshot(role, cursor, total, value, raw):
    return {
        'role': role,
        'cursor': cursor,
        'total': total,
        'rate': 2.5,
        'label': role,
        'predictions': [{'n': 1, 'frac': value, 'raw': raw}],
        'history': [{'seq': total, 'frac': value, 'raw': raw}],
    }


class _FakeRngService:
    def __init__(self, by_role):
        self.by_role = by_role
        self.args = None

    def snapshot(self, history_len, predict_len):
        self.args = (history_len, predict_len)
        return {
            'status': '监控中',
            'by_role': self.by_role,
            'selected': self.by_role.get('imp'),
        }

    def stop(self):
        pass


class RngUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _holder(self, service):
        spin = QSpinBox()
        spin.setValue(7)
        return SimpleNamespace(
            _rng_svc=service,
            rng_pred_spin=spin,
            lbl_rng_info=QLabel(),
            rng_pred_table=QTableWidget(0, 2),
            rng_hist_table=QTableWidget(0, 2),
            lbl_rng_trivial_info=QLabel(),
            rng_trivial_pred_table=QTableWidget(0, 2),
            rng_trivial_hist_table=QTableWidget(0, 2),
            btn_rng_imp_export=QPushButton(),
            btn_rng_trivial_export=QPushButton(),
            _battle_cache=BattleSessionCache(),
            btn_battle_cache_export=QPushButton(),
            btn_stage_enemy_export=QPushButton(),
            btn_deploy_export=QPushButton(),
            _sync_battle_cache_controls=lambda: None,
            lbl_rng_status=QLabel(),
            _tlog=lambda *_args: None,
        )

    def test_tick_renders_battle_and_visual_sequences_together(self):
        service = _FakeRngService({
            'imp': _role_snapshot('imp', 4, 12, 0.125, 0x1234),
            'trivial': _role_snapshot('trivial', 9, 31, 0.875, 0xABCD),
        })
        holder = self._holder(service)

        CoachWindow._on_rng_tick(holder)

        self.assertEqual(service.args, (RNG_HISTORY_LEN, 7))
        self.assertIn('游标 #4', holder.lbl_rng_info.text())
        self.assertIn('游标 #9', holder.lbl_rng_trivial_info.text())
        self.assertEqual(holder.rng_pred_table.item(0, 1).text(), '0.1250')
        self.assertEqual(holder.rng_trivial_pred_table.item(0, 1).text(), '0.8750')
        self.assertEqual(holder.rng_hist_table.columnCount(), 2)
        self.assertEqual(holder.rng_hist_table.item(0, 1).text(), '0.1250')
        self.assertEqual(
            holder.rng_trivial_hist_table.item(0, 1).text(), '0.8750')
        self.assertTrue(holder.btn_rng_imp_export.isEnabled())
        self.assertTrue(holder.btn_rng_trivial_export.isEnabled())

    def test_missing_visual_sequence_clears_its_old_rows(self):
        service = _FakeRngService({
            'imp': _role_snapshot('imp', 4, 12, 0.125, 0x1234),
        })
        holder = self._holder(service)
        holder.rng_trivial_pred_table.setRowCount(1)
        holder.rng_trivial_hist_table.setRowCount(1)

        CoachWindow._on_rng_tick(holder)

        self.assertEqual(holder.rng_trivial_pred_table.rowCount(), 0)
        self.assertEqual(holder.rng_trivial_hist_table.rowCount(), 0)
        self.assertIn('表现随机未定位', holder.lbl_rng_trivial_info.text())
        self.assertTrue(holder.btn_rng_imp_export.isEnabled())
        self.assertFalse(holder.btn_rng_trivial_export.isEnabled())

    def test_rng_panels_can_shrink_and_history_has_no_raw_column(self):
        window = CoachWindow()
        try:
            self.assertEqual(window.rng_hist_table.columnCount(), 2)
            self.assertEqual(window.rng_trivial_hist_table.columnCount(), 2)
            self.assertTrue(window.lbl_rng_info.wordWrap())
            self.assertTrue(window.lbl_rng_trivial_info.wordWrap())
            self.assertEqual(
                window.rng_imp_panel.sizePolicy().horizontalPolicy(),
                QSizePolicy.Policy.Ignored)
            self.assertEqual(
                window.rng_trivial_panel.sizePolicy().horizontalPolicy(),
                QSizePolicy.Policy.Ignored)
            self.assertLessEqual(window.rng_pred_table.minimumWidth(), 120)
            self.assertLessEqual(window.rng_hist_table.minimumWidth(), 120)
            self.assertFalse(window.btn_rng_imp_export.isEnabled())
            self.assertFalse(window.btn_rng_trivial_export.isEnabled())
        finally:
            window.close()

    def test_export_payload_is_single_role_and_omits_raw_values(self):
        data = _role_snapshot('imp', 4, 12, 0.125, 0x1234)
        data['history'][0]['ts'] = 123.5
        payload = _build_rng_export_payload(
            'imp', data, '2026-08-10T12:00:00+0800')

        self.assertEqual(payload['role'], 'imp')
        self.assertEqual(payload['roleName'], '战斗随机')
        self.assertEqual(payload['history'], [
            {'seq': 12, 'value': 0.125, 'timestamp': 123.5},
        ])
        self.assertEqual(payload['predictions'], [
            {'n': 1, 'value': 0.125},
        ])
        self.assertNotIn('raw', json.dumps(payload))

    def test_each_role_exports_to_its_own_file(self):
        service = _FakeRngService({
            'imp': _role_snapshot('imp', 4, 12, 0.125, 0x1234),
            'trivial': _role_snapshot('trivial', 9, 31, 0.875, 0xABCD),
        })
        holder = self._holder(service)
        with tempfile.TemporaryDirectory() as temp_dir:
            combat_path = Path(temp_dir) / 'combat.json'
            visual_path = Path(temp_dir) / 'visual.json'
            with patch.object(
                    QFileDialog, 'getSaveFileName',
                    side_effect=[
                        (str(combat_path), 'JSON (*.json)'),
                        (str(visual_path), 'JSON (*.json)'),
                    ]):
                CoachWindow._on_rng_export(holder, 'imp')
                CoachWindow._on_rng_export(holder, 'trivial')

            combat = json.loads(combat_path.read_text(encoding='utf-8'))
            visual = json.loads(visual_path.read_text(encoding='utf-8'))
            self.assertEqual(service.args, (RNG_EXPORT_HISTORY_LEN, 7))
            self.assertEqual(combat['role'], 'imp')
            self.assertEqual(visual['role'], 'trivial')
            self.assertEqual(combat['history'][0]['value'], 0.125)
            self.assertEqual(visual['history'][0]['value'], 0.875)

    def test_cached_rng_can_export_after_service_is_gone(self):
        holder = self._holder(None)
        holder._battle_cache.observe_rng({
            'imp': _role_snapshot('imp', 4, 12, 0.125, 0x1234),
        })
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / 'cached.json'
            with patch.object(
                    QFileDialog, 'getSaveFileName',
                    return_value=(str(path), 'JSON (*.json)')):
                CoachWindow._on_rng_export(holder, 'imp')
            payload = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(payload['role'], 'imp')
        self.assertEqual(payload['history'][0]['value'], 0.125)
        self.assertIn('本局最终缓存', holder.lbl_rng_status.text())


if __name__ == '__main__':
    unittest.main()
