"""
明日方舟打轴工具 — 独立桌面程序（PySide6）。
读取游戏时间与帧（tools/timer 内存方案），加载前端导出的排轴 JSON，显示事项与当前步骤。
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import ctypes
import threading
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QCursor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# 保证可导入 app.services（从 backend 目录运行），并兼容 PyInstaller 冻结路径。
if getattr(sys, "frozen", False):
    _RUNTIME_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    _BACKEND_ROOT = _RUNTIME_ROOT / "backend"
    _REPO_ROOT = _RUNTIME_ROOT
else:
    _BACKEND_ROOT = Path(__file__).resolve().parent
    _REPO_ROOT = _BACKEND_ROOT.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.schedule_engine import build_status_payload, game_frame_for_anchor
from app.services.schedule_store import ScheduleStore
from app.services.timer_provider import TimerDataProvider
from app.services.timeline_cache import TimelineCacheService

AUTO_REFRESH_MS = 8
STATUS_BUILD_MS = 33
FAST_UI_MS = 8
STEP_UI_MS = 33
SLOW_UI_MS = 150
WS_PUSH_MS = 8

COLS = ["轨道", "时间范围", "状态", "距开始 / 剩余", "备注"]


def _validate_payload(data: dict) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "不是有效的 JSON 对象。"
    if "rows" not in data or "meta" not in data:
        return False, "缺少 rows 或 meta（需与前端导出格式一致）。"
    if not isinstance(data.get("rows"), list):
        return False, "rows 必须是数组。"
    if not isinstance(data.get("meta"), dict):
        return False, "meta 必须是对象。"
    return True, ""


def _format_game_time(value: object) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.3f}s"
    except (TypeError, ValueError):
        return str(value)


class CoachWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("明日方舟打轴工具")
        self.resize(1180, 760)
        self.setMinimumSize(900, 560)

        self._provider = TimerDataProvider()
        self._store = ScheduleStore()
        self._cache = TimelineCacheService()

        self._anchor_game_frame: int | None = None
        self._exec_from_current = False
        self._schedule_state_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._last_status_payload: dict | None = None
        self._status_version = 0
        self._rendered_step_version = -1
        self._rendered_slow_version = -1
        self._last_list_signature: tuple[tuple[object, ...], ...] = ()
        self._last_scroll_target_index = -1

        self._hook_port: int = 0
        self._ws_port: int = 0
        self._ws_clients: set = set()
        self._ws_loop: asyncio.AbstractEventLoop | None = None

        self._build_ui()
        self._start_hook_server()
        self._start_ws_server()
        self._start_workers()
        self._start_timers()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.page_scroll = QScrollArea()
        self.page_scroll.setObjectName("MainPageScroll")
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.page_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        root_layout.addWidget(self.page_scroll)

        page = QWidget()
        self.page_scroll.setWidget(page)
        main = QVBoxLayout(page)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("明日方舟打轴工具 · 桌面版 Made by Tim(321346659)")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #e8e8e8;")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.btn_pin_top = QPushButton("窗口置顶")
        self.btn_pin_top.setCheckable(True)
        self.btn_pin_top.setToolTip("开启后窗口始终显示在最前")
        self.btn_pin_top.toggled.connect(self._on_toggle_stay_on_top)
        self._style_toggle_exec_button(self.btn_pin_top, checked=False)
        title_row.addWidget(self.btn_pin_top)
        btn_ws_info = QPushButton("接口说明")
        btn_ws_info.setToolTip("查看 WebSocket 接口地址与使用方式")
        btn_ws_info.clicked.connect(self._show_ws_info)
        self._style_secondary_button(btn_ws_info)
        title_row.addWidget(btn_ws_info)
        main.addLayout(title_row)
        sub = QLabel("用「寻址工具」逐步扫描内存；完成后会自动读取时间与逻辑帧并实时刷新显示。")
        sub.setStyleSheet("color: #9a9a9a;")
        main.addWidget(sub)

        box_cfg = QGroupBox("内存寻址（tools/timer）")
        l_cfg = QHBoxLayout(box_cfg)
        btn_tool = QPushButton("打开寻址工具")
        btn_tool.clicked.connect(self._on_open_timer_tool)
        btn_refresh = QPushButton("刷新游戏状态")
        btn_refresh.clicked.connect(self._on_refresh_game)
        l_cfg.addWidget(btn_tool)
        l_cfg.addWidget(btn_refresh)
        l_cfg.addWidget(QLabel("（寻址工具需管理员权限；扫描完成后自动推送地址到本工具）"))
        l_cfg.addStretch(1)
        main.addWidget(box_cfg)

        box_game_json = QGroupBox("游戏状态 & 排轴数据")
        l_gj = QHBoxLayout(box_game_json)
        l_gj.setContentsMargins(4, 4, 4, 4)
        l_gj.setSpacing(10)

        # ---- 左侧：排轴数据 ----
        json_left = QVBoxLayout()
        json_left.setSpacing(10)

        card_file = QFrame()
        card_file.setObjectName("ScheduleSubCard")
        card_file.setStyleSheet(
            "#ScheduleSubCard { background: #252526; border: 1px solid #3c3c3c; border-radius: 8px; }"
            "QLabel#CardTitle { color: #b0b0b0; font-size: 11px; font-weight: 600; }"
        )
        cf_l = QVBoxLayout(card_file)
        cf_l.setContentsMargins(12, 10, 12, 10)
        title_file = QLabel("数据与缓存")
        title_file.setObjectName("CardTitle")
        cf_l.addWidget(title_file)
        row_file = QHBoxLayout()
        row_file.setSpacing(10)
        btn_load = QPushButton("从文件加载 JSON")
        btn_load.setToolTip("选择前端导出的排轴 JSON 文件")
        btn_load.clicked.connect(self._on_load_json)
        self._style_primary_button(btn_load)
        btn_clear = QPushButton("清空排轴")
        btn_clear.setToolTip("清空已加载的排轴数据")
        btn_clear.clicked.connect(self._on_clear_schedule)
        self._style_muted_button(btn_clear)
        row_file.addWidget(btn_load)
        row_file.addWidget(btn_clear)
        row_file.addStretch(1)
        lbl_uid = QLabel("用户 ID")
        lbl_uid.setStyleSheet("color:#9a9a9a;")
        self.ed_cache_user = QLineEdit("default")
        self.ed_cache_user.setPlaceholderText("default")
        self.ed_cache_user.setMaximumWidth(160)
        self.ed_cache_user.setMinimumHeight(30)
        btn_cache = QPushButton("从缓存载入")
        btn_cache.setToolTip("从 backend/data/timeline_cache 读取对应用户的缓存")
        btn_cache.clicked.connect(self._on_load_cache)
        self._style_secondary_button(btn_cache)
        row_file.addWidget(lbl_uid)
        row_file.addWidget(self.ed_cache_user)
        row_file.addWidget(btn_cache)
        cf_l.addLayout(row_file)
        json_left.addWidget(card_file)

        card_time = QFrame()
        card_time.setObjectName("ScheduleSubCard2")
        card_time.setStyleSheet(
            "#ScheduleSubCard2 { background: #252526; border: 1px solid #3c3c3c; border-radius: 8px; }"
            "QLabel#CardTitle { color: #b0b0b0; font-size: 11px; font-weight: 600; }"
        )
        ct_l = QVBoxLayout(card_time)
        ct_l.setContentsMargins(12, 10, 12, 10)
        title_time = QLabel("时间基准与提醒")
        title_time.setObjectName("CardTitle")
        ct_l.addWidget(title_time)

        row_mode = QHBoxLayout()
        row_mode.setSpacing(8)
        lbl_mode = QLabel("时间基准")
        lbl_mode.setStyleSheet("color:#9a9a9a; min-width:64px;")
        self.btn_exec_start = QPushButton("从头执行")
        self.btn_exec_start.setCheckable(True)
        self.btn_exec_start.setChecked(True)
        self.btn_exec_start.setToolTip("轴上帧数与游戏逻辑帧一一对应")
        self.btn_exec_current = QPushButton("从当前帧起算")
        self.btn_exec_current.setCheckable(True)
        self.btn_exec_current.setToolTip("将当前游戏帧对齐到下方「起始轴帧」")
        self._style_toggle_exec_button(self.btn_exec_start, checked=True)
        self._style_toggle_exec_button(self.btn_exec_current, checked=False)
        self.btn_exec_start.toggled.connect(self._on_exec_start_toggled)
        self.btn_exec_current.toggled.connect(self._on_exec_current_toggled)
        row_mode.addWidget(lbl_mode)
        row_mode.addWidget(self.btn_exec_start)
        row_mode.addWidget(self.btn_exec_current)
        row_mode.addStretch(1)
        ct_l.addLayout(row_mode)

        row_anchor = QHBoxLayout()
        row_anchor.setSpacing(10)
        lbl_sf = QLabel("起始轴帧")
        lbl_sf.setStyleSheet("color:#9a9a9a;")
        self.ed_start_frame = QLineEdit("0")
        self.ed_start_frame.setMaximumWidth(100)
        self.ed_start_frame.setMinimumHeight(30)
        self.ed_start_frame.setPlaceholderText("0")
        btn_apply_anchor = QPushButton("应用当前帧对齐")
        btn_apply_anchor.setToolTip("把当前游戏帧映射到上面的起始轴帧，并切换到「从当前帧起算」")
        btn_apply_anchor.clicked.connect(self._apply_anchor_from_current_frame)
        self._style_secondary_button(btn_apply_anchor)
        lbl_remind = QLabel("即将开始提醒")
        lbl_remind.setStyleSheet("color:#9a9a9a;")
        self.spin_remind_sec = QSpinBox()
        self.spin_remind_sec.setRange(0, 999)
        self.spin_remind_sec.setValue(5)
        self.spin_remind_sec.setSuffix(" 秒")
        self.spin_remind_sec.setToolTip("距开始小于该时间的事项会出现在「即将开始提醒」")
        self.spin_remind_sec.setMinimumHeight(30)
        self.spin_remind_sec.setMinimumWidth(110)
        row_anchor.addWidget(lbl_sf)
        row_anchor.addWidget(self.ed_start_frame)
        row_anchor.addWidget(btn_apply_anchor)
        row_anchor.addSpacing(24)
        row_anchor.addWidget(lbl_remind)
        row_anchor.addWidget(self.spin_remind_sec)
        row_anchor.addStretch(1)
        ct_l.addLayout(row_anchor)
        json_left.addWidget(card_time)

        l_gj.addLayout(json_left, 3)

        # ---- 右侧：游戏时间 & 逻辑帧 ----
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        card_time_disp = QFrame()
        card_time_disp.setObjectName("GameTimeCard")
        card_time_disp.setStyleSheet(
            "#GameTimeCard { background: #252526; border: 1px solid #3c3c3c; border-radius: 8px; }"
        )
        ctd_l = QVBoxLayout(card_time_disp)
        ctd_l.setContentsMargins(16, 12, 16, 12)
        ctd_l.setSpacing(4)
        lbl_time_title = QLabel("游戏时间")
        lbl_time_title.setStyleSheet("color:#9a9a9a; font-size:12px; font-weight:600;")
        lbl_time_title.setAlignment(Qt.AlignCenter)
        ctd_l.addWidget(lbl_time_title)
        self.lbl_game_time_big = QLabel("—")
        self.lbl_game_time_big.setStyleSheet("font-size:48px; font-weight:700; color:#7ec8ff;")
        self.lbl_game_time_big.setAlignment(Qt.AlignCenter)
        ctd_l.addWidget(self.lbl_game_time_big)
        right_panel.addWidget(card_time_disp)

        card_frame_disp = QFrame()
        card_frame_disp.setObjectName("GameFrameCard")
        card_frame_disp.setStyleSheet(
            "#GameFrameCard { background: #252526; border: 1px solid #3c3c3c; border-radius: 8px; }"
        )
        cfd_l = QVBoxLayout(card_frame_disp)
        cfd_l.setContentsMargins(16, 12, 16, 12)
        cfd_l.setSpacing(4)
        lbl_frame_title = QLabel("逻辑帧")
        lbl_frame_title.setStyleSheet("color:#9a9a9a; font-size:12px; font-weight:600;")
        lbl_frame_title.setAlignment(Qt.AlignCenter)
        cfd_l.addWidget(lbl_frame_title)
        self.lbl_frame_big = QLabel("—")
        self.lbl_frame_big.setStyleSheet("font-size:48px; font-weight:700; color:#ffd66b;")
        self.lbl_frame_big.setAlignment(Qt.AlignCenter)
        cfd_l.addWidget(self.lbl_frame_big)
        right_panel.addWidget(card_frame_disp)

        self.lbl_game = QLabel("正在等待实时刷新…")
        self.lbl_game.setWordWrap(True)
        self.lbl_game.setStyleSheet("color:#9a9a9a; font-size:11px;")
        right_panel.addWidget(self.lbl_game)
        right_panel.addStretch(1)

        l_gj.addLayout(right_panel, 1)

        main.addWidget(box_game_json)

        box_step = QGroupBox("当前进度")
        l_step = QVBoxLayout(box_step)
        self.lbl_step = QLabel("—")
        self.lbl_step.setWordWrap(True)
        self.lbl_step.setStyleSheet("background:#252526;color:#7ec8ff;font-weight:700;padding:6px;")
        self.lbl_remind = QLabel("提醒：—")
        self.lbl_remind.setWordWrap(True)
        self.lbl_remind.setStyleSheet("background:#252526;color:#ffd66b;font-weight:700;padding:6px;")
        l_step.addWidget(self.lbl_step)
        l_step.addWidget(self.lbl_remind)
        main.addWidget(box_step)

        box_table = QGroupBox("时间轴事项")
        l_table = QVBoxLayout(box_table)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        l_table.addWidget(self.table)
        main.addWidget(box_table, 1)

        app = QApplication.instance()
        if app:
            app.setStyleSheet(
                "QWidget{background:#1e1e1e;color:#e8e8e8;}"
                "QLineEdit,QTableWidget,QGroupBox,QSpinBox{background:#2d2d2d;border:1px solid #444;border-radius:4px;padding:4px;}"
                "QGroupBox{font-weight:600;margin-top:8px;padding-top:8px;}"
                "QScrollArea#MainPageScroll{background:transparent;}"
                "QScrollBar:vertical{width:10px;background:#2d2d2d;margin:0;}"
                "QScrollBar::handle:vertical{min-height:24px;background:#555;border-radius:4px;}"
                "QScrollBar::handle:vertical:hover{background:#666;}"
                "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
            )

    def _style_primary_button(self, btn: QPushButton) -> None:
        btn.setMinimumHeight(34)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(
            "QPushButton{background:#3d7eff;color:white;border:none;border-radius:6px;padding:6px 14px;font-weight:600;}"
            "QPushButton:hover{background:#5a90ff;} QPushButton:pressed{background:#2d62cc;}"
        )

    def _style_secondary_button(self, btn: QPushButton) -> None:
        btn.setMinimumHeight(34)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(
            "QPushButton{background:#3c3c3c;color:#e8e8e8;border:1px solid #555;border-radius:6px;padding:6px 14px;}"
            "QPushButton:hover{background:#4a4a4a;}"
        )

    def _style_muted_button(self, btn: QPushButton) -> None:
        btn.setMinimumHeight(34)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(
            "QPushButton{background:transparent;color:#d4a0a0;border:1px solid #663333;border-radius:6px;padding:6px 14px;}"
            "QPushButton:hover{background:#3a2525;}"
        )

    def _style_toggle_exec_button(self, btn: QPushButton, checked: bool) -> None:
        btn.setMinimumHeight(34)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        if checked:
            btn.setStyleSheet(
                "QPushButton{background:#1a4a7a;color:#e8e8e8;border:2px solid #3d7eff;border-radius:6px;"
                "padding:6px 16px;font-weight:600;} QPushButton:hover{background:#224a7a;}"
            )
        else:
            btn.setStyleSheet(
                "QPushButton{background:#333;color:#9a9a9a;border:1px solid #444;border-radius:6px;padding:6px 16px;}"
                "QPushButton:hover{background:#3d3d3d;color:#cccccc;}"
            )

    def _on_exec_start_toggled(self, checked: bool) -> None:
        if not checked:
            if not self.btn_exec_current.isChecked():
                self.btn_exec_start.blockSignals(True)
                self.btn_exec_start.setChecked(True)
                self.btn_exec_start.blockSignals(False)
            return
        self.btn_exec_current.blockSignals(True)
        self.btn_exec_current.setChecked(False)
        self.btn_exec_current.blockSignals(False)
        self._style_toggle_exec_button(self.btn_exec_start, True)
        self._style_toggle_exec_button(self.btn_exec_current, False)
        with self._schedule_state_lock:
            self._anchor_game_frame = None
            self._exec_from_current = False

    def _on_exec_current_toggled(self, checked: bool) -> None:
        if not checked:
            if not self.btn_exec_start.isChecked():
                self.btn_exec_current.blockSignals(True)
                self.btn_exec_current.setChecked(True)
                self.btn_exec_current.blockSignals(False)
            return
        self.btn_exec_start.blockSignals(True)
        self.btn_exec_start.setChecked(False)
        self.btn_exec_start.blockSignals(False)
        self._style_toggle_exec_button(self.btn_exec_start, False)
        self._style_toggle_exec_button(self.btn_exec_current, True)
        with self._schedule_state_lock:
            self._exec_from_current = True

    def _show_ws_info(self) -> None:
        if self._ws_port == 0:
            QMessageBox.information(self, "WebSocket 接口", "WebSocket 服务未启动（可能缺少 websockets 库）。\n请执行 pip install websockets 后重试。")
            return
        addr = f"ws://127.0.0.1:{self._ws_port}"
        text = (
            f"WebSocket 接口地址：\n{addr}\n\n"
            "服务端实时推送游戏时间与逻辑帧，客户端只需连接即可接收数据。\n\n"
            "消息格式（JSON）：\n"
            '{\n'
            '  "game_time": 12.345,    // float，游戏内时间（秒）\n'
            '  "frame_count": 741,     // int，游戏逻辑帧\n'
            '  "connected": true       // bool，内存读取是否正常\n'
            '}\n\n'
            "JavaScript 连接示例：\n"
            f'const ws = new WebSocket("{addr}");\n'
            "ws.onmessage = (e) => {\n"
            "  const data = JSON.parse(e.data);\n"
            "  console.log(data.game_time, data.frame_count);\n"
            "};"
        )
        dlg = QMessageBox(self)
        dlg.setWindowTitle("WebSocket 接口说明")
        dlg.setText(text)
        dlg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        dlg.exec()

    def _on_toggle_stay_on_top(self, checked: bool) -> None:
        # Qt requires re-show after changing top-most flag.
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        self.show()
        self.raise_()
        self.activateWindow()
        self._style_toggle_exec_button(self.btn_pin_top, checked)

    def _start_hook_server(self) -> None:
        """启动本地 TCP 服务端，接收寻址工具推送的 hook 数据。"""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        self._hook_port = srv.getsockname()[1]

        def _serve():
            while not self._stop_event.is_set():
                srv.settimeout(1.0)
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    data = b""
                    while b"\n" not in data:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        data += chunk
                    if data:
                        raw = json.loads(data.decode("utf-8").strip())
                        pn = (raw.get("process_name") or "").strip()
                        addr = (raw.get("time_address") or "").strip()
                        if pn and addr:
                            self._provider.apply_hook(pn, addr)
                except Exception:
                    pass
                finally:
                    conn.close()

        threading.Thread(target=_serve, name="ak-hook-tcp-server", daemon=True).start()

    def _start_ws_server(self) -> None:
        try:
            import websockets
            from websockets.exceptions import ConnectionClosed
        except ImportError:
            return

        def _snapshot_msg() -> str:
            game = self._provider.get_game_data()
            return json.dumps({
                "game_time": game.get("game_time"),
                "frame_count": game.get("frame_count"),
                "connected": game.get("connected", False),
            })

        async def _send_one(ws, msg: str) -> None:
            try:
                await ws.send(msg)
            except ConnectionClosed:
                self._ws_clients.discard(ws)

        async def _ws_handler(ws):
            self._ws_clients.add(ws)
            try:
                try:
                    await ws.send(_snapshot_msg())
                except ConnectionClosed:
                    return
                await ws.wait_closed()
            finally:
                self._ws_clients.discard(ws)

        async def _ws_push_loop():
            while not self._stop_event.is_set():
                clients = list(self._ws_clients)
                if clients:
                    msg = _snapshot_msg()
                    await asyncio.gather(
                        *(_send_one(ws, msg) for ws in clients),
                        return_exceptions=True,
                    )
                await asyncio.sleep(WS_PUSH_MS / 1000)

        async def _ws_main():
            async with websockets.serve(
                _ws_handler, "127.0.0.1", 0,
            ) as server:
                self._ws_port = server.sockets[0].getsockname()[1]
                while not self._stop_event.is_set():
                    await asyncio.sleep(0.5)

        def _run():
            self._ws_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._ws_loop)
            self._ws_loop.run_until_complete(asyncio.gather(
                _ws_main(),
                _ws_push_loop(),
                return_exceptions=True,
            ))

        threading.Thread(target=_run, name="ak-ws-server", daemon=True).start()

    def _start_workers(self) -> None:
        threading.Thread(target=self._memory_worker, name="ak-memory-worker", daemon=True).start()
        threading.Thread(target=self._status_worker, name="ak-status-worker", daemon=True).start()

    def _start_timers(self) -> None:
        self.t_fast = QTimer(self)
        self.t_fast.timeout.connect(self._tick_fast)
        self.t_fast.start(FAST_UI_MS)
        self.t_step = QTimer(self)
        self.t_step.timeout.connect(self._tick_step)
        self.t_step.start(STEP_UI_MS)
        self.t_slow = QTimer(self)
        self.t_slow.timeout.connect(self._tick_slow)
        self.t_slow.start(SLOW_UI_MS)

    def _memory_worker(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._provider.refresh_sample()
            except Exception:
                pass
            self._stop_event.wait(AUTO_REFRESH_MS / 1000)

    def _status_worker(self) -> None:
        while not self._stop_event.is_set():
            try:
                st = self._build_status()
                with self._state_lock:
                    self._last_status_payload = st
                    self._status_version += 1
            except Exception:
                pass
            self._stop_event.wait(STATUS_BUILD_MS / 1000)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._stop_event.set()
        if self._ws_clients:
            for ws in list(self._ws_clients):
                try:
                    asyncio.run_coroutine_threadsafe(ws.close(), self._ws_loop)
                except Exception:
                    pass
        return super().closeEvent(event)

    def _build_status(self) -> dict:
        game = self._provider.get_game_data()
        payload = self._store.get()
        with self._schedule_state_lock:
            use_anchor = self._exec_from_current
            anchor = self._anchor_game_frame if use_anchor else None
        return build_status_payload(payload, game, relative_anchor_game_frame=anchor)

    def _latest_status(self) -> tuple[dict | None, int]:
        with self._state_lock:
            return self._last_status_payload, self._status_version

    def _on_open_timer_tool(self) -> None:
        script = _REPO_ROOT / "tools" / "timer" / "ak_timer_ui.py"
        if not script.is_file():
            QMessageBox.critical(self, "寻址工具", f"未找到脚本：\n{script}")
            return
        try:
            env = os.environ.copy()
            env["AK_HOOK_PORT"] = str(self._hook_port)
            # 冻结后 sys.executable 指向当前主程序 exe，直接调用会重新打开自身。
            if getattr(sys, "frozen", False):
                py_cmd = shutil.which("python") or shutil.which("py")
                if not py_cmd:
                    QMessageBox.critical(
                        self,
                        "寻址工具",
                        "未找到可用的 Python 解释器（python/py）。\n"
                        f"请手动运行：\n{script}",
                    )
                    return
                cmd = [py_cmd, str(script)]
            else:
                cmd = [sys.executable, str(script)]
            subprocess.Popen(cmd, cwd=str(script.parent), env=env, close_fds=sys.platform != "win32")
        except OSError as e:
            QMessageBox.critical(self, "寻址工具", f"无法启动：{e}")

    def _on_refresh_game(self) -> None:
        res = self._provider.refresh_sample()
        if not res.get("ok"):
            QMessageBox.warning(self, "游戏状态", res.get("message", "刷新失败"))

    def _apply_anchor_from_current_frame(self) -> None:
        payload = self._store.get()
        if not payload:
            QMessageBox.warning(self, "时间基准", "请先加载排轴 JSON。")
            return
        try:
            start_frame = int((self.ed_start_frame.text() or "0").strip())
        except ValueError:
            QMessageBox.warning(self, "时间基准", "起始轴帧必须是整数。")
            return
        cf = game_frame_for_anchor(payload, self._provider.get_game_data())
        if cf is None:
            QMessageBox.warning(self, "时间基准", "无法解析当前游戏帧，请确认寻址完成。")
            return
        with self._schedule_state_lock:
            self._anchor_game_frame = int(cf) - start_frame
            self._exec_from_current = True
        self.btn_exec_start.blockSignals(True)
        self.btn_exec_start.setChecked(False)
        self.btn_exec_start.blockSignals(False)
        self.btn_exec_current.blockSignals(True)
        self.btn_exec_current.setChecked(True)
        self.btn_exec_current.blockSignals(False)
        self._style_toggle_exec_button(self.btn_exec_start, False)
        self._style_toggle_exec_button(self.btn_exec_current, True)
        QMessageBox.information(self, "时间基准", f"已应用：当前游戏帧 F{int(cf)} 对齐到轴上 F{start_frame}。")

    def _on_load_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择排轴 JSON", str(_REPO_ROOT), "JSON Files (*.json);;All Files (*.*)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            QMessageBox.critical(self, "加载失败", str(e))
            return
        ok, msg = _validate_payload(data)
        if not ok:
            QMessageBox.critical(self, "格式错误", msg)
            return
        self._store.load(data)
        QMessageBox.information(self, "排轴", "已加载，列表将自动刷新。")

    def _on_clear_schedule(self) -> None:
        self._store.clear()
        QMessageBox.information(self, "排轴", "已清空。")

    def _on_load_cache(self) -> None:
        uid = self.ed_cache_user.text().strip() or "default"
        res = self._cache.load(uid)
        if not res.get("ok"):
            QMessageBox.critical(self, "缓存", res.get("message", "读取失败"))
            return
        if not res.get("has_cache") or not res.get("data"):
            QMessageBox.warning(self, "缓存", f"用户「{uid}」无缓存文件。")
            return
        data = res["data"]
        ok, msg = _validate_payload(data)
        if not ok:
            QMessageBox.critical(self, "格式错误", msg)
            return
        self._store.load(data)
        QMessageBox.information(self, "排轴", f"已从缓存载入用户 {res.get('user_id', uid)}。")

    def _tick_fast(self) -> None:
        game = self._provider.get_game_data()
        self.lbl_game_time_big.setText(_format_game_time(game.get("game_time")))
        fc = game.get("frame_count")
        self.lbl_frame_big.setText(f"F{int(fc)}" if fc is not None else "—")

    def _tick_step(self) -> None:
        st, version = self._latest_status()
        if st is None or version == self._rendered_step_version:
            return
        items = st.get("items") or []
        active = [it for it in items if it.get("phase") == "active"]
        if active:
            lines = [f"{i + 1}. {it.get('row_name', '')} — {it.get('label') or '区间'}（{it.get('until_end_text', '—')}）" for i, it in enumerate(active)]
            self.lbl_step.setText("正在执行：\n" + "\n".join(lines))
        else:
            step = st.get("current_step") or {}
            self.lbl_step.setText(step.get("summary") or st.get("message") or "—")

        remind_sec = float(max(0, self.spin_remind_sec.value()))
        fps = max(1, int(st.get("fps") or 60))
        remind_frames = int(remind_sec * fps)
        upcoming = [
            it for it in items
            if it.get("phase") == "upcoming"
            and isinstance(it.get("frames_until_start"), int)
            and 0 <= int(it.get("frames_until_start")) <= remind_frames
        ]
        if upcoming:
            lines = [f"{i + 1}. {it.get('row_name', '')} — {it.get('label') or '区间'}（{it.get('until_start_text', '—')}）" for i, it in enumerate(upcoming)]
            self.lbl_remind.setText("即将开始提醒：\n" + "\n".join(lines))
        else:
            self.lbl_remind.setText(f"即将开始提醒：未来 {remind_sec:g} 秒内无新事项")
        self._rendered_step_version = version

    def _tick_slow(self) -> None:
        st, version = self._latest_status()
        if st is None or version == self._rendered_slow_version:
            return
        game = self._provider.get_game_data()
        lr = game.get("last_refresh")
        start_frame = (self.ed_start_frame.text() or "0").strip()
        with self._schedule_state_lock:
            from_current = self._exec_from_current
            anchor_val = self._anchor_game_frame
        if from_current:
            mode_line = f"时间基准: 从当前帧起算（当前帧映射到轴上 F{start_frame}，锚点={anchor_val}）"
        else:
            mode_line = "时间基准: 从头执行"
        self.lbl_game.setText(
            "\n".join(
                [
                    mode_line,
                    f"连接: {'是' if game.get('connected') else '否'}  |  已配置地址: {'是' if game.get('configured') else '否'}",
                    f"排轴对照帧: {st.get('current_frame') if st.get('current_frame') is not None else '—'}  FPS={st.get('fps', 60)}",
                    f"最近一次刷新: {lr if lr else '—'}",
                    f"说明: {game.get('message', '')}",
                ]
            )
        )
        self._render_table(st.get("items") or [])
        self._rendered_slow_version = version

    def _render_table(self, items: list[dict]) -> None:
        signature = tuple(
            (
                it.get("row_name", ""),
                it.get("range_text", "") or "—",
                it.get("phase", ""),
                it.get("until_start_text", "—"),
                it.get("until_end_text", "—"),
                (it.get("note") or "")[:120],
            )
            for it in items
        )
        if signature == self._last_list_signature:
            return
        self.table.setRowCount(len(items))
        for i, it in enumerate(items):
            phase = it.get("phase", "")
            phase_zh = {"active": "进行中", "upcoming": "未开始", "past": "已结束", "unknown": "未知"}.get(phase, phase)
            values = [
                it.get("row_name", ""),
                it.get("range_text", "") or "—",
                phase_zh,
                f"{it.get('until_start_text', '—')} / {it.get('until_end_text', '—')}",
                (it.get("note") or "")[:120],
            ]
            for c, v in enumerate(values):
                cell = self.table.item(i, c)
                if cell is None:
                    cell = QTableWidgetItem()
                    self.table.setItem(i, c, cell)
                cell.setText(str(v))
                if phase == "active":
                    cell.setBackground(QColor("#1a3d5c"))
                elif phase == "past":
                    cell.setBackground(QColor("#2d2d2d"))
                    cell.setForeground(QColor("#777777"))
                else:
                    cell.setBackground(QColor("#2d2d2d"))
                    cell.setForeground(QColor("#e8e8e8"))
        active_indices = [idx for idx, it in enumerate(items) if it.get("phase") == "active"]
        target = active_indices[-1] if active_indices else 0
        if target != self._last_scroll_target_index and self.table.rowCount() > 0:
            self.table.scrollToItem(self.table.item(target, 0), QTableWidget.PositionAtTop)
            self._last_scroll_target_index = target
        self._last_list_signature = signature


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def main() -> None:
    # Set Windows AppUserModelID so the taskbar uses our icon instead of the default Python/Windows icon.
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ArknightsTimeline")

    if sys.platform == "win32" and not _is_admin():
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        sys.exit()

    app = QApplication.instance() or QApplication(sys.argv)

    # Set application icon (window title bar + taskbar).
    icon_path = _REPO_ROOT / "aaa.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    win = CoachWindow()
    win.show()
    app.exec()


if __name__ == "__main__":
    main()
