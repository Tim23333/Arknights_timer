# -*- coding: utf-8 -*-
"""Qt worker lifecycle regressions.

These tests deliberately avoid a real emulator/ADB connection.  Blocking I/O is
represented by events so the ordering between ``done``, ``finished`` and window
cleanup remains deterministic.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import textwrap
import time
from pathlib import Path
from types import MethodType

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from backend import desktop_app
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication


class _CloseProbe:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


def test_enemy_scan_request_stop_wakes_reader_channel():
    class Reader:
        def __init__(self) -> None:
            self.stop_calls = 0

        def request_poll_stop(self) -> None:
            self.stop_calls += 1

    reader = Reader()
    worker = desktop_app.EnemyScanWorker(reader)

    worker.request_stop()

    assert reader.stop_calls == 1


def test_deploy_scan_request_stop_closes_reader_and_memcore():
    worker = desktop_app.DeployScanWorker("unused-adb")
    reader = _CloseProbe()
    memcore = _CloseProbe()
    with worker._io_lock:
        worker._reader = reader
        worker._mc = memcore

    worker.request_stop()

    assert reader.close_calls == 1
    assert memcore.close_calls == 1


def test_rng_scan_request_stop_closes_service_and_transport():
    channel = _CloseProbe()
    memcore = _CloseProbe()

    class Service:
        def __init__(self) -> None:
            self.stop_calls = 0
            self.reader = type("Reader", (), {"chan": channel, "mc": memcore})()

        def stop(self) -> None:
            self.stop_calls += 1

    service = Service()
    worker = desktop_app.RngScanWorker("unused-adb")
    with worker._io_lock:
        worker._service = service

    worker.request_stop()

    assert service.stop_calls == 1
    assert channel.close_calls == 1
    assert memcore.close_calls == 1


class _BlockingReader:
    """Deploy reader whose first read remains blocked until the test releases it."""

    def __init__(self, release_on_close: bool) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release_on_close = release_on_close
        self.close_calls = 0

    def is_chain_valid(self) -> bool:
        self.entered.set()
        self.release.wait(10)
        return False

    def get_events(self):
        return []

    def get_battle_state(self):
        return {}

    def close(self) -> None:
        self.close_calls += 1
        if self.release_on_close:
            self.release.set()


class _BlockingWorker(QThread):
    """A worker that records cancellation but intentionally remains in I/O."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()
        self.stop_calls = 0

    def request_stop(self) -> None:
        self.stop_calls += 1
        self.requestInterruption()

    def run(self) -> None:
        self.entered.set()
        self.release.wait(10)


def _bind(holder, *names: str) -> None:
    for name in names:
        setattr(holder, name, MethodType(getattr(desktop_app.CoachWindow, name), holder))


def test_common_scan_cleanup_keeps_strong_reference_until_worker_finishes():
    """Closing/timeout cleanup must not release an uncooperative QThread."""
    holder = type("WindowStub", (), {})()
    worker = _BlockingWorker()
    holder._deploy_scan = worker
    holder._enemy_scan = None
    holder._rng_worker = None
    holder._guest_worker = None
    holder._scan_worker_attr = desktop_app.CoachWindow._scan_worker_attr
    _bind(holder, "_scan_worker", "_request_scan_worker_stop")
    worker.start()
    assert worker.entered.wait(1)

    try:
        assert holder._request_scan_worker_stop("deploy") is False
        assert worker.stop_calls == 1
        assert holder._deploy_scan is worker
        assert worker.isRunning()
    finally:
        worker.release.set()
        assert worker.wait(1000)

    # Ownership is released only by the finished-signal consumer, never by the
    # stop request itself.
    assert holder._deploy_scan is worker


class _Control:
    def __init__(self) -> None:
        self.enabled = True
        self.text_value = ""

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def setText(self, text: str) -> None:
        self.text_value = str(text)

    def text(self) -> str:
        return self.text_value


class _TimerProbe:
    def __init__(self) -> None:
        self.active = True

    def isActive(self) -> bool:
        return self.active

    def stop(self) -> None:
        self.active = False


class _ToastProbe:
    def __init__(self) -> None:
        self.messages = []

    def show(self, message, **kwargs) -> None:
        self.messages.append((str(message), kwargs))


class _RunningScanProbe:
    def __init__(self) -> None:
        self.stop_calls = 0

    def request_stop(self) -> None:
        self.stop_calls += 1

    def isRunning(self) -> bool:
        return True


@pytest.mark.parametrize("step", ["deploy", "enemy", "rng"])
def test_auto_refresh_timeout_holds_reentry_lock_until_scan_finishes(step):
    """All three scan types remain owned while their cancellation is in flight."""
    holder = type("WindowStub", (), {})()
    workers = {kind: _RunningScanProbe() for kind in ("deploy", "enemy", "rng")}
    holder._deploy_scan = workers["deploy"]
    holder._enemy_scan = workers["enemy"]
    holder._rng_worker = workers["rng"]
    holder._guest_worker = None
    holder._auto_refresh_enabled = True
    holder._auto_refresh_step = step
    holder._auto_refresh_stopping_step = None
    holder._auto_refresh_abort_reason = ""
    holder._auto_refresh_retries = 0
    holder._auto_refresh_timeout = _TimerProbe()
    holder._toast = _ToastProbe()
    holder._on_deploy_stop = lambda: None
    holder._stop_enemy_poll = lambda: True
    holder._on_rng_stop = lambda: None
    started = []
    holder._start_auto_refresh_step = started.append
    holder._scan_worker_attr = desktop_app.CoachWindow._scan_worker_attr
    _bind(
        holder,
        "_scan_worker",
        "_scan_worker_pending",
        "_request_scan_worker_stop",
        "_stop_auto_refresh_timeout",
        "_on_auto_refresh_step_timeout",
        "_complete_auto_refresh_abort",
        "_run_auto_refresh",
    )

    holder._on_auto_refresh_step_timeout()

    assert workers[step].stop_calls == 1
    assert holder._scan_worker(step) is workers[step]
    assert holder._auto_refresh_step == step
    assert holder._auto_refresh_stopping_step == step
    assert holder._auto_refresh_abort_reason == f"{step} 扫描超时"
    assert holder._auto_refresh_timeout.active is False

    # A new stage-change notification cannot overwrite the still-running worker.
    holder._run_auto_refresh()
    assert started == []


class _DoneBeforeFinishedWorker(QThread):
    """Emit a scan result, then keep run() alive to reproduce Qt's ordering gap."""

    done = Signal(object, str)

    def __init__(self) -> None:
        super().__init__()
        self.result = None
        self.done_emitted = threading.Event()
        self.release = threading.Event()

    def run(self) -> None:
        self.result = (None, "simulated failure")
        self.done.emit(*self.result)
        self.done_emitted.set()
        self.release.wait(10)


def test_scan_result_is_routed_only_after_qthread_finished():
    """A failed scan must not retry in the done->finished destruction window."""
    app = QApplication.instance() or QApplication([])
    holder = type("WindowStub", (), {})()
    worker = _DoneBeforeFinishedWorker()
    holder._deploy_scan = worker
    holder._enemy_scan = None
    holder._rng_worker = None
    holder._guest_worker = None
    holder._closing = False
    holder._auto_refresh_enabled = True
    holder._auto_refresh_step = "deploy"
    holder._auto_refresh_stopping_step = None
    holder._auto_refresh_abort_reason = ""
    holder._auto_refresh_retries = 0
    holder._auto_refresh_timeout = _TimerProbe()
    holder._toast = _ToastProbe()
    holder._guest_addressing_active = False
    holder.btn_deploy_scan = _Control()
    holder.lbl_deploy_status = _Control()
    holder._scan_worker_attr = desktop_app.CoachWindow._scan_worker_attr
    starts = []
    holder._start_auto_refresh_step = starts.append
    holder._discard_scan_result = lambda _kind, _result: None
    holder._schedule_close_retry = lambda: None
    _bind(
        holder,
        "_scan_worker",
        "_connect_scan_worker",
        "_on_scan_worker_finished",
        "_on_deploy_scan_done",
        "_on_auto_refresh_step_done",
        "_stop_auto_refresh_timeout",
        "_abort_auto_refresh",
        "_complete_auto_refresh_abort",
    )
    holder._connect_scan_worker("deploy", worker)
    worker.start()
    assert worker.done_emitted.wait(1)

    # Process any queued Python/Qt callbacks while run() is deliberately alive.
    app.processEvents()
    assert worker.isRunning()
    assert holder._deploy_scan is worker
    assert starts == []

    worker.release.set()
    assert worker.wait(1000)
    deadline = time.monotonic() + 1
    while holder._deploy_scan is worker and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)

    assert holder._deploy_scan is None
    assert starts == ["deploy"]


def test_blocked_deploy_poll_stop_survives_in_subprocess():
    """Regression for the former Windows 0xC0000409 QThread destruction crash."""
    script = textwrap.dedent(
        r"""
        import os
        import threading
        import time
        from types import MethodType
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        from backend.desktop_app import CoachWindow, DeployPollWorker

        class Reader:
            def __init__(self):
                self.entered = threading.Event()
                self.release = threading.Event()
            def is_chain_valid(self):
                self.entered.set()
                self.release.wait(10)
                return False
            def get_events(self): return []
            def get_battle_state(self): return {}
            def close(self): pass  # Deliberately unresponsive transport.

        class Control:
            def setEnabled(self, value): pass
            def setText(self, value): pass

        app = QApplication.instance() or QApplication([])
        holder = type('Holder', (), {})()
        holder.btn_deploy_stop = Control()
        holder.btn_deploy_scan = Control()
        holder.lbl_deploy_status = Control()
        holder._closing = False
        holder._schedule_close_retry = lambda: None
        holder._finish_deploy_poll_stop = MethodType(
            CoachWindow._finish_deploy_poll_stop, holder)
        holder._stop_deploy_poll = MethodType(CoachWindow._stop_deploy_poll, holder)
        reader = Reader()
        holder._deploy_poll = DeployPollWorker(reader, interval=0.01)
        holder._deploy_poll.start()
        assert reader.entered.wait(1)
        # This read outlives the old wait(3000) cutoff.  The fixed code must keep
        # the sole Python owner in holder._deploy_poll for the entire gap.
        threading.Timer(3.2, reader.release.set).start()
        assert holder._stop_deploy_poll() is False
        assert holder._deploy_poll is not None
        while holder._deploy_poll is not None and holder._deploy_poll.isRunning():
            app.processEvents()
            time.sleep(0.01)
        if holder._deploy_poll is not None:
            holder._finish_deploy_poll_stop(holder._deploy_poll)
        app.processEvents()
        assert holder._deploy_poll is None
        """
    )
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(repo_root), env.get("PYTHONPATH", ""))))
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=12,
    )

    assert completed.returncode == 0, (
        f"child returncode={completed.returncode}\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
