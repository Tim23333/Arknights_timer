# -*- coding: utf-8 -*-
"""运行时自定义选项：JSON 持久化 + 内存态 + 变更通知。

供 UI 用户与纯 Python 工具包用户共享同一份配置。读写 exe/源码同目录下的
``custom_options.json``；写入后立即落盘，运行时修改即时生效。
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable

from app.toast import LEVELS

# SLF4J 五级信息分类：直接复用 toast.py 的权威 LEVELS，避免两处字面量漂移。
# UI 时长输入框的顺序与键名、运行时查表都以此为唯一来源。
TOAST_LEVELS: tuple[str, ...] = LEVELS

DEFAULTS: dict[str, Any] = {
    "auto_detect_stage_change": {
        "enabled": False,
    },
    "auto_addressing": {
        "enabled": False,
    },
    "websocket_api": {
        "enabled": True,
    },
    "toast": {
        "enabled": True,
        "duration_ms": {
            "trace": 5000,
            "debug": 6000,
            "info": 8000,
            "warn": 10000,
            "error": 15000,
        },
    },
}

CONFIG_FILENAME = "custom_options.json"


def default_path() -> str:
    """返回默认配置路径（exe/源码所在目录 + 固定文件名）。"""
    import sys

    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    return str(base / CONFIG_FILENAME)


def load(path: str | Path | None = None) -> dict[str, Any]:
    """读取配置文件；不存在则返回 DEFAULTS 深拷贝，不自动创建文件。"""
    p = Path(path or default_path())
    if not p.is_file():
        return copy.deepcopy(DEFAULTS)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return copy.deepcopy(DEFAULTS)
    if not isinstance(data, dict):
        return copy.deepcopy(DEFAULTS)
    return _merge(DEFAULTS, data)


def save(path: str | Path | None, data: dict[str, Any]) -> None:
    """把配置写入磁盘；目标目录不存在时创建。"""
    p = Path(path or default_path())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _merge(defaults: dict, incoming: dict) -> dict:
    """递归合并：incoming 覆盖 defaults，缺省 key 用默认值。"""
    result = copy.deepcopy(defaults)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


class CustomOptions:
    """内存态配置对象；set 时写盘并通知监听方。"""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path or default_path())
        self._data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        self._listeners: list[Callable[[], None]] = []

    def load(self) -> "CustomOptions":
        self._data = load(self._path)
        return self

    def get(self, section: str, key: str | None = None) -> Any:
        """读取配置；key 缺省时返回整个 section。未设置时回退默认值。"""
        merged = _merge(DEFAULTS, self._data)
        if key is None:
            return merged.get(section)
        return (merged.get(section) or {}).get(key)

    def set(self, section: str, key: str, value: Any) -> None:
        """写入内存并落盘，然后通知监听方。"""
        self._data.setdefault(section, {})
        self._data[section][key] = value
        save(self._path, self._data)
        for listener in list(self._listeners):
            listener()

    def add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    @property
    def path(self) -> str:
        return str(self._path)


__all__ = ["DEFAULTS", "CustomOptions", "default_path", "load", "save"]
