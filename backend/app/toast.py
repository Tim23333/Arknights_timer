# -*- coding: utf-8 -*-
"""气泡式弹窗（toast）工具模块：右上角、置顶、按时长自动关闭、红叉手动关、排队堆叠。

- ``ToastQueue``/``ToastQueueItem``：可单测的队列逻辑（顺序、容量、重排）。
- ``ToastWidget``：Qt 气泡部件；``ToastManager`` 挂到主窗口右上角并管理堆叠。
- 信息分类：``level``（SLF4J 五级：trace/debug/info/warn/error）决定展示时长；
  独立的 ``semantic``（如 success/error）决定气泡样式，两者正交。
- 展示时长可配置化：``ToastManager(options=...)`` 传入 ``duration_ms`` 分档时长与
  ``enabled`` 总开关；未显式传 ``duration`` 时按 ``level`` 查表。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

TOAST_DURATION_MS = 30000
MAX_TOASTS = 5

# SLF4J 五级信息分类；level 决定展示时长
LEVELS = ("trace", "debug", "info", "warn", "error")
DEFAULT_LEVEL = "info"

# 每档默认展示时长（ms）；可被 ToastManager(options=...) 覆盖
DEFAULT_DURATIONS_MS = {
    "trace": 5000,
    "debug": 6000,
    "info": 8000,
    "warn": 10000,
    "error": 15000,
}


@dataclass
class ToastQueueItem:
    """一条待显示/显示中的气泡。seq 用于稳定排序与去重。

    level: SLF4J 五档之一，决定展示时长（duration 未显式给时按它查表）。
    semantic: 独立语义值（如 success/error），决定气泡样式；空串走 level 默认样式。
    duration: 展示毫秒数；None 表示在 show() 内按 level 解析。
    """

    seq: int
    text: str
    title: str = ""
    level: str = DEFAULT_LEVEL
    semantic: str = ""
    duration: Optional[int] = None
    widget: Optional[object] = None


class ToastQueue:
    """FIFO 气泡队列；超过容量时淘汰最旧条目。"""

    def __init__(self, max_toasts: int = MAX_TOASTS) -> None:
        self._max = max_toasts
        self._items: list[ToastQueueItem] = []
        self._next_seq = 0

    @property
    def items(self) -> list[ToastQueueItem]:
        return list(self._items)

    def push(self, item: ToastQueueItem | None) -> None:
        if item is None:
            return
        item.seq = item.seq or self._next_seq
        self._next_seq = max(self._next_seq, item.seq + 1)
        self._items.append(item)
        if len(self._items) > self._max:
            removed = self._items.pop(0)
            if removed.widget is not None:
                removed.widget.close()

    def remove(self, item: ToastQueueItem) -> None:
        if item in self._items:
            self._items.remove(item)

    def reflow(self) -> list[int]:
        """返回每个条目按序的纵向偏移；越新越靠下。"""
        return [index for index in range(len(self._items))]


class ToastManager:
    """挂到主窗口右上角、管理多个 ToastWidget 的容器。

    提供纯逻辑接口（show/remove/clear），Qt 部件由子类或调用方提供。

    options: 可选配置 dict：
      - enabled: bool，总开关；False 时 show() 返回 None 且不排队。
      - duration_ms: dict[level, int]，每档展示时长（ms），缺省回退 DEFAULT_DURATIONS_MS。
    """

    def __init__(
        self,
        max_toasts: int = MAX_TOASTS,
        options: Optional[dict] = None,
    ) -> None:
        self._queue = ToastQueue(max_toasts=max_toasts)
        self._seq = 0
        opts = options or {}
        self._enabled = bool(opts.get("enabled", True))
        durations = opts.get("duration_ms") or {}
        self._durations = {**DEFAULT_DURATIONS_MS, **durations}

    def update_options(self, options: Optional[dict]) -> None:
        """运行时更新配置（enabled 总开关 + duration_ms 分档时长）。"""
        opts = options or {}
        self._enabled = bool(opts.get("enabled", True))
        durations = opts.get("duration_ms") or {}
        self._durations = {**DEFAULT_DURATIONS_MS, **durations}

    def show(
        self,
        text: str,
        level: str = DEFAULT_LEVEL,
        semantic: str = "",
        title: str = "",
        duration: Optional[int] = None,
    ) -> Optional[ToastQueueItem]:
        """弹出一条气泡。总开关关闭时返回 None 且不排队。

        duration 显式传则覆盖；None 按 level 查 options.duration_ms（缺省回退默认档）。
        """
        if not self._enabled:
            return None
        if duration is None:
            duration = self._durations.get(
                level, DEFAULT_DURATIONS_MS.get(level, TOAST_DURATION_MS))
        self._seq += 1
        item = ToastQueueItem(
            seq=self._seq, text=text, level=level, semantic=semantic,
            title=title, duration=duration)
        self._queue.push(item)
        self._on_changed()
        return item

    def dismiss(self, item: ToastQueueItem) -> None:
        self._queue.remove(item)
        self._on_changed()

    def clear(self) -> None:
        for item in self._queue.items:
            if item.widget is not None:
                item.widget.close()
        self._queue = ToastQueue(max_toasts=self._queue._max)
        self._on_changed()

    @property
    def items(self) -> list[ToastQueueItem]:
        return self._queue.items

    def _on_changed(self) -> None:
        # 由 ToastManagerQt 重写，触发 Qt 布局刷新。
        pass


try:  # Qt 部件仅在 GUI 环境可用；无 Qt 时保留纯逻辑 ToastManager。
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import (
        QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
    )

    class _ToastWidget(QFrame):
        """单个气泡：右上角、置顶、按 level 时长自动关、红叉手动关。"""

        def __init__(
            self,
            parent: QWidget,
            manager: "ToastManagerQt",
            item: ToastQueueItem,
        ) -> None:
            super().__init__(parent)
            self._manager = manager
            self._item = item
            # 作为主窗口的子部件显示（不设 Qt.Tool / FramelessWindowHint），
            # 这样气泡天然局限在主窗口内、随窗口移动。仅置顶保证可见。
            self.setWindowFlags(Qt.WindowType.Widget
                                | Qt.WindowType.WindowStaysOnTopHint)
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
            self.setStyleSheet(self._style(item.semantic, item.level))
            lay = QHBoxLayout(self)
            lay.setContentsMargins(10, 8, 10, 8)
            col = QVBoxLayout()
            if item.title:
                title = QLabel(item.title)
                title.setStyleSheet("font-weight:bold; color:white;")
                col.addWidget(title)
            body = QLabel(item.text)
            body.setWordWrap(True)
            body.setStyleSheet("color:white;")
            col.addWidget(body)
            lay.addLayout(col, 1)
            close_btn = QPushButton("✕")
            close_btn.setObjectName("toastCloseBtn")
            close_btn.setFixedSize(18, 18)
            # 用 objectName 选择器提升特异性，覆盖主窗口全局 QPushButton 样式
            close_btn.setStyleSheet(
                "QPushButton#toastCloseBtn { color:white; background:transparent; "
                "border:none; border-radius:0; padding:0; font-weight:bold; "
                "font-size:14px; }"
                "QPushButton#toastCloseBtn:hover { color:#ff6b6b; }")
            close_btn.clicked.connect(self._on_close)
            lay.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)
            self.adjustSize()
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._on_close)
            self._timer.start(item.duration or TOAST_DURATION_MS)

        @staticmethod
        def _style(semantic: str, level: str) -> str:
            """气泡底色：优先按 semantic 语义取色，其次按 level 默认取色。"""
            semantic_colors = {
                "success": "rgba(40, 110, 60, 0.92)",
                "error": "rgba(160, 50, 50, 0.94)",
                "info": "rgba(40, 40, 40, 0.92)",
            }
            level_colors = {
                "trace": "rgba(60, 60, 60, 0.92)",
                "debug": "rgba(60, 70, 80, 0.92)",
                "info": "rgba(40, 40, 40, 0.92)",
                "warn": "rgba(140, 110, 40, 0.92)",
                "error": "rgba(160, 50, 50, 0.94)",
            }
            bg = semantic_colors.get(semantic)
            if bg is None:
                bg = level_colors.get(level, level_colors["info"])
            return (
                "QFrame { background: %s; border-radius: 8px; "
                "border: 1px solid rgba(255,255,255,0.25); }" % bg)

        def _on_close(self) -> None:
            self._manager.dismiss(self._item)

    class ToastManagerQt(ToastManager):
        """挂到主窗口右上角、管理多个 ToastWidget 的 Qt 实现。"""

        def __init__(
            self,
            parent: QWidget,
            max_toasts: int = MAX_TOASTS,
            options: Optional[dict] = None,
        ) -> None:
            super().__init__(max_toasts=max_toasts, options=options)
            self._parent = parent
            self._widgets: list[_ToastWidget] = []

        def _on_changed(self) -> None:
            # 与队列同步部件生命周期，并重新排布。
            self._widgets = [
                w for w in self._widgets if w._item in self._queue.items]
            for item in self._queue.items:
                if item.widget is None:
                    widget = _ToastWidget(self._parent, self, item)
                    item.widget = widget
                    self._widgets.append(widget)
                    widget.show()
            self._reflow()

        def _reflow(self) -> None:
            for index, widget in enumerate(self._widgets):
                widget.adjustSize()
                # 右上角，从上往下堆叠（后到的往下排）。
                x = self._parent.width() - widget.width() - 16
                y = 16 + index * (widget.height() + 8)
                widget.move(x, y)

        def dismiss(self, item: ToastQueueItem) -> None:
            if item.widget is not None:
                item.widget.close()
                item.widget = None
            super().dismiss(item)

        def show(
            self,
            text: str,
            level: str = DEFAULT_LEVEL,
            semantic: str = "",
            title: str = "",
            duration: Optional[int] = None,
        ) -> Optional[ToastQueueItem]:
            return super().show(
                text, level=level, semantic=semantic, title=title,
                duration=duration)

except Exception:  # pragma: no cover - 无 PySide6 环境
    ToastManagerQt = None  # type: ignore[assignment]


__all__ = [
    "TOAST_DURATION_MS",
    "MAX_TOASTS",
    "LEVELS",
    "DEFAULT_LEVEL",
    "DEFAULT_DURATIONS_MS",
    "ToastQueue",
    "ToastQueueItem",
    "ToastManager",
    "ToastManagerQt",
]
