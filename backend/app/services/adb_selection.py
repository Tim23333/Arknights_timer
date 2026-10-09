"""Asynchronous local ADB selection with validation and source-switch ownership.

Discovery and subprocess calls run on one bounded worker, never on the Qt/HTTP
threads. Only the Qt owner may open a picker, stop readers or commit a switch.
Cancelled/obsolete validation results cannot change readers or preferences.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import threading
import time
import uuid

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from tools.enemy_health import memcore


class AdbSelection(QObject):
    """Own one pollable selection job and its cancellation/lifecycle boundary."""
    completed = Signal(object)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._job = None
        self._thread = None
        self._cancel = threading.Event()
        self._closed = False
        self._dialog = None
        self._resume_auto = None
        self._stop_deadline = 0
        self._stops_requested = False
        self.completed.connect(self._complete, Qt.ConnectionType.QueuedConnection)
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._finish_switch)

    @property
    def switching(self):
        return self._job is not None and self._job['status'] == 'stopping'

    def snapshot(self, job_id):
        if self._job is None or job_id != self._job['id']:
            raise ValueError('ADB 任务已过期，请重新操作')
        return copy.deepcopy(self._job)

    def cancel(self, job_id):
        self.snapshot(job_id)
        if self._job['status'] in {'running', 'stopping'}:
            stopping = self.switching
            self._cancel.set()
            message = '已取消，未切换 ADB。'
            if stopping:
                message += ' 已发出的停止请求不会自动恢复监控。'
            self._terminal('cancelled', message)
            if self._dialog is not None:
                self._dialog.reject()
        return self.snapshot(job_id)

    def close(self):
        self._closed = True
        self._cancel.set()
        self._timer.stop()
        self._restore_auto()
        if self._dialog is not None:
            self._dialog.reject()

    def start(self, operation, params):
        if self._closed or getattr(self.window, '_closing', False):
            raise ValueError('程序正在退出')
        if ((self._job and self._job['status'] in {'running', 'stopping'})
                or (self._thread is not None and self._thread.is_alive())):
            raise ValueError('上一项 ADB 操作尚未结束，请稍后重试')
        path = params.get('path', self.window._enemy_reader.mc.adb_path)
        serial = params.get('serial', self.window._enemy_reader.mc.adb_serial)
        if (not isinstance(path, str) or not isinstance(serial, str)
                or len(path) > 4096 or len(serial) > 256 or '\0' in path + serial):
            raise ValueError('ADB 路径和设备地址必须为有效字符串')
        path, serial = os.path.normpath(path.strip()) if path.strip() else '', serial.strip()
        if operation == 'apply' and self.window._adb_scan_is_running():
            raise ValueError('扫描任务仍在执行，请等待结束再切换 ADB')
        if operation not in {'browse', 'detect', 'devices', 'apply'}:
            raise ValueError('未知 ADB 操作')
        self._cancel = threading.Event()
        self._job = {'id': uuid.uuid4().hex, 'operation': operation, 'status': 'running',
                     'message': '正在选择文件…' if operation == 'browse' else '正在验证 ADB 和探测设备…',
                     'result': None}
        self._epoch = getattr(self.window, '_source_epoch', 0)
        if operation == 'browse':
            dialog = QFileDialog(self.window, '选择 adb.exe')
            # NOTICE: Qt 6.9.2 on Windows logged native cleanupThread failure
            # when cancelling this asynchronous picker from the Web UI. Use
            # the Qt widget picker: its lifecycle remains on the owner thread.
            # Reconsider native mode only after open/cancel/shutdown are proven
            # safe on the deployed Qt version. Set before other properties:
            # https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QFileDialog.html
            dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            dialog.setNameFilters(['ADB 程序 (adb.exe)', '可执行文件 (*.exe)', '所有文件 (*)'])
            if path:
                dialog.setDirectory(str(Path(path).parent))
            self._dialog = dialog
            job_id = self._job['id']
            dialog.fileSelected.connect(lambda selected: self._picked(job_id, selected))
            dialog.rejected.connect(lambda: self.cancel(job_id))
            dialog.finished.connect(lambda _: self._dispose_dialog(dialog))
            # Keep the dialog alive and return immediately; a user can spend
            # longer in the picker than the HTTP command's 4 s deadline.
            dialog.open()
        else:
            self._thread = threading.Thread(target=self._read, args=(copy.deepcopy(self._job), path, serial, self._cancel),
                                            name='timeline-adb-selection', daemon=True)
            self._thread.start()
        return copy.deepcopy(self._job)

    def _dispose_dialog(self, dialog):
        if self._dialog is dialog:
            self._dialog = None
        dialog.deleteLater()

    def _picked(self, job_id, path):
        if self._job['id'] == job_id and self._job['status'] == 'running':
            self._job['result'] = {'path': os.path.normpath(path)}
            self._terminal('done', '已选择文件，点击“使用此 ADB”完成验证。')

    def _read(self, job, path, serial, cancel):
        try:
            candidates = []
            if job['operation'] == 'detect':
                for item in memcore.find_running_emulator_adbs():
                    if cancel.is_set():
                        return
                    ok, detail = memcore.probe_adb_executable(item['adb_path'])
                    if ok:
                        candidates.append({**item, 'detail': detail})
                if not candidates:
                    raise ValueError('未从运行中的模拟器找到可用 ADB，请启动模拟器或浏览 adb.exe。')
                path = next((item['adb_path'] for item in candidates
                             if os.path.normcase(item['adb_path']) == os.path.normcase(path)), candidates[0]['adb_path'])
            if cancel.is_set():
                return
            ok, detail = memcore.probe_adb_executable(path)
            if not ok:
                raise ValueError(f'ADB 不可用：{detail}')
            if cancel.is_set():
                return
            rows = memcore.query_adb_devices(path, connect_known=True, connect_serial=serial)
            online = [row['serial'] for row in rows if row.get('state') == 'device']
            if not serial and len(online) == 1:
                serial = online[0]
            if job['operation'] == 'apply':
                if not online:
                    raise ValueError('ADB 可以运行，但没有在线设备。请启动模拟器并核对连接地址。')
                if not serial:
                    raise ValueError('存在多个在线设备，请选择与 MAA 连接地址相同的设备。')
                if serial not in online:
                    raise ValueError(f'设备 {serial} 不在线；在线设备：{", ".join(online)}')
            job['result'] = {'path': path, 'serial': serial, 'devices': rows,
                             'candidates': candidates, 'detail': detail}
            job['message'] = f'ADB 验证通过；在线设备：{", ".join(online) or "无"}'
        except Exception as exc:
            job['error'] = str(exc)
        if not cancel.is_set() and not self._closed:
            try:
                self.completed.emit(job)
            except RuntimeError:
                # NOTICE: shutdown can destroy the QObject between the closed
                # check and emit; the bounded subprocess worker owns no widgets.
                pass

    @Slot(object)
    def _complete(self, job):
        if (self._closed or self._cancel.is_set() or not self._job
                or self._job['id'] != job['id'] or self._job['status'] != 'running'):
            return
        if getattr(self.window, '_closing', False):
            self._terminal('cancelled', '程序正在退出，未应用 ADB 配置。')
            return
        if 'error' in job:
            self._terminal('error', job['error'])
            return
        self._job['result'] = job['result']
        if job['operation'] != 'apply':
            self._terminal('done', job['message'])
            return
        w = self.window
        if getattr(w, '_source_epoch', 0) != self._epoch or w._adb_scan_is_running():
            self._terminal('error', '验证期间读取来源已改变或开始扫描，请重新选择 ADB。')
            return
        # Invalidate scheduled auto-scan callbacks before asynchronously stopping
        # old sources. Restore the preference, not an obsolete callback chain.
        self._resume_auto = w._auto_refresh_enabled
        w._auto_refresh_enabled = False
        w._auto_refresh_wait_gen += 1
        w._stage_reset_wait_gen += 1
        w._cache_current_deploy(final_reason='adb_switched')
        w._cache_rng_from_service()
        self._job['status'] = 'stopping'
        self._job['message'] = '验证通过，正在停止旧设备监控…'
        self._stop_deadline = time.monotonic() + 15
        self._stops_requested = False
        self._timer.start()
        self._finish_switch()

    def _finish_switch(self):
        if self._closed or self._cancel.is_set() or not self.switching:
            return
        w = self.window
        try:
            if getattr(w, '_closing', False):
                self._terminal('cancelled', '程序正在退出，未应用 ADB 配置。')
                return
            if getattr(w, '_source_epoch', 0) != self._epoch or w._adb_scan_is_running():
                raise ValueError('读取来源或扫描状态已改变，已取消 ADB 切换。')
            if not self._stops_requested:
                self._stops_requested = True
                stopped = all([w._stop_enemy_poll(), w._on_rng_stop(), w._stop_deploy_poll()])
            else:
                # Existing stop callbacks own QThread/service disposal. Do not
                # repeatedly request stops and multiply their retry timer chains.
                stopped = all(source is None for source in (w._enemy_poll, w._rng_svc, w._deploy_poll))
            if not stopped:
                if time.monotonic() >= self._stop_deadline:
                    raise ValueError('旧监控尚未完全退出，未切换或保存 ADB；请稍后重试。')
                return
            result = self._job['result']
            if not w._activate_adb_path(result['path'], result['serial']):
                raise ValueError('旧监控未完成停止，ADB 未切换。')
            result['persisted'] = memcore.save_adb_config(result['path'], result['serial'])
            message = f"ADB 已切换；设备地址：{result['serial']}。请重新扫描。"
            if not result['persisted']:
                message += ' 配置保存失败，下次启动需要重新选择。'
            self._terminal('done', message)
        except Exception as exc:
            self._terminal('error', str(exc))

    def _restore_auto(self):
        if self._resume_auto is not None:
            if not getattr(self.window, '_closing', False):
                self.window._auto_refresh_enabled = self._resume_auto
            self._resume_auto = None

    def _terminal(self, status, message):
        self._timer.stop()
        self._restore_auto()
        self._job.update(status=status, message=message)
