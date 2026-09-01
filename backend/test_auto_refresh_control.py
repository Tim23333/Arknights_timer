"""Automatic-refresh cancellation and thread-boundary regressions."""

import inspect
from types import MethodType

import backend.desktop_app as desktop_app


class _FakeQTimer:
    queued = []

    @classmethod
    def singleShot(cls, delay, callback):
        cls.queued.append((delay, callback))


class _Provider:
    moved = False
    game_time = 0.0
    frame_count = 0

    def game_time_moved(self):
        return self.moved

    def get_game_data(self):
        return {
            "game_time": self.game_time,
            "frame_count": self.frame_count,
        }


class _WindowStub:
    def __init__(self):
        self._auto_refresh_enabled = True
        self._auto_refresh_wait_gen = 1
        self._provider = _Provider()
        self.runs = 0

    def _run_auto_refresh(self):
        self.runs += 1


def _bind(stub, name):
    method = getattr(desktop_app.CoachWindow, name)
    setattr(stub, name, MethodType(method, stub))


def test_old_wait_generation_cannot_revive_after_toggle(monkeypatch):
    """关闭后重新开启时，旧 QTimer 轮询不能加入新一代刷新链。"""
    _FakeQTimer.queued = []
    monkeypatch.setattr(desktop_app, "QTimer", _FakeQTimer)
    stub = _WindowStub()
    for name in (
        "_auto_refresh_wait_current",
        "_run_auto_refresh_from_wait",
        "_wait_game_time_moved_then_refresh",
    ):
        _bind(stub, name)

    stub._wait_game_time_moved_then_refresh(1)
    assert len(_FakeQTimer.queued) == 1

    # 模拟关闭(gen=2)后立刻重新开启(gen=3)，旧 gen=1 回调随后才到达。
    stub._auto_refresh_wait_gen = 3
    stub._provider.moved = True
    _, old_callback = _FakeQTimer.queued.pop(0)
    old_callback()

    assert stub.runs == 0
    assert _FakeQTimer.queued == []


def test_initial_wait_ignores_cross_stage_moved_latch(monkeypatch):
    """旧局 moved=True 不能让主界面 time=0 的新等待链提前扫描。"""
    _FakeQTimer.queued = []
    monkeypatch.setattr(desktop_app, "QTimer", _FakeQTimer)
    stub = _WindowStub()
    stub._provider.moved = True  # TimerDataProvider 的历史锁存值
    _bind(stub, "_auto_refresh_wait_current")
    _bind(stub, "_run_auto_refresh_from_wait")
    _bind(stub, "_wait_game_time_moved_then_refresh")

    stub._wait_game_time_moved_then_refresh(1)
    assert stub.runs == 0
    assert len(_FakeQTimer.queued) == 1

    stub._provider.game_time = 0.2
    stub._provider.frame_count = 6
    _, callback = _FakeQTimer.queued.pop(0)
    callback()
    assert stub.runs == 0
    assert len(_FakeQTimer.queued) == 1

    stub._provider.game_time = 0.45
    stub._provider.frame_count = 14
    _, callback = _FakeQTimer.queued.pop(0)
    callback()
    # 最终启动仍经 singleShot(0) 回到主事件循环。
    assert stub.runs == 0
    assert len(_FakeQTimer.queued) == 1
    _, callback = _FakeQTimer.queued.pop(0)
    callback()
    assert stub.runs == 1


def test_memory_thread_only_requests_qt_relocation_via_signal():
    source = inspect.getsource(desktop_app.CoachWindow._memory_worker)
    assert "guestRelocateRequested.emit()" in source
    assert "self._maybe_relocate_guest_clock()" not in source


def test_stage_reset_waits_for_two_forward_positive_samples(monkeypatch):
    """归0后不能立刻扫描；新局时间/帧稳定前只保留等待链。"""
    _FakeQTimer.queued = []
    monkeypatch.setattr(desktop_app, "QTimer", _FakeQTimer)
    stub = _WindowStub()
    stub._closing = False
    stub._stage_reset_wait_gen = 1
    stub._auto_refresh_step = None
    stub._auto_refresh_stopping_step = None
    for name in (
        "_stage_reset_wait_current",
        "_wait_new_stage_running_then_refresh",
    ):
        _bind(stub, name)

    # 仍在场景切换的 time=0：不得启动。
    stub._wait_new_stage_running_then_refresh(1)
    assert stub.runs == 0
    assert len(_FakeQTimer.queued) == 1

    # 第一份正时间只建立新局基线。
    stub._provider.game_time = 0.25
    stub._provider.frame_count = 8
    _, callback = _FakeQTimer.queued.pop(0)
    callback()
    assert stub.runs == 0
    assert len(_FakeQTimer.queued) == 1

    # 第二份必须继续正向走动，才允许刷新。
    stub._provider.game_time = 0.5
    stub._provider.frame_count = 15
    _, callback = _FakeQTimer.queued.pop(0)
    callback()
    assert stub.runs == 1
    assert _FakeQTimer.queued == []


def test_newer_stage_reset_generation_cancels_old_ready_wait(monkeypatch):
    """连续换关时只有最新 reset generation 能启动扫描。"""
    _FakeQTimer.queued = []
    monkeypatch.setattr(desktop_app, "QTimer", _FakeQTimer)
    stub = _WindowStub()
    stub._closing = False
    stub._stage_reset_wait_gen = 1
    stub._auto_refresh_step = None
    stub._auto_refresh_stopping_step = None
    for name in (
        "_stage_reset_wait_current",
        "_wait_new_stage_running_then_refresh",
    ):
        _bind(stub, name)

    stub._wait_new_stage_running_then_refresh(1)
    assert len(_FakeQTimer.queued) == 1
    stub._stage_reset_wait_gen = 2
    stub._provider.game_time = 1.0
    stub._provider.frame_count = 30
    _, old_callback = _FakeQTimer.queued.pop(0)
    old_callback()

    assert stub.runs == 0
    assert _FakeQTimer.queued == []


def test_new_stage_reset_cancels_inflight_refresh_before_waiting():
    """新归0必须先停止上一局扫描，再为最新一局建立独立等待代际。"""
    stub = _WindowStub()
    stub._stage_reset_wait_gen = 4
    stub._auto_refresh_step = "deploy"
    stub._auto_refresh_stopping_step = None
    aborts = []
    waits = []

    def abort(reason):
        aborts.append(reason)
        stub._auto_refresh_step = None

    stub._abort_auto_refresh = abort
    stub._wait_new_stage_running_then_refresh = waits.append
    _bind(stub, "_on_game_time_reset_main")

    stub._on_game_time_reset_main()

    assert aborts == ["检测到更新的关卡，取消上一轮刷新"]
    assert stub._stage_reset_wait_gen == 5
    assert waits == [5]
