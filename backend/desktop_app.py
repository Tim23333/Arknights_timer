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

from PySide6.QtCore import QSettings, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
from tools.enemy_health import EnemyReader
from tools.enemy_health import game_structs as enemy_gs
from tools.enemy_health.memcore import (
    MemCore, find_running_emulator_adbs, save_adb_path,
)
from app.enemy_ui import (
    ENEMY_COLUMN_DEFS, ENEMY_COLUMN_INDEX, EnemyColumnDialog, EnemyDetailDialog,
    EnemyPrecisionDialog, default_precision_values, format_column_value,
    load_visible_columns, save_visible_columns, visible_enemy_rows,
)
from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader

# tools/ak_live_rng 为扁平模块结构 (无 __init__.py), 将其目录加入 sys.path 按文件导入;
# 打包时 tools/ 已整体作为数据文件内嵌 (_MEIPASS/tools/ak_live_rng/*.py), 冻结下同样可导入。
_rng_dir = str(_REPO_ROOT / 'tools' / 'ak_live_rng')
if _rng_dir not in sys.path:
    sys.path.insert(0, _rng_dir)
try:
    from rng_service import RngService
except Exception:   # 模块缺失时禁用随机数区块, 不影响其他功能
    RngService = None

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
ENEMY_DETAIL_FULL_SEC = 0.05  # Buff/关卡效果独立通道约 20Hz；动态数据随主表每帧刷新

ENEMY_COLS = [col['label'] for col in ENEMY_COLUMN_DEFS]
ENEMY_COL_WIDTHS = [col['width'] for col in ENEMY_COLUMN_DEFS]
ENEMY_STATE_NAMES = {0: 'NONE', 1: 'INITED', 2: '战斗中', 3: '已结束'}


def probe_adb_executable(path: str) -> tuple[bool, str]:
    """验证用户选择的是可运行的 adb；参数列表调用可正确处理空格和中文路径。"""
    path = os.path.normpath(path or '')
    if not path or not os.path.isfile(path):
        return False, '所选文件不存在'
    try:
        result = subprocess.run(
            [path, 'version'], capture_output=True, text=True, errors='replace',
            timeout=8,
            creationflags=(getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                           if os.name == 'nt' else 0),
        )
    except subprocess.TimeoutExpired:
        return False, '执行 adb version 超时'
    except OSError as exc:
        return False, f'无法运行所选文件：{exc}'
    output = '\n'.join(
        part.strip() for part in (result.stdout, result.stderr) if part.strip())
    if result.returncode != 0:
        return False, output.splitlines()[0] if output else f'退出码 {result.returncode}'
    return True, output.splitlines()[0] if output else 'ADB 可执行文件验证通过'


class AdbSelectionDialog(QDialog):
    """手动浏览或按运行中模拟器进程自动定位 adb.exe。"""

    def __init__(self, parent=None, current_path: str = '') -> None:
        super().__init__(parent)
        self.setWindowTitle('选择 ADB')
        self.setMinimumWidth(700)
        self.probe_detail = ''

        layout = QVBoxLayout(self)
        intro = QLabel(
            '选择模拟器自带的 adb.exe。也可以先启动模拟器，再点击“自动探测运行中模拟器”。')
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.path_combo = QComboBox()
        self.path_combo.setEditable(True)
        self.path_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.path_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        line_edit = self.path_combo.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText('请选择或输入 adb.exe 的完整路径')
            line_edit.setClearButtonEnabled(True)
        if current_path:
            self.path_combo.addItem(os.path.normpath(current_path))
        layout.addWidget(self.path_combo)

        action_row = QHBoxLayout()
        browse = QPushButton('浏览 adb.exe…')
        browse.clicked.connect(self._browse)
        action_row.addWidget(browse)
        self.btn_auto_detect = QPushButton('自动探测运行中模拟器')
        self.btn_auto_detect.clicked.connect(self._auto_detect)
        action_row.addWidget(self.btn_auto_detect)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.status = QLabel('')
        self.status.setWordWrap(True)
        self.status.setStyleSheet('color:#9a9a9a;')
        layout.addWidget(self.status)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('使用此 ADB')
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_path(self) -> str:
        return os.path.normpath(self.path_combo.currentText().strip())

    def _browse(self) -> None:
        current = self.selected_path()
        start_dir = os.path.dirname(current) if os.path.isfile(current) else ''
        path, _ = QFileDialog.getOpenFileName(
            self, '选择 adb.exe', start_dir,
            'ADB 程序 (adb.exe);;可执行文件 (*.exe);;所有文件 (*)')
        if path:
            self.path_combo.setCurrentText(os.path.normpath(path))
            self.status.setText('已选择文件，点击“使用此 ADB”完成验证。')

    def _auto_detect(self) -> None:
        self.btn_auto_detect.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            detected = find_running_emulator_adbs()
            usable = []
            details = []
            for item in detected:
                path = item['adb_path']
                ok, detail = probe_adb_executable(path)
                if ok:
                    usable.append(path)
                    details.append(
                        f"{item['process_name']} → {path}（{detail}）")
            if not usable:
                self.status.setStyleSheet('color:#d07a7a;')
                self.status.setText(
                    '未从运行进程中找到可用 ADB。请确认模拟器已完全启动，或使用“浏览 adb.exe…”。')
                return
            current = self.selected_path()
            self.path_combo.clear()
            for path in usable:
                self.path_combo.addItem(path)
            if current in usable:
                self.path_combo.setCurrentText(current)
            self.status.setStyleSheet('color:#58a66a;')
            self.status.setText(
                f'已发现 {len(usable)} 个可用 ADB：\n' + '\n'.join(details))
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_auto_detect.setEnabled(True)

    def _validate_and_accept(self) -> None:
        path = self.selected_path()
        ok, detail = probe_adb_executable(path)
        if not ok:
            QMessageBox.warning(
                self, 'ADB 不可用', f'所选文件未通过验证：\n{path}\n\n{detail}')
            return
        self.probe_detail = detail
        super().accept()

def _format_game_time(value: object) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.3f}s"
    except (TypeError, ValueError):
        return str(value)


class EnemyScanWorker(QThread):
    """后台线程：定位当前关卡、出怪计划和实时敌人列表。"""
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
                self.done.emit(
                    True,
                    f"定位完成，预定敌人 {self.reader.planned_count} 个，"
                    f"当前注册实例 {len(self.reader.enemy_addrs)} 个（场上数随后实时判定）")
            else:
                self.done.emit(False, "定位失败：请确认明日方舟已进入战斗关卡")
        except Exception as e:
            self.done.emit(False, f"出错: {e}")


class EnemyPollWorker(QThread):
    """后台线程: 常驻通道准实时轮询敌人数据"""
    snapshot = Signal(dict)

    def __init__(self, reader: EnemyReader, interval: float = ENEMY_POLL_SEC) -> None:
        super().__init__()
        self.reader = reader
        self.interval = interval
        self._detail_lock = threading.Lock()
        self._detail_addr = 0
        self._detail_due = 0.0
        self._detail_heavy_cache = None
        self._detail_loading = False
        self._detail_error = ''

    def set_detail_target(self, addr: int = 0) -> None:
        """选择需要完整实时详情的敌人；0 表示停止详情读取。"""
        with self._detail_lock:
            addr = int(addr or 0)
            if addr != self._detail_addr:
                self._detail_addr = addr
                self._detail_due = 0.0
                self._detail_heavy_cache = None
                self._detail_error = ''

    def _start_detail_refresh(self, addr: int) -> None:
        with self._detail_lock:
            if self._detail_loading or addr != self._detail_addr:
                return
            self._detail_loading = True

        def load() -> None:
            cache = None
            error = ''
            try:
                full = self.reader.read_enemy_detail(addr, heavy_only=True)
                if full is not None:
                    cache = {
                        'raw_attributes': dict(full.raw_attributes),
                        'buffs': list(full.buffs),
                        'global_buffs': list(full.global_buffs),
                    }
                else:
                    error = '敌人详情对象已失效。'
            except Exception as exc:
                error = f'详情刷新失败：{exc}'
            finally:
                with self._detail_lock:
                    if addr == self._detail_addr:
                        if cache is not None:
                            self._detail_heavy_cache = cache
                            self._detail_error = ''
                        elif error:
                            self._detail_error = error
                        self._detail_due = time.monotonic() + ENEMY_DETAIL_FULL_SEC
                    self._detail_loading = False

        threading.Thread(
            target=load, name='EnemyDetailRefresh', daemon=True).start()

    def _append_detail(self, snap: dict) -> None:
        now = time.monotonic()
        with self._detail_lock:
            addr = self._detail_addr
            due = self._detail_due
        if not addr:
            return
        if not snap.get('ok'):
            return

        # 只跟踪当前敌人列表中的同一实例；退场后保留最后一帧并给详情页提示。
        roster_enemy = next((enemy for enemy in snap.get('enemies', ())
                             if getattr(enemy, 'addr', 0) == addr
                             and getattr(enemy, 'lifecycle', 'active') == 'active'), None)
        live = roster_enemy is not None
        if not live:
            snap['detail_enemy'] = None
            snap['detail_error'] = '敌人已退场或对象已失效，已停止更新。'
            return
        # 重型数据由独立线程+独立 27274 通道读取，主轮询从不等待它。
        if now >= due:
            self._start_detail_refresh(addr)
        with self._detail_lock:
            heavy = dict(self._detail_heavy_cache or {})
            error = self._detail_error
        roster_enemy.raw_attributes = dict(heavy.get('raw_attributes', {}))
        roster_enemy.buffs = list(heavy.get('buffs', ()))
        roster_enemy.global_buffs = list(heavy.get('global_buffs', ()))
        snap['detail_enemy'] = roster_enemy
        if error:
            snap['detail_error'] = error

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
                self._append_detail(snap)
                self.snapshot.emit(snap)
                dt = time.time() - t0
                wait = max(0.001, self.interval - dt)
                self.msleep(int(wait * 1000))
        finally:
            if winmm:
                winmm.timeEndPeriod(1)


RNG_PREDICT_LEN = 30    # 未来预测默认发数 (界面可改, 1-500)
RNG_HISTORY_LEN = 18    # 最近消耗展示条数
RNG_UI_MS = 150         # 快照刷新间隔 (服务自带 5ms 轮询线程, UI 只读快照)

DEPLOY_COLS = ['时间', '逻辑帧', '操作', '干员', '朝向', '位置', '附加信息']
DEPLOY_COL_WIDTHS = [80, 75, 60, 120, 50, 80, 120]
DEPLOY_POLL_SEC = 0.3   # 操作记录轮询间隔 (memsrv 批量读每次仅数 ms)
DEPLOY_OP_CN = {0: '部署', 1: '撤退', 2: '技能', 3: 'CHEAT'}
DEPLOY_DIR_CN = {0: '上', 1: '右', 2: '下', 3: '左', 4: '-'}


class DeployScanWorker(QThread):
    """后台线程: 先定位关卡信息，再定位 BattleLogger；不阻塞 UI。"""
    log = Signal(str)
    stage = Signal(dict)       # 阶段 1 完成即发出，不等待操作链
    done = Signal(object, str)   # (DeployTrackerReader|None, 错误消息)

    def __init__(self, adb_path: str) -> None:
        super().__init__()
        self.adb_path = adb_path

    def run(self) -> None:
        try:
            mc = MemCore(adb_path=self.adb_path)
            pid = mc.connect()
            self.log.emit(f"游戏 PID = {pid}")
            reader = DeployTrackerReader(mc)
            reader.set_status_callback(lambda m: (self.log.emit(str(m)), _tlog('[部署]', m)))
            reader.set_stage_callback(lambda info: self.stage.emit(dict(info)))
            if reader.locate():
                self.done.emit(reader, '')
            else:
                suffix = ('；关卡信息已获取，但操作记录定位失败'
                          if reader.get_stage_info() else '')
                self.done.emit(None, f'定位失败: 请确认已进入作战关卡{suffix}')
        except Exception as e:
            self.done.emit(None, f'出错: {e}')


class DeployPollWorker(QThread):
    """后台线程: 准实时轮询操作日志 (BattleLogger.m_logs)"""
    snapshot = Signal(list, dict, bool)   # events, battle_state, chain_ok

    def __init__(self, reader: DeployTrackerReader, interval: float = DEPLOY_POLL_SEC) -> None:
        super().__init__()
        self.reader = reader
        self.interval = interval

    def run(self) -> None:
        while not self.isInterruptionRequested():
            try:
                ok = self.reader.is_chain_valid()
                events = self.reader.get_events() if ok else []
                battle = self.reader.get_battle_state() if ok else {}
                self.snapshot.emit(events, battle, ok)
            except Exception:
                self.snapshot.emit([], {}, True)   # 偶发读失败不判死, 下轮重试
            self.msleep(int(self.interval * 1000))


class RngScanWorker(QThread):
    """后台线程: attach + 扫描定位 RNG 引擎 (慢, 不能阻塞 UI)"""
    log = Signal(str)
    done = Signal(object, str)   # (RngService|None, 错误消息)

    def __init__(self, adb_path: str) -> None:
        super().__init__()
        self.adb_path = adb_path

    def run(self) -> None:
        try:
            svc = RngService(backend='adb', adb_path=self.adb_path,
                             on_status=lambda m: (self.log.emit(str(m)), _tlog('[RNG]', m)))
            if not svc.attach():
                self.done.emit(None, 'adb 连接失败 (游戏未运行?)')
                return
            if not svc.locate():
                self.done.emit(None, '定位失败: 请确认已进入战斗关卡')
                return
            self.done.emit(svc, '')
        except Exception as e:
            self.done.emit(None, f'出错: {e}')


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
        self._enemy_rows: dict = {}    # roster_id -> 表格行号（按关卡预定顺序稳定）
        self._enemy_row_lifecycle: dict = {}  # roster_id -> 上次生命周期（静态行免重复绘制）
        self._enemy_row_spawn_wait: dict = {} # roster_id -> 上次倒计时文本（仅变化时更新）
        self._bar_colors: dict = {}    # roster_id -> 当前血条颜色
        self._skill_lines: dict = {}   # roster_id -> 技能格行数（变化才调整行高）
        self._enemy_dec: dict = default_precision_values()
        self._enemy_last: list = []    # 最近一帧敌人 (改小数位时立即重绘用)
        self._enemy_detail_dialog: EnemyDetailDialog | None = None
        self._settings = QSettings('ArknightsTools', 'ArknightsTimeline')
        self._enemy_visible_cols = load_visible_columns(
            self._settings, 'enemy_table/visible_columns')
        self._frame_txt: str = ''      # ms/帧 显示 (0.5s 节流, 避免高频抖动)
        self._frame_ts: float = 0.0
        self._widths_fitted: bool = False   # 首次有数据时已做过列宽自适应

        # 随机数追踪 (ak_live_rng): 扫描定位后服务自带轮询线程, UI 定时读快照
        self._rng_svc = None               # RngService | None
        self._rng_worker: RngScanWorker | None = None
        self._rng_timer = QTimer(self)
        self._rng_timer.timeout.connect(self._on_rng_tick)

        # 操作记录 (deploy_tracker): 定位后轮询 BattleLogger.m_logs
        self._deploy_reader: DeployTrackerReader | None = None
        self._deploy_scan: DeployScanWorker | None = None
        self._deploy_poll: DeployPollWorker | None = None
        self._deploy_events: list = []     # 实时操作 (live)
        self._deploy_journal: list = []    # 代理作战序列 (静态, 非代理模式为空)
        self._deploy_squad: list = []
        self._deploy_stage: str = ''
        self._deploy_stage_info: dict = {}
        self._deploy_seen: int = 0         # 已渲染到表格的事件数

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
        self.btn_select_adb = QPushButton("选择 ADB")
        self.btn_select_adb.clicked.connect(self._on_select_adb)
        self._style_secondary_button(self.btn_select_adb)
        title_row.addWidget(self.btn_select_adb)
        self._update_adb_button()
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

        # ---- 游戏时间 & 逻辑帧 (左) + 全局操作记录 (右) ----
        box_game = QGroupBox("游戏状态 / 操作记录（tools/deploy_tracker）")
        l_game = QHBoxLayout(box_game)
        l_game.setContentsMargins(4, 4, 4, 4)
        l_game.setSpacing(10)

        # 左列: 时间/帧卡片上下排列
        left_col = QVBoxLayout()
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
        left_col.addWidget(card_time_disp)

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
        left_col.addWidget(card_frame_disp)

        self.lbl_game = QLabel("正在等待实时刷新…")
        self.lbl_game.setWordWrap(True)
        self.lbl_game.setStyleSheet("color:#9a9a9a; font-size:11px;")
        left_col.addWidget(self.lbl_game)
        left_col.addStretch(1)
        l_game.addLayout(left_col)

        # 右列: 全局操作记录 (部署/技能/撤退)
        right_col = QVBoxLayout()
        deploy_ctrl = QHBoxLayout()
        self.btn_deploy_scan = QPushButton("扫描关卡及操作")
        self.btn_deploy_scan.setToolTip(
            "先读取当前关卡信息，再定位 BattleLogger；刚进关卡、无操作记录也可定位")
        self.btn_deploy_scan.clicked.connect(self._on_deploy_scan)
        self._style_primary_button(self.btn_deploy_scan)
        self.btn_deploy_stop = QPushButton("停止")
        self.btn_deploy_stop.setEnabled(False)
        self.btn_deploy_stop.clicked.connect(self._on_deploy_stop)
        self._style_muted_button(self.btn_deploy_stop)
        self.btn_deploy_export = QPushButton("导出 JSON")
        self.btn_deploy_export.setToolTip("导出当前操作记录为 JSON (同 ak_live_log 格式)")
        self.btn_deploy_export.setEnabled(False)
        self.btn_deploy_export.clicked.connect(self._on_deploy_export)
        self._style_muted_button(self.btn_deploy_export)
        self.lbl_deploy_status = QLabel("未扫描")
        self.lbl_deploy_status.setStyleSheet("color:#9a9a9a;")
        deploy_ctrl.addWidget(self.btn_deploy_scan)
        deploy_ctrl.addWidget(self.btn_deploy_stop)
        deploy_ctrl.addWidget(self.btn_deploy_export)
        deploy_ctrl.addWidget(self.lbl_deploy_status, 1)
        right_col.addLayout(deploy_ctrl)
        self.deploy_table = QTableWidget(0, len(DEPLOY_COLS))
        self.deploy_table.setHorizontalHeaderLabels(DEPLOY_COLS)
        self.deploy_table.verticalHeader().setVisible(False)
        self.deploy_table.setSelectionMode(QTableWidget.NoSelection)
        self.deploy_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.deploy_table.setAlternatingRowColors(True)
        self.deploy_table.setMinimumHeight(190)
        dhdr = self.deploy_table.horizontalHeader()
        dhdr.setSectionResizeMode(QHeaderView.Interactive)
        dhdr.setStretchLastSection(True)
        for i, w in enumerate(DEPLOY_COL_WIDTHS):
            self.deploy_table.setColumnWidth(i, w)
        right_col.addWidget(self.deploy_table)
        l_game.addLayout(right_col, 1)
        main.addWidget(box_game)

        # ---- 敌人数据控制 ----
        box_enemy = QGroupBox("敌人数据（tools/enemy_health）")
        l_enemy = QVBoxLayout(box_enemy)
        row_btn = QHBoxLayout()
        self.btn_enemy_scan = QPushButton("开始扫描")
        self.btn_enemy_scan.setToolTip(
            "进入关卡后定位 BattleController，并读取完整预定出怪序列；"
            "场上尚无敌人也可扫描（通常约 20-40 秒）")
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
        self.btn_enemy_columns = QPushButton("显示列")
        self.btn_enemy_columns.setToolTip("勾选主表需要展示的身份、状态、损伤条和每一项最终属性")
        self.btn_enemy_columns.clicked.connect(self._on_enemy_columns)
        self._style_muted_button(self.btn_enemy_columns)
        self.btn_enemy_fit = QPushButton("列宽自适应")
        self.btn_enemy_fit.setToolTip("按内容自动调整所有列宽 (也可直接拖动表头分隔线手动调整)")
        self.btn_enemy_fit.clicked.connect(lambda: self.enemy_table.resizeColumnsToContents())
        self._style_muted_button(self.btn_enemy_fit)
        self.chk_enemy_hide_departed = QCheckBox("离场敌方不显示")
        self.chk_enemy_hide_departed.setChecked(True)
        self.chk_enemy_hide_departed.setToolTip("默认隐藏死亡、漏怪或其他原因离场的敌人；取消勾选可查看完整记录")
        self.chk_enemy_hide_departed.toggled.connect(self._on_enemy_departed_filter)
        row_btn.addWidget(self.btn_enemy_scan)
        row_btn.addWidget(self.btn_enemy_stop)
        row_btn.addWidget(self.btn_enemy_precision)
        row_btn.addWidget(self.btn_enemy_columns)
        row_btn.addWidget(self.btn_enemy_fit)
        row_btn.addWidget(self.chk_enemy_hide_departed)
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
        hdr.setSectionResizeMode(QHeaderView.Interactive)   # 所有列宽均可拖动调整
        hdr.setStretchLastSection(True)   # 末列 (状态) 自动填满剩余宽度
        for i, w in enumerate(ENEMY_COL_WIDTHS):
            self.enemy_table.setColumnWidth(i, w)
        self._apply_enemy_column_visibility()
        l_table.addWidget(self.enemy_table)
        main.addWidget(box_table, 1)

        # ---- 随机数追踪 (tools/ak_live_rng) ----
        box_rng = QGroupBox("随机数追踪（tools/ak_live_rng）")
        l_rng = QVBoxLayout(box_rng)
        row_rng = QHBoxLayout()
        self.btn_rng_scan = QPushButton("扫描随机数")
        self.btn_rng_scan.setToolTip(
            "进关卡后点击: 扫描定位随机数引擎并实时监控 (首次约 15-30 秒, 之后走缓存秒级)")
        self.btn_rng_scan.clicked.connect(self._on_rng_scan)
        self._style_primary_button(self.btn_rng_scan)
        self.btn_rng_stop = QPushButton("停止")
        self.btn_rng_stop.setEnabled(False)
        self.btn_rng_stop.clicked.connect(self._on_rng_stop)
        self._style_muted_button(self.btn_rng_stop)
        row_rng.addWidget(self.btn_rng_scan)
        row_rng.addWidget(self.btn_rng_stop)
        row_rng.addWidget(QLabel("预测数:"))
        self.rng_pred_spin = QSpinBox()
        self.rng_pred_spin.setRange(1, 500)
        self.rng_pred_spin.setValue(RNG_PREDICT_LEN)
        self.rng_pred_spin.setSuffix(" 发")
        self.rng_pred_spin.setToolTip("未来预测的随机数个数 (1-500)")
        row_rng.addWidget(self.rng_pred_spin)
        self.lbl_rng_status = QLabel("未扫描")
        self.lbl_rng_status.setStyleSheet("color:#9a9a9a;")
        row_rng.addWidget(self.lbl_rng_status, 1)
        l_rng.addLayout(row_rng)
        self.lbl_rng_info = QLabel("—")
        self.lbl_rng_info.setStyleSheet("color:#e8e8e8; font-family:Consolas,monospace;")
        l_rng.addWidget(self.lbl_rng_info)
        row_rng_tables = QHBoxLayout()
        pred_box = QVBoxLayout()
        lbl_pred = QLabel("未来预测 (下一发在最上)")
        lbl_pred.setStyleSheet("color:#9a9a9a;")
        pred_box.addWidget(lbl_pred)
        self.rng_pred_table = QTableWidget(0, 2)
        self.rng_pred_table.setHorizontalHeaderLabels(['第几发', '值'])
        self.rng_pred_table.verticalHeader().setVisible(False)
        self.rng_pred_table.setSelectionMode(QTableWidget.NoSelection)
        self.rng_pred_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rng_pred_table.setAlternatingRowColors(True)
        self.rng_pred_table.setColumnWidth(0, 70)
        self.rng_pred_table.setColumnWidth(1, 110)
        self.rng_pred_table.setMinimumWidth(200)
        pred_box.addWidget(self.rng_pred_table)
        row_rng_tables.addLayout(pred_box)
        hist_box = QVBoxLayout()
        lbl_hist = QLabel("最近消耗 (旧→新)")
        lbl_hist.setStyleSheet("color:#9a9a9a;")
        hist_box.addWidget(lbl_hist)
        self.rng_hist_table = QTableWidget(0, 3)
        self.rng_hist_table.setHorizontalHeaderLabels(['序号', '值', '原始值'])
        self.rng_hist_table.verticalHeader().setVisible(False)
        self.rng_hist_table.setSelectionMode(QTableWidget.NoSelection)
        self.rng_hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rng_hist_table.setAlternatingRowColors(True)
        self.rng_hist_table.setColumnWidth(0, 80)
        self.rng_hist_table.setColumnWidth(1, 110)
        self.rng_hist_table.setColumnWidth(2, 120)
        self.rng_hist_table.setMinimumWidth(330)
        hist_box.addWidget(self.rng_hist_table)
        row_rng_tables.addLayout(hist_box)
        row_rng_tables.addStretch(1)
        l_rng.addLayout(row_rng_tables)
        if RngService is None:
            self.btn_rng_scan.setEnabled(False)
            self.lbl_rng_status.setText("模块缺失 (tools/ak_live_rng)")
        main.addWidget(box_rng)

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
        self._stop_deploy_poll()
        if self._deploy_reader is not None:
            self._deploy_reader.close()
            self._deploy_reader = None
        self._rng_timer.stop()
        if self._rng_svc is not None:
            try:
                self._rng_svc.stop()
            except Exception:
                pass
            self._rng_svc = None
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

    def _update_adb_button(self) -> None:
        path = os.path.normpath(self._enemy_reader.mc.adb_path or '')
        if path and os.path.isfile(path):
            self.btn_select_adb.setText('选择 ADB（已设置）')
            self.btn_select_adb.setToolTip(f'当前 ADB：\n{path}\n\n点击可重新选择')
        else:
            self.btn_select_adb.setText('选择 ADB')
            self.btn_select_adb.setToolTip('选择模拟器安装目录中的 adb.exe')

    def _adb_scan_is_running(self) -> bool:
        return any(worker is not None and worker.isRunning() for worker in (
            self._enemy_scan, self._rng_worker, self._deploy_scan))

    def _activate_adb_path(self, path: str) -> None:
        """停止旧连接并让敌人、RNG、操作记录统一改用新 ADB。"""
        self._stop_enemy_poll()
        self._on_rng_stop()
        self._stop_deploy_poll()
        if self._deploy_reader is not None:
            self._deploy_reader.close()
            self._deploy_reader = None
        self._enemy_reader.close()
        self._enemy_reader = EnemyReader(adb_path=path, log=_tlog)

        if self._enemy_detail_dialog is not None:
            self._enemy_detail_dialog.close()
            self._enemy_detail_dialog = None
        self.enemy_table.setRowCount(0)
        self._enemy_last.clear()
        self._enemy_rows.clear()
        self._enemy_row_lifecycle.clear()
        self._enemy_row_spawn_wait.clear()
        self._bar_colors.clear()
        self._skill_lines.clear()
        self.enemy_progress.setValue(0)
        self.enemy_progress.setFormat('等待扫描')
        self.btn_enemy_scan.setText('开始扫描')
        self.lbl_enemy_status.setText('ADB 已切换，请重新扫描')

        self.rng_pred_table.setRowCount(0)
        self.rng_hist_table.setRowCount(0)
        self.lbl_rng_status.setText('ADB 已切换，请重新扫描')

        self.deploy_table.setRowCount(0)
        self._deploy_events = []
        self._deploy_journal = []
        self._deploy_squad = []
        self._deploy_stage = ''
        self._deploy_stage_info = {}
        self._deploy_seen = 0
        self.btn_deploy_export.setEnabled(False)
        self.lbl_deploy_status.setText('ADB 已切换，请重新扫描')
        self._update_adb_button()

    def _select_adb(self, show_success: bool = True) -> bool:
        if self._adb_scan_is_running():
            QMessageBox.warning(
                self, '选择 ADB', '当前正在定位扫描，请等待本次扫描完成后再切换 ADB。')
            return False
        current = os.path.normpath(self._enemy_reader.mc.adb_path or '')
        dialog = AdbSelectionDialog(self, current if os.path.isfile(current) else '')
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        path = dialog.selected_path()
        detail = dialog.probe_detail
        persisted = save_adb_path(path)
        self._activate_adb_path(path)
        if show_success:
            suffix = '' if persisted else '\n\n警告：配置文件写入失败，下次启动需要重新选择。'
            QMessageBox.information(
                self, 'ADB 已选择',
                f'已切换到：\n{path}\n\n{detail}\n\n'
                f'敌人、随机数和操作记录扫描都会使用此 ADB。{suffix}')
        return True

    def _on_select_adb(self) -> None:
        self._select_adb(show_success=True)

    def _ensure_adb(self) -> bool:
        """扫描前确保 adb 可用; 找不到时弹框让用户手动选择并持久化"""
        mc = self._enemy_reader.mc
        if mc.adb_path and os.path.isfile(mc.adb_path):
            self._update_adb_button()
            return True
        QMessageBox.information(
            self, "需要 adb",
            "未找到 adb.exe。\n\n"
            "请选择 MuMu 模拟器安装目录下的 shell\\adb.exe，例如：\n"
            "D:\\Program Files\\MuMu9\\emulator\\MuMuPlayer-12.0\\shell\\adb.exe")
        return self._select_adb(show_success=False)

    def _on_enemy_scan(self) -> None:
        if not self._ensure_adb():
            self.lbl_enemy_status.setText('状态: 未选择 adb.exe, 取消扫描')
            return
        self._stop_enemy_poll()
        self.enemy_table.setRowCount(0)   # 换关卡重扫: 清掉旧敌人行
        self._enemy_rows.clear()
        self._enemy_row_lifecycle.clear()
        self._enemy_row_spawn_wait.clear()
        self._bar_colors.clear()
        self._skill_lines.clear()
        self.btn_enemy_scan.setEnabled(False)
        self.enemy_progress.setValue(0)
        self.enemy_progress.setFormat('开始定位关卡与出怪序列 ... %p%')
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

    # ================= 随机数追踪 (ak_live_rng) =================

    def _on_rng_scan(self) -> None:
        if RngService is None:
            return
        if not self._ensure_adb():
            self.lbl_rng_status.setText('未选择 adb.exe, 取消扫描')
            return
        self._on_rng_stop()   # 停掉上一轮监控
        self.btn_rng_scan.setEnabled(False)
        self.btn_rng_stop.setEnabled(True)
        self.lbl_rng_status.setText('扫描定位中 ...')
        self._rng_worker = RngScanWorker(self._enemy_reader.mc.adb_path)
        self._rng_worker.log.connect(
            lambda m: self.lbl_rng_status.setText(str(m).strip() or self.lbl_rng_status.text()))
        self._rng_worker.done.connect(self._on_rng_scan_done)
        self._rng_worker.start()

    def _on_rng_scan_done(self, svc, msg: str) -> None:
        self.btn_rng_scan.setEnabled(True)
        if svc is None:
            self.lbl_rng_status.setText(msg)
            self.btn_rng_stop.setEnabled(False)
            return
        self._rng_svc = svc
        svc.select_role('imp')   # 只展示关键随机 (战斗判定), 表现随机不在界面出现
        svc.start()
        self._rng_timer.start(RNG_UI_MS)
        self.lbl_rng_status.setText('监控中')
        self.btn_rng_stop.setEnabled(True)

    def _on_rng_stop(self) -> None:
        self._rng_timer.stop()
        if self._rng_svc is not None:
            try:
                self._rng_svc.stop()
            except Exception:
                pass
            self._rng_svc = None
        self.btn_rng_stop.setEnabled(False)
        self.btn_rng_scan.setEnabled(RngService is not None)
        self.lbl_rng_status.setText('已停止')

    def _on_rng_tick(self) -> None:
        svc = self._rng_svc
        if svc is None:
            return
        try:
            snap = svc.snapshot(RNG_HISTORY_LEN, self.rng_pred_spin.value())
        except Exception:
            return
        sel = snap.get('selected')
        if sel is None:
            self.lbl_rng_info.setText(str(snap.get('status') or '—'))
            return
        self.lbl_rng_info.setText(
            f"游标 #{sel.get('cursor', 0)}   已消耗 {sel.get('total', 0)} 发   "
            f"{sel.get('rate', 0.0):.1f} 发/秒   [{sel.get('label', '')}]")
        preds = sel.get('predictions') or []
        self.rng_pred_table.setRowCount(len(preds))
        for i, p in enumerate(preds):
            self.rng_pred_table.setItem(i, 0, QTableWidgetItem(str(p.get('n', i + 1))))
            self.rng_pred_table.setItem(i, 1, QTableWidgetItem(f"{p.get('frac', 0.0):.4f}"))
        hist = sel.get('history') or []
        self.rng_hist_table.setRowCount(len(hist))
        for i, h in enumerate(hist):
            items = [QTableWidgetItem(str(h.get('seq', 0))),
                     QTableWidgetItem(f"{h.get('frac', 0.0):.4f}"),
                     QTableWidgetItem(f"0x{h.get('raw', 0) & 0xFFFFFFFF:08X}")]
            for c, it in enumerate(items):
                self.rng_hist_table.setItem(i, c, it)

    # ================= 操作记录 (deploy_tracker) =================

    def _on_deploy_scan(self) -> None:
        if not self._ensure_adb():
            self.lbl_deploy_status.setText('未选择 adb.exe, 取消扫描')
            return
        self._on_deploy_stop()
        self.deploy_table.setRowCount(0)
        self._deploy_events = []
        self._deploy_journal = []
        self._deploy_squad = []
        self._deploy_stage = ''
        self._deploy_stage_info = {}
        if self._deploy_reader is not None:
            self._deploy_reader.close()
        self._deploy_reader = None
        self._deploy_seen = 0
        self.btn_deploy_scan.setEnabled(False)
        self.btn_deploy_export.setEnabled(False)
        self.lbl_deploy_status.setText('阶段 1/2：正在扫描关卡信息 ...')
        self._deploy_scan = DeployScanWorker(self._enemy_reader.mc.adb_path)
        self._deploy_scan.log.connect(
            lambda m: self.lbl_deploy_status.setText(str(m).strip() or self.lbl_deploy_status.text()))
        self._deploy_scan.stage.connect(self._on_deploy_stage)
        self._deploy_scan.done.connect(self._on_deploy_scan_done)
        self._deploy_scan.start()

    def _deploy_stage_label(self) -> str:
        info = self._deploy_stage_info
        code = info.get('code') or ''
        name = info.get('name') or ''
        stage_id = info.get('stageId') or self._deploy_stage
        return ' '.join(x for x in (code, name, f'({stage_id})' if stage_id else '') if x)

    def _on_deploy_stage(self, info: dict) -> None:
        """阶段 1 回调：操作记录仍在定位时，先把关卡信息交给界面/后端状态。"""
        self._deploy_stage_info = dict(info or {})
        self._deploy_stage = self._deploy_stage_info.get('stageId') or ''
        label = self._deploy_stage_label() or self._deploy_stage_info.get('levelId') or '未知关卡'
        self.lbl_deploy_status.setText(f'已识别关卡 {label}；阶段 2/2：正在定位操作记录 ...')
        self.btn_deploy_export.setEnabled(bool(self._deploy_stage_info))

    def _on_deploy_scan_done(self, reader, msg: str) -> None:
        self.btn_deploy_scan.setEnabled(True)
        if reader is None:
            self.lbl_deploy_status.setText(msg)
            return
        self._deploy_reader = reader
        try:
            st = reader.get_state()   # 一次性取 编队/代理序列/关卡信息 (顺带补齐干员名)
            self._deploy_squad = st.get('squad') or []
            self._deploy_journal = st.get('journalEvents') or []
            self._deploy_journal = self._attach_deploy_frames(self._deploy_journal, [])
            self._deploy_stage_info = st.get('stage') or self._deploy_stage_info
            self._deploy_stage = st.get('stageId') or ''
        except Exception:
            pass
        if self._deploy_journal:
            # 代理作战: 序列为静态完整记录, 无需轮询
            self._append_deploy_rows(self._deploy_journal)
            stage = f"   {self._deploy_stage_label()}" if self._deploy_stage_label() else ''
            self.lbl_deploy_status.setText(
                f"代理作战序列 {len(self._deploy_journal)} 条 (静态){stage}")
        else:
            self._start_deploy_poll()
        self.btn_deploy_export.setEnabled(
            bool(self._deploy_stage_info or self._deploy_journal or self._deploy_events))

    def _start_deploy_poll(self) -> None:
        self._stop_deploy_poll()
        self._deploy_poll = DeployPollWorker(self._deploy_reader)
        self._deploy_poll.snapshot.connect(self._on_deploy_snapshot)
        self._deploy_poll.start()
        self.btn_deploy_stop.setEnabled(True)
        stage = f"   {self._deploy_stage_label()}" if self._deploy_stage_label() else ''
        self.lbl_deploy_status.setText(f'监控中 ...{stage}')

    def _stop_deploy_poll(self) -> None:
        if self._deploy_poll:
            self._deploy_poll.requestInterruption()
            self._deploy_poll.wait(3000)
            self._deploy_poll = None
        self.btn_deploy_stop.setEnabled(False)

    def _on_deploy_stop(self) -> None:
        self._stop_deploy_poll()
        self.btn_deploy_scan.setEnabled(True)
        if self._deploy_reader is not None:
            self.lbl_deploy_status.setText('已停止')

    def _on_deploy_snapshot(self, events: list, battle: dict, chain_ok: bool) -> None:
        if not chain_ok:
            self._stop_deploy_poll()
            self.lbl_deploy_status.setText('地址链失效 (关卡已结束?), 请重新扫描')
            return
        if battle:
            stage = f"   {self._deploy_stage_label()}" if self._deploy_stage_label() else ''
            self.lbl_deploy_status.setText(
                f"监控中{stage}   战斗时间 {battle.get('playTime', 0.0):.1f}s   "
                f"{battle.get('stateName', '')}   x{battle.get('speedLevel', '?')}")
        if len(events) < self._deploy_seen:   # 列表重建 (新一局), 重渲染
            self.deploy_table.setRowCount(0)
            self._deploy_seen = 0
            previous = []
        else:
            previous = self._deploy_events
        events = self._attach_deploy_frames(events, previous)
        self._deploy_events = events
        self._update_deploy_frame_cells(events)
        new = events[self._deploy_seen:]
        if new:
            self._append_deploy_rows(new)
            self._deploy_seen = len(events)
        self.btn_deploy_export.setEnabled(bool(self._deploy_stage_info or events))

    @staticmethod
    def _deploy_event_key(ev: dict) -> tuple:
        return (ev.get('timestamp'), ev.get('uniqueId'), ev.get('op'),
                ev.get('direction'), ev.get('gridRow'), ev.get('gridCol'),
                ev.get('extraInfo'))

    def _attach_deploy_frames(self, events: list, previous: list) -> list:
        """用主计时器的有界时间-帧缓存给事件补帧，并沿用已经确认的结果。"""
        unresolved = []
        for i, ev in enumerate(events):
            old = previous[i] if i < len(previous) else None
            if (old and self._deploy_event_key(old) == self._deploy_event_key(ev)
                    and old.get('frame') is not None):
                for key in ('frame', 'frameSource', 'frameSampleTime', 'frameTimeDelta'):
                    if key in old:
                        ev[key] = old[key]
                continue
            unresolved.append((ev, ev.get('timestamp')))
        matches = self._provider.get_frames_for_game_times(
            [timestamp for _ev, timestamp in unresolved])
        for (ev, _timestamp), match in zip(unresolved, matches):
            if match is None:
                ev['frame'] = None
                continue
            ev['frame'] = match['frame']
            ev['frameSource'] = match['source']
            ev['frameSampleTime'] = match['sampleTime']
            ev['frameTimeDelta'] = match['timeDelta']
        return events

    def _update_deploy_frame_cells(self, events: list) -> None:
        """定时器稍后配置成功时，补写已经显示但此前没有帧号的行。"""
        row_count = min(self.deploy_table.rowCount(), len(events))
        for row in range(row_count):
            frame = events[row].get('frame')
            text = f"F{int(frame)}" if frame is not None else '—'
            item = self.deploy_table.item(row, 1)
            if item is None:
                self.deploy_table.setItem(row, 1, QTableWidgetItem(text))
            elif item.text() != text:
                item.setText(text)

    @staticmethod
    def _deploy_pos_label(ev: dict) -> str:
        """左手 JSON 坐标：gridRow 0=A，gridCol 0=1，例如 (5,8) -> F9。"""
        try:
            row = int(ev.get('gridRow'))
            col = int(ev.get('gridCol'))
        except (TypeError, ValueError):
            return ''
        if not (0 <= row < 26 and col >= 0):
            return ''
        return f'{chr(ord("A") + row)}{col + 1}'

    def _build_deploy_export_payload(self, events: list) -> dict:
        actions = []
        for ev in events:
            action = {
                'action_type': DEPLOY_OP_CN.get(ev.get('op'), ev.get('opName', '')),
                'frame': int(ev['frame']),
                'oper': ev.get('charName') or ev.get('charId') or '',
                'pos': self._deploy_pos_label(ev),
            }
            if ev.get('op') == 0 and ev.get('direction') in DEPLOY_DIR_CN:
                direction = DEPLOY_DIR_CN[ev['direction']]
                if direction != '-':
                    action['direction'] = direction
            actions.append(action)
        return {
            'settings': {
                'map_code': self._deploy_stage_info.get('code', ''),
                'map_name': self._deploy_stage_info.get('name', ''),
            },
            'actions': actions,
        }

    def _append_deploy_rows(self, events: list) -> None:
        # 编队表补充 charId/instId -> 中文名 (覆盖 trap/token 等)
        inst_names = {c.get('charInstId'): c.get('charName')
                      for c in self._deploy_squad if c.get('charName')}
        id_names = {c.get('charId'): c.get('charName')
                    for c in self._deploy_squad if c.get('charName')}
        tbl = self.deploy_table
        for ev in events:
            name = (ev.get('charName')
                    or inst_names.get(ev.get('uniqueId'))
                    or id_names.get(ev.get('charId'))
                    or ev.get('charId') or '')
            row = tbl.rowCount()
            tbl.insertRow(row)
            tbl.setItem(row, 0, QTableWidgetItem(f"{ev.get('timestamp', 0.0):.3f}"))
            frame = ev.get('frame')
            tbl.setItem(row, 1, QTableWidgetItem(
                f"F{int(frame)}" if frame is not None else '—'))
            tbl.setItem(row, 2, QTableWidgetItem(
                DEPLOY_OP_CN.get(ev.get('op'), ev.get('opName', ''))))
            tbl.setItem(row, 3, QTableWidgetItem(name))
            tbl.setItem(row, 4, QTableWidgetItem(
                DEPLOY_DIR_CN.get(ev.get('direction'), str(ev.get('direction', '')))))
            tbl.setItem(row, 5, QTableWidgetItem(
                f"({ev.get('gridRow', 0)},{ev.get('gridCol', 0)})"))
            tbl.setItem(row, 6, QTableWidgetItem(ev.get('extraInfo') or ''))
        tbl.scrollToBottom()

    def _on_deploy_export(self) -> None:
        events = self._deploy_journal or self._deploy_events
        if not events and not self._deploy_stage_info:
            QMessageBox.information(self, '导出', '当前没有可导出的关卡或操作记录')
            return
        events = self._attach_deploy_frames(events, events)
        if self._deploy_journal:
            self._deploy_journal = events
        else:
            self._deploy_events = events
        self._update_deploy_frame_cells(events)
        missing_frames = sum(ev.get('frame') is None for ev in events)
        if missing_frames:
            QMessageBox.warning(
                self, '无法导出',
                f'仍有 {missing_frames} 条操作没有匹配到精确逻辑帧。\n'
                '请先用寻址工具配置游戏时间/帧地址，并等待对应操作发生后再导出。')
            return
        payload = self._build_deploy_export_payload(events)
        default = f"deploy_log_{time.strftime('%Y%m%d_%H%M%S')}.json"
        path, _ = QFileDialog.getSaveFileName(self, '导出操作记录', default, 'JSON (*.json)')
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError as e:
            QMessageBox.critical(self, '导出失败', str(e))
            return
        self.lbl_deploy_status.setText(f'已导出 {len(events)} 条 -> {path}')
        self._tlog(f'[部署] 已导出 {len(events)} 条 -> {path}')

    def _on_enemy_snapshot(self, snap: dict) -> None:
        if TEST_BUILD:   # 轮询错误 (数据链失效/重建) 去重后输出控制台
            msg = snap.get('msg')
            if msg and msg != getattr(self, '_last_snap_msg', None):
                self._last_snap_msg = msg
                _tlog("轮询:", msg)
        # 主表与详情页使用同一次 60fps 渲染节流，避免两处显示不同步。
        now = time.time()
        if snap.get('ok') and now - self._enemy_last_render < ENEMY_RENDER_SEC:
            return
        self._enemy_last_render = now
        detail_dialog = self._enemy_detail_dialog
        if detail_dialog is not None and 'detail_enemy' in snap:
            detail_enemy = snap.get('detail_enemy')
            if (detail_enemy is not None
                    and detail_enemy.addr == detail_dialog.enemy.addr):
                detail_dialog.update_enemy(detail_enemy)
            elif snap.get('detail_error'):
                detail_dialog.set_live_error(snap['detail_error'])
        st = ENEMY_STATE_NAMES.get(snap['state'], '?') if snap['state'] >= 0 else '-'
        spd = enemy_gs.SpeedLevel.NAMES.get(snap['speed_level'], '?') if snap['speed_level'] >= 0 else '-'
        t = int(snap['play_time'])
        if now - self._frame_ts >= 0.5:   # ms/帧 0.5s 节流, 避免高频刷新抖动
            self._frame_ts = now
            self._frame_txt = f"   {snap['frame_ms']:.0f}ms/帧" if snap.get('frame_ms') else ''
        on_field = snap.get('on_field_count', sum(
            getattr(enemy, 'lifecycle', 'active') == 'active'
            for enemy in snap['enemies']))
        planned = snap.get('planned_count', 0)
        total_text = f"场上敌人: {on_field}"
        if planned:
            total_text += f" / 预定: {planned}"
        text = (f"状态: {st}   倍速: {spd} (x{snap['time_scale']:g})   "
                f"战斗时间: {t // 60:02d}:{t % 60:02d}   {total_text}"
                + self._frame_txt)
        if snap.get('msg'):
            text += f"   ({snap['msg']})"
        self.lbl_enemy_status.setText(text)
        self._render_enemy_table(snap['enemies'])

    def _render_enemy_table(self, enemies) -> None:
        self._enemy_last = enemies
        enemies = visible_enemy_rows(
            enemies, hide_departed=self.chk_enemy_hide_departed.isChecked())
        tbl = self.enemy_table
        if enemies and not self._widths_fitted:
            self._widths_fitted = True
            tbl.resizeColumnsToContents()   # 首次有数据时自适应一次, 之后交用户手调
        # 增量刷新：按本局 roster_id 锚定行；固定敌人保持关卡预定顺序，
        # 动态召唤/分支敌人首次出现时追加。过滤切换时才重建一次。
        tbl.setUpdatesEnabled(False)
        try:
            seen = set()
            for e in enemies:
                row_key = getattr(e, 'roster_id', 0) or e.addr
                seen.add(row_key)
                row = self._enemy_rows.get(row_key)
                is_new = row is None
                if row is None:
                    row = tbl.rowCount()
                    tbl.insertRow(row)
                    self._make_enemy_row(row, row_key)
                    self._enemy_rows[row_key] = row
                lifecycle = getattr(e, 'lifecycle', 'active')
                # 场上行全量刷新；未出场行只刷新倒计时列，避免几十行每帧重排。
                if (is_new or lifecycle == 'active'
                        or self._enemy_row_lifecycle.get(row_key) != lifecycle):
                    self._update_enemy_row(row, e)
                elif lifecycle == 'pending':
                    self._update_enemy_spawn_wait(row, e, row_key)
                self._enemy_row_lifecycle[row_key] = lifecycle
            gone = [a for a in self._enemy_rows if a not in seen]
            for a in sorted(gone, key=lambda a: -self._enemy_rows[a]):
                tbl.removeRow(self._enemy_rows.pop(a))
                self._bar_colors.pop(a, None)
                self._skill_lines.pop(a, None)
                self._enemy_row_lifecycle.pop(a, None)
                self._enemy_row_spawn_wait.pop(a, None)
            if gone:   # removeRow 后行号位移, 依 item(0) 存的 addr 重建映射
                self._enemy_rows = {tbl.item(r, 0).data(Qt.UserRole): r
                                    for r in range(tbl.rowCount())}
        finally:
            tbl.setUpdatesEnabled(True)

    def _on_enemy_departed_filter(self, _checked: bool) -> None:
        # 过滤切换时重建一次，确保重新显示的离场项仍按预定出怪序排列。
        self.enemy_table.setRowCount(0)
        self._enemy_rows.clear()
        self._enemy_row_lifecycle.clear()
        self._enemy_row_spawn_wait.clear()
        self._bar_colors.clear()
        self._skill_lines.clear()
        self._render_enemy_table(self._enemy_last)

    def _update_enemy_spawn_wait(self, row: int, enemy, row_key: int) -> None:
        text = format_column_value('spawn_wait', enemy, self._enemy_dec, row)
        if self._enemy_row_spawn_wait.get(row_key) == text:
            return
        self._enemy_row_spawn_wait[row_key] = text
        item = self.enemy_table.item(row, ENEMY_COLUMN_INDEX['spawn_wait'])
        if item is not None:
            item.setText(text)
            item.setToolTip(text)

    def _on_enemy_precision(self) -> None:
        dlg = EnemyPrecisionDialog(
            self, self._enemy_dec, self._enemy_visible_cols)
        if dlg.exec() == QDialog.Accepted:
            self._enemy_dec.update(dlg.values())
            self._render_enemy_table(self._enemy_last)   # 立即按新精度重绘

    def _apply_enemy_column_visibility(self) -> None:
        if not hasattr(self, 'enemy_table'):
            return
        for idx, col in enumerate(ENEMY_COLUMN_DEFS):
            self.enemy_table.setColumnHidden(idx, col['key'] not in self._enemy_visible_cols)

    def _on_enemy_columns(self) -> None:
        dlg = EnemyColumnDialog(self, self._enemy_visible_cols)
        if dlg.exec() != QDialog.Accepted:
            return
        self._enemy_visible_cols = dlg.values()
        save_visible_columns(
            self._settings, 'enemy_table/visible_columns', self._enemy_visible_cols)
        self._apply_enemy_column_visibility()
        self._render_enemy_table(self._enemy_last)

    def _open_enemy_detail(self, roster_id: int) -> None:
        # 用主表最近快照立即打开，完整 Buff/关卡效果由轮询线程异步补全并持续刷新。
        enemy = next((item for item in self._enemy_last
                      if (getattr(item, 'roster_id', 0) or item.addr) == roster_id), None)
        if enemy is None:
            QMessageBox.information(self, '敌人详情', '该敌人已退场或对象已失效。')
            return
        dialog = EnemyDetailDialog(self, enemy)
        self._enemy_detail_dialog = dialog
        poll = self._enemy_poll
        lifecycle = getattr(enemy, 'lifecycle', 'active')
        if lifecycle == 'departed':
            dialog.set_live_error('敌人已离场，显示最后一次记录。')
        elif poll is not None and enemy.addr:
            poll.set_detail_target(enemy.addr)
        try:
            dialog.exec()
        finally:
            if poll is self._enemy_poll:
                poll.set_detail_target(0)
            if self._enemy_detail_dialog is dialog:
                self._enemy_detail_dialog = None

    def _make_enemy_row(self, row: int, roster_id: int) -> None:
        tbl = self.enemy_table
        hp_col = ENEMY_COLUMN_INDEX['hp']
        detail_col = ENEMY_COLUMN_INDEX['detail']
        for c in range(len(ENEMY_COLS)):
            if c not in (hp_col, detail_col):
                it = QTableWidgetItem()
                it.setTextAlignment(Qt.AlignCenter)
                tbl.setItem(row, c, it)
        row_col = ENEMY_COLUMN_INDEX['row']
        tbl.item(row, row_col).setData(Qt.UserRole, roster_id)
        for key in ('name', 'eid', 'skill', 'abnormal_status', 'immune_status'):
            item = tbl.item(row, ENEMY_COLUMN_INDEX[key])
            if item:
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        bar = QProgressBar()
        bar.setTextVisible(True)
        tbl.setCellWidget(row, hp_col, bar)
        detail = QPushButton('详情')
        detail.setToolTip('读取并显示该敌人的完整属性、状态、损伤条、Buff 与关卡效果')
        detail.clicked.connect(
            lambda _checked=False, rid=roster_id: self._open_enemy_detail(rid))
        tbl.setCellWidget(row, detail_col, detail)

    def _update_enemy_row(self, row: int, e) -> None:
        tbl = self.enemy_table
        d = self._enemy_dec

        def setc(key, text, grey=False):
            c = ENEMY_COLUMN_INDEX[key]
            it = tbl.item(row, c)
            if it is None:
                return
            it.setText(str(text))
            if grey:
                it.setForeground(QColor('#888888'))
            else:
                it.setData(Qt.ForegroundRole, None)

        for col in ENEMY_COLUMN_DEFS:
            key = col['key']
            if key in ('hp', 'detail'):
                continue
            setc(key, format_column_value(key, e, d, row),
                 grey=(getattr(e, 'lifecycle', 'active') != 'active'
                       or (key == 'life_status' and not e.alive)))
        row_key = getattr(e, 'roster_id', 0) or e.addr
        self._enemy_row_spawn_wait[row_key] = format_column_value(
            'spawn_wait', e, d, row)

        hp_col = ENEMY_COLUMN_INDEX['hp']
        bar = tbl.cellWidget(row, hp_col)
        lifecycle = getattr(e, 'lifecycle', 'active')
        mx = max(1, int(e.max_hp))
        bar.setMaximum(mx)
        bar.setValue(max(0, int(e.hp)) if lifecycle != 'pending' else 0)
        if lifecycle == 'pending':
            bar.setFormat('未出场')
        elif lifecycle == 'departed':
            bar.setFormat(f'已离场  {e.hp:.{d["hp"]}f} / {e.max_hp:.{d["hp"]}f}')
        else:
            bar.setFormat(f'{e.hp:.{d["hp"]}f} / {e.max_hp:.{d["hp"]}f}  %p%')
        ratio = e.hp / e.max_hp if e.max_hp > 0 else 0
        color = '#5cb85c' if ratio > 0.5 else ('#f0ad4e' if ratio > 0.2 else '#d9534f')
        if lifecycle != 'active' or not e.alive:
            color = '#888888'
        if self._bar_colors.get(row_key) != color:   # 颜色变化才重设样式 (触发重排版)
            self._bar_colors[row_key] = color
            bar.setStyleSheet(f'QProgressBar::chunk {{ background-color: {color}; }}')

        detail = tbl.cellWidget(row, ENEMY_COLUMN_INDEX['detail'])
        if detail is not None:
            detail.setEnabled(lifecycle != 'pending')
            detail.setToolTip(
                '未出场，暂无运行时详情' if lifecycle == 'pending'
                else '显示该敌人的完整属性、状态、损伤条、Buff 与关卡效果')

        cd_text = format_column_value('skill', e, d, row)
        n_lines = cd_text.count('\n')          # 行数变化才重排行高 (重排会触发布局)
        if self._skill_lines.get(row_key) != n_lines:
            self._skill_lines[row_key] = n_lines
            tbl.resizeRowToContents(row)

    # ================= 定时刷新 =================

    def _tick_fast(self) -> None:
        game = self._provider.get_game_data()
        self.lbl_game_time_big.setText(_format_game_time(game.get("game_time")))
        fc = game.get("frame_count")
        self.lbl_frame_big.setText(f"F{int(fc)}" if fc is not None else "—")

    def _tick_slow(self) -> None:
        game = self._provider.get_game_data()
        timeline = self._provider.get_frame_timeline_stats()
        if self._deploy_journal and any(
                ev.get('frame') is None for ev in self._deploy_journal):
            self._deploy_journal = self._attach_deploy_frames(
                self._deploy_journal, self._deploy_journal)
            self._update_deploy_frame_cells(self._deploy_journal)
        lr = game.get("last_refresh")
        self.lbl_game.setText(
            "\n".join(
                [
                    f"连接: {'是' if game.get('connected') else '否'}  |  已配置地址: {'是' if game.get('configured') else '否'}",
                    f"最近一次刷新: {lr if lr else '—'}",
                    f"帧映射缓存: {timeline['size']} / {timeline['maxSize']}",
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
