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

    def test_invalid_version_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "数字格式"):
            windows_version_tuple("release")


if __name__ == '__main__':
    unittest.main()
