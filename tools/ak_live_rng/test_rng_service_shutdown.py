"""RngService 停止/资源回收的并发回归测试。"""

import os
import sys
import threading
import time

import pytest


HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from adb_reader import AdbReader, _RngTcpChannel  # noqa: E402
import rng_service as rng_service_module  # noqa: E402
from memscan import PymemReader  # noqa: E402
from rng_service import RngService  # noqa: E402


class _BlockingReader:
    def __init__(self, release_on_close=True):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release_on_close = release_on_close
        self.close_calls = 0

    def blocking_read(self):
        self.entered.set()
        self.release.wait(5.0)

    def close(self):
        self.close_calls += 1
        if self.release_on_close:
            self.release.set()


class _BlockingTracker:
    def __init__(self, reader):
        self.reader = reader
        self.engine = {"id": 1, "role": "imp", "label": "test"}

    def poll(self):
        self.reader.blocking_read()
        return []

    def snapshot(self, _history_len, _predict_len):
        return {"id": 1, "role": "imp", "total": 0, "history": []}


class _CloseCounter:
    def __init__(self, raises=False):
        self.calls = 0
        self.raises = raises

    def close(self):
        self.calls += 1
        if self.raises:
            raise RuntimeError("close failed")


def _service_with_blocking_tracker(reader):
    service = RngService(reader=reader, use_cache=False, poll_interval=0.001)
    service._trackers = {1: _BlockingTracker(reader)}
    service._selected_id = 1
    return service


def test_stop_closes_reader_then_joins_poll_thread_and_is_idempotent():
    reader = _BlockingReader()
    service = _service_with_blocking_tracker(reader)

    assert service.start()
    assert reader.entered.wait(1.0)
    thread = service._thread

    assert service.stop(timeout=0.5)
    assert not thread.is_alive()
    assert reader.close_calls == 1

    assert service.stop(timeout=0.01)
    assert reader.close_calls == 1
    assert not service.start(), "已释放 reader 的服务不能被旧延迟任务复活"


def test_stop_timeout_is_bounded_and_later_call_can_finish_join():
    reader = _BlockingReader(release_on_close=False)
    service = _service_with_blocking_tracker(reader)
    service.start()
    assert reader.entered.wait(1.0)

    started = time.monotonic()
    assert not service.stop(timeout=0.02)
    assert time.monotonic() - started < 0.5
    assert service._thread.is_alive()

    reader.release.set()
    assert service.stop(timeout=0.5)
    assert not service._thread.is_alive()
    assert reader.close_calls == 1


def test_stop_called_from_poll_thread_does_not_self_join():
    reader = _BlockingReader()
    service = RngService(reader=reader, use_cache=False)
    result = []

    def stop_from_poll_thread():
        result.append(service.stop(timeout=0.1))

    service._poll_loop = stop_from_poll_thread
    assert service.start()
    thread = service._thread
    thread.join(1.0)

    assert not thread.is_alive()
    assert result == [False], "self-call 应跳过 join，但不能谎报当前线程已退出"
    assert reader.close_calls == 1


def test_stop_cancels_delayed_rescan_without_leaving_event_set():
    reader = _BlockingReader()
    service = RngService(reader=reader, use_cache=False)

    assert service.request_rescan(0.08)
    assert service._rescan_due is not None
    assert service.stop(timeout=0.01)
    time.sleep(0.12)

    assert service._rescan_due is None
    assert not service._rescan.is_set()
    assert not service.request_rescan(0)


def test_locate_with_cache_disabled_does_not_write_cache(monkeypatch):
    engine = {"id": 7, "role": "imp", "label": "test"}
    monkeypatch.setattr(
        rng_service_module.memscan, "locate_battle_random",
        lambda _reader, status: [engine])
    service = RngService(
        backend="pymem", reader=object(), use_cache=False,
        on_status=lambda _message: None)
    writes = []
    service._save_cache = lambda engines: writes.append(engines)

    assert service.locate()
    assert writes == []


def test_legacy_reader_fallback_closes_channel_and_memcore():
    channel = _CloseCounter()
    memcore = _CloseCounter()

    class LegacyReader:
        pass

    reader = LegacyReader()
    reader.chan = channel
    reader.mc = memcore
    service = RngService(reader=reader, use_cache=False)

    assert service.stop(timeout=0.01)
    assert channel.calls == 1
    assert memcore.calls == 1


def test_reader_close_failure_still_uses_nested_resource_fallbacks():
    channel = _CloseCounter()
    memcore = _CloseCounter()

    class BrokenCloseReader:
        def __init__(self):
            self.chan = channel
            self.mc = memcore

        def close(self):
            raise RuntimeError("broken reader close")

    service = RngService(reader=BrokenCloseReader(), use_cache=False)
    assert service.stop(timeout=0.01)
    assert channel.calls == 1
    assert memcore.calls == 1


def test_adb_reader_close_releases_both_channels_once():
    memcore = _CloseCounter()
    channel = _CloseCounter()
    reader = AdbReader(memcore)
    reader.chan = channel

    reader.close()
    reader.close()

    assert channel.calls == 1
    # MemCore.close() 自身是幂等的；AdbReader 也不应重复调用它。
    assert memcore.calls == 1
    with pytest.raises(RuntimeError, match="已关闭"):
        reader._channel()


def test_rng_tcp_channel_cannot_reopen_after_permanent_close():
    channel = _RngTcpChannel(object(), port=27272)
    channel.close_permanently()

    with pytest.raises(RuntimeError, match="永久关闭"):
        channel.open()


def test_pymem_reader_close_process_is_idempotent():
    class FakePymem:
        process_handle = 123

        def __init__(self):
            self.close_calls = 0

        def close_process(self):
            self.close_calls += 1

    pm = FakePymem()
    reader = PymemReader(pm)
    reader.close()
    reader.close()

    assert pm.close_calls == 1
    assert reader.read(0x1000, 4) is None
    assert reader.regions() == []


def test_status_listener_can_be_replaced_and_cannot_break_rng_service():
    service = RngService(reader=object(), use_cache=False)

    def broken_listener(_message):
        raise RuntimeError("deleted Qt signal source")

    service.set_status_listener(broken_listener)
    # 展示层异常必须被隔离，不能从 _status 冒泡并杀死 polling thread。
    service._status("first")
    assert service.status_msg == "first"

    received = []
    service.set_status_listener(received.append)
    service._status("second")
    assert received == ["second"]

    service.set_status_listener(None)
    service._status("third")
    assert service.status_msg == "third"
    assert received == ["second"]


def test_broken_status_listener_does_not_kill_polling_thread():
    class LostTracker:
        engine = {"id": 7, "role": "imp", "label": "lost"}

        def poll(self):
            return None

        def snapshot(self, _history_len, _predict_len):
            return {"id": 7, "role": "imp", "total": 0, "history": []}

    service = RngService(
        reader=object(), use_cache=False, poll_interval=0.001,
        on_status=lambda _message: (_ for _ in ()).throw(
            RuntimeError("listener failed")))
    service._trackers = {7: LostTracker()}
    service._selected_id = 7

    assert service.start()
    deadline = time.monotonic() + 1.0
    while "状态丢失" not in service.status_msg and time.monotonic() < deadline:
        time.sleep(0.005)

    assert "状态丢失" in service.status_msg
    assert service._thread.is_alive()
    assert service.stop(timeout=0.5)
