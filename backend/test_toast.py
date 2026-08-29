# -*- coding: utf-8 -*-
"""TDD: toast 气泡队列逻辑（顺序、时长、去重/上限）。"""
import unittest

from backend.app.toast import (
    MAX_TOASTS,
    TOAST_DURATION_MS,
    ToastQueue,
    ToastQueueItem,
)


class ToastQueueTests(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(TOAST_DURATION_MS, 30000)
        self.assertGreater(MAX_TOASTS, 0)

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
        # 后到的往下排：索引越大越靠下。
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


if __name__ == "__main__":
    unittest.main()
