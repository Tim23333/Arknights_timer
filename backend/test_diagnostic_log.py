# -*- coding: utf-8 -*-
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from backend.app.diagnostic_log import DiagnosticLogManager, DiagnosticLogWindow
from backend.app.version import VERSION_LABEL


class DiagnosticLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_package_contains_session_and_runtime_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DiagnosticLogManager(temp_dir)
            manager.set_context_provider(lambda: {
                'adb_path': '',
                'adb_serial': '127.0.0.1:16384',
                'reader': {'resolved_ids': 3, 'resolved_attributes': 2},
            })
            manager.log('测试诊断行', 123)
            output = manager.build_package(Path(temp_dir) / 'diagnostics.zip')
            manager.close()

            self.assertTrue(output.is_file())
            with zipfile.ZipFile(output) as archive:
                self.assertTrue(
                    {'session.log', 'diagnostics.txt', 'runtime_context.json'}
                    .issubset(set(archive.namelist())))
                session = archive.read('session.log').decode('utf-8')
                report = archive.read('diagnostics.txt').decode('utf-8')
                context = archive.read('runtime_context.json').decode('utf-8')
            self.assertIn('测试诊断行 123', session)
            self.assertIn(
                f'ArknightsTimeline {VERSION_LABEL} 测试版诊断信息', report)
            self.assertIn('resolved_ids', context)

    def test_window_shows_existing_lines_and_close_only_hides(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DiagnosticLogManager(temp_dir)
            manager.log('窗口启动前日志')
            window = DiagnosticLogWindow(manager)
            self.assertIn(VERSION_LABEL, window.windowTitle())
            self.assertIn('窗口启动前日志', window.output.toPlainText())
            window.show()
            window.close()
            self.assertFalse(window.isVisible())
            manager.log('窗口隐藏后日志')
            self.app.processEvents()
            self.assertIn('窗口隐藏后日志', window.output.toPlainText())
            window.shutdown()
            manager.close()
            manager.close()

    def test_old_logs_are_pruned_on_startup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_files = [
                root / 'session_20000101_000000_1.log',
                root / 'fault_20000101_000000_1.log',
                root / 'ArknightsTimeline_v9.9.9_diagnostics_20000101_000000.zip',
            ]
            recent = root / 'session_20990101_000000_2.log'
            for path in (*old_files, recent):
                path.write_text('x', encoding='utf-8')
            old_time = time.time() - 30 * 86400
            for path in old_files:
                os.utime(path, (old_time, old_time))

            manager = DiagnosticLogManager(temp_dir)
            manager.close()

            for path in old_files:
                self.assertFalse(path.exists(), path.name)
            self.assertTrue(recent.exists())


if __name__ == '__main__':
    unittest.main()
