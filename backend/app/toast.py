# -*- coding: utf-8 -*-
"""气泡式弹窗（toast）工具模块：右上角、置顶、30s 自动关闭、红叉手动关、排队堆叠。

- ``ToastQueue``/``ToastQueueItem``：可单测的队列逻辑（顺序、容量、重排）。
- ``ToastWidget``：Qt 气泡部件；``ToastManager`` 挂到主窗口右上角并管理堆叠。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

TOAST_DURATION_MS = 30000
MAX_TOASTS = 5


@dataclass
class ToastQueueItem:
    """一条待显示/显示中的气泡。seq 用于稳定排序与去重。"""

    seq: int
    text: str
    title: str = ""
    kind: str = "info"  # info | success | error
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
    """

    def __init__(self, max_toasts: int = MAX_TOASTS) -> None:
        self._queue = ToastQueue(max_toasts=max_toasts)
        self._seq = 0

    def show(self, text: str, kind: str = "info", title: str = "") -> ToastQueueItem:
        self._seq += 1
        item = ToastQueueItem(seq=self._seq, text=text, kind=kind, title=title)
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
        """单个气泡：右上角、置顶、30s 自动关、红叉手动关。"""

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
            self.setStyleSheet(self._style(item.kind))
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
            self._timer.start(TOAST_DURATION_MS)

        @staticmethod
        def _style(kind: str) -> str:
            colors = {
                "info": "rgba(40, 40, 40, 0.92)",
                "success": "rgba(40, 110, 60, 0.92)",
                "error": "rgba(160, 50, 50, 0.94)",
            }
            bg = colors.get(kind, colors["info"])
            return (
                "QFrame { background: %s; border-radius: 8px; "
                "border: 1px solid rgba(255,255,255,0.25); }" % bg)

        def _on_close(self) -> None:
            self._manager.dismiss(self._item)

    class ToastManagerQt(ToastManager):
        """挂到主窗口右上角、管理多个 ToastWidget 的 Qt 实现。"""

        def __init__(self, parent: QWidget, max_toasts: int = MAX_TOASTS) -> None:
            super().__init__(max_toasts=max_toasts)
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

        def show(self, text: str, kind: str = "info",
                 title: str = "") -> ToastQueueItem:
            return super().show(text, kind=kind, title=title)

except Exception:  # pragma: no cover - 无 PySide6 环境
    ToastManagerQt = None  # type: ignore[assignment]


__all__ = [
    "TOAST_DURATION_MS",
    "MAX_TOASTS",
    "ToastQueue",
    "ToastQueueItem",
    "ToastManager",
    "ToastManagerQt",
]
