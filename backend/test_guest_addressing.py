# -*- coding: utf-8 -*-
"""TDD: GuestBattleClock 纯逻辑解码测试。

真实 memsrv 连接用 env 守卫跳过；这里只测不依赖设备的纯逻辑
（clock 快照解码 + frame/time 提取 + 连续失败失效），
与 game_structs 的 FP 语义一致。
"""
import struct
import unittest

from tools.enemy_health.guest_addressing import GuestBattleClock
from tools.enemy_health.game_structs import fp_to_float


def _pack_clock_snapshot(frame: int, play_fp: int) -> bytes:
    """构造 static_fields+0x14 起的原子快照字节（frame u32 + FP u64）。"""
    return struct.pack("<IQ", frame, play_fp)


class GuestClockDecodeTests(unittest.TestCase):
    def test_fp_to_float_roundtrip_positive(self):
        # Q32.32: 1.5 -> 0x180000000
        self.assertAlmostEqual(fp_to_float(0x180000000), 1.5, places=6)

    def test_fp_to_float_negative(self):
        # -1.5 -> 0xFFFFFFFFFF80000000 (two's complement)
        neg = (1 << 64) - 0x180000000
        self.assertAlmostEqual(fp_to_float(neg), -1.5, places=6)

    def test_decode_snapshot_extracts_frame_and_time(self):
        raw = _pack_clock_snapshot(195, 0x680000000)  # 6.5
        got = GuestBattleClock._decode_clock_snapshot(raw)
        self.assertEqual(got, (195, 6.5))

    def test_decode_short_raw_returns_none(self):
        self.assertIsNone(GuestBattleClock._decode_clock_snapshot(b"\x00"))

    def test_decode_time_out_of_range_returns_none(self):
        # FP 超界（864000 秒以上）→ None
        raw = _pack_clock_snapshot(1, 0x2000000000)  # 128.0 小时? 0x2000000000/2^32=128s 合法
        # 用远超上限的值：0x1_0000_0000_0000 → 65536 秒，仍 <864000，改用更大的
        # 直接验证 range：864001 秒 FP
        big_fp = int(864001 * (1 << 32))
        raw_big = _pack_clock_snapshot(1, big_fp)
        self.assertIsNone(GuestBattleClock._decode_clock_snapshot(raw_big))

    def test_clock_range_sanity(self):
        # 合法战斗秒数范围 [-1, 864000]
        for fp_val in (0, 0x100000000, 0x2800000000):
            t = fp_to_float(fp_val)
            self.assertLessEqual(-1.0, t)
            self.assertLessEqual(t, 864000.0)

    def test_read_fail_invalidates_after_threshold(self):
        clock = GuestBattleClock.__new__(GuestBattleClock)  # 不触发 __init__（无设备）
        clock.static_fields = 0x1234
        clock.frame_addr = 0x1000
        clock.time_addr = 0x2000
        clock._consecutive_fails = 0
        # 未达阈值前不失效
        for _ in range(GuestBattleClock.INVALIDATE_AFTER_FAILS - 1):
            self.assertIsNone(clock._on_read_fail())
        self.assertTrue(clock.is_stage_locked())
        # 达阈值后失效
        self.assertIsNone(clock._on_read_fail())
        self.assertFalse(clock.is_stage_locked())
        self.assertEqual(clock.static_fields, 0)


if __name__ == "__main__":
    unittest.main()
