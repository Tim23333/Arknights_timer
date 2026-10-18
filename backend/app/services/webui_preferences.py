"""Program-relative WebUI presentation preferences, independent of game state.

HTTP workers own these infrequent reads/writes. No preferences are loaded from
the Qt, capture or clock threads. One process-wide lock protects read/modify/
replace even if more than one local HTTP server shares the same config file.
"""

import json
import re
import threading
from pathlib import Path

from .. import custom_options, storage_paths

_LOCK = threading.Lock()
_TABLE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_MAX_TABLES = 256
_MAX_COLUMNS = 2048
_MAX_FILE_BYTES = 2 * 1024 * 1024


def _validate_table(table):
    if not isinstance(table, str) or not _TABLE_ID.fullmatch(table):
        raise ValueError("表格标识必须为 1 至 128 个字母、数字或 _ . : -，且以字母或数字开头")


def _validate_order(order):
    if not isinstance(order, list) or len(order) > _MAX_COLUMNS:
        raise ValueError(f"列顺序必须是最多 {_MAX_COLUMNS} 项的字段键列表")
    if any(not isinstance(key, str) or not 0 < len(key) <= 128
           or any(ord(char) < 32 or ord(char) == 127 for char in key) for key in order):
        raise ValueError("字段键必须为 1 至 128 个非控制字符")
    if len(set(order)) != len(order):
        raise ValueError("列顺序不能包含重复字段键")


def _validate_document(data):
    if (not isinstance(data, dict) or set(data) != {"version", "columnOrders"}
            or type(data["version"]) is not int or data["version"] != 1):
        raise ValueError("不支持的 WebUI 配置格式或版本")
    orders = data["columnOrders"]
    if not isinstance(orders, dict) or len(orders) > _MAX_TABLES:
        raise ValueError(f"表格配置必须为最多 {_MAX_TABLES} 项的对象")
    for table, order in orders.items():
        _validate_table(table)
        _validate_order(order)


class WebUiPreferences:
    """Only column identifiers are persisted; never sampled field values.

    Missing files mean defaults. Corrupt, unreadable or future-version files
    instead fail explicitly, so a later user gesture cannot erase preferences.
    Successful writes reuse the existing same-directory atomic replacement.
    """

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else storage_paths.data_root() / "config" / "webui.json"

    def _read_unlocked(self):
        try:
            with self.path.open("rb") as stream:
                raw = stream.read(_MAX_FILE_BYTES + 1)
        except FileNotFoundError:
            return {"version": 1, "columnOrders": {}}
        except OSError as error:
            raise RuntimeError("无法读取 WebUI 排序配置，请检查程序 data/config 目录权限") from error
        try:
            if len(raw) > _MAX_FILE_BYTES:
                raise ValueError("配置文件超过大小限制")
            data = json.loads(raw.decode("utf-8"))
            _validate_document(data)
            return data
        except (ValueError, UnicodeError) as error:
            raise RuntimeError("WebUI 排序配置损坏或版本不受支持，已保留原文件") from error

    def read(self):
        with _LOCK:
            return self._read_unlocked()

    def update(self, table, order):
        """Update one table; ``None`` removes its preference (restore defaults)."""
        _validate_table(table)
        if order is not None:
            _validate_order(order)
        with _LOCK:
            candidate = self._read_unlocked()
            if order is None:
                candidate["columnOrders"].pop(table, None)
            else:
                candidate["columnOrders"][table] = list(order)
            _validate_document(candidate)
            if len(json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")) > _MAX_FILE_BYTES:
                raise ValueError("WebUI 排序配置超过大小限制")
            try:
                custom_options.save(self.path, candidate)
            except OSError as error:
                raise RuntimeError("无法保存 WebUI 排序配置，请检查程序 data/config 目录权限；原配置未替换") from error
            return candidate
