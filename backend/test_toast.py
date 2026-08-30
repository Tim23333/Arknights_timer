# -*- coding: utf-8 -*-
"""TDD: toast 气泡队列逻辑（顺序、时长分层、semantic、去重/上限）。"""
import unittest

from backend.app.toast import (
    DEFAULT_DURATIONS_MS,
    LEVELS,
    MAX_TOASTS,
    TOAST_DURATION_MS,
    ToastManager,
    ToastQueue,
    ToastQueueItem,
)


class ToastQueueTests(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(TOAST_DURATION_MS, 30000)
        self.assertGreater(MAX_TOASTS, 0)

    def test_levels_slf4j_five(self):
        self.assertEqual(LEVELS, ("trace", "debug", "info", "warn", "error"))

    def test_default_durations_present_for_all_levels(self):
        for lvl in LEVELS:
            self.assertIn(lvl, DEFAULT_DURATIONS_MS)
            self.assertGreater(DEFAULT_DURATIONS_MS[lvl], 0)

    def test_push_keeps_fifo_order(self):
        q = ToastQueue()
        q.push(ToastQueueItem(seq=1, text="a"))
        q.push(ToastQueueItem(seq=2, text="b"))
        q.push(ToastQueueItem(seq=3, text="c"))
        self.assertEqual([item.text for item in q.items], ["a", "b", "c"])

    def test_remove_drops_specific_item(self):
        q = ToastQueue()
        a = ToastQueueItem(seq=1, text="a")
        b = ToastQueueItem(seq=2, text="b")
        q.push(a)
        q.push(b)
        q.remove(a)
        self.assertEqual([item.text for item in q.items], ["b"])

    def test_reflow_returns_indices_for_newest_bottom(self):
        q = ToastQueue()
        q.push(ToastQueueItem(seq=1, text="a"))
        q.push(ToastQueueItem(seq=2, text="b"))
        offsets = q.reflow()
        self.assertEqual(len(offsets), 2)
        self.assertLess(offsets[0], offsets[1])

    def test_push_evicts_oldest_when_over_capacity(self):
        q = ToastQueue(max_toasts=2)
        q.push(ToastQueueItem(seq=1, text="a"))
        q.push(ToastQueueItem(seq=2, text="b"))
        q.push(ToastQueueItem(seq=3, text="c"))
        self.assertEqual([item.text for item in q.items], ["b", "c"])


class ToastManagerTests(unittest.TestCase):
    def test_show_returns_item_with_seq(self):
        mgr = ToastManager()
        a = mgr.show("a")
        b = mgr.show("b")
        self.assertEqual([i.text for i in mgr.items], ["a", "b"])
        self.assertLess(a.seq, b.seq)

    def test_show_level_default_info(self):
        mgr = ToastManager()
        item = mgr.show("x")
        self.assertEqual(item.level, "info")

    def test_show_level_custom(self):
        mgr = ToastManager()
        item = mgr.show("x", level="error")
        self.assertEqual(item.level, "error")

    def test_show_semantic_default_empty(self):
        mgr = ToastManager()
        item = mgr.show("x")
        self.assertEqual(item.semantic, "")

    def test_show_semantic_custom(self):
        mgr = ToastManager()
        item = mgr.show("x", semantic="success")
        self.assertEqual(item.semantic, "success")

    def test_show_duration_from_level(self):
        # 无 options 时按 level 从默认档取时长
        mgr = ToastManager()
        item = mgr.show("x", level="error")
        self.assertEqual(item.duration, DEFAULT_DURATIONS_MS["error"])

    def test_show_duration_from_options(self):
        opts = {"duration_ms": {"info": 1234}}
        mgr = ToastManager(options=opts)
        item = mgr.show("x")
        self.assertEqual(item.duration, 1234)

    def test_show_duration_explicit_override(self):
        mgr = ToastManager()
        item = mgr.show("x", duration=500)
        self.assertEqual(item.duration, 500)

    def test_show_disabled_noop(self):
        mgr = ToastManager(options={"enabled": False})
        item = mgr.show("x")
        self.assertIsNone(item)
        self.assertEqual(mgr.items, [])

    def test_dismiss_removes_from_queue(self):
        mgr = ToastManager()
        a = mgr.show("a")
        mgr.show("b")
        mgr.dismiss(a)
        self.assertEqual([i.text for i in mgr.items], ["b"])


if __name__ == "__main__":
    unittest.main()
