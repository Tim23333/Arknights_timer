# -*- coding: utf-8 -*-
import unittest

from backend.app.version import VERSION, VERSION_LABEL, windows_version_tuple


class VersionTests(unittest.TestCase):
    def test_configured_version_has_display_label(self):
        self.assertTrue(VERSION)
        self.assertEqual(VERSION_LABEL, f"v{VERSION.lstrip('vV')}")

    def test_windows_version_is_four_numeric_parts(self):
        self.assertEqual(len(windows_version_tuple()), 4)
        self.assertTrue(all(isinstance(part, int)
                            for part in windows_version_tuple()))

    def test_prerelease_suffix_does_not_break_windows_version(self):
        self.assertEqual(windows_version_tuple("v3.2.4-beta.1"), (3, 2, 4, 0))

    def test_underscore_suffix_does_not_break_windows_version(self):
        self.assertEqual(windows_version_tuple("3.4.4_pre"), (3, 4, 4, 0))

    def test_version_numbers_can_appear_after_a_text_prefix(self):
        self.assertEqual(
            windows_version_tuple("release_candidate_3.4.4_pre"),
            (3, 4, 4, 0))

    def test_text_only_version_falls_back_without_error(self):
        self.assertEqual(windows_version_tuple("release"), (0, 0, 0, 0))

    def test_oversized_parts_are_clamped_without_error(self):
        self.assertEqual(
            windows_version_tuple("999999.2.3.4"),
            (65535, 2, 3, 4))


if __name__ == '__main__':
    unittest.main()
