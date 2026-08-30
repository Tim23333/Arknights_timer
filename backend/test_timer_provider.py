# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from backend.app.services.timer_provider import TimerDataProvider


class TimerDataProviderTimelineTests(unittest.TestCase):
    @patch('backend.app.services.timer_provider.AKMemoryReader')
    def test_initialization_and_clear_use_array_compatible_operation(self, reader_cls):
        provider = TimerDataProvider()
        reader_cls.assert_called_once_with(process_name='MuMuVMMHeadless.exe')

        provider._frame_times.extend([1.0, 2.0])
        provider._frame_counts.extend([30, 60])
        provider._clear_frame_timeline()

        self.assertEqual(list(provider._frame_times), [])
        self.assertEqual(list(provider._frame_counts), [])

    @patch('backend.app.services.timer_provider.AKMemoryReader')
    def test_new_battle_rewinds_and_clears_previous_samples(self, _reader_cls):
        provider = TimerDataProvider()
        provider._record_frame_sample(10.0, 300)
        provider._record_frame_sample(11.0, 330)
        provider._record_frame_sample(0.5, 15)

        self.assertEqual(list(provider._frame_times), [0.5])
        self.assertEqual(list(provider._frame_counts), [15])

    @patch('backend.app.services.timer_provider.AKMemoryReader')
    def test_guest_configured_refresh_uses_guest_reader(self, _reader_cls):
        """configure_guest 后 refresh_sample 走 guest 路径读 frame/time。"""
        provider = TimerDataProvider()
        fake_reader = FakeGuestReader()

        provider.configure_guest(fake_reader)
        result = provider.refresh_sample()

        self.assertTrue(result["ok"])
        self.assertEqual(result["game_time"], 6.5)
        self.assertEqual(result["frame_count"], 195)
        self.assertEqual(fake_reader.read_count, 1)
        self.assertEqual(provider.get_game_data()["game_time"], 6.5)

    @patch('backend.app.services.timer_provider.AKMemoryReader')
    def test_clear_guest_falls_back_to_host(self, reader_cls):
        """clear_guest 后 refresh_sample 回到宿主路径。"""
        # mock reader 未配置地址（time_address=None）→ 应返回"未配置"
        reader_cls.return_value.time_address = None
        provider = TimerDataProvider()
        provider.configure_guest(FakeGuestReader())
        provider.clear_guest()

        result = provider.refresh_sample()
        self.assertFalse(result["ok"])
        # 未走 guest 路径 → 返回的是宿主侧的"未配置"初始消息
        self.assertIn("寻址工具", result.get("message", ""))

    @patch('backend.app.services.timer_provider.AKMemoryReader')
    def test_configure_guest_resets_stage_detection_state(self, _reader_cls):
        """换数据源即换基线：旧局的走秒/归0状态不带入新源。

        回归 PR#3 review P3：重定位成功（游戏重启后）首读 time=0，
        若旧局残留 _game_time_moved 会被误判为关卡切换并广播，
        在主界面触发一轮注定失败的自动刷新链。
        """
        provider = TimerDataProvider()
        reader = FakeGuestReader()
        provider.configure_guest(reader)

        # 第一局：走秒置 moved（0.0 → 10.0 两次采样）
        reader.set_clock(0, 0.0)
        provider.refresh_sample()
        reader.set_clock(300, 10.0)
        provider.refresh_sample()
        self.assertTrue(provider.game_time_moved())

        # 模拟游戏重启后重定位：换新 reader，首读 time=0（主界面空壳）
        reader2 = FakeGuestReader(time_value=0.0, frame_value=0)
        provider.configure_guest(reader2)
        self.assertFalse(provider.game_time_moved())
        provider.refresh_sample()
        # 旧局残留状态已清零 → time=0 不触发归0广播
        self.assertFalse(provider.consume_game_time_reset())

    @patch('backend.app.services.timer_provider.AKMemoryReader')
    def test_game_time_reset_detects_new_stage(self, _reader_cls):
        """进过关卡（time 变动）后归 0 → 判定新关卡（consume 返回 True）。"""
        provider = TimerDataProvider()
        reader = FakeGuestReader()
        provider.configure_guest(reader)

        # 先置基线 0.0，再走秒 0→10（进关卡，置 game_time_moved）
        reader.set_clock(0, 0.0)
        provider.refresh_sample()
        reader.set_clock(300, 10.0)
        provider.refresh_sample()
        self.assertTrue(provider.game_time_moved())
        self.assertFalse(provider.consume_game_time_reset())
        # 归 0（新关卡载入）
        reader.set_clock(3, 0.0005)
        provider.refresh_sample()
        self.assertTrue(provider.consume_game_time_reset())
        # 消费后清除
        self.assertFalse(provider.consume_game_time_reset())

    @patch('backend.app.services.timer_provider.AKMemoryReader')
    def test_game_time_reset_ignored_before_moved(self, _reader_cls):
        """未进过关卡（time 恒 0）时归 0 不广播（主界面空壳不误触发）。"""
        provider = TimerDataProvider()
        reader = FakeGuestReader()
        provider.configure_guest(reader)

        # time 恒 0（主界面空壳），game_time_moved 未置位
        reader.set_clock(0, 0.0)
        provider.refresh_sample()
        reader.set_clock(0, 0.0)
        provider.refresh_sample()
        self.assertFalse(provider.game_time_moved())
        self.assertFalse(provider.consume_game_time_reset())

    @patch('backend.app.services.timer_provider.AKMemoryReader')
    def test_game_time_normal_advance_no_reset(self, _reader_cls):
        """时间正常递增（10→11）不触发归 0。"""
        provider = TimerDataProvider()
        reader = FakeGuestReader()
        provider.configure_guest(reader)

        reader.set_clock(300, 10.0)
        provider.refresh_sample()  # 10.0
        reader.set_clock(330, 11.0)  # 递增
        provider.refresh_sample()  # 11.0
        self.assertFalse(provider.consume_game_time_reset())

    @patch('backend.app.services.timer_provider.AKMemoryReader')
    def test_game_time_moved_detects_progression(self, _reader_cls):
        """时间值从 0 变动到非 0（进关卡走秒）→ game_time_moved 置位。"""
        provider = TimerDataProvider()
        reader = FakeGuestReader()
        provider.configure_guest(reader)

        # 首次读 time=0 (主界面空壳), 时间未变动
        reader.set_clock(0, 0.0)
        provider.refresh_sample()
        self.assertFalse(provider.game_time_moved())
        # time 仍 0, 不变动
        reader.set_clock(0, 0.0)
        provider.refresh_sample()
        self.assertFalse(provider.game_time_moved())
        # time 变到非 0 (进关卡走秒)
        reader.set_clock(30, 1.0)
        provider.refresh_sample()
        self.assertTrue(provider.game_time_moved())

    @patch('backend.app.services.timer_provider.AKMemoryReader')
    def test_reset_broadcast_notifies_subscribers(self, _reader_cls):
        """归 0 时广播给所有订阅者（多订阅者互不影响）。"""
        provider = TimerDataProvider()
        reader = FakeGuestReader()
        provider.configure_guest(reader)

        notified = []
        provider.subscribe_game_time_reset(
            lambda: notified.append("sub1"))
        provider.subscribe_game_time_reset(
            lambda: notified.append("sub2"))

        # 先走秒（进关卡，置 game_time_moved）
        reader.set_clock(300, 10.0)
        provider.refresh_sample()  # 10.0, 无归0
        self.assertEqual(notified, [])
        reader.set_clock(330, 11.0)
        provider.refresh_sample()  # 11.0 变动，置 moved
        self.assertTrue(provider.game_time_moved())

        reader.set_clock(3, 0.0005)  # 归0
        provider.refresh_sample()
        self.assertEqual(sorted(notified), ["sub1", "sub2"])

    @patch('backend.app.services.timer_provider.AKMemoryReader')
    def test_reset_broadcast_unsubscribe(self, _reader_cls):
        """退订后不再收到广播。"""
        provider = TimerDataProvider()
        reader = FakeGuestReader()
        provider.configure_guest(reader)

        notified = []
        cb = lambda: notified.append("sub")  # noqa: E731
        provider.subscribe_game_time_reset(cb)
        provider.unsubscribe_game_time_reset(cb)

        # 先走秒置 moved（进关卡）
        reader.set_clock(300, 10.0)
        provider.refresh_sample()
        reader.set_clock(330, 11.0)
        provider.refresh_sample()
        self.assertTrue(provider.game_time_moved())
        # 归 0：已退订 → 不应收到广播
        reader.set_clock(3, 0.0005)
        provider.refresh_sample()
        self.assertEqual(notified, [])


class FakeGuestReader:
    """返回固定 frame/time 的假 guest 读取器。"""

    def __init__(self, time_value: float = 6.5, frame_value: int = 195):
        self.read_count = 0
        self._time = time_value
        self._frame = frame_value

    def set_clock(self, frame: int, time: float):
        """测试用：调整下次读取返回的 frame/time。"""
        self._frame = frame
        self._time = time

    def read_battle_clock(self):
        self.read_count += 1
        return (self._frame, self._time)


if __name__ == '__main__':
    unittest.main()
