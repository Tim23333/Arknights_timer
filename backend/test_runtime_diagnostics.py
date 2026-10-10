"""Diagnostic lifecycle and export contracts; only external environment I/O is stubbed."""
import threading
import os
import zipfile
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from backend.app.diagnostic_log import DiagnosticLogManager
from backend.app.services.runtime_diagnostics import RuntimeDiagnostics
from backend.app.toast import ToastManager


def test_late_webui_logger_uses_same_portable_default(monkeypatch, tmp_path):
    import backend.app.diagnostic_log as logging_module
    QApplication.instance() or QApplication([])
    monkeypatch.delenv('TIMELINE_LOG_DIR', raising=False)
    monkeypatch.setattr(logging_module, 'data_root', lambda: tmp_path / 'program-data')
    window = SimpleNamespace(_diagnostic_logger=None, _toast=ToastManager(),
                             _custom_options=SimpleNamespace(_path=tmp_path / 'preferences' / 'options.json'),
                             _diagnostic_context=lambda: {'test_build': False})
    service = RuntimeDiagnostics(window)
    try:
        assert service.logger.log_root == tmp_path / 'program-data' / 'logs'
    finally:
        service.close()


@pytest.fixture
def diagnostics(tmp_path):
    app = QApplication.instance() or QApplication([])
    logger = DiagnosticLogManager(tmp_path)
    window = SimpleNamespace(_diagnostic_logger=logger, _toast=ToastManager(),
                             _diagnostic_context=lambda: {'test_build': True, 'adb_path': ''})
    service = RuntimeDiagnostics(window)
    yield service, window, logger
    service.close()
    if service._thread:
        service._thread.join(3)
    logger.close()


def completed(service, job):
    service._thread.join(3)
    assert not service._thread.is_alive()
    result = service.command('logs-job', {'id': job['id']})
    assert result['status'] != 'running'
    return result


def test_reuses_test_mode_logger_and_tracks_enabled_backend_notifications(diagnostics):
    service, window, logger = diagnostics
    assert service.logger is logger
    assert service.metadata()['testMode'] is True
    window._toast.show('成功', semantic='success', duration=1234)
    item = service.notifications()['items'][-1]
    assert item['text'] == '成功'
    assert item['duration'] == 1234
    assert item['semantic'] == 'success'
    assert '成功' in service.command('logs-read', {})['items'][-1]['text']
    window._toast.update_options({'enabled': False})
    window._toast.show('不可见')
    assert service.notifications()['lastSeq'] == 1
    service.close()
    window._toast.update_options({'enabled': True})
    window._toast.show('已取消订阅')
    assert service.notifications()['lastSeq'] == 1
    logger.log('共享日志不会被服务关闭')
    assert '共享日志' in logger.snapshot_lines()[-1]


def test_cursor_gap_full_text_and_zip_preserve_history(diagnostics):
    service, _, logger = diagnostics
    logger.log('最早的日志')
    for index in range(10005):
        logger.log('日志', index)
    page = logger.snapshot(1, 5)
    assert page['gap'] is True
    assert len(page['items']) == 5
    assert len(logger.snapshot()['items']) == 10000
    export = completed(service, service.command('logs-export', {'format': 'text'}))
    path = service.download(export['id'])
    assert '最早的日志' in path.read_text(encoding='utf-8')
    archive_job = completed(service, service.command('logs-export', {'format': 'zip'}))
    with zipfile.ZipFile(service.download(archive_job['id'])) as archive:
        assert '最早的日志' in archive.read('session.log').decode('utf-8')
        assert 'test_build' in archive.read('runtime_context.json').decode('utf-8')
        assert 'diagnostics.txt' in archive.namelist()


@pytest.mark.parametrize('params', [{'after': -1}, {'after': True}, {'limit': 0}, {'limit': 10001}, {'limit': '5'}])
def test_rejects_invalid_cursors_and_sizes(diagnostics, params):
    service, _, _ = diagnostics
    with pytest.raises(ValueError):
        service.command('logs-read', params)


def test_unknown_jobs_formats_commands_and_paths_are_rejected(diagnostics):
    service, _, _ = diagnostics
    for action, params in [('logs-job', {'id': 'missing'}), ('logs-export', {'format': 'html'}), ('logs-unknown', {})]:
        with pytest.raises(ValueError):
            service.command(action, params)
    with pytest.raises(ValueError):
        service.download('../session.log')


def test_log_folder_uses_local_system_opener(diagnostics, monkeypatch):
    service, _, logger = diagnostics
    calls = []
    if os.name == 'nt':
        monkeypatch.setattr(os, 'startfile', calls.append)
    else:
        monkeypatch.setattr('backend.app.services.runtime_diagnostics.subprocess.Popen', calls.append)
    result = service.command('logs-folder', {})
    assert result['accepted'] is True
    assert str(logger.log_root) in str(calls[0])


def test_old_export_job_handles_are_bounded(diagnostics):
    service, _, _ = diagnostics
    first = completed(service, service.command('logs-export', {'format': 'text'}))
    for _ in range(32):
        completed(service, service.command('logs-export', {'format': 'text'}))
    with pytest.raises(ValueError):
        service.command('logs-job', {'id': first['id']})


def test_environment_work_is_bounded_and_does_not_block_reading(diagnostics, monkeypatch):
    service, _, logger = diagnostics
    entered, release = threading.Event(), threading.Event()
    def environment(context):
        entered.set()
        assert release.wait(3)
        logger.log('环境信息已就绪')
    monkeypatch.setattr(logger, 'append_environment_snapshot', environment)
    job = service.command('logs-environment', {})
    assert entered.wait(1)
    try:
        with pytest.raises(ValueError, match='尚未结束'):
            service.command('logs-export', {})
        logger.log('后台工作期间仍可写入')
        assert '仍可写入' in service.command('logs-read', {})['items'][-1]['text']
        with pytest.raises(ValueError):
            service.download(job['id'])
    finally:
        release.set()
    assert completed(service, job)['status'] == 'done'
    assert '环境信息已就绪' in logger.snapshot_lines()[-1]


def test_export_errors_are_reported_and_owned_logger_closes_after_worker(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = SimpleNamespace(_toast=ToastManager(), _custom_options=SimpleNamespace(_path=tmp_path / 'options.json'),
                             _diagnostic_context=lambda: {'test_build': False})
    service = RuntimeDiagnostics(window)
    def fail(path):
        raise OSError('测试磁盘错误')
    export_session = service.logger.export_session
    monkeypatch.setattr(service.logger, 'export_session', fail)
    job = completed(service, service.command('logs-export', {'format': 'text'}))
    assert job['status'] == 'error'
    assert '磁盘错误' in job['message']
    monkeypatch.setattr(service.logger, 'export_session', export_session)
    entered, release = threading.Event(), threading.Event()
    def environment(context):
        entered.set(); release.wait(3)
    monkeypatch.setattr(service.logger, 'append_environment_snapshot', environment)
    service.command('logs-environment', {})
    assert entered.wait(1)
    service.close()
    release.set(); service._thread.join(3)
    with pytest.raises(RuntimeError):
        service.logger.export_session(tmp_path / 'closed.log')


def test_slow_export_disk_does_not_lock_out_realtime_logging(diagnostics, monkeypatch, tmp_path):
    # ROOT CAUSE: holding the manager lock while copying the whole session made
    # a slow export stall Qt/reader log calls. Only a completed byte boundary is
    # locked now; the public export runs its slow writes after releasing it.
    service, _, logger = diagnostics
    logger.log('导出边界之前')
    entered, release, logged = threading.Event(), threading.Event(), threading.Event()
    output = tmp_path / 'slow.log'
    real_open = type(output).open
    class SlowFile:
        def __enter__(self):
            self.file = real_open(output, 'wb')
            return self
        def __exit__(self, *args):
            self.file.close()
        def write(self, value):
            entered.set()
            assert release.wait(3)
            return self.file.write(value)
    def open_file(path, *args, **kwargs):
        return SlowFile() if path == output and args == ('wb',) else real_open(path, *args, **kwargs)
    monkeypatch.setattr(type(output), 'open', open_file)
    exporter = threading.Thread(target=logger.export_session, args=(output,))
    exporter.start()
    assert entered.wait(1)
    def write_live():
        logger.log('导出期间的新行')
        logged.set()
    writer = threading.Thread(target=write_live)
    writer.start()
    try:
        assert logged.wait(1)
    finally:
        release.set(); exporter.join(3); writer.join(3)
    text = output.read_text(encoding='utf-8')
    assert '边界之前' in text
    assert '期间的新行' not in text
