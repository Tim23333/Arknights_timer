# -*- coding: utf-8 -*-
"""TDD: custom_options 模块读写、默认值、即时生效与变更通知。"""
import json
import tempfile
import unittest
from pathlib import Path

from backend.app.custom_options import (
    DEFAULTS,
    CustomOptions,
    default_path,
    load,
    save,
)


class CustomOptionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "custom_options.json"

    def test_defaults_contains_expected_keys(self):
        self.assertIn("auto_detect_stage_change", DEFAULTS)
        block = DEFAULTS["auto_detect_stage_change"]
        self.assertFalse(block["enabled"])
        self.assertEqual(block["check_interval_ms"], 100)

    def test_defaults_auto_addressing_disabled(self):
        self.assertIn("auto_addressing", DEFAULTS)
        self.assertFalse(DEFAULTS["auto_addressing"]["enabled"])

    def test_load_missing_file_returns_defaults(self):
        data = load(self.path)
        self.assertEqual(data, DEFAULTS)
        # 不存在的文件不会自动创建，以免污染目录
        self.assertFalse(self.path.exists())

    def test_save_and_load_roundtrip(self):
        data = load(self.path)
        data["auto_detect_stage_change"]["enabled"] = True
        data["auto_detect_stage_change"]["check_interval_ms"] = 250
        save(self.path, data)

        reloaded = load(self.path)
        self.assertTrue(reloaded["auto_detect_stage_change"]["enabled"])
        self.assertEqual(
            reloaded["auto_detect_stage_change"]["check_interval_ms"], 250)

    def test_save_writes_valid_json(self):
        save(self.path, DEFAULTS)
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(raw, DEFAULTS)

    def test_custom_options_get_set_and_persist(self):
        opts = CustomOptions(self.path)
        opts.load()
        self.assertFalse(opts.get("auto_detect_stage_change", "enabled"))

        opts.set("auto_detect_stage_change", "enabled", True)
        opts.set("auto_detect_stage_change", "check_interval_ms", 500)

        # 内存即时生效
        self.assertTrue(opts.get("auto_detect_stage_change", "enabled"))
        self.assertEqual(
            opts.get("auto_detect_stage_change", "check_interval_ms"), 500)

        # 已写盘，可被另一个实例读回
        opts2 = CustomOptions(self.path)
        opts2.load()
        self.assertTrue(opts2.get("auto_detect_stage_change", "enabled"))
        self.assertEqual(
            opts2.get("auto_detect_stage_change", "check_interval_ms"), 500)

    def test_auto_addressing_get_set_and_persist(self):
        opts = CustomOptions(self.path)
        opts.load()
        self.assertFalse(opts.get("auto_addressing", "enabled"))

        opts.set("auto_addressing", "enabled", True)
        self.assertTrue(opts.get("auto_addressing", "enabled"))

        opts2 = CustomOptions(self.path)
        opts2.load()
        self.assertTrue(opts2.get("auto_addressing", "enabled"))

    def test_set_notifies_listeners(self):
        opts = CustomOptions(self.path)
        opts.load()
        seen = []
        opts.add_listener(lambda: seen.append("changed"))

        opts.set("auto_detect_stage_change", "enabled", True)
        self.assertEqual(seen, ["changed"])

    def test_missing_subkey_returns_default(self):
        opts = CustomOptions(self.path)
        opts.load()
        # 未设置的子键应回退到默认值
        self.assertEqual(opts.get("auto_detect_stage_change", "check_interval_ms"), 100)

    def test_default_path_points_to_custom_options_json(self):
        p = Path(default_path())
        self.assertEqual(p.name, "custom_options.json")


if __name__ == "__main__":
    unittest.main()
