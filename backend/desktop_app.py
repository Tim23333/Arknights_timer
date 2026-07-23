"""
明日方舟游戏数据显示工具 — 独立桌面程序（PySide6）。
读取游戏时间与帧（tools/timer 内存方案）；通过 tools/enemy_health
实时展示关卡内敌人数据（名称/血量/坐标/属性）。
"""
from __future__ import annotations

import asyncio
import ctypes
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# 保证可导入 app.services 与 tools/*（从 backend 目录运行），并兼容 PyInstaller 冻结路径。
if getattr(sys, "frozen", False):
    _RUNTIME_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    _BACKEND_ROOT = _RUNTIME_ROOT / "backend"
    _REPO_ROOT = _RUNTIME_ROOT
else:
    _BACKEND_ROOT = Path(__file__).resolve().parent
    _REPO_ROOT = _BACKEND_ROOT.parent
for _p in (str(_BACKEND_ROOT), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.services.timer_provider import TimerDataProvider
from tools.enemy_health import EnemyReader, format_skill_cd
from tools.enemy_health import game_structs as enemy_gs

# 测试版检测: build_exe.py --test 打包时内嵌 TEST_BUILD 标记文件
# (开发调试可设环境变量 AK_TEST_BUILD=1)。测试版带控制台窗口,
# 全部内部日志实时输出到控制台, 用于现场排查 (如换机扫描失败)。
TEST_BUILD = os.environ.get("AK_TEST_BUILD") == "1" or (
    getattr(sys, "frozen", False)
    and (Path(getattr(sys, "_MEIPASS", ".")) / "TEST_BUILD").is_file())


def _tlog(*a) -> None:
    """测试版控制台日志 (正式版为空操作, 开销可忽略)"""
    if TEST_BUILD:
        print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)

AUTO_REFRESH_MS = 8
FAST_UI_MS = 8
SLOW_UI_MS = 150
WS_PUSH_MS = 8
ENEMY_POLL_SEC = 0.01      # 敌人轮询间隔 (memsrv 通道单帧 <1ms, 2倍速 60fps=16.7ms)
ENEMY_RENDER_SEC = 0.016   # 表格渲染节流 (60fps)

ENEMY_COLS = ['#', '名称', '编号', '敌人ID', '血量', '坐标',
              '攻击', '防御', '法抗', '移速', '攻速', '技能 CD', '状态']
ENEMY_STATE_NAMES = {0: 'NONE', 1: 'INITED', 2: '战斗中', 3: '已结束'}

# 支持自定义小数位的数值列 (key, 显示名)
ENEMY_DEC_COLS = [('hp', '血量'), ('pos', '坐标'), ('atk', '攻击'), ('def', '防御'),
                  ('res', '法抗'), ('mspd', '移速'), ('aspd', '攻速'), ('skill', '技能CD')]


class EnemyPrecisionDialog(QDialog):
    """每列小数位数设置 (0-6)"""

    def __init__(self, parent, dec: dict) -> None:
        super().__init__(parent)
        self.setWindowTitle('小数位设置')
        form = QFormLayout(self)
        self.spins: dict = {}
        for k, label in ENEMY_DEC_COLS:
            s = QSpinBox()
            s.setRange(0, 6)
            s.setValue(dec.get(k, 4))
            s.setSuffix(' 位')
            form.addRow(f'{label}:', s)
            self.spins[k] = s
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def values(self) -> dict:
        return {k: s.value() for k, s in self.spins.items()}


def _format_game_time(value: object) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.3f}s"
    except (TypeError, ValueError):
        return str(value)


class EnemyScanWorker(QThread):
    """后台线程: 连接 + 全堆扫描定位敌人列表"""
    log = Signal(str)
    progress = Signal(int, str)
    done = Signal(bool, str)

    def __init__(self, reader: EnemyReader, force: bool = True) -> None:
        super().__init__()
        self.reader = reader
        self.force = force

    def run(self) -> None:
        try:
            if TEST_BUILD:   # 测试版: 日志同时进 GUI 标签和控制台
                self.reader.log = lambda m: (self.log.emit(str(m)), _tlog(m))
            else:
                self.reader.log = lambda m: self.log.emit(str(m))
            self.reader.progress = lambda pct, desc: self.progress.emit(int(pct), str(desc))
            if TEST_BUILD:   # 换机扫描失败排查: 先输出 adb 链路诊断
                mc = self.reader.mc
                _tlog("诊断 adb_path =", mc.adb_path)
                try:
                    _tlog("诊断 adb devices:",
                          mc.adb("devices", timeout=10).decode(errors="replace").strip().replace("\r", "").replace("\n", " | "))
                    _tlog("诊断 adb root:", mc.adb("root", timeout=10).decode(errors="replace").strip())
                    _tlog("诊断 pidof:", mc.shell(f"pidof {mc.package}", timeout=10).strip() or "(空, 游戏未运行?)")
                except Exception as ex:
                    _tlog("诊断 adb 检查失败:", f"{type(ex).__name__}: {ex}")
            pid = self.reader.connect()
            self.log.emit(f"游戏 PID = {pid}")
            ok = self.reader.bootstrap(force=self.force)
            if ok:
                self.done.emit(True, f"定位完成, 敌人 {len(self.reader.enemy_addrs)} 个")
            else:
                self.done.emit(False, "定位失败: 请确认已进入关卡且场上有敌人")
        except Exception as e:
            self.done.emit(False, f"出错: {e}")


class EnemyPollWorker(QThread):
    """后台线程: 常驻通道准实时轮询敌人数据"""
    snapshot = Signal(dict)

    def __init__(self, reader: EnemyReader, interval: float = ENEMY_POLL_SEC) -> None:
        super().__init__()
        self.reader = reader
        self.interval = interval

    def run(self) -> None:
        # Windows 默认睡眠粒度 15.6ms, 提到 1ms 才能睡出 <16ms 的轮询间隔
        winmm = getattr(ctypes.windll, 'winmm', None) if sys.platform == 'win32' else None
        if winmm:
            winmm.timeBeginPeriod(1)
        try:
            while not self.isInterruptionRequested():
                t0 = time.time()
                try:
                    snap = self.reader.poll_fast()
                except Exception as e:
                    snap = {'ok': False, 'state': -1, 'speed_level': -1, 'time_scale': 0.0,
                            'play_time': 0.0, 'enemies': [], 'msg': f'轮询出错: {e}'}
                self.snapshot.emit(snap)
                dt = time.time() - t0
                wait = max(0.001, self.interval - dt)
                self.msleep(int(wait * 1000))
        finally:
            if winmm:
                winmm.timeEndPeriod(1)


class CoachWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("明日方舟游戏数据显示工具" + (" [测试版]" if TEST_BUILD else ""))
        self.resize(1180, 760)
        self.setMinimumSize(900, 560)

        self._provider = TimerDataProvider()
        self._stop_event = threading.Event()

        self._hook_port: int = 0
        self._ws_port: int = 0
        self._ws_clients: set = set()
        self._ws_loop: asyncio.AbstractEventLoop | None = None

        # 敌人数据
        self._enemy_reader = EnemyReader(log=_tlog)   # 测试版日志进控制台, 正式版空操作
        self._enemy_scan: EnemyScanWorker | None = None
        self._enemy_poll: EnemyPollWorker | None = None
        self._enemy_last_render = 0.0
        self._enemy_rows: dict = {}    # enemy addr -> 表格行号 (行位置稳定, 新敌人底部新增)
        self._bar_colors: dict = {}    # enemy addr -> 当前血条颜色
        self._skill_lines: dict = {}   # enemy addr -> 技能格行数 (变化才调整行高)
        self._enemy_dec: dict = {k: 4 for k, _ in ENEMY_DEC_COLS}   # 每列小数位数 (0-6)
        self._enemy_last: list = []    # 最近一帧敌人 (改小数位时立即重绘用)
        self._frame_txt: str = ''      # ms/帧 显示 (0.5s 节流, 避免高频抖动)
        self._frame_ts: float = 0.0
        self._widths_fitted: bool = False   # 首次有数据时已做过列宽自适应

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
        title = QLabel("明日方舟游戏数据显示工具 · 桌面版 Made by Tim(321346659)")
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
        sub = QLabel("寻址工具读取游戏时间/逻辑帧；进入关卡后点「开始扫描」实时展示敌人数据。")
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

        # ---- 游戏时间 & 逻辑帧 ----
        box_game = QGroupBox("游戏状态")
        l_game = QHBoxLayout(box_game)
        l_game.setContentsMargins(4, 4, 4, 4)
        l_game.setSpacing(10)

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
        l_game.addWidget(card_time_disp, 1)

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
        l_game.addWidget(card_frame_disp, 1)

        self.lbl_game = QLabel("正在等待实时刷新…")
        self.lbl_game.setWordWrap(True)
        self.lbl_game.setStyleSheet("color:#9a9a9a; font-size:11px;")
        l_game.addWidget(self.lbl_game, 1)
        main.addWidget(box_game)

        # ---- 敌人数据控制 ----
        box_enemy = QGroupBox("敌人数据（tools/enemy_health）")
        l_enemy = QVBoxLayout(box_enemy)
        row_btn = QHBoxLayout()
        self.btn_enemy_scan = QPushButton("开始扫描")
        self.btn_enemy_scan.setToolTip("全堆扫描定位敌人列表 (进关卡且场上有敌人后点击, 约 1-3 分钟)")
        self.btn_enemy_scan.clicked.connect(self._on_enemy_scan)
        self._style_primary_button(self.btn_enemy_scan)
        self.btn_enemy_stop = QPushButton("停止监控")
        self.btn_enemy_stop.setEnabled(False)
        self.btn_enemy_stop.clicked.connect(self._stop_enemy_poll)
        self._style_muted_button(self.btn_enemy_stop)
        self.enemy_progress = QProgressBar()
        self.enemy_progress.setRange(0, 100)
        self.enemy_progress.setValue(0)
        self.enemy_progress.setTextVisible(True)
        self.enemy_progress.setFormat('就绪')
        self.btn_enemy_precision = QPushButton("小数位设置")
        self.btn_enemy_precision.setToolTip("分别设置每一列数值的小数位数 (0-6)")
        self.btn_enemy_precision.clicked.connect(self._on_enemy_precision)
        self._style_muted_button(self.btn_enemy_precision)
        self.btn_enemy_fit = QPushButton("列宽自适应")
        self.btn_enemy_fit.setToolTip("按内容自动调整所有列宽 (也可直接拖动表头分隔线手动调整)")
        self.btn_enemy_fit.clicked.connect(lambda: self.enemy_table.resizeColumnsToContents())
        self._style_muted_button(self.btn_enemy_fit)
        row_btn.addWidget(self.btn_enemy_scan)
        row_btn.addWidget(self.btn_enemy_stop)
        row_btn.addWidget(self.btn_enemy_precision)
        row_btn.addWidget(self.btn_enemy_fit)
        row_btn.addWidget(self.enemy_progress, 1)
        l_enemy.addLayout(row_btn)
        self.lbl_enemy_status = QLabel("未开始扫描")
        self.lbl_enemy_status.setStyleSheet("color:#9a9a9a;")
        l_enemy.addWidget(self.lbl_enemy_status)
        main.addWidget(box_enemy)

        # ---- 底部: 敌人信息表 ----
        box_table = QGroupBox("敌人信息")
        l_table = QVBoxLayout(box_table)
        self.enemy_table = QTableWidget(0, len(ENEMY_COLS))
        self.enemy_table.setHorizontalHeaderLabels(ENEMY_COLS)
        self.enemy_table.verticalHeader().setVisible(False)
        self.enemy_table.setSelectionMode(QTableWidget.NoSelection)
        self.enemy_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.enemy_table.setAlternatingRowColors(True)
        hdr = self.enemy_table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)   # 列宽可拖动调整
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)   # 名称
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)   # 血量条
        l_table.addWidget(self.enemy_table)
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

    def _start_timers(self) -> None:
        self.t_fast = QTimer(self)
        self.t_fast.timeout.connect(self._tick_fast)
        self.t_fast.start(FAST_UI_MS)
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

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._stop_event.set()
        self._stop_enemy_poll()
        self._enemy_reader.close()
        if self._ws_clients:
            for ws in list(self._ws_clients):
                try:
                    asyncio.run_coroutine_threadsafe(ws.close(), self._ws_loop)
                except Exception:
                    pass
        return super().closeEvent(event)

    def _on_open_timer_tool(self) -> None:
        try:
            env = os.environ.copy()
            env["AK_HOOK_PORT"] = str(self._hook_port)

            if getattr(sys, "frozen", False):
                # 打包后：从内嵌资源中提取并运行寻址工具
                import tempfile
                import shutil

                # 内嵌的寻址工具路径（PyInstaller 解压后的临时目录）
                embedded_exe = Path(sys._MEIPASS) / "tools" / "AKTimerTool.exe"
                if not embedded_exe.is_file():
                    QMessageBox.critical(
                        self,
                        "寻址工具",
                        f"未找到内嵌的寻址工具：\n{embedded_exe}\n\n"
                        "请重新打包程序。"
                    )
                    return

                # 提取到用户临时目录（避免重复提取）
                temp_dir = Path(tempfile.gettempdir()) / "ArknightsTimeline"
                temp_dir.mkdir(exist_ok=True)
                temp_exe = temp_dir / "AKTimerTool.exe"

                # 如果临时文件不存在或大小不同，则提取
                if not temp_exe.exists() or temp_exe.stat().st_size != embedded_exe.stat().st_size:
                    shutil.copy2(embedded_exe, temp_exe)
                    print(f"[INFO] 已提取寻址工具到: {temp_exe}")

                cmd = [str(temp_exe)]
                subprocess.Popen(cmd, env=env)
            else:
                # 开发模式：直接调用 Python 脚本
                script = _REPO_ROOT / "tools" / "timer" / "ak_timer_ui.py"
                if not script.is_file():
                    QMessageBox.critical(self, "寻址工具", f"未找到脚本：\n{script}")
                    return
                cmd = [sys.executable, str(script)]
                subprocess.Popen(cmd, cwd=str(script.parent), env=env, close_fds=sys.platform != "win32")
        except OSError as e:
            QMessageBox.critical(self, "寻址工具", f"无法启动：{e}")

    def _on_refresh_game(self) -> None:
        res = self._provider.refresh_sample()
        if not res.get("ok"):
            QMessageBox.warning(self, "游戏状态", res.get("message", "刷新失败"))

    # ================= 敌人数据 =================

    def _ensure_adb(self) -> bool:
        """扫描前确保 adb 可用; 找不到时弹框让用户手动选择并持久化"""
        mc = self._enemy_reader.mc
        if mc.adb_path and os.path.isfile(mc.adb_path):
            return True
        QMessageBox.information(
            self, "需要 adb",
            "未找到 adb.exe。\n\n"
            "请选择 MuMu 模拟器安装目录下的 shell\\adb.exe，例如：\n"
            "D:\\Program Files\\MuMu9\\emulator\\MuMuPlayer-12.0\\shell\\adb.exe")
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 adb.exe", "", "adb (adb.exe);;所有文件 (*)")
        if path and os.path.isfile(path):
            mc.adb_path = path
            from tools.enemy_health.memcore import save_adb_path
            save_adb_path(path)
            return True
        return False

    def _on_enemy_scan(self) -> None:
        if not self._ensure_adb():
            self.lbl_enemy_status.setText('状态: 未选择 adb.exe, 取消扫描')
            return
        self._stop_enemy_poll()
        self.enemy_table.setRowCount(0)   # 换关卡重扫: 清掉旧敌人行
        self._enemy_rows.clear()
        self._bar_colors.clear()
        self._skill_lines.clear()
        self.btn_enemy_scan.setEnabled(False)
        self.enemy_progress.setValue(0)
        self.enemy_progress.setFormat('开始全堆扫描 ... %p%')
        self._enemy_scan = EnemyScanWorker(self._enemy_reader, force=True)
        self._enemy_scan.log.connect(self._on_enemy_log)
        self._enemy_scan.progress.connect(self._on_enemy_progress)
        self._enemy_scan.done.connect(self._on_enemy_scan_done)
        self._enemy_scan.start()

    def _on_enemy_log(self, msg: str) -> None:
        msg = msg.strip()
        if msg:
            self.lbl_enemy_status.setText(msg)

    def _on_enemy_progress(self, pct: int, desc: str) -> None:
        self.enemy_progress.setValue(pct)
        self.enemy_progress.setFormat(f'{desc} %p%')

    def _on_enemy_scan_done(self, ok: bool, msg: str) -> None:
        self.lbl_enemy_status.setText(msg)
        self.btn_enemy_scan.setEnabled(True)
        self.btn_enemy_scan.setText('重新扫描')
        if ok:
            self.enemy_progress.setValue(100)
            self.enemy_progress.setFormat('就绪')
            self._start_enemy_poll()
        else:
            self.enemy_progress.setFormat('定位失败')

    def _start_enemy_poll(self) -> None:
        self._stop_enemy_poll()
        self._enemy_poll = EnemyPollWorker(self._enemy_reader)
        self._enemy_poll.snapshot.connect(self._on_enemy_snapshot)
        self._enemy_poll.start()
        self.btn_enemy_stop.setEnabled(True)
        self.lbl_enemy_status.setText('实时监控中 ...')

    def _stop_enemy_poll(self) -> None:
        if self._enemy_poll:
            self._enemy_poll.requestInterruption()
            self._enemy_poll.wait(3000)
            self._enemy_poll = None
        self.btn_enemy_stop.setEnabled(False)

    def _on_enemy_snapshot(self, snap: dict) -> None:
        if TEST_BUILD:   # 轮询错误 (数据链失效/重建) 去重后输出控制台
            msg = snap.get('msg')
            if msg and msg != getattr(self, '_last_snap_msg', None):
                self._last_snap_msg = msg
                _tlog("轮询:", msg)
        # 渲染节流: 轮询 33ms, 渲染 30fps
        now = time.time()
        if snap.get('ok') and now - self._enemy_last_render < ENEMY_RENDER_SEC:
            return
        self._enemy_last_render = now
        st = ENEMY_STATE_NAMES.get(snap['state'], '?') if snap['state'] >= 0 else '-'
        spd = enemy_gs.SpeedLevel.NAMES.get(snap['speed_level'], '?') if snap['speed_level'] >= 0 else '-'
        t = int(snap['play_time'])
        if now - self._frame_ts >= 0.5:   # ms/帧 0.5s 节流, 避免高频刷新抖动
            self._frame_ts = now
            self._frame_txt = f"   {snap['frame_ms']:.0f}ms/帧" if snap.get('frame_ms') else ''
        text = (f"状态: {st}   倍速: {spd} (x{snap['time_scale']:g})   "
                f"战斗时间: {t // 60:02d}:{t % 60:02d}   敌人数: {len(snap['enemies'])}"
                + self._frame_txt)
        if snap.get('msg'):
            text += f"   ({snap['msg']})"
        self.lbl_enemy_status.setText(text)
        self._render_enemy_table(snap['enemies'])

    def _render_enemy_table(self, enemies) -> None:
        self._enemy_last = enemies
        tbl = self.enemy_table
        if enemies and not self._widths_fitted:
            self._widths_fitted = True
            tbl.resizeColumnsToContents()   # 首次有数据时自适应一次, 之后交用户手调
        # 增量刷新: 按敌人地址锚定行, 已有行原地更新, 新敌人底部新增,
        # 消失的行才删除——杜绝整表重建导致的闪烁
        tbl.setUpdatesEnabled(False)
        try:
            seen = set()
            for e in enemies:
                seen.add(e.addr)
                row = self._enemy_rows.get(e.addr)
                if row is None:
                    row = tbl.rowCount()
                    tbl.insertRow(row)
                    self._make_enemy_row(row, e.addr)
                    self._enemy_rows[e.addr] = row
                self._update_enemy_row(row, e)
            gone = [a for a in self._enemy_rows if a not in seen]
            for a in sorted(gone, key=lambda a: -self._enemy_rows[a]):
                tbl.removeRow(self._enemy_rows.pop(a))
                self._bar_colors.pop(a, None)
                self._skill_lines.pop(a, None)
            if gone:   # removeRow 后行号位移, 依 item(0) 存的 addr 重建映射
                self._enemy_rows = {tbl.item(r, 0).data(Qt.UserRole): r
                                    for r in range(tbl.rowCount())}
        finally:
            tbl.setUpdatesEnabled(True)

    def _on_enemy_precision(self) -> None:
        dlg = EnemyPrecisionDialog(self, self._enemy_dec)
        if dlg.exec() == QDialog.Accepted:
            self._enemy_dec = dlg.values()
            self._render_enemy_table(self._enemy_last)   # 立即按新精度重绘

    def _make_enemy_row(self, row: int, addr: int) -> None:
        tbl = self.enemy_table
        for c in range(len(ENEMY_COLS)):
            if c != 4:
                it = QTableWidgetItem()
                it.setTextAlignment(Qt.AlignCenter)
                tbl.setItem(row, c, it)
        tbl.item(row, 0).setData(Qt.UserRole, addr)
        tbl.item(row, 1).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        tbl.item(row, 3).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        tbl.item(row, 11).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        bar = QProgressBar()
        bar.setTextVisible(True)
        tbl.setCellWidget(row, 4, bar)

    def _update_enemy_row(self, row: int, e) -> None:
        tbl = self.enemy_table
        d = self._enemy_dec

        def setc(c, text, grey=False):
            it = tbl.item(row, c)
            it.setText(str(text))
            if grey:
                it.setForeground(QColor('#888888'))

        setc(0, row)
        setc(1, e.name or e.eid or '?')
        setc(2, e.code or '-')
        setc(3, e.eid)

        bar = tbl.cellWidget(row, 4)
        mx = max(1, int(e.max_hp))
        bar.setMaximum(mx)
        bar.setValue(max(0, int(e.hp)))
        bar.setFormat(f'{e.hp:.{d["hp"]}f} / {e.max_hp:.{d["hp"]}f}  %p%')
        ratio = e.hp / e.max_hp if e.max_hp > 0 else 0
        color = '#5cb85c' if ratio > 0.5 else ('#f0ad4e' if ratio > 0.2 else '#d9534f')
        if not e.alive:
            color = '#888888'
        if self._bar_colors.get(e.addr) != color:   # 颜色变化才重设样式 (触发重排版)
            self._bar_colors[e.addr] = color
            bar.setStyleSheet(f'QProgressBar::chunk {{ background-color: {color}; }}')

        setc(5, f'({e.pos_x:.{d["pos"]}f}, {e.pos_y:.{d["pos"]}f})')
        setc(6, f'{e.atk:.{d["atk"]}f}')
        setc(7, f'{e.def_:.{d["def"]}f}')
        setc(8, f'{e.res:.{d["res"]}f}')
        setc(9, f'{e.mspd:.{d["mspd"]}f}')
        setc(10, f'{e.aspd:.{d["aspd"]}f}')
        cd_text = format_skill_cd(e.skills, sep='\n', prec=d['skill'])
        setc(11, cd_text)
        n_lines = cd_text.count('\n')          # 行数变化才重排行高 (重排会触发布局)
        if self._skill_lines.get(e.addr) != n_lines:
            self._skill_lines[e.addr] = n_lines
            tbl.resizeRowToContents(row)
        setc(12, '存活' if e.alive else ('退场' if e.finish else '阵亡'), grey=not e.alive)

    # ================= 定时刷新 =================

    def _tick_fast(self) -> None:
        game = self._provider.get_game_data()
        self.lbl_game_time_big.setText(_format_game_time(game.get("game_time")))
        fc = game.get("frame_count")
        self.lbl_frame_big.setText(f"F{int(fc)}" if fc is not None else "—")

    def _tick_slow(self) -> None:
        game = self._provider.get_game_data()
        lr = game.get("last_refresh")
        self.lbl_game.setText(
            "\n".join(
                [
                    f"连接: {'是' if game.get('connected') else '否'}  |  已配置地址: {'是' if game.get('configured') else '否'}",
                    f"最近一次刷新: {lr if lr else '—'}",
                    f"说明: {game.get('message', '')}",
                ]
            )
        )


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

    if TEST_BUILD:
        import faulthandler
        import traceback
        faulthandler.enable()

        def _thread_hook(args):
            print(f"!!! 线程 {args.thread.name if args.thread else '?'} 未捕获异常:", flush=True)
            traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback)
        threading.excepthook = _thread_hook
        _tlog("========== 测试版 (控制台实时日志) ==========")
        _tlog("frozen:", getattr(sys, "frozen", False), "| exe:", sys.executable)
        _tlog("工作目录:", os.getcwd(), "| 管理员权限:", _is_admin())
        try:
            from tools.enemy_health.memcore import find_mumu_adb
            _tlog("adb 探测:", find_mumu_adb() or "(未找到)")
        except Exception as e:
            _tlog("adb 探测异常:", e)

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
