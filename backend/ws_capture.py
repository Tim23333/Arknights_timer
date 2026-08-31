"""以独立客户端监控本机 WebSocket，并把原始消息持久化为 NDJSON。

这是面向插件维护者的诊断工具，而非插件运行时的一部分：它只连接公开的
``/v1/game`` 与 ``/v1/ops``，不会读取游戏内存，也不会调用 ``desktop_app``。
窗口用于检查实时消息流，NDJSON 文件则保留可复盘的原始协议记录；两者均以
WebSocket 返回值为唯一数据来源。默认输出目录在 D 盘，以免占用系统盘空间。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import websockets


# 用户机器的 C 盘空间有限；运行期诊断数据默认固定写入 D 盘。
DEFAULT_OUTPUT_DIR = Path(os.environ.get(
    "ARKNIGHTS_TIMER_DATA_DIR", r"D:\ArknightsTimerData")) / "websocket-monitor"
GAME_URL = "ws://127.0.0.1:8765/v1/game"
OPS_URL = "ws://127.0.0.1:8765/v1/ops"
TOPICS = {
    "battle": {"rateHz": 20},
    "stage": {"rateHz": 5},
    "enemies": {"rateHz": 10},
    "characters": {"rateHz": 10},
    "enemy_detail": {"scope": "all", "rateHz": 5},
    "character_detail": {"scope": "all", "rateHz": 5},
    "deploy": {"rateHz": 10, "includeHistory": True},
    "rng": {"rateHz": 5},
    "quality": {"rateHz": 2},
}

# A scanner address is normally longer than semantic values such as 0x0.
# Keep this detector aligned with the server-side public-protocol sanitizer.
_INTERNAL_ADDRESS_PATTERN = re.compile(
    r"(?<![0-9A-Za-z])0x[0-9a-fA-F]{4,}(?![0-9A-Za-z])")
_INTERNAL_FIELD_NAMES = frozenset({"obj", "array", "process", "via", "addr", "address", "pointer"})
_CONNECT_POLL_SECONDS = 0.05


@dataclass
class MonitorState:
    """当前一次采集的轻量状态，供命令行和桌面监控界面展示。"""

    started_at: float = field(default_factory=time.monotonic)
    messages: int = 0
    bytes_written: int = 0
    topic_counts: Counter[str] = field(default_factory=Counter)
    latest: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def observe(self, message: dict[str, Any], encoded_size: int) -> None:
        """合并一条协议消息，并仅保留界面所需的最新摘要。"""
        topic = str(message.get("type", "unknown"))
        data = message.get("data")
        self.messages += 1
        self.bytes_written += encoded_size
        self.topic_counts[topic] += 1
        if isinstance(data, dict):
            self.latest[topic] = data
            if topic == "rng.updated" and _contains_internal_address(data):
                warning = "RNG 消息包含不应公开的内部字段或地址文本。"
                if warning not in self.warnings:
                    self.warnings.append(warning)

    def summary(self) -> dict[str, Any]:
        """构造跨线程安全的界面摘要，不携带完整高频单位列表。"""
        battle = self.latest.get("battle.updated", {})
        enemies = self.latest.get("enemies.updated", {})
        characters = self.latest.get("characters.updated", {})
        quality = self.latest.get("quality.updated", {})
        return {
            "elapsed": time.monotonic() - self.started_at,
            "messages": self.messages,
            "bytesWritten": self.bytes_written,
            "topicCounts": dict(self.topic_counts),
            "battle": {key: battle.get(key) for key in (
                "state", "gameTime", "fixedFrame", "connected", "clockSource")},
            "entities": {
                "enemies": len(enemies.get("items", [])),
                "characters": len(characters.get("items", [])),
            },
            "quality": {key: quality.get(key) for key in (
                "sampleHz", "loopMs", "frameMs", "ioMs", "droppedOutboundFrames")},
            "warnings": list(self.warnings),
        }


def _contains_internal_address(value: Any) -> bool:
    """检测不应出现在公开协议中的指针字段或嵌入式地址文本。"""
    if isinstance(value, dict):
        return any(
            key.lower() in _INTERNAL_FIELD_NAMES
            or _contains_internal_address(child)
            for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_internal_address(child) for child in value)
    return isinstance(value, str) and _INTERNAL_ADDRESS_PATTERN.search(value) is not None


class NdjsonWriter:
    """按秒批量刷新 NDJSON，减少高频采样对磁盘的同步写入压力。

    每行都是一条完整 JSON 记录，包含本机捕获时刻、来源端点和未转换的协议
    消息。发生进程退出时 ``close`` 会强制刷新剩余缓冲，方便后续离线分析。
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._output = path.open("w", encoding="utf-8", buffering=1024 * 1024)
        self._last_flush = time.monotonic()

    def write(self, source: str, message: dict[str, Any]) -> int:
        record = json.dumps({
            "capturedAt": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "message": message,
        }, ensure_ascii=False, separators=(",", ":")) + "\n"
        self._output.write(record)
        if time.monotonic() - self._last_flush >= 1.0:
            self._output.flush()
            self._last_flush = time.monotonic()
        return len(record.encode("utf-8"))

    def close(self) -> None:
        self._output.flush()
        self._output.close()


async def _connect_with_cancellation(
    url: str,
    stop_requested: Callable[[], bool] | None,
) -> Any | None:
    """建立连接，同时让桌面窗口能够在握手期间快速停止采集。

    ``websockets.connect`` 的默认握手超时比 Qt 关闭动画更长；这里以短轮询
    检查取消请求，并主动取消未完成的连接任务。返回 ``None`` 表示用户在
    连接完成前关闭了监控器，而不是协议错误。
    """
    connect_task = asyncio.ensure_future(
        websockets.connect(url, open_timeout=2, close_timeout=1))
    while not connect_task.done():
        if stop_requested is not None and stop_requested():
            connect_task.cancel()
            await asyncio.gather(connect_task, return_exceptions=True)
            return None
        await asyncio.sleep(_CONNECT_POLL_SECONDS)
    return await connect_task


async def capture(
    duration_seconds: float,
    output_path: Path,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    on_message: Callable[[str, dict[str, Any]], None] | None = None,
    stop_requested: Callable[[], bool] | None = None,
) -> MonitorState:
    """连接两类端点、持续采样并保存原始协议消息。

    ``duration_seconds`` 为 0 时持续运行，直到调用方取消协程。窗口工作线程把
    中断请求传入 ``stop_requested``；包括连接握手阶段在内都会在约 50ms 内响应。
    """
    state = MonitorState()
    writer = NdjsonWriter(output_path)
    game = ops = None
    try:
        game = await _connect_with_cancellation(GAME_URL, stop_requested)
        if game is None:
            return state
        ops = await _connect_with_cancellation(OPS_URL, stop_requested)
        if ops is None:
            return state

        async def record(source: str, raw: str) -> None:
            message = json.loads(raw)
            state.observe(message, writer.write(source, message))
            if on_message is not None:
                on_message(source, message)

        await record("game", await game.recv())
        await record("ops", await ops.recv())
        await game.send(json.dumps({
            "type": "subscribe", "requestId": "desktop-monitor", "topics": TOPICS,
        }))
        await ops.send(json.dumps({
            "type": "subscribe", "topics": {"ops.heartbeat": {"rateHz": 1}},
        }))

        next_update = time.monotonic()
        while ((duration_seconds <= 0 or time.monotonic() - state.started_at < duration_seconds)
               and not (stop_requested and stop_requested())):
            game_task = asyncio.create_task(game.recv())
            ops_task = asyncio.create_task(ops.recv())
            done, pending = await asyncio.wait(
                {game_task, ops_task}, timeout=1, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                await record("game" if task is game_task else "ops", task.result())
            if on_update is not None and time.monotonic() >= next_update:
                on_update(state.summary())
                next_update = time.monotonic() + 0.2
    finally:
        if on_update is not None:
            on_update(state.summary())
        writer.close()
        if game is not None:
            await game.close()
        if ops is not None:
            await ops.close()
    return state


def _format_bytes(value: int) -> str:
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KiB"
    return f"{value / 1024 / 1024:.1f} MiB"


def run_headless(duration_seconds: float, output_path: Path) -> None:
    """执行无界面采集，适合自动化测试或脚本调用。"""
    state = asyncio.run(capture(duration_seconds, output_path))
    print(json.dumps({
        "capturedMessages": state.messages,
        "bytesWritten": state.bytes_written,
        "output": str(output_path),
    }, ensure_ascii=False))


def run_window(duration_seconds: float, output_path: Path) -> None:
    """启动仅消费 WebSocket 消息的插件式测试前端。"""
    from PySide6.QtCore import QThread, QTimer, Qt, Signal
    from PySide6.QtWidgets import (
        QApplication, QAbstractItemView, QFormLayout, QGroupBox, QHBoxLayout,
        QLabel, QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit,
        QPushButton, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
        QVBoxLayout, QWidget,
    )

    class CaptureWorker(QThread):
        """将 asyncio 采集循环隔离在 Qt 工作线程中。

        Qt 主线程只接收不可变的消息对象并绘制界面；停止时使用
        ``requestInterruption``，由 ``capture`` 的协作式取消逻辑关闭网络连接和
        NDJSON 文件，绝不强制终止线程。
        """
        updated = Signal(dict)
        received = Signal(str, dict)
        failed = Signal(str)
        completed = Signal(dict)

        def run(self) -> None:
            try:
                state = asyncio.run(capture(
                    duration_seconds, output_path, self.updated.emit,
                    on_message=lambda source, message: self.received.emit(source, message),
                    stop_requested=self.isInterruptionRequested,
                ))
            except Exception as error:
                print(f"WebSocket monitor worker failed: {error}", file=sys.stderr)
                self.failed.emit(str(error))
            else:
                self.completed.emit({
                    "messages": state.messages, "bytesWritten": state.bytes_written,
                })

    class MonitorWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Arknights Timer · WebSocket 监控")
            self.resize(1300, 860)
            self._worker = CaptureWorker(self)
            self._worker.updated.connect(self.update_view)
            self._worker.received.connect(self.receive_message)
            self._worker.failed.connect(self.show_failure)
            self._worker.completed.connect(self.show_completed)
            self._latest: dict[str, dict[str, Any]] = {}
            self._dirty_topics: set[str] = set()
            self._summary: dict[str, Any] = {}
            self._close_requested = False
            self._build()
            self._refresh_timer = QTimer(self)
            self._refresh_timer.setInterval(100)
            self._refresh_timer.timeout.connect(self.refresh_tables)
            self._refresh_timer.start()
            self._worker.start()

        def _build(self) -> None:
            root = QWidget(self)
            layout = QVBoxLayout(root)
            summary = QFormLayout()
            self.status = QLabel("正在连接本机 WebSocket 服务…")
            self.elapsed = QLabel("0.0 秒 · 0 条")
            self.messages = QLabel("0")
            self.output = QLabel(str(output_path))
            summary.addRow("状态", self.status)
            summary.addRow("已运行", self.elapsed)
            summary.addRow("已采集", self.messages)
            summary.addRow("D 盘数据文件", self.output)
            layout.addLayout(summary)

            self.tabs = QTabWidget()
            self.tabs.addTab(self._build_overview(), "战斗 / 运维")
            self.tabs.addTab(self._build_entities("enemy"), "敌人")
            self.tabs.addTab(self._build_entities("character"), "干员 / 召唤物")
            self.tabs.addTab(self._build_deploy(), "操作记录")
            self.tabs.addTab(self._build_rng(), "随机数")
            self.tabs.addTab(self._build_protocol_flow(), "协议流")
            layout.addWidget(self.tabs, 1)
            controls = QHBoxLayout()
            self.stop = QPushButton("停止并保存")
            self.stop.clicked.connect(self.close)
            controls.addWidget(self.stop)
            controls.addStretch(1)
            layout.addLayout(controls)
            self.setCentralWidget(root)

        @staticmethod
        def _table(headers: list[str]) -> QTableWidget:
            table = QTableWidget(0, len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setAlternatingRowColors(True)
            table.horizontalHeader().setStretchLastSection(True)
            return table

        def _build_overview(self) -> QWidget:
            page = QWidget()
            layout = QHBoxLayout(page)
            battle_box = QGroupBox("游戏状态（battle.updated）")
            battle_layout = QVBoxLayout(battle_box)
            self.battle_view = QPlainTextEdit("等待 battle.updated…")
            self.battle_view.setReadOnly(True)
            battle_layout.addWidget(self.battle_view)
            layout.addWidget(battle_box, 1)
            ops_box = QGroupBox("服务与采样质量（ops / quality）")
            ops_layout = QVBoxLayout(ops_box)
            self.ops_view = QPlainTextEdit("等待 ops.status / quality.updated…")
            self.ops_view.setReadOnly(True)
            ops_layout.addWidget(self.ops_view)
            self.topic_table = self._table(["主题", "收到消息数"])
            ops_layout.addWidget(self.topic_table)
            layout.addWidget(ops_box, 1)
            return page

        def _build_entities(self, kind: str) -> QWidget:
            page = QWidget()
            layout = QHBoxLayout(page)
            if kind == "enemy":
                self.enemy_table = self._table([
                    "ID", "名称", "生命周期", "存活", "HP", "最大 HP", "X", "Y", "动作",
                ])
                self.enemy_detail = QPlainTextEdit("选择一行查看 enemy_detail.updated 对应完整数据。")
                self.enemy_table.itemSelectionChanged.connect(
                    lambda: self.show_entity_detail("enemy"))
                table, detail = self.enemy_table, self.enemy_detail
            else:
                self.character_table = self._table([
                    "ID", "名称", "类型", "存活", "HP", "最大 HP", "SP", "最大 SP", "位置",
                ])
                self.character_detail = QPlainTextEdit("选择一行查看 character_detail.updated 对应完整数据。")
                self.character_table.itemSelectionChanged.connect(
                    lambda: self.show_entity_detail("character"))
                table, detail = self.character_table, self.character_detail
            detail.setReadOnly(True)
            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.addWidget(table)
            splitter.addWidget(detail)
            splitter.setSizes([850, 450])
            layout.addWidget(splitter)
            return page

        def _build_deploy(self) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)
            self.deploy_status = QLabel("等待 deploy.updated…")
            layout.addWidget(self.deploy_status)
            self.deploy_table = self._table([
                "时间", "操作", "单位", "逻辑帧", "行", "列", "方向", "来源",
            ])
            layout.addWidget(self.deploy_table)
            return page

        def _build_rng(self) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)
            warning = QLabel("此页展示接口原样数据，用于验证字段；若出现地址字段会明确提示。")
            warning.setWordWrap(True)
            layout.addWidget(warning)
            self.rng_view = QPlainTextEdit("等待 rng.updated…")
            self.rng_view.setReadOnly(True)
            layout.addWidget(self.rng_view)
            return page

        def _build_protocol_flow(self) -> QWidget:
            page = QWidget()
            layout = QHBoxLayout(page)
            self.flow_list = QListWidget()
            self.flow_list.setMaximumWidth(490)
            self.flow_list.currentItemChanged.connect(self.show_raw_message)
            self.raw_view = QPlainTextEdit("选择左侧任一消息查看完整 JSON。")
            self.raw_view.setReadOnly(True)
            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.addWidget(self.flow_list)
            splitter.addWidget(self.raw_view)
            splitter.setSizes([490, 790])
            layout.addWidget(splitter)
            return page

        def update_view(self, summary: dict[str, Any]) -> None:
            self._summary = summary
            self.status.setText("采集中（所有显示数据均来自 WebSocket）")
            self.elapsed.setText(f"{summary['elapsed']:.1f} 秒 · {summary['messages']:,} 条")
            self.messages.setText(
                f"{summary['messages']:,} 条 · {_format_bytes(summary['bytesWritten'])}")

        def receive_message(self, source: str, message: dict[str, Any]) -> None:
            topic = str(message.get("type", "unknown"))
            self._latest[topic] = message
            self._dirty_topics.add(topic)
            captured = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            item = QListWidgetItem(
                f"{captured}  [{source}]  #{message.get('sequence', '—')}  {topic}")
            item.setData(Qt.ItemDataRole.UserRole, message)
            self.flow_list.addItem(item)
            while self.flow_list.count() > 500:
                self.flow_list.takeItem(0)

        def refresh_tables(self) -> None:
            if not self._dirty_topics:
                return
            dirty = self._dirty_topics
            self._dirty_topics = set()
            if {"battle.updated", "quality.updated", "ops.status", "ops.heartbeat"} & dirty:
                self.refresh_overview()
            if "enemies.updated" in dirty:
                self.refresh_entity_table("enemy")
            if "enemy_detail.updated" in dirty:
                self.show_entity_detail("enemy")
            if "characters.updated" in dirty:
                self.refresh_entity_table("character")
            if "character_detail.updated" in dirty:
                self.show_entity_detail("character")
            if "deploy.updated" in dirty:
                self.refresh_deploy()
            if "rng.updated" in dirty:
                self.refresh_rng()

        def refresh_overview(self) -> None:
            battle = self._latest.get("battle.updated", {}).get("data", {})
            quality = self._latest.get("quality.updated", {}).get("data", {})
            ops = self._latest.get("ops.heartbeat", self._latest.get("ops.status", {})).get("data", {})
            self.battle_view.setPlainText(json.dumps(battle, ensure_ascii=False, indent=2))
            self.ops_view.setPlainText(json.dumps({"ops": ops, "quality": quality}, ensure_ascii=False, indent=2))
            counts = self._summary.get("topicCounts", {})
            self.topic_table.setRowCount(len(counts))
            for row, (topic, count) in enumerate(sorted(counts.items())):
                self.topic_table.setItem(row, 0, QTableWidgetItem(topic))
                self.topic_table.setItem(row, 1, QTableWidgetItem(str(count)))

        def refresh_entity_table(self, kind: str) -> None:
            """刷新实体快照，同时保持用户正在查看的行和滚动位置。

            单位主题最高每秒更新十次。直接重建表格会把滚动条推回顶部并清空
            选择，导致右侧完整详情在用户阅读时不断回弹。
            """
            topic = "enemies.updated" if kind == "enemy" else "characters.updated"
            items = self._latest.get(topic, {}).get("data", {}).get("items", [])
            table = self.enemy_table if kind == "enemy" else self.character_table
            selected = self._selected_id(table)
            scroll_bar = table.verticalScrollBar()
            scroll_value = scroll_bar.value()
            selected_row = None
            table.setUpdatesEnabled(False)
            table.blockSignals(True)
            try:
                table.setRowCount(len(items))
                for row, entity in enumerate(items):
                    position = entity.get("position") or {}
                    if kind == "enemy":
                        action = entity.get("action") or {}
                        values = [entity.get("id"), entity.get("name"), entity.get("lifecycle"),
                                  entity.get("alive"), entity.get("hp"), entity.get("maxHp"),
                                  position.get("x"), position.get("y"), action.get("phase")]
                    else:
                        values = [entity.get("id"), entity.get("name"), entity.get("kind"),
                                  entity.get("alive"), entity.get("hp"), entity.get("maxHp"),
                                  entity.get("sp"), entity.get("maxSp"), position]
                    for column, value in enumerate(values):
                        cell = QTableWidgetItem("—" if value is None else str(value))
                        if column == 0:
                            cell.setData(Qt.ItemDataRole.UserRole, str(entity.get("id", "")))
                        table.setItem(row, column, cell)
                    if selected and str(entity.get("id")) == selected:
                        selected_row = row
                if selected_row is not None:
                    table.selectRow(selected_row)
                scroll_bar.setValue(min(scroll_value, scroll_bar.maximum()))
            finally:
                table.blockSignals(False)
                table.setUpdatesEnabled(True)

        @staticmethod
        def _selected_id(table: QTableWidget) -> str | None:
            items = table.selectedItems()
            return (items[0].data(Qt.ItemDataRole.UserRole) if items else None)

        def show_entity_detail(self, kind: str) -> None:
            table = self.enemy_table if kind == "enemy" else self.character_table
            detail = self.enemy_detail if kind == "enemy" else self.character_detail
            entity_id = self._selected_id(table)
            if not entity_id:
                return
            topic = f"{kind}_detail.updated"
            details = self._latest.get(topic, {}).get("data", {}).get("items", [])
            entity = next((item for item in details if str(item.get("id")) == entity_id), None)
            detail.setPlainText(json.dumps(
                entity or {"id": entity_id, "status": "当前未取得对应完整详情。"},
                ensure_ascii=False, indent=2))

        def refresh_deploy(self) -> None:
            data = self._latest.get("deploy.updated", {}).get("data", {})
            events = data.get("events", [])
            journal = data.get("journal", [])
            self.deploy_status.setText(f"当前关卡完整实时操作：{len(events)} 条；代理作战序列：{len(journal)} 条")
            self.deploy_table.setRowCount(len(events))
            for row, event in enumerate(events):
                values = [event.get("timestamp"), event.get("opName", event.get("op")),
                          event.get("charName", event.get("charId")), event.get("frame"),
                          event.get("gridRow"), event.get("gridCol"), event.get("directionName"),
                          event.get("frameSource")]
                for column, value in enumerate(values):
                    self.deploy_table.setItem(row, column, QTableWidgetItem("—" if value is None else str(value)))

        def refresh_rng(self) -> None:
            data = self._latest.get("rng.updated", {}).get("data", {})
            prefix = (
                "⚠ 检测到不应公开的内部字段或地址文本：可能连接到了旧版插件，"
                "请保留本次记录并检查服务版本。\n\n"
                if _contains_internal_address(data) else ""
            )
            self.rng_view.setPlainText(prefix + json.dumps(data, ensure_ascii=False, indent=2))

        def show_raw_message(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
            if current is not None:
                self.raw_view.setPlainText(json.dumps(
                    current.data(Qt.ItemDataRole.UserRole), ensure_ascii=False, indent=2))
            battle = summary["battle"]
            entities = summary["entities"]
            quality = summary["quality"]
            lines = [
                f"战斗：{battle.get('state')} · {battle.get('gameTime')}s · 帧 {battle.get('fixedFrame')}",
                f"实体：敌人 {entities['enemies']} · 干员/召唤物 {entities['characters']}",
                "质量：采样 {sampleHz}Hz · loop {loopMs}ms · frame {frameMs}ms · "
                "I/O {ioMs}ms · 丢帧 {droppedOutboundFrames}".format(**quality),
            ]
            if summary["warnings"]:
                lines.extend(f"⚠ {warning}" for warning in summary["warnings"])
            self.detail.setPlainText("\n".join(lines))

        def show_failure(self, error: str) -> None:
            self.status.setText(f"连接/采集失败：{error}")
            self.stop.setText("关闭")

        def show_completed(self, result: dict[str, Any]) -> None:
            self.status.setText("采集已结束，文件已刷新。")
            self.messages.setText(
                f"{result['messages']:,} 条 · {_format_bytes(result['bytesWritten'])}")
            self.stop.setText("关闭")

        def closeEvent(self, event) -> None:  # noqa: N802 - Qt 生命周期入口。
            if self._worker.isRunning():
                if not self._close_requested:
                    self._close_requested = True
                    self.status.setText("正在停止并刷新 D 盘文件…")
                    self.stop.setEnabled(False)
                self._worker.requestInterruption()
                # Keep the window alive until the cooperative worker has closed
                # both sockets and flushed the NDJSON file. Destroying a running
                # QThread is unsafe and previously raced the 2-second wait.
                QTimer.singleShot(50, self.close)
                event.ignore()
                return
            event.accept()

    app = QApplication.instance() or QApplication(sys.argv)
    window = MonitorWindow()
    window.show()
    app.exec()


def parse_arguments() -> argparse.Namespace:
    """解析监控器参数；默认使用窗口模式和 D 盘运行数据目录。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action="store_true", help="不显示窗口，仅采集并保存。")
    parser.add_argument("--duration", type=float, default=600.0,
                        help="采集秒数；0 表示持续到手动关闭。默认 600。")
    parser.add_argument("--output", type=Path, help="覆盖默认 D 盘输出文件。")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()
    filename = datetime.now().strftime("websocket_%Y%m%d_%H%M%S.ndjson")
    output = arguments.output or DEFAULT_OUTPUT_DIR / filename
    if arguments.headless:
        run_headless(arguments.duration, output)
    else:
        run_window(arguments.duration, output)
