import os
import unittest
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QLabel, QSpinBox, QTableWidget

from backend.desktop_app import CoachWindow, RNG_HISTORY_LEN


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
            rng_hist_table=QTableWidget(0, 3),
            lbl_rng_trivial_info=QLabel(),
            rng_trivial_pred_table=QTableWidget(0, 2),
            rng_trivial_hist_table=QTableWidget(0, 3),
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
        self.assertEqual(holder.rng_hist_table.item(0, 2).text(), '0x00001234')
        self.assertEqual(
            holder.rng_trivial_hist_table.item(0, 2).text(), '0x0000ABCD')

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


if __name__ == '__main__':
    unittest.main()
