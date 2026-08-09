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


if __name__ == '__main__':
    unittest.main()
