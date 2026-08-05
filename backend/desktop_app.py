"""
明日方舟游戏数据显示工具 — 独立桌面程序（PySide6）。
读取游戏时间与帧（tools/timer 内存方案）；通过 tools/enemy_health
实时展示关卡内敌人数据（名称/血量/坐标/属性）。
"""
from __future__ import annotations

import asyncio
import ctypes
from ctypes import wintypes
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QSettings, Qt, QThread, QTimer, Signal
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
    QSizeGrip,
    QSizePolicy,
    QSlider,
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
from tools.character_status import CharacterReader
from tools.enemy_health.memcore import (
    MemCore, find_running_emulator_adbs, query_adb_devices, save_adb_config,
)
from app.enemy_ui import (
    ENEMY_COLUMN_DEFS, ENEMY_COLUMN_INDEX, EnemyColumnDialog, EnemyDetailDialog,
    EnemyPrecisionDialog, apply_column_order, default_precision_values,
    format_column_value, load_column_order, load_visible_columns,
    save_column_order, save_visible_columns, visible_enemy_rows,
)
from app.character_ui import (
    CHARACTER_COLS, CHARACTER_COL_WIDTHS, CHARACTER_COLUMN_DEFS,
    CHARACTER_COLUMN_INDEX, CharacterColumnDialog, CharacterDetailDialog,
    CharacterOverviewDialog, CharacterPrecisionDialog, GlobalDamageDetailDialog,
    default_character_precision,
    format_character_column, load_character_columns, save_character_columns,
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
CHARACTER_DETAIL_FULL_SEC = 0.05

ENEMY_COLS = [col['label'] for col in ENEMY_COLUMN_DEFS]
ENEMY_COL_WIDTHS = [col['width'] for col in ENEMY_COLUMN_DEFS]
ENEMY_STATE_NAMES = {0: 'NONE', 1: 'INITED', 2: '战斗中', 3: '已结束'}


def _system_prefers_dark(app: QApplication | None = None) -> bool:
    """读取系统应用主题；Qt 无法判断时回退 Windows 注册表和系统调色板。"""
    app = app or QApplication.instance()
    if app is not None:
        try:
            scheme = app.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return True
            if scheme == Qt.ColorScheme.Light:
                return False
        except (AttributeError, RuntimeError):
            pass
    if sys.platform == 'win32':
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize')
            value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
            winreg.CloseKey(key)
            return int(value) == 0
        except (OSError, ValueError, TypeError):
            pass
    if app is not None:
        return app.palette().window().color().lightness() < 128
    return True


def _theme_stylesheet(dark: bool) -> str:
    """生成覆盖主窗口及其弹窗的完整主题，避免系统控件与硬编码深色混用。"""
    if dark:
        c = {
            'bg': '#1e1e1e', 'panel': '#252526', 'input': '#2d2d2d',
            'text': '#e8e8e8', 'muted': '#a3a3a3', 'border': '#454545',
            'header': '#343434', 'alt': '#272727', 'hover': '#3b3b3b',
            'selection': '#315f9e', 'scroll': '#555555', 'scroll_hover': '#686868',
            'primary': '#3d7eff', 'primary_hover': '#5a90ff', 'primary_press': '#2d62cc',
            'secondary': '#3c3c3c', 'secondary_hover': '#4a4a4a',
            'muted_btn': '#d4a0a0', 'muted_border': '#663333', 'muted_hover': '#3a2525',
            'toggle': '#333333', 'toggle_text': '#aaaaaa',
            'toggle_on': '#1a4a7a', 'progress': '#333333',
            'time': '#7ec8ff', 'frame': '#ffd66b', 'disabled': '#707070',
        }
    else:
        c = {
            'bg': '#f3f5f7', 'panel': '#ffffff', 'input': '#ffffff',
            'text': '#202124', 'muted': '#60656d', 'border': '#c9ced6',
            'header': '#e8ecf1', 'alt': '#f4f6f8', 'hover': '#e6e9ed',
            'selection': '#c9ddff', 'scroll': '#b4bac2', 'scroll_hover': '#969da6',
            'primary': '#2563d9', 'primary_hover': '#3475eb', 'primary_press': '#194fae',
            'secondary': '#f5f6f8', 'secondary_hover': '#e7eaee',
            'muted_btn': '#9b3434', 'muted_border': '#d7a4a4', 'muted_hover': '#f8e8e8',
            'toggle': '#eef0f3', 'toggle_text': '#555b63',
            'toggle_on': '#d9e9ff', 'progress': '#e2e5e9',
            'time': '#0069b5', 'frame': '#9a6500', 'disabled': '#999ea5',
        }
    return f"""
QWidget {{ background-color:{c['bg']}; color:{c['text']}; }}
QMainWindow, QDialog, QMessageBox {{ background-color:{c['bg']}; }}
QLabel, QCheckBox, QRadioButton {{ background-color:transparent; }}
QToolTip {{ background-color:{c['panel']}; color:{c['text']}; border:1px solid {c['border']}; padding:4px; }}
QLabel#PageTitle {{ font-size:20px; font-weight:700; color:{c['text']}; }}
QLabel[role="muted"] {{ color:{c['muted']}; }}
QLabel[role="primaryText"] {{ color:{c['text']}; }}
QLabel#GameTimeValue {{ font-size:48px; font-weight:700; color:{c['time']}; }}
  QLabel#GameFrameValue {{ font-size:48px; font-weight:700; color:{c['frame']}; }}
  QLabel#EnemyCompactGameStatus {{ color:{c['text']}; border-left:1px solid {c['border']}; padding-left:10px; font-weight:600; }}
  QFrame#GameTimeCard, QFrame#GameFrameCard {{ background-color:{c['panel']}; border:1px solid {c['border']}; border-radius:8px; }}
QWidget#EnemyMiniWindow {{ background-color:{c['bg']}; border:1px solid {c['border']}; }}
QFrame#EnemyMiniToolbar {{ background-color:{c['panel']}; border:1px solid {c['border']}; border-radius:5px; }}
QLabel#EnemyMiniDragLabel {{ color:{c['text']}; font-weight:600; }}
  QGroupBox {{ background-color:{c['panel']}; border:1px solid {c['border']}; border-radius:6px; font-weight:600; margin-top:9px; padding-top:9px; }}
  QGroupBox::title {{ subcontrol-origin:margin; subcontrol-position:top left; left:9px; padding:0 4px; background-color:{c['panel']}; }}
  QGroupBox::indicator {{ width:14px; height:14px; }}
QLineEdit, QComboBox, QAbstractSpinBox, QTextEdit, QPlainTextEdit, QListWidget, QTreeWidget {{ background-color:{c['input']}; color:{c['text']}; border:1px solid {c['border']}; border-radius:4px; padding:4px; selection-background-color:{c['selection']}; }}
QComboBox QAbstractItemView {{ background-color:{c['input']}; color:{c['text']}; border:1px solid {c['border']}; selection-background-color:{c['selection']}; }}
QTableWidget {{ background-color:{c['input']}; alternate-background-color:{c['alt']}; color:{c['text']}; gridline-color:{c['border']}; border:1px solid {c['border']}; selection-background-color:{c['selection']}; selection-color:{c['text']}; }}
QHeaderView::section, QTableCornerButton::section {{ background-color:{c['header']}; color:{c['text']}; border:0; border-right:1px solid {c['border']}; border-bottom:1px solid {c['border']}; padding:5px; }}
QTabWidget::pane {{ background-color:{c['panel']}; border:1px solid {c['border']}; }}
QTabBar::tab {{ background-color:{c['header']}; color:{c['text']}; border:1px solid {c['border']}; padding:6px 12px; }}
QTabBar::tab:selected {{ background-color:{c['panel']}; border-bottom-color:{c['panel']}; }}
QPushButton {{ background-color:{c['secondary']}; color:{c['text']}; border:1px solid {c['border']}; border-radius:6px; padding:6px 14px; }}
QPushButton:hover {{ background-color:{c['secondary_hover']}; }}
QPushButton:disabled {{ color:{c['disabled']}; background-color:{c['bg']}; }}
QPushButton[buttonRole="primary"] {{ background-color:{c['primary']}; color:white; border:none; font-weight:600; }}
QPushButton[buttonRole="primary"]:hover {{ background-color:{c['primary_hover']}; }}
QPushButton[buttonRole="primary"]:pressed {{ background-color:{c['primary_press']}; }}
QPushButton[buttonRole="secondary"] {{ background-color:{c['secondary']}; color:{c['text']}; border:1px solid {c['border']}; }}
QPushButton[buttonRole="secondary"]:hover {{ background-color:{c['secondary_hover']}; }}
QPushButton[buttonRole="muted"] {{ background-color:transparent; color:{c['muted_btn']}; border:1px solid {c['muted_border']}; }}
QPushButton[buttonRole="muted"]:hover {{ background-color:{c['muted_hover']}; }}
QPushButton[buttonRole="toggleOff"] {{ background-color:{c['toggle']}; color:{c['toggle_text']}; border:1px solid {c['border']}; }}
QPushButton[buttonRole="toggleOff"]:hover {{ background-color:{c['secondary_hover']}; color:{c['text']}; }}
QPushButton[buttonRole="toggleOn"] {{ background-color:{c['toggle_on']}; color:{c['text']}; border:2px solid {c['primary']}; font-weight:600; }}
QProgressBar {{ background-color:{c['progress']}; color:{c['text']}; border:1px solid {c['border']}; border-radius:4px; text-align:center; }}
QProgressBar::chunk {{ background-color:{c['primary']}; border-radius:3px; }}
QSlider::groove:horizontal {{ height:5px; background:{c['progress']}; border-radius:2px; }}
QSlider::sub-page:horizontal {{ background:{c['primary']}; border-radius:2px; }}
QSlider::handle:horizontal {{ width:14px; margin:-5px 0; background:{c['text']}; border:1px solid {c['border']}; border-radius:7px; }}
QCheckBox {{ spacing:6px; }}
QScrollArea#MainPageScroll {{ background:transparent; border:0; }}
QScrollBar:vertical {{ width:11px; background:{c['bg']}; margin:0; }}
QScrollBar:horizontal {{ height:11px; background:{c['bg']}; margin:0; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ min-height:24px; min-width:24px; background:{c['scroll']}; border-radius:4px; }}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{ background:{c['scroll_hover']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width:0; height:0; }}
"""


def _enemy_mini_stylesheet(dark: bool, opacity: int) -> str:
    """Mini 浮层仅淡化背景，文字与边框始终保持清晰。"""
    opacity = max(25, min(100, int(opacity)))
    bg_alpha = round(255 * opacity / 100)
    panel_alpha = min(255, bg_alpha + 18)
    alt_alpha = min(255, bg_alpha + 28)
    header_alpha = min(255, bg_alpha + 42)
    if dark:
        bg = (24, 25, 27)
        panel = (32, 34, 38)
        alternate = (45, 48, 53)
        header = (55, 59, 65)
        text = '#ffffff'
        muted = '#e1e7ef'
        border = 'rgba(220, 230, 242, 205)'
        grid = 'rgba(190, 203, 219, 150)'
        selection = 'rgba(55, 116, 205, 220)'
        progress = 'rgba(25, 27, 31, 205)'
        button = 'rgba(49, 53, 59, 225)'
    else:
        bg = (241, 244, 248)
        panel = (255, 255, 255)
        alternate = (224, 230, 237)
        header = (211, 219, 228)
        text = '#11151a'
        muted = '#252c34'
        border = 'rgba(32, 43, 56, 190)'
        grid = 'rgba(43, 55, 69, 135)'
        selection = 'rgba(87, 145, 225, 205)'
        progress = 'rgba(232, 236, 241, 220)'
        button = 'rgba(248, 249, 251, 235)'

    def rgba(rgb: tuple[int, int, int], alpha: int) -> str:
        return f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha})'

    return f"""
QWidget#EnemyMiniWindow {{
    background-color:{rgba(bg, bg_alpha)};
    border:2px solid {border};
}}
QWidget#EnemyMiniWindow QFrame#EnemyMiniToolbar {{
    background-color:{rgba(panel, panel_alpha)};
    border:1px solid {border};
    border-radius:5px;
}}
QWidget#EnemyMiniWindow QLabel {{
    background-color:transparent;
    color:{text};
    font-weight:600;
}}
QWidget#EnemyMiniWindow QLabel#EnemyMiniDragLabel {{
    color:{text};
    font-weight:700;
}}
QWidget#EnemyMiniWindow QTableWidget {{
    background-color:{rgba(panel, panel_alpha)};
    alternate-background-color:{rgba(alternate, alt_alpha)};
    color:{text};
    font-weight:600;
    gridline-color:{grid};
    border:2px solid {border};
    selection-background-color:{selection};
    selection-color:{text};
}}
QWidget#EnemyMiniWindow QTableWidget::item {{
    color:{text};
    padding:3px;
    border-bottom:1px solid {grid};
}}
QWidget#EnemyMiniWindow QHeaderView::section,
QWidget#EnemyMiniWindow QTableCornerButton::section {{
    background-color:{rgba(header, header_alpha)};
    color:{text};
    font-weight:700;
    border:0;
    border-right:1px solid {border};
    border-bottom:2px solid {border};
    padding:5px;
}}
QWidget#EnemyMiniWindow QProgressBar {{
    background-color:{progress};
    color:{text};
    font-weight:700;
    border:1px solid {border};
    border-radius:4px;
    text-align:center;
}}
QWidget#EnemyMiniWindow QProgressBar::chunk {{
    background-color:#3d83ff;
    border-radius:3px;
}}
QWidget#EnemyMiniWindow QPushButton {{
    background-color:{button};
    color:{text};
    font-weight:600;
    border:1px solid {border};
    border-radius:5px;
}}
QWidget#EnemyMiniWindow QScrollBar {{ color:{muted}; }}
"""


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
    """选择 ADB 程序和具体设备地址；两者共同决定内存读取目标。"""

    def __init__(self, parent=None, current_path: str = '',
                 current_serial: str = '') -> None:
        super().__init__(parent)
        self.setWindowTitle('选择 ADB')
        self.setMinimumWidth(700)
        self.probe_detail = ''

        layout = QVBoxLayout(self)
        intro = QLabel(
            '选择模拟器自带的 adb.exe，并指定与 MAA“连接地址”相同的设备地址。'
            '也可以先启动模拟器，再点击“自动探测运行中模拟器”。')
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

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel('设备地址：'))
        self.device_combo = QComboBox()
        self.device_combo.setEditable(True)
        self.device_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.device_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        device_edit = self.device_combo.lineEdit()
        if device_edit is not None:
            device_edit.setPlaceholderText('例如 127.0.0.1:16384（与 MAA 连接地址一致）')
            device_edit.setClearButtonEnabled(True)
        if current_serial:
            self.device_combo.addItem(current_serial)
        device_row.addWidget(self.device_combo, 1)
        self.btn_refresh_devices = QPushButton('刷新设备地址')
        self.btn_refresh_devices.clicked.connect(self._refresh_devices)
        device_row.addWidget(self.btn_refresh_devices)
        layout.addLayout(device_row)

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

    def selected_serial(self) -> str:
        return self.device_combo.currentText().strip()

    def _populate_devices(self, rows: list, preferred: str = '') -> list[str]:
        online = [str(row.get('serial') or '') for row in rows
                  if row.get('state') == 'device' and row.get('serial')]
        current = preferred or self.selected_serial()
        self.device_combo.clear()
        for serial in online:
            self.device_combo.addItem(serial)
        if current:
            if current not in online:
                self.device_combo.addItem(current)
            self.device_combo.setCurrentText(current)
        elif len(online) == 1:
            self.device_combo.setCurrentText(online[0])
        return online

    def _refresh_devices(self) -> None:
        path = self.selected_path()
        ok, detail = probe_adb_executable(path)
        if not ok:
            QMessageBox.warning(self, 'ADB 不可用', f'请先选择可用的 adb.exe：\n\n{detail}')
            return
        self.btn_refresh_devices.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            preferred = self.selected_serial()
            rows = query_adb_devices(
                path, connect_known=True, connect_serial=preferred)
            online = self._populate_devices(rows, preferred)
            all_text = ', '.join(
                f"{row['serial']}（{row['state']}）" for row in rows) or '无'
            if online:
                self.status.setStyleSheet('color:#58a66a;')
                self.status.setText(
                    f'ADB 可执行文件：{detail}\n已发现在线设备：{", ".join(online)}')
            else:
                self.status.setStyleSheet('color:#d07a7a;')
                self.status.setText(
                    f'ADB 可执行文件正常，但未发现在线设备。当前列表：{all_text}\n'
                    '请确认模拟器已启动，并核对 MAA 中显示的连接地址。')
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_refresh_devices.setEnabled(True)

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
            rows = query_adb_devices(
                self.selected_path(), connect_known=True,
                connect_serial=self.selected_serial())
            online = self._populate_devices(rows)
            if online:
                self.status.setText(
                    self.status.text() + f'\n在线设备：{", ".join(online)}')
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
        rows = query_adb_devices(
            path, connect_known=True, connect_serial=self.selected_serial())
        online = self._populate_devices(rows)
        serial = self.selected_serial()
        if not online:
            QMessageBox.warning(
                self, '未发现设备',
                'adb.exe 可以运行，但没有在线设备。\n\n'
                '请先启动模拟器，并确认 MAA 中的连接地址。')
            return
        if not serial:
            if len(online) == 1:
                serial = online[0]
                self.device_combo.setCurrentText(serial)
            else:
                QMessageBox.warning(
                    self, '请选择设备',
                    '当前存在多个在线 ADB 设备，请选择与 MAA“连接地址”相同的设备。')
                return
        if serial not in online:
            QMessageBox.warning(
                self, '设备不在线',
                f'设备 {serial} 当前不在线。\n\n在线设备：{", ".join(online)}')
            return
        self.probe_detail = f'{detail}\n目标设备：{serial}'
        super().accept()

def _format_game_time(value: object) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.3f}s"
    except (TypeError, ValueError):
        return str(value)


def _format_enemy_read_mode(snapshot: dict) -> str:
    """把扫描器发布的通道状态转成稳定、可读的界面文案。"""
    mode = snapshot.get('read_mode', '')
    backend = snapshot.get('read_backend', '')
    if mode == 'fast':
        if backend == 'srv':
            return '高速通道（memsrv）'
        if backend == 'sh':
            return 'TCP 兼容通道（shell）'
        return '高速通道（TCP）'
    if mode == 'slow':
        return '慢速兜底（ADB）'
    return '检测中'


class SectionFloatWindow(QDialog):
    """承载一个主页面模块的非模态独立窗口。"""
    dockRequested = Signal()
    closing = Signal()

    def __init__(self, title: str, style_source: QWidget | None = None) -> None:
        # 浮窗不能把主窗口设为 Qt parent，否则 Windows 会将其登记为主窗口的
        # owned window，主窗口最小化时系统也会连带隐藏浮窗。生命周期由
        # CollapsibleGroupBox._float_window 持有，并在主程序退出时主动停靠关闭。
        super().__init__(None, Qt.WindowType.Window)
        if style_source is not None:
            self.setWindowIcon(style_source.windowIcon())
        self.setWindowTitle(f'模块浮窗 · {title}')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        toolbar = QHBoxLayout()
        label = QLabel(title)
        label.setStyleSheet('font-weight:600;')
        toolbar.addWidget(label)
        toolbar.addStretch(1)
        dock = QPushButton('停靠回主界面')
        dock.setToolTip('把此模块放回主程序页面原来的位置')
        dock.clicked.connect(self.dockRequested)
        toolbar.addWidget(dock)
        root.addLayout(toolbar)
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        root.addLayout(self.content_layout, 1)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.closing.emit()
        super().closeEvent(event)


class CollapsibleGroupBox(QGroupBox):
    """可折叠、可独立浮窗并可无损停靠回原位的通用模块。"""
    collapsedChanged = Signal(bool)
    floatingChanged = Signal(bool)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._section_title = title
        self._float_window: SectionFloatWindow | None = None
        self._collapsed_before_float = False
        self._content = QWidget(self)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(6, 10, 6, 6)
        self._outer.setSpacing(0)
        self._floating_hint = QLabel('已在浮窗显示', self)
        self._floating_hint.setProperty('role', 'muted')
        self._floating_hint.hide()
        self.btn_float = QPushButton('浮窗', self)
        self.btn_float.setFixedSize(58, 24)
        self.btn_float.setToolTip('将此模块从主页面分离为独立窗口')
        self.btn_float.clicked.connect(self.float_content)
        self._outer.addWidget(self._content)
        self.setCheckable(True)
        self.setChecked(True)
        self.setToolTip("点击标题可收起或展开；点击“浮窗”可独立显示此模块")
        self.toggled.connect(self._on_toggled)

    @property
    def content_widget(self) -> QWidget:
        return self._content

    def setContentLayout(self, layout) -> None:
        self._content.setLayout(layout)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        margin = 7
        self.btn_float.move(
            max(margin, self.width() - self.btn_float.width() - margin), 1)
        self._floating_hint.adjustSize()
        self._floating_hint.move(
            max(margin, self.btn_float.x() - self._floating_hint.width() - 8),
            max(2, (self.btn_float.height() - self._floating_hint.height()) // 2))

    def is_collapsed(self) -> bool:
        return not self.isChecked()

    def set_collapsed(self, collapsed: bool) -> None:
        if self.is_floating():
            return
        self.setChecked(not collapsed)

    def is_floating(self) -> bool:
        return self._float_window is not None

    def float_content(self) -> None:
        if self._float_window is not None:
            self._float_window.show()
            self._float_window.raise_()
            self._float_window.activateWindow()
            return
        self._collapsed_before_float = self.is_collapsed()
        if self.is_collapsed():
            self.setChecked(True)
        window = SectionFloatWindow(self._section_title, self.window())
        window.dockRequested.connect(self.dock_content)
        window.closing.connect(lambda: self.dock_content(close_window=False))
        self._outer.removeWidget(self._content)
        self._content.setParent(window)
        window.content_layout.addWidget(self._content)
        self._content.show()
        self._float_window = window
        self.setCheckable(False)
        self._floating_hint.show()
        self.btn_float.setText('显示浮窗')
        self.btn_float.setToolTip('显示并激活此模块的独立窗口')
        self.setMaximumHeight(self.fontMetrics().height() + 28)
        preferred = self.size()
        window.resize(max(620, preferred.width()), max(260, preferred.height()))
        window.show()
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None and parent.layout() is not None:
            parent.layout().invalidate()
        self.floatingChanged.emit(True)

    def dock_content(self, close_window: bool = True) -> None:
        window = self._float_window
        if window is None:
            return
        self._float_window = None
        window.content_layout.removeWidget(self._content)
        self._content.setParent(self)
        self._outer.addWidget(self._content)
        self.setCheckable(True)
        self._floating_hint.hide()
        self.btn_float.setText('浮窗')
        self.btn_float.setToolTip('将此模块从主页面分离为独立窗口')
        self.setChecked(not self._collapsed_before_float)
        self._on_toggled(not self._collapsed_before_float)
        if close_window:
            window.close()
        self.updateGeometry()
        self.floatingChanged.emit(False)

    def _on_toggled(self, expanded: bool) -> None:
        if self.is_floating():
            return
        self._content.setVisible(expanded)
        # 隐藏内容后限制区块高度，避免 QScrollArea 继续为其保留空白。
        self.setMaximumHeight(16777215 if expanded else self.fontMetrics().height() + 28)
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None:
            parent.updateGeometry()
            if parent.layout() is not None:
                parent.layout().invalidate()
        self.collapsedChanged.emit(not expanded)


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
                _tlog("诊断 adb_serial =", mc.adb_serial or "(自动选择)")
                try:
                    _tlog("诊断 adb devices:",
                          mc.adb_host("devices", "-l", timeout=10).decode(errors="replace").strip().replace("\r", "").replace("\n", " | "))
                except Exception as ex:
                    _tlog("诊断 adb 检查失败:", f"{type(ex).__name__}: {ex}")
            pid = self.reader.connect()
            self.log.emit(
                f"ADB {self.reader.mc.adb_serial} / {self.reader.mc.package} / 游戏 PID = {pid}")
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

    def __init__(self, reader: EnemyReader, character_reader: CharacterReader | None = None,
                 interval: float = ENEMY_POLL_SEC) -> None:
        super().__init__()
        self.reader = reader
        self.character_reader = character_reader
        self.interval = interval
        self._detail_lock = threading.Lock()
        self._detail_addr = 0
        self._detail_due = 0.0
        self._detail_heavy_cache = None
        self._detail_loading = False
        self._detail_error = ''
        self._character_detail_lock = threading.Lock()
        self._character_detail_addr = 0
        self._character_detail_due = 0.0
        self._character_detail_cache = None
        self._character_detail_loading = False
        self._character_detail_error = ''
        self.track_unattributed_damage = False

    def set_track_unattributed_damage(self, enabled: bool) -> None:
        self.track_unattributed_damage = bool(enabled)

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
                        'special_shield': full.special_shield,
                        'special_shield_mask': full.special_shield_mask,
                        'special_shield_sources': list(full.special_shield_sources),
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
        if 'special_shield' in heavy:
            roster_enemy.special_shield = heavy['special_shield']
            roster_enemy.special_shield_mask = heavy.get('special_shield_mask', 0)
            roster_enemy.special_shield_sources = list(
                heavy.get('special_shield_sources', ()))
        snap['detail_enemy'] = roster_enemy
        if error:
            snap['detail_error'] = error

    def set_character_detail_target(self, addr: int = 0) -> None:
        with self._character_detail_lock:
            addr = int(addr or 0)
            if addr != self._character_detail_addr:
                self._character_detail_addr = addr
                self._character_detail_due = 0.0
                self._character_detail_cache = None
                self._character_detail_error = ''

    def _start_character_detail_refresh(self, addr: int) -> None:
        with self._character_detail_lock:
            if (self._character_detail_loading
                    or addr != self._character_detail_addr
                    or self.character_reader is None):
                return
            self._character_detail_loading = True

        def load() -> None:
            detail = None
            error = ''
            try:
                detail = self.character_reader.read_character_detail(addr)
                if detail is None:
                    error = '干员详情对象已失效。'
            except Exception as exc:
                error = f'干员详情刷新失败：{exc}'
            finally:
                with self._character_detail_lock:
                    if addr == self._character_detail_addr:
                        if detail is not None:
                            self._character_detail_cache = detail
                            self._character_detail_error = ''
                        elif error:
                            self._character_detail_error = error
                        self._character_detail_due = (
                            time.monotonic() + CHARACTER_DETAIL_FULL_SEC)
                    self._character_detail_loading = False

        threading.Thread(
            target=load, name='CharacterDetailRefresh', daemon=True).start()

    def _append_character_detail(self, snap: dict) -> None:
        with self._character_detail_lock:
            addr = self._character_detail_addr
            due = self._character_detail_due
        if not addr or not snap.get('character_ok'):
            return
        live = next((character for character in snap.get('characters', ())
                     if character.addr == addr), None)
        if live is None:
            snap['detail_character'] = None
            snap['character_detail_error'] = '干员已离场或对象已失效，已停止更新。'
            return
        if time.monotonic() >= due:
            self._start_character_detail_refresh(addr)
        with self._character_detail_lock:
            detail = self._character_detail_cache
            error = self._character_detail_error
        if detail is not None:
            live = CharacterReader.merge_detail(live, detail)
        else:
            snap['character_detail_loading'] = True
        snap['detail_character'] = live
        if error:
            snap['character_detail_error'] = error

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
                if self.character_reader is not None:
                    try:
                        char_snap = self.character_reader.poll_fast(
                            snap.get('enemies'), self.track_unattributed_damage)
                    except Exception as e:
                        char_snap = {
                            'ok': False, 'characters': [],
                            'msg': f'干员轮询出错: {e}', 'frame_ms': 0.0,
                        }
                    snap['character_ok'] = bool(char_snap.get('ok'))
                    snap['characters'] = list(char_snap.get('characters', ()))
                    snap['global_damage_summary'] = char_snap.get(
                        'global_damage_summary')
                    snap['character_msg'] = char_snap.get('msg', '')
                    snap['character_frame_ms'] = char_snap.get('frame_ms', 0.0)
                self._append_detail(snap)
                self._append_character_detail(snap)
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

    def __init__(self, adb_path: str, adb_serial: str = '') -> None:
        super().__init__()
        self.adb_path = adb_path
        self.adb_serial = adb_serial

    def run(self) -> None:
        try:
            mc = MemCore(adb_path=self.adb_path, adb_serial=self.adb_serial)
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

    def __init__(self, adb_path: str, adb_serial: str = '') -> None:
        super().__init__()
        self.adb_path = adb_path
        self.adb_serial = adb_serial

    def run(self) -> None:
        try:
            svc = RngService(backend='adb', adb_path=self.adb_path,
                             adb_serial=self.adb_serial,
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


class EnemyMiniWindow(QWidget):
    """置顶敌人表浮层。

    锁定后窗口继续整体穿透，让左键交给后方程序；Windows 低级鼠标钩子只在
    表格矩形内截获滚轮与右键，分别用于滚动和打开详情。
    """

    locked_wheel = Signal(int, int, int)       # global x, y, wheel delta
    locked_right_click = Signal(int, int)      # global x, y
    MAX_LOCKED_ROWS = 20

    def __init__(self, owner: 'CoachWindow', table: QTableWidget) -> None:
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(None, flags)
        self.owner = owner
        self.table = table
        self._locked = False
        self._restoring = False
        self._drag_offset = None
        self._unlocked_geometry = None
        self._locked_visible_rows = 0
        self._locked_table_rect = None
        self._mouse_hook_thread = None
        self._mouse_hook_thread_id = 0
        self._mouse_hook_proc = None
        self._mouse_hook_ready = threading.Event()
        self._mouse_hook_suspended = False
        self._app_filter_installed = False
        self.setObjectName('EnemyMiniWindow')
        # 使用逐像素透明背景，避免 setWindowOpacity 同时冲淡文字和表格线。
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle('敌人数据 · 迷你模式')
        self.setMinimumSize(620, 220)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)
        self.toolbar = QFrame()
        self.toolbar.setObjectName('EnemyMiniToolbar')
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(8, 4, 4, 4)
        toolbar_layout.setSpacing(7)

        self.drag_label = QLabel('敌人数据 · 拖动此处移动')
        self.drag_label.setObjectName('EnemyMiniDragLabel')
        self.drag_label.setToolTip('按住此处拖动浮层')
        self.drag_label.installEventFilter(self)
        toolbar_layout.addWidget(self.drag_label, 1)
        toolbar_layout.addWidget(QLabel('透明度'))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(25, 100)
        self.opacity_slider.setFixedWidth(150)
        opacity = int(owner._settings.value('enemy_mini/opacity', 78))
        self.opacity_slider.setValue(max(25, min(100, opacity)))
        self.opacity_slider.setToolTip('调整整个敌人浮层的透明度')
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        toolbar_layout.addWidget(self.opacity_slider)
        self.opacity_label = QLabel()
        self.opacity_label.setMinimumWidth(38)
        toolbar_layout.addWidget(self.opacity_label)
        self.btn_lock = QPushButton('锁定 (Alt+K)')
        self.btn_lock.setToolTip(
            '锁定后左键穿透；表格区域仍可滚轮浏览、右键打开详情；Alt+K 解锁')
        self.btn_lock.clicked.connect(lambda: self.set_locked(True))
        toolbar_layout.addWidget(self.btn_lock)
        self.btn_exit = QPushButton('退出迷你')
        self.btn_exit.clicked.connect(owner._exit_enemy_mini_mode)
        toolbar_layout.addWidget(self.btn_exit)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setToolTip('拖动调整浮层大小')
        toolbar_layout.addWidget(self.size_grip)
        root.addWidget(self.toolbar)
        root.addWidget(table, 1)

        self.locked_wheel.connect(self._on_locked_wheel)
        self.locked_right_click.connect(self._on_locked_right_click)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._app_filter_installed = True

        self._on_opacity_changed(self.opacity_slider.value())
        geometry = owner._settings.value('enemy_mini/geometry')
        if geometry and self.restoreGeometry(geometry):
            pass
        else:
            self.resize(1080, 420)
            center = owner.frameGeometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    @property
    def locked(self) -> bool:
        return self._locked

    def _on_opacity_changed(self, value: int) -> None:
        # 原生窗口始终完全不透明；透明度只由带 alpha 的背景色承担。
        self.setWindowOpacity(1.0)
        self.refresh_visual_style(value)
        self.opacity_label.setText(f'{value}%')
        self.owner._settings.setValue('enemy_mini/opacity', value)

    def refresh_visual_style(self, opacity: int | None = None) -> None:
        if opacity is None:
            opacity = self.opacity_slider.value()
        self.setStyleSheet(
            _enemy_mini_stylesheet(bool(self.owner._theme_dark), int(opacity)))

    def set_locked(self, locked: bool) -> None:
        locked = bool(locked)
        if locked == self._locked:
            return
        geometry = self.geometry()
        if locked:
            self._unlocked_geometry = geometry
        else:
            self._stop_locked_mouse_hook()
        self._locked = locked
        self.toolbar.setVisible(not locked)
        # WindowTransparentForInput 是窗口系统级穿透，不只是忽略 Qt 子控件事件。
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, locked)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, locked)
        self.show()
        if not locked and self._unlocked_geometry is not None:
            self.setGeometry(self._unlocked_geometry)
        else:
            self.setGeometry(geometry)
        if not locked:
            self.raise_()
            self.activateWindow()
        else:
            QTimer.singleShot(0, self._finish_locked_setup)
        QTimer.singleShot(0, self.owner._fit_enemy_columns)

    def _finish_locked_setup(self) -> None:
        if not self._locked:
            return
        self.sync_locked_size()
        self._update_locked_table_rect()
        self._start_locked_mouse_hook()

    def sync_locked_size(self) -> None:
        """按存活敌人行自动扩高，最多在视口中同时容纳 20 行。"""
        if not self._locked or not self.isVisible():
            return
        active_count = sum(
            getattr(enemy, 'lifecycle', 'active') == 'active'
            and bool(getattr(enemy, 'alive', False))
            for enemy in self.owner._enemy_last)
        if active_count:
            visible_rows = min(active_count, self.MAX_LOCKED_ROWS)
        else:
            visible_rows = min(max(1, self.table.rowCount()), self.MAX_LOCKED_ROWS)
        visible_rows = min(visible_rows, self.table.rowCount()) if self.table.rowCount() else 0
        self._locked_visible_rows = visible_rows

        margins = self.layout().contentsMargins()
        height = margins.top() + margins.bottom() + self.table.horizontalHeader().height()
        height += self.table.frameWidth() * 2 + 2
        height += sum(self.table.rowHeight(row) for row in range(visible_rows))
        if self.table.horizontalScrollBar().isVisible():
            height += self.table.horizontalScrollBar().sizeHint().height()
        target = max(self.minimumHeight(), height)
        available = self.screen().availableGeometry()
        target = min(target, available.height())
        if self.height() != target:
            top_left = self.frameGeometry().topLeft()
            self.resize(self.width(), target)
            x = min(max(top_left.x(), available.left()),
                    max(available.left(), available.right() - self.width() + 1))
            y = min(max(top_left.y(), available.top()),
                    max(available.top(), available.bottom() - self.height() + 1))
            self.move(x, y)
        self._update_locked_table_rect()

    def _update_locked_table_rect(self) -> None:
        if not self._locked or not self.table.isVisible():
            self._locked_table_rect = None
            return
        viewport = self.table.viewport()
        top_left = viewport.mapToGlobal(viewport.rect().topLeft())
        bottom_right = viewport.mapToGlobal(viewport.rect().bottomRight())
        self._locked_table_rect = (
            top_left.x(), top_left.y(), bottom_right.x(), bottom_right.y())

    def _point_in_locked_table(self, x: int, y: int) -> bool:
        rect = self._locked_table_rect
        return bool(rect and rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3])

    def _table_row_at_global(self, x: int, y: int) -> int:
        pos = self.table.viewport().mapFromGlobal(QPoint(x, y))
        if not self.table.viewport().rect().contains(pos):
            return -1
        return self.table.rowAt(pos.y())

    def _open_detail_at_global(self, x: int, y: int) -> None:
        row = self._table_row_at_global(x, y)
        if row >= 0:
            self.owner._open_enemy_detail_from_row(row)

    def _on_locked_wheel(self, x: int, y: int, delta: int) -> None:
        if not self._locked or not self._point_in_locked_table(x, y) or not delta:
            return
        bar = self.table.verticalScrollBar()
        notches = max(1, abs(delta) // 120)
        direction = -1 if delta > 0 else 1
        bar.setValue(bar.value() + direction * notches * 3)
        self._update_locked_table_rect()

    def _on_locked_right_click(self, x: int, y: int) -> None:
        if self._locked and self._point_in_locked_table(x, y):
            self._open_detail_at_global(x, y)

    def set_mouse_hook_suspended(self, suspended: bool) -> None:
        self._mouse_hook_suspended = bool(suspended)

    def _start_locked_mouse_hook(self) -> None:
        if (not self._locked or self._mouse_hook_thread is not None
                or sys.platform != 'win32'
                or QApplication.platformName().lower() == 'offscreen'):
            return
        self._mouse_hook_ready.clear()

        def run_hook():
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            class Point(ctypes.Structure):
                _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]

            class MouseData(ctypes.Structure):
                _fields_ = [
                    ('pt', Point), ('mouseData', ctypes.c_ulong),
                    ('flags', ctypes.c_ulong), ('time', ctypes.c_ulong),
                    ('dwExtraInfo', ctypes.c_size_t),
                ]

            proc_type = ctypes.WINFUNCTYPE(
                ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t)
            user32.SetWindowsHookExW.argtypes = [
                ctypes.c_int, proc_type, ctypes.c_void_p, ctypes.c_uint]
            user32.SetWindowsHookExW.restype = ctypes.c_void_p
            user32.CallNextHookEx.argtypes = [
                ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t]
            user32.CallNextHookEx.restype = ctypes.c_ssize_t
            user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
            user32.UnhookWindowsHookEx.restype = ctypes.c_bool
            kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p

            def callback(code, message, lparam):
                if code >= 0 and self._locked and not self._mouse_hook_suspended:
                    data = ctypes.cast(lparam, ctypes.POINTER(MouseData)).contents
                    x, y = int(data.pt.x), int(data.pt.y)
                    if self._point_in_locked_table(x, y):
                        if message == 0x020A:  # WM_MOUSEWHEEL
                            delta = ctypes.c_short((data.mouseData >> 16) & 0xFFFF).value
                            self.locked_wheel.emit(x, y, int(delta))
                            return 1
                        if message == 0x0205:  # WM_RBUTTONUP
                            self.locked_right_click.emit(x, y)
                            return 1
                        if message == 0x0204:  # WM_RBUTTONDOWN
                            return 1
                return user32.CallNextHookEx(None, code, message, lparam)

            self._mouse_hook_proc = proc_type(callback)
            self._mouse_hook_thread_id = int(kernel32.GetCurrentThreadId())
            module = kernel32.GetModuleHandleW(None)
            hook = user32.SetWindowsHookExW(14, self._mouse_hook_proc, module, 0)
            self._mouse_hook_ready.set()
            if not hook:
                self._mouse_hook_thread_id = 0
                return
            msg = wintypes.MSG()
            try:
                while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
            finally:
                user32.UnhookWindowsHookEx(hook)
                self._mouse_hook_thread_id = 0

        self._mouse_hook_thread = threading.Thread(
            target=run_hook, name='EnemyMiniMouseHook', daemon=True)
        self._mouse_hook_thread.start()
        self._mouse_hook_ready.wait(0.5)
        if not self._mouse_hook_thread.is_alive():
            self._mouse_hook_thread = None
            self._mouse_hook_proc = None
            self._mouse_hook_thread_id = 0

    def _stop_locked_mouse_hook(self) -> None:
        thread = self._mouse_hook_thread
        if thread is None:
            return
        thread_id = self._mouse_hook_thread_id
        if thread_id and sys.platform == 'win32':
            try:
                ctypes.windll.user32.PostThreadMessageW(thread_id, 0x0012, 0, 0)
            except Exception:
                pass
        thread.join(0.8)
        if thread.is_alive():
            # 保留回调引用，避免钩子仍在执行时被 GC；_locked=False 时它只透传。
            return
        self._mouse_hook_thread = None
        self._mouse_hook_proc = None
        self._mouse_hook_thread_id = 0

    def _shutdown_input(self) -> None:
        self._mouse_hook_suspended = True
        self._locked = False
        self._stop_locked_mouse_hook()
        if self._app_filter_installed:
            app = QApplication.instance()
            if app is not None:
                app.removeEventFilter(self)
            self._app_filter_installed = False

    def toggle_locked(self) -> None:
        self.set_locked(not self._locked)

    def eventFilter(self, watched, event):  # type: ignore[override]
        if watched is self.drag_label and not self._locked:
            if (event.type() == QEvent.Type.MouseButtonPress
                    and event.button() == Qt.MouseButton.LeftButton):
                self._drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft())
                return True
            if (event.type() == QEvent.Type.MouseMove
                    and self._drag_offset is not None
                    and event.buttons() & Qt.MouseButton.LeftButton):
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                return True
            if event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_offset = None
                return True
        if (not self._locked and event.type() == QEvent.Type.MouseButtonRelease
                and isinstance(watched, QWidget)
                and (watched is self.table or self.table.isAncestorOf(watched))):
            button = event.button()
            # 详情按钮自己的左键 clicked 已连接；右键和其他单元格的左右键在此统一处理。
            if button in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
                if button == Qt.MouseButton.LeftButton and isinstance(watched, QPushButton):
                    return super().eventFilter(watched, event)
                global_pos = event.globalPosition().toPoint()
                row = self._table_row_at_global(global_pos.x(), global_pos.y())
                if row >= 0:
                    QTimer.singleShot(0, lambda r=row: self.owner._open_enemy_detail_from_row(r))
                    event.accept()
                    return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_locked_table_rect()
        QTimer.singleShot(0, self.owner._fit_enemy_columns)

    def moveEvent(self, event) -> None:  # type: ignore[override]
        super().moveEvent(event)
        self._update_locked_table_rect()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if (event.key() == Qt.Key.Key_K
                and event.modifiers() & Qt.KeyboardModifier.AltModifier):
            self.toggle_locked()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape and not self._locked:
            self.owner._exit_enemy_mini_mode()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._shutdown_input()
        if self._restoring:
            event.accept()
            return
        event.ignore()
        QTimer.singleShot(0, self.owner._exit_enemy_mini_mode)


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
        # 干员与敌人共用 BattleController、UnitManager、MemCore 和高速 TCP 通道，
        # 不再进行第二次全内存定位。
        self._character_reader = CharacterReader(self._enemy_reader)
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
        self._enemy_mini: EnemyMiniWindow | None = None
        self._mini_hotkey_down = False
        self._mini_hotkey_timer = QTimer(self)
        self._mini_hotkey_timer.setInterval(40)
        self._mini_hotkey_timer.timeout.connect(self._poll_enemy_mini_hotkey)
        self._mini_hotkey_timer.start()
        self._enemy_visible_cols = load_visible_columns(
            self._settings, 'enemy_table/visible_columns')
        self._enemy_col_order = load_column_order(
            self._settings, 'enemy_table/column_order',
            [col['key'] for col in ENEMY_COLUMN_DEFS])
        self._character_last_render = 0.0
        self._character_frame_status_ts = 0.0
        self._character_frame_ms_sum = 0.0
        self._character_frame_ms_count = 0
        self._character_rows: dict[int, int] = {}
        self._character_bar_colors: dict[int, str] = {}
        self._character_skill_lines: dict[int, int] = {}
        self._character_dec = default_character_precision()
        self._character_last: list = []
        self._character_stats_history: list = []
        self._character_detail_dialog: CharacterDetailDialog | None = None
        self._global_damage_detail_dialog: GlobalDamageDetailDialog | None = None
        self._character_overview_dialog: CharacterOverviewDialog | None = None
        self._character_visible_cols = load_character_columns(
            self._settings, 'character_table/visible_columns')
        self._character_col_order = load_column_order(
            self._settings, 'character_table/column_order',
            [col['key'] for col in CHARACTER_COLUMN_DEFS])
        self._character_widths_fitted = False
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

        self._theme_dark = _system_prefers_dark()
        self._theme_timer = QTimer(self)
        self._theme_timer.setInterval(1500)
        self._theme_timer.timeout.connect(self._sync_system_theme)

        self._build_ui()
        app = QApplication.instance()
        if app is not None:
            try:
                app.styleHints().colorSchemeChanged.connect(
                    lambda _scheme: self._sync_system_theme())
            except (AttributeError, RuntimeError):
                pass
        self._theme_timer.start()
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
        self._page_widget = page
        self._page_layout = main
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(8)

        title_row = QHBoxLayout()
        self.page_title = QLabel("明日方舟游戏数据显示工具 · 桌面版 Made by Tim(321346659)")
        self.page_title.setObjectName('PageTitle')
        title_row.addWidget(self.page_title)
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
        sub.setProperty('role', 'muted')
        main.addWidget(sub)

        box_cfg = CollapsibleGroupBox("内存寻址（tools/timer）")
        self.box_cfg = box_cfg
        l_cfg = QHBoxLayout()
        box_cfg.setContentLayout(l_cfg)
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
        box_game = CollapsibleGroupBox("游戏状态 / 操作记录（tools/deploy_tracker）")
        self.box_game = box_game
        l_game = QHBoxLayout()
        box_game.setContentLayout(l_game)
        l_game.setContentsMargins(4, 4, 4, 4)
        l_game.setSpacing(10)

        # 左列: 时间/帧卡片上下排列
        left_col = QVBoxLayout()
        card_time_disp = QFrame()
        card_time_disp.setObjectName("GameTimeCard")
        ctd_l = QVBoxLayout(card_time_disp)
        ctd_l.setContentsMargins(16, 12, 16, 12)
        ctd_l.setSpacing(4)
        lbl_time_title = QLabel("游戏时间")
        lbl_time_title.setProperty('role', 'muted')
        lbl_time_title.setStyleSheet("font-size:12px; font-weight:600;")
        lbl_time_title.setAlignment(Qt.AlignCenter)
        ctd_l.addWidget(lbl_time_title)
        self.lbl_game_time_big = QLabel("—")
        self.lbl_game_time_big.setObjectName('GameTimeValue')
        self.lbl_game_time_big.setAlignment(Qt.AlignCenter)
        ctd_l.addWidget(self.lbl_game_time_big)
        left_col.addWidget(card_time_disp)

        card_frame_disp = QFrame()
        card_frame_disp.setObjectName("GameFrameCard")
        cfd_l = QVBoxLayout(card_frame_disp)
        cfd_l.setContentsMargins(16, 12, 16, 12)
        cfd_l.setSpacing(4)
        lbl_frame_title = QLabel("逻辑帧")
        lbl_frame_title.setProperty('role', 'muted')
        lbl_frame_title.setStyleSheet("font-size:12px; font-weight:600;")
        lbl_frame_title.setAlignment(Qt.AlignCenter)
        cfd_l.addWidget(lbl_frame_title)
        self.lbl_frame_big = QLabel("—")
        self.lbl_frame_big.setObjectName('GameFrameValue')
        self.lbl_frame_big.setAlignment(Qt.AlignCenter)
        cfd_l.addWidget(self.lbl_frame_big)
        left_col.addWidget(card_frame_disp)

        self.lbl_game = QLabel("正在等待实时刷新…")
        self.lbl_game.setWordWrap(True)
        self.lbl_game.setProperty('role', 'muted')
        self.lbl_game.setStyleSheet("font-size:11px;")
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
        self.lbl_deploy_status.setProperty('role', 'muted')
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
        box_enemy = CollapsibleGroupBox("敌人数据（tools/enemy_health）")
        self.box_enemy = box_enemy
        l_enemy = QVBoxLayout()
        box_enemy.setContentLayout(l_enemy)
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
        self.btn_enemy_fit.setToolTip(
            "按当前可见列和表格宽度智能排版；优先保证血量、损伤条完整显示，仍可拖动表头手调")
        self.btn_enemy_fit.clicked.connect(self._fit_enemy_columns)
        self._style_muted_button(self.btn_enemy_fit)
        self.btn_enemy_mini = QPushButton("迷你模式")
        self.btn_enemy_mini.setToolTip(
            "将实时敌人表显示为半透明置顶浮层；锁定后左键穿透，"
            "表格仍可滚轮浏览、右键查看详情；Alt+K 锁定/解锁")
        self.btn_enemy_mini.clicked.connect(self._enter_enemy_mini_mode)
        self._style_secondary_button(self.btn_enemy_mini)
        self.chk_enemy_hide_departed = QCheckBox("离场敌方不显示")
        self.chk_enemy_hide_departed.setChecked(True)
        self.chk_enemy_hide_departed.setToolTip("默认隐藏死亡、漏怪或其他原因离场的敌人；取消勾选可查看完整记录")
        self.chk_enemy_hide_departed.toggled.connect(self._on_enemy_departed_filter)
        row_btn.addWidget(self.btn_enemy_scan)
        row_btn.addWidget(self.btn_enemy_stop)
        row_btn.addWidget(self.btn_enemy_precision)
        row_btn.addWidget(self.btn_enemy_columns)
        row_btn.addWidget(self.btn_enemy_fit)
        row_btn.addWidget(self.btn_enemy_mini)
        row_btn.addWidget(self.chk_enemy_hide_departed)
        row_btn.addWidget(self.enemy_progress, 1)
        self.lbl_enemy_compact_game = QLabel("游戏时间：—\n逻辑帧：—")
        self.lbl_enemy_compact_game.setObjectName('EnemyCompactGameStatus')
        self.lbl_enemy_compact_game.setProperty('role', 'muted')
        self.lbl_enemy_compact_game.setMinimumWidth(145)
        self.lbl_enemy_compact_game.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_enemy_compact_game.hide()
        row_btn.addWidget(self.lbl_enemy_compact_game)
        l_enemy.addLayout(row_btn)
        self.lbl_enemy_status = QLabel("未开始扫描")
        self.lbl_enemy_status.setProperty('role', 'muted')
        l_enemy.addWidget(self.lbl_enemy_status)
        main.addWidget(box_enemy)

        # ---- 底部: 敌人信息表 ----
        box_table = CollapsibleGroupBox("敌人信息")
        self.box_table = box_table
        box_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        l_table = QVBoxLayout()
        box_table.setContentLayout(l_table)
        self._enemy_table_box = box_table
        self._enemy_table_host = box_table.content_widget
        self._enemy_table_layout = l_table
        self.enemy_table = QTableWidget(0, len(ENEMY_COLS))
        self.enemy_table.setHorizontalHeaderLabels(ENEMY_COLS)
        self.enemy_table.verticalHeader().setVisible(False)
        self.enemy_table.setSelectionMode(QTableWidget.NoSelection)
        self.enemy_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.enemy_table.setAlternatingRowColors(True)
        self.enemy_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        hdr = self.enemy_table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)   # 所有列宽均可拖动调整
        hdr.setStretchLastSection(False)  # 隐藏列会使“末列拉伸”失效；由智能布局分配全部空间
        hdr.setMinimumSectionSize(28)
        for i, w in enumerate(ENEMY_COL_WIDTHS):
            self.enemy_table.setColumnWidth(i, w)
        self._apply_enemy_column_visibility()
        self._apply_enemy_column_order()
        l_table.addWidget(self.enemy_table)
        main.addWidget(box_table, 1)

        # ---- 场上干员 / 召唤物（与敌人共用定位和高速读取通道） ----
        box_character = CollapsibleGroupBox("干员数据（tools/character_status）")
        self.box_character = box_character
        l_character = QVBoxLayout()
        box_character.setContentLayout(l_character)
        row_character = QHBoxLayout()
        self.btn_character_scan = QPushButton("扫描干员")
        self.btn_character_scan.setToolTip(
            "复用敌人扫描得到的 BattleController/UnitManager，不会再次全量扫描内存")
        self.btn_character_scan.clicked.connect(self._on_character_scan)
        self._style_primary_button(self.btn_character_scan)
        self.btn_character_stop = QPushButton("停止监控")
        self.btn_character_stop.setEnabled(False)
        self.btn_character_stop.clicked.connect(self._stop_enemy_poll)
        self._style_muted_button(self.btn_character_stop)
        self.btn_character_precision = QPushButton("小数位设置")
        self.btn_character_precision.clicked.connect(self._on_character_precision)
        self._style_muted_button(self.btn_character_precision)
        self.btn_character_columns = QPushButton("显示列")
        self.btn_character_columns.clicked.connect(self._on_character_columns)
        self._style_muted_button(self.btn_character_columns)
        self.btn_character_fit = QPushButton("列宽自适应")
        self.btn_character_fit.clicked.connect(self._fit_character_columns)
        self._style_muted_button(self.btn_character_fit)
        self.btn_character_overview = QPushButton("数据总览")
        self.btn_character_overview.clicked.connect(
            self._open_character_overview)
        self.btn_character_overview.setToolTip(
            "实时查看各干员总输出与治疗量占比饼图")
        self._style_muted_button(self.btn_character_overview)
        self.chk_character_tokens = QCheckBox("显示召唤物/装置")
        self.chk_character_tokens.setChecked(True)
        self.chk_character_tokens.setToolTip(
            "取消后只显示普通干员；友方召唤物和可部署装置仍可在详情中单独识别")
        self.chk_character_tokens.toggled.connect(self._on_character_filter)
        self.chk_unattributed_damage = QCheckBox("无来源总伤")
        self.chk_unattributed_damage.setChecked(False)
        self.chk_unattributed_damage.setToolTip(
            "从勾选时开始启用敌人生命高速差分，补充 BattleStats 不记录的无来源伤害；"
            "默认关闭以节省性能")
        self.chk_unattributed_damage.toggled.connect(
            self._on_unattributed_damage_tracking)
        for widget in (
                self.btn_character_scan, self.btn_character_stop,
                self.btn_character_precision, self.btn_character_columns,
                self.btn_character_fit, self.btn_character_overview,
                self.chk_character_tokens,
                self.chk_unattributed_damage):
            row_character.addWidget(widget)
        self.lbl_character_status = QLabel("未开始扫描")
        self.lbl_character_status.setProperty('role', 'muted')
        row_character.addWidget(self.lbl_character_status, 1)
        l_character.addLayout(row_character)
        main.addWidget(box_character)

        box_character_table = CollapsibleGroupBox("干员信息")
        self.box_character_table = box_character_table
        box_character_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        l_character_table = QVBoxLayout()
        box_character_table.setContentLayout(l_character_table)
        self.character_table = QTableWidget(0, len(CHARACTER_COLS))
        self.character_table.setHorizontalHeaderLabels(CHARACTER_COLS)
        self.character_table.verticalHeader().setVisible(False)
        self.character_table.setSelectionMode(QTableWidget.NoSelection)
        self.character_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.character_table.setAlternatingRowColors(True)
        self.character_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        character_header = self.character_table.horizontalHeader()
        character_header.setSectionResizeMode(QHeaderView.Interactive)
        character_header.setStretchLastSection(False)
        character_header.setMinimumSectionSize(28)
        for idx, width in enumerate(CHARACTER_COL_WIDTHS):
            self.character_table.setColumnWidth(idx, width)
        self._apply_character_column_visibility()
        self._apply_character_column_order()
        l_character_table.addWidget(self.character_table)
        main.addWidget(box_character_table, 1)

        # ---- 随机数追踪 (tools/ak_live_rng) ----
        box_rng = CollapsibleGroupBox("随机数追踪（tools/ak_live_rng）")
        self.box_rng = box_rng
        l_rng = QVBoxLayout()
        box_rng.setContentLayout(l_rng)
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
        self.lbl_rng_status.setProperty('role', 'muted')
        row_rng.addWidget(self.lbl_rng_status, 1)
        l_rng.addLayout(row_rng)
        self.lbl_rng_info = QLabel("—")
        self.lbl_rng_info.setProperty('role', 'primaryText')
        self.lbl_rng_info.setStyleSheet("font-family:Consolas,monospace;")
        l_rng.addWidget(self.lbl_rng_info)
        row_rng_tables = QHBoxLayout()
        pred_box = QVBoxLayout()
        lbl_pred = QLabel("未来预测 (下一发在最上)")
        lbl_pred.setProperty('role', 'muted')
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
        lbl_hist.setProperty('role', 'muted')
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

        self._collapsible_sections = {
            'timer': box_cfg,
            'game': box_game,
            'enemy': box_enemy,
            'enemy_table': box_table,
            'character': box_character,
            'character_table': box_character_table,
            'rng': box_rng,
        }
        box_game.collapsedChanged.connect(self._on_game_section_collapsed)
        box_table.floatingChanged.connect(
            lambda _floating: QTimer.singleShot(0, self._fit_enemy_columns))
        box_character_table.floatingChanged.connect(
            lambda _floating: QTimer.singleShot(0, self._fit_character_columns))

        self._apply_theme(self._theme_dark, force=True)

    def _on_game_section_collapsed(self, collapsed: bool) -> None:
        """游戏状态隐藏时，把关键时间信息迁移到敌人控制栏。"""
        self.lbl_enemy_compact_game.setVisible(collapsed)
        self._page_layout.invalidate()
        self._page_widget.updateGeometry()

    def _module_dialog_parent(self, section: CollapsibleGroupBox) -> QWidget:
        """让模块内弹出的设置/详情窗口跟随对应浮窗，避免被主窗口遮挡。"""
        return section._float_window or self

    def _style_primary_button(self, btn: QPushButton) -> None:
        btn.setMinimumHeight(34)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setProperty('buttonRole', 'primary')

    def _style_secondary_button(self, btn: QPushButton) -> None:
        btn.setMinimumHeight(34)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setProperty('buttonRole', 'secondary')

    def _style_muted_button(self, btn: QPushButton) -> None:
        btn.setMinimumHeight(34)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setProperty('buttonRole', 'muted')

    def _style_toggle_exec_button(self, btn: QPushButton, checked: bool) -> None:
        btn.setMinimumHeight(34)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        btn.setProperty('buttonRole', 'toggleOn' if checked else 'toggleOff')
        style = btn.style()
        style.unpolish(btn)
        style.polish(btn)
        btn.update()

    def _apply_theme(self, dark: bool, force: bool = False) -> None:
        dark = bool(dark)
        if not force and self._theme_dark == dark:
            return
        self._theme_dark = dark
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(_theme_stylesheet(dark))
        if self._enemy_mini is not None:
            self._enemy_mini.refresh_visual_style()

    def _sync_system_theme(self) -> None:
        self._apply_theme(_system_prefers_dark())

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
        self._mini_hotkey_timer.stop()
        if self._enemy_mini is not None:
            self._enemy_mini._restoring = True
            self._enemy_mini.close()
            self._enemy_mini = None
        for section in getattr(self, '_collapsible_sections', {}).values():
            section.dock_content()
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
        serial = self._enemy_reader.mc.adb_serial or '自动选择'
        if path and os.path.isfile(path):
            self.btn_select_adb.setText('选择 ADB（已设置）')
            self.btn_select_adb.setToolTip(
                f'当前 ADB：\n{path}\n\n目标设备：{serial}\n\n点击可重新选择')
        else:
            self.btn_select_adb.setText('选择 ADB')
            self.btn_select_adb.setToolTip('选择模拟器安装目录中的 adb.exe')

    def _adb_scan_is_running(self) -> bool:
        return any(worker is not None and worker.isRunning() for worker in (
            self._enemy_scan, self._rng_worker, self._deploy_scan))

    def _activate_adb_path(self, path: str, serial: str = '') -> None:
        """停止旧连接并让敌人、RNG、操作记录统一改用新 ADB。"""
        self._stop_enemy_poll()
        self._on_rng_stop()
        self._stop_deploy_poll()
        if self._deploy_reader is not None:
            self._deploy_reader.close()
            self._deploy_reader = None
        self._enemy_reader.close()
        self._enemy_reader = EnemyReader(
            adb_path=path, adb_serial=serial, log=_tlog)
        self._character_reader = CharacterReader(self._enemy_reader)

        if self._enemy_detail_dialog is not None:
            self._enemy_detail_dialog.close()
            self._enemy_detail_dialog = None
        if self._character_detail_dialog is not None:
            self._character_detail_dialog.close()
            self._character_detail_dialog = None
        if self._global_damage_detail_dialog is not None:
            self._global_damage_detail_dialog.close()
            self._global_damage_detail_dialog = None
        if self._character_overview_dialog is not None:
            self._character_overview_dialog.close()
            self._character_overview_dialog = None
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
        self.character_table.setRowCount(0)
        self._character_last.clear()
        self._character_rows.clear()
        self._character_bar_colors.clear()
        self._character_skill_lines.clear()
        self._character_stats_history.clear()
        self.btn_character_scan.setText('扫描干员')
        self.lbl_character_status.setText('ADB 已切换，请重新扫描')

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
        current_serial = self._enemy_reader.mc.adb_serial or ''
        dialog = AdbSelectionDialog(
            self, current if os.path.isfile(current) else '', current_serial)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        path = dialog.selected_path()
        serial = dialog.selected_serial()
        detail = dialog.probe_detail
        persisted = save_adb_config(path, serial)
        self._activate_adb_path(path, serial)
        if show_success:
            suffix = '' if persisted else '\n\n警告：配置文件写入失败，下次启动需要重新选择。'
            QMessageBox.information(
                self, 'ADB 已选择',
                f'已切换到：\n{path}\n设备地址：{serial}\n\n{detail}\n\n'
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

    def _enter_enemy_mini_mode(self) -> None:
        if self._enemy_mini is not None:
            self._enemy_mini.show()
            self._enemy_mini.raise_()
            if not self._enemy_mini.locked:
                self._enemy_mini.activateWindow()
            return
        self._enemy_table_layout.removeWidget(self.enemy_table)
        mini = EnemyMiniWindow(self, self.enemy_table)
        self._enemy_mini = mini
        mini.show()
        mini.raise_()
        mini.activateWindow()
        self.hide()
        QTimer.singleShot(0, self._fit_enemy_columns)

    def _exit_enemy_mini_mode(self) -> None:
        mini = self._enemy_mini
        if mini is None:
            return
        self._settings.setValue('enemy_mini/geometry', mini.saveGeometry())
        mini._restoring = True
        mini.hide()
        layout = mini.layout()
        if layout is not None:
            layout.removeWidget(self.enemy_table)
        self.enemy_table.setParent(self._enemy_table_host)
        self._enemy_table_layout.addWidget(self.enemy_table)
        self._enemy_mini = None
        mini.close()
        mini.deleteLater()
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(0, self._fit_enemy_columns)

    def _poll_enemy_mini_hotkey(self) -> None:
        """全局轮询 Alt+K；锁定浮层无法获取焦点，因此不能只依赖 Qt Shortcut。"""
        if self._enemy_mini is None or sys.platform != 'win32':
            self._mini_hotkey_down = False
            return
        try:
            user32 = ctypes.windll.user32
            alt_down = bool(user32.GetAsyncKeyState(0x12) & 0x8000)  # VK_MENU
            k_down = bool(user32.GetAsyncKeyState(0x4B) & 0x8000)    # K
            down = alt_down and k_down
        except Exception:
            down = False
        if down and not self._mini_hotkey_down:
            self._enemy_mini.toggle_locked()
        self._mini_hotkey_down = down

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
        self.character_table.setRowCount(0)
        self._character_last.clear()
        self._character_rows.clear()
        self._character_bar_colors.clear()
        self._character_skill_lines.clear()
        self._character_stats_history.clear()
        self._character_frame_ms_sum = 0.0
        self._character_frame_ms_count = 0
        self.btn_enemy_scan.setEnabled(False)
        self.btn_character_scan.setEnabled(False)
        self.lbl_character_status.setText('等待共享定位完成 ...')
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
        self.btn_character_scan.setEnabled(True)
        self.btn_enemy_scan.setText('重新扫描')
        if ok:
            self.enemy_progress.setValue(100)
            self.enemy_progress.setFormat('就绪')
            char_ok = self._character_reader.bootstrap()
            self.btn_character_scan.setText('重新扫描')
            self.lbl_character_status.setText(
                '共享定位完成，准备读取场上干员' if char_ok
                else '共享定位完成，正在等待干员容器可读')
            self._start_enemy_poll()
        else:
            self.enemy_progress.setFormat('定位失败')
            self.lbl_character_status.setText('共享定位失败')

    def _on_character_scan(self) -> None:
        """干员读取复用敌人定位；按钮用于首次定位或强制刷新整条共享链。"""
        self._on_enemy_scan()

    def _start_enemy_poll(self) -> None:
        self._stop_enemy_poll()
        self._enemy_poll = EnemyPollWorker(
            self._enemy_reader, self._character_reader)
        self._enemy_poll.set_track_unattributed_damage(
            self.chk_unattributed_damage.isChecked())
        self._enemy_poll.snapshot.connect(self._on_enemy_snapshot)
        self._enemy_poll.start()
        self.btn_enemy_stop.setEnabled(True)
        self.btn_character_stop.setEnabled(True)
        self.lbl_enemy_status.setText('实时监控中 ...')
        self.lbl_character_status.setText('实时监控中 ...')

    def _stop_enemy_poll(self) -> None:
        if self._enemy_poll:
            self._enemy_poll.requestInterruption()
            self._enemy_poll.wait(3000)
            self._enemy_poll = None
        self.btn_enemy_stop.setEnabled(False)
        if hasattr(self, 'btn_character_stop'):
            self.btn_character_stop.setEnabled(False)

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
        self._rng_worker = RngScanWorker(
            self._enemy_reader.mc.adb_path, self._enemy_reader.mc.adb_serial)
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
        self._deploy_scan = DeployScanWorker(
            self._enemy_reader.mc.adb_path, self._enemy_reader.mc.adb_serial)
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
        if snap.get('ok'):
            self._enemy_last_render = now
        detail_dialog = self._enemy_detail_dialog
        if detail_dialog is not None and 'detail_enemy' in snap:
            detail_enemy = snap.get('detail_enemy')
            if (detail_enemy is not None
                    and detail_enemy.addr == detail_dialog.enemy.addr):
                detail_dialog.update_enemy(detail_enemy)
            elif snap.get('detail_error'):
                detail_dialog.set_live_error(snap['detail_error'])
        character_dialog = self._character_detail_dialog
        if character_dialog is not None and 'detail_character' in snap:
            detail_character = snap.get('detail_character')
            if (detail_character is not None
                    and detail_character.addr == character_dialog.character.addr):
                character_dialog.update_character(detail_character)
                if snap.get('character_detail_loading'):
                    character_dialog.live_status.setText(
                        '动态数据实时更新中，正在首次读取完整 Buff / 天赋详情 ...')
                    character_dialog.live_status.setStyleSheet('color:#888888;')
            elif snap.get('character_detail_error'):
                character_dialog.set_live_error(snap['character_detail_error'])
        global_damage_dialog = self._global_damage_detail_dialog
        if global_damage_dialog is not None:
            summary = snap.get('global_damage_summary')
            if summary is not None:
                global_damage_dialog.update_summary(summary)
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
        read_mode = _format_enemy_read_mode(snap)
        text = (f"读取: {read_mode}   状态: {st}   倍速: {spd} (x{snap['time_scale']:g})   "
                f"战斗时间: {t // 60:02d}:{t % 60:02d}   {total_text}"
                + self._frame_txt)
        if snap.get('msg'):
            text += f"   ({snap['msg']})"
        if snap.get('ok'):
            self.lbl_enemy_status.setText(text)
            self._render_enemy_table(snap['enemies'])
        else:
            # 读取失败的帧没有任何真实数据: 不清空表格 (内存中敌人仍在,
            # 清空既是假信息又会引起闪烁), 只在状态栏报告, 下帧成功即恢复。
            self.lbl_enemy_status.setText(
                f"读取: {read_mode}   {snap.get('msg') or '数据链失效'}")
        characters = list(snap.get('characters', ()))
        history = snap.get('character_stats_history')
        if history is not None:
            self._character_stats_history = list(history)
        overview_dialog = self._character_overview_dialog
        if overview_dialog is not None:
            overview_dialog.update_characters(
                characters + self._character_stats_history)
        if snap.get('character_ok'):
            char_ms = float(snap.get('character_frame_ms', 0.0) or 0.0)
            if char_ms > 0:
                self._character_frame_ms_sum += char_ms
                self._character_frame_ms_count += 1
            # 帧耗时本身会随每批读取轻微抖动，只按 0.5 秒采样更新标签；
            # 表格中的生命、技力和伤害统计仍保持原本的高频刷新。
            if now - self._character_frame_status_ts >= 0.5:
                self._character_frame_status_ts = now
                real_characters = [character for character in characters
                                   if not getattr(
                                       character, 'is_global_damage_summary', False)]
                ordinary = sum(not character.is_token
                               for character in real_characters)
                tokens = len(real_characters) - ordinary
                average_ms = (self._character_frame_ms_sum
                              / self._character_frame_ms_count
                              if self._character_frame_ms_count else 0.0)
                self._character_frame_ms_sum = 0.0
                self._character_frame_ms_count = 0
                self.lbl_character_status.setText(
                    f'实时监控中  干员 {ordinary} / 召唤物与装置 {tokens}'
                    + (f'  {average_ms:.1f}ms/帧' if average_ms else ''))
            self._render_character_table(characters)
        else:
            self.lbl_character_status.setText(
                snap.get('character_msg') or '干员容器暂不可读')

    def _render_enemy_table(self, enemies) -> None:
        self._enemy_last = enemies
        enemies = visible_enemy_rows(
            enemies, hide_departed=self.chk_enemy_hide_departed.isChecked())
        tbl = self.enemy_table
        fit_after_render = bool(enemies and not self._widths_fitted)
        desired_order = [getattr(e, 'roster_id', 0) or e.addr for e in enemies]
        current_order = [
            tbl.item(row, ENEMY_COLUMN_INDEX['row']).data(Qt.UserRole)
            for row in range(tbl.rowCount())
            if tbl.item(row, ENEMY_COLUMN_INDEX['row']) is not None
        ]
        # 已有未出场敌人变为存活、或动态召唤加入时，真正重排物理行。
        # 只在顺序变化的那一帧重建，稳定状态下仍保持逐单元格增量刷新。
        if current_order and current_order != desired_order:
            tbl.setRowCount(0)
            self._enemy_rows.clear()
            self._enemy_row_lifecycle.clear()
            self._enemy_row_spawn_wait.clear()
            self._bar_colors.clear()
            self._skill_lines.clear()
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
        if fit_after_render:
            self._widths_fitted = True
            self._fit_enemy_columns()
        mini = self._enemy_mini
        if mini is not None and mini.locked:
            mini.sync_locked_size()

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
            self._module_dialog_parent(self.box_enemy),
            self._enemy_dec, self._enemy_visible_cols)
        if dlg.exec() == QDialog.Accepted:
            self._enemy_dec.update(dlg.values())
            self._widths_fitted = False
            self._render_enemy_table(self._enemy_last)   # 立即按新精度重绘
            if not self._enemy_last:
                self._fit_enemy_columns()

    def _apply_enemy_column_visibility(self) -> None:
        if not hasattr(self, 'enemy_table'):
            return
        for idx, col in enumerate(ENEMY_COLUMN_DEFS):
            self.enemy_table.setColumnHidden(idx, col['key'] not in self._enemy_visible_cols)

    def _apply_enemy_column_order(self) -> None:
        if not hasattr(self, 'enemy_table'):
            return
        apply_column_order(
            self.enemy_table, self._enemy_col_order, ENEMY_COLUMN_INDEX)

    def _fit_enemy_columns(self) -> None:
        """按当前可见内容测宽并填满视口，保护进度条文字等 cellWidget 内容。"""
        if not hasattr(self, 'enemy_table'):
            return
        tbl = self.enemy_table
        visible = [
            idx for idx, col in enumerate(ENEMY_COLUMN_DEFS)
            if not tbl.isColumnHidden(idx) and col['key'] in self._enemy_visible_cols
        ]
        if not visible:
            return

        header_metrics = tbl.horizontalHeader().fontMetrics()
        cell_metrics = tbl.fontMetrics()
        # 剩余空间优先分给这些信息列；内容过宽时除血量外均可压到可读下限。
        expanding_keys = {
            'name', 'code', 'eid', 'abnormal_status', 'immune_status',
            'skill', 'spawn_wait',
        }
        minimum_by_key = {
            'row': 38, 'name': 64, 'code': 56, 'eid': 105, 'hp': 175,
            'pos': 92, 'action_state': 66, 'abnormal_status': 82,
            'immune_status': 82, 'skill': 72, 'life_status': 66,
            'spawn_wait': 72, 'detail': 62,
            'ep_sanity': 170, 'ep_water': 170, 'ep_fire': 170,
            'ep_dark': 170, 'ep_anger': 170,
        }
        maximum_by_key = {
            'row': 46, 'name': 190, 'code': 90, 'eid': 240, 'hp': 245,
            'pos': 135, 'action_state': 100, 'abnormal_status': 240,
            'immune_status': 240, 'skill': 260, 'life_status': 100,
            'spawn_wait': 280, 'detail': 78,
            'ep_sanity': 220, 'ep_water': 220, 'ep_fire': 220,
            'ep_dark': 220, 'ep_anger': 220,
        }

        preferred = {}
        minimum = {}
        for idx in visible:
            col = ENEMY_COLUMN_DEFS[idx]
            key = col['key']
            header_width = header_metrics.horizontalAdvance(col['label']) + 18
            if key.startswith('attr_'):
                min_width = 64 if key == f'attr_{enemy_gs.AttributeType.MAGIC_RESISTANCE}' else 58
                max_width = 115
            else:
                min_width = minimum_by_key.get(key, 58)
                max_width = maximum_by_key.get(key, 155)
            content_width = header_width
            for row in range(tbl.rowCount()):
                if key == 'hp':
                    widget = tbl.cellWidget(row, idx)
                    text = widget.format().replace('%p%', '100%') if widget else ''
                elif key == 'detail':
                    widget = tbl.cellWidget(row, idx)
                    text = widget.text() if isinstance(widget, QPushButton) else '详情'
                else:
                    item = tbl.item(row, idx)
                    text = item.text() if item is not None else ''
                for line in str(text).splitlines() or ('',):
                    content_width = max(
                        content_width, cell_metrics.horizontalAdvance(line) +
                        (26 if key == 'hp' else 18))
            preferred[idx] = max(min_width, min(content_width, max_width))
            minimum[idx] = min_width

        viewport_width = max(100, tbl.viewport().width() - 2)
        total = sum(preferred.values())
        expanding = [idx for idx in visible
                     if ENEMY_COLUMN_DEFS[idx]['key'] in expanding_keys]
        shrinkable = [idx for idx in visible
                      if ENEMY_COLUMN_DEFS[idx]['key'] != 'hp']

        # 内容过宽时只压缩说明性长文本列；血量和损伤条保持完整，必要时出现横向滚动条。
        if total > viewport_width and shrinkable:
            overflow = total - viewport_width
            capacities = {idx: max(0, preferred[idx] - minimum[idx]) for idx in shrinkable}
            capacity = sum(capacities.values())
            if capacity:
                shrink = min(overflow, capacity)
                used = 0
                for pos, idx in enumerate(shrinkable):
                    remaining = max(0, shrink - used)
                    if pos == len(shrinkable) - 1:
                        amount = min(capacities[idx], remaining)
                    else:
                        amount = min(
                            capacities[idx], remaining,
                            round(shrink * capacities[idx] / capacity))
                    preferred[idx] -= amount
                    used += amount
                # 舍入造成的少量余量继续从仍可收缩的列中扣除。
                remainder = shrink - used
                for idx in shrinkable:
                    if remainder <= 0:
                        break
                    amount = min(remainder, preferred[idx] - minimum[idx])
                    preferred[idx] -= amount
                    remainder -= amount

        # 内容不足时把全部剩余空间平均分配给信息列，不再留下大片空白。
        total = sum(preferred.values())
        if total < viewport_width:
            expand = expanding or [visible[-1]]
            spare = viewport_width - total
            each, remainder = divmod(spare, len(expand))
            for pos, idx in enumerate(expand):
                preferred[idx] += each + (1 if pos < remainder else 0)

        tbl.setUpdatesEnabled(False)
        try:
            for idx in visible:
                tbl.setColumnWidth(idx, preferred[idx])
        finally:
            tbl.setUpdatesEnabled(True)
        self._widths_fitted = True

    def _on_enemy_columns(self) -> None:
        dlg = EnemyColumnDialog(
            self._module_dialog_parent(self.box_enemy), self._enemy_visible_cols,
            self._enemy_col_order)
        if dlg.exec() != QDialog.Accepted:
            return
        self._enemy_visible_cols = dlg.values()
        # 可见列按对话框中的拖动顺序；隐藏列保持原相对顺序附后
        self._enemy_col_order = dlg.ordered_keys() + [
            key for key in self._enemy_col_order
            if key not in self._enemy_visible_cols]
        save_visible_columns(
            self._settings, 'enemy_table/visible_columns', self._enemy_visible_cols)
        save_column_order(
            self._settings, 'enemy_table/column_order', self._enemy_col_order)
        self._apply_enemy_column_visibility()
        self._apply_enemy_column_order()
        self._widths_fitted = False
        self._render_enemy_table(self._enemy_last)
        if not self._enemy_last:
            self._fit_enemy_columns()

    def _open_enemy_detail_from_row(self, row: int) -> None:
        if not (0 <= row < self.enemy_table.rowCount()):
            return
        item = self.enemy_table.item(row, ENEMY_COLUMN_INDEX['row'])
        roster_id = item.data(Qt.UserRole) if item is not None else None
        if roster_id is None:
            return
        enemy = next((entry for entry in self._enemy_last
                      if (getattr(entry, 'roster_id', 0) or entry.addr) == roster_id), None)
        if enemy is None or getattr(enemy, 'lifecycle', 'active') == 'pending':
            return
        self._open_enemy_detail(roster_id)

    def _open_enemy_detail(self, roster_id: int) -> None:
        # 用主表最近快照立即打开，完整 Buff/关卡效果由轮询线程异步补全并持续刷新。
        enemy = next((item for item in self._enemy_last
                      if (getattr(item, 'roster_id', 0) or item.addr) == roster_id), None)
        if enemy is None:
            QMessageBox.information(self, '敌人详情', '该敌人已退场或对象已失效。')
            return
        mini = self._enemy_mini
        dialog = EnemyDetailDialog(
            mini or self._module_dialog_parent(self.box_table), enemy)
        self._enemy_detail_dialog = dialog
        poll = self._enemy_poll
        lifecycle = getattr(enemy, 'lifecycle', 'active')
        if lifecycle == 'departed':
            dialog.set_live_error('敌人已离场，显示最后一次记录。')
        elif poll is not None and enemy.addr:
            poll.set_detail_target(enemy.addr)
        if mini is not None:
            mini.set_mouse_hook_suspended(True)
        try:
            dialog.exec()
        finally:
            if mini is self._enemy_mini:
                mini.set_mouse_hook_suspended(False)
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
            text = str(text)
            it.setText(text)
            it.setToolTip(text)
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
            bar.setFormat(f'{e.hp:.{d["hp"]}f}/{e.max_hp:.{d["hp"]}f}')
        else:
            # 颜色和填充比例已经表达百分比；紧凑文本优先完整显示精确生命值。
            bar.setFormat(f'{e.hp:.{d["hp"]}f}/{e.max_hp:.{d["hp"]}f}')
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

    # ================= 场上干员数据 =================

    def _filtered_characters(self, characters):
        if self.chk_character_tokens.isChecked():
            return list(characters)
        return [character for character in characters
                if (not character.is_token
                    or getattr(character, 'is_global_damage_summary', False))]

    def _render_character_table(self, characters) -> None:
        self._character_last = list(characters)
        characters = self._filtered_characters(characters)
        tbl = self.character_table
        desired = [character.addr for character in characters]
        current = [
            tbl.item(row, CHARACTER_COLUMN_INDEX['row']).data(Qt.UserRole)
            for row in range(tbl.rowCount())
            if tbl.item(row, CHARACTER_COLUMN_INDEX['row']) is not None
        ]
        if current != desired:
            tbl.setRowCount(0)
            self._character_rows.clear()
            self._character_bar_colors.clear()
            self._character_skill_lines.clear()
        fit_after = bool(characters and not self._character_widths_fitted)
        tbl.setUpdatesEnabled(False)
        try:
            for row, character in enumerate(characters):
                if row >= tbl.rowCount():
                    tbl.insertRow(row)
                    self._make_character_row(row, character.addr)
                self._character_rows[character.addr] = row
                self._update_character_row(row, character)
            while tbl.rowCount() > len(characters):
                tbl.removeRow(tbl.rowCount() - 1)
        finally:
            tbl.setUpdatesEnabled(True)
        if fit_after:
            self._fit_character_columns()

    def _make_character_row(self, row: int, addr: int) -> None:
        tbl = self.character_table
        hp_col = CHARACTER_COLUMN_INDEX['hp']
        sp_col = CHARACTER_COLUMN_INDEX['sp']
        detail_col = CHARACTER_COLUMN_INDEX['detail']
        for column in range(len(CHARACTER_COLS)):
            if column not in (hp_col, sp_col, detail_col):
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignCenter)
                tbl.setItem(row, column, item)
        tbl.item(row, CHARACTER_COLUMN_INDEX['row']).setData(Qt.UserRole, addr)
        for key in ('name', 'cid', 'abnormal_status', 'skill'):
            item = tbl.item(row, CHARACTER_COLUMN_INDEX[key])
            if item is not None:
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hp_bar = QProgressBar()
        hp_bar.setTextVisible(True)
        tbl.setCellWidget(row, hp_col, hp_bar)
        sp_bar = QProgressBar()
        sp_bar.setTextVisible(True)
        tbl.setCellWidget(row, sp_col, sp_bar)
        detail = QPushButton('详情')
        if addr < 0:
            detail.setToolTip('显示全局总伤、可归属伤害与全部无来源/未归属伤害')
        else:
            detail.setToolTip('显示该干员/召唤物的完整属性、状态、技能、Buff、天赋与元素损伤')
        detail.clicked.connect(
            lambda _checked=False, target=addr: self._open_character_detail(target))
        tbl.setCellWidget(row, detail_col, detail)

    def _update_character_row(self, row: int, character) -> None:
        tbl = self.character_table
        decimals = self._character_dec

        for col in CHARACTER_COLUMN_DEFS:
            key = col['key']
            if key in ('hp', 'sp', 'detail'):
                continue
            item = tbl.item(row, CHARACTER_COLUMN_INDEX[key])
            if item is None:
                continue
            text = str(format_character_column(key, character, decimals, row))
            item.setText(text)
            item.setToolTip(text)

        hp_bar = tbl.cellWidget(row, CHARACTER_COLUMN_INDEX['hp'])
        sp_bar = tbl.cellWidget(row, CHARACTER_COLUMN_INDEX['sp'])
        if getattr(character, 'is_global_damage_summary', False):
            hp_bar.setRange(0, 1)
            hp_bar.setValue(0)
            hp_bar.setFormat('-')
            hp_bar.setStyleSheet(
                'QProgressBar::chunk { background-color: #777777; }')
            sp_bar.setRange(0, 1)
            sp_bar.setValue(0)
            sp_bar.setFormat('-')
            sp_bar.setStyleSheet(
                'QProgressBar::chunk { background-color: #777777; }')
            return
        hp_max = max(1, int(character.max_hp))
        hp_bar.setMaximum(hp_max)
        hp_bar.setValue(max(0, min(hp_max, int(character.hp))))
        hp_bar.setFormat(
            f'{character.hp:.{decimals["hp"]}f}/{character.max_hp:.{decimals["hp"]}f}')
        hp_ratio = character.hp / character.max_hp if character.max_hp > 0 else 0
        color = '#5cb85c' if hp_ratio > 0.5 else ('#f0ad4e' if hp_ratio > 0.2 else '#d9534f')
        if not character.alive:
            color = '#888888'
        if self._character_bar_colors.get(character.addr) != color:
            self._character_bar_colors[character.addr] = color
            hp_bar.setStyleSheet(
                f'QProgressBar::chunk {{ background-color: {color}; }}')

        sp_max = max(1, int(character.max_sp))
        sp_bar.setMaximum(sp_max)
        sp_bar.setValue(max(0, min(sp_max, int(character.sp))))
        sp_bar.setFormat(
            f'{character.sp:.{decimals["sp"]}f}/{character.max_sp}')
        sp_bar.setStyleSheet(
            'QProgressBar::chunk { background-color: #4ca3dd; }')

        skill_text = format_character_column(
            'skill', character, decimals, row)
        lines = skill_text.count('\n')
        if self._character_skill_lines.get(character.addr) != lines:
            self._character_skill_lines[character.addr] = lines
            tbl.resizeRowToContents(row)

    def _on_character_filter(self, _checked: bool) -> None:
        self.character_table.setRowCount(0)
        self._character_rows.clear()
        self._character_bar_colors.clear()
        self._character_skill_lines.clear()
        self._render_character_table(self._character_last)

    def _on_unattributed_damage_tracking(self, checked: bool) -> None:
        poll = self._enemy_poll
        if poll is not None:
            poll.set_track_unattributed_damage(checked)
        if not checked:
            # 下一帧读取器会清除无来源累计；先给用户即时反馈。
            self.lbl_character_status.setText('无来源总伤统计已关闭')

    def _open_character_overview(self) -> None:
        dialog = CharacterOverviewDialog(
            self._module_dialog_parent(self.box_character),
            self._character_last + self._character_stats_history)
        self._character_overview_dialog = dialog
        try:
            dialog.exec()
        finally:
            if self._character_overview_dialog is dialog:
                self._character_overview_dialog = None

    def _on_character_precision(self) -> None:
        dialog = CharacterPrecisionDialog(
            self._module_dialog_parent(self.box_character),
            self._character_dec, self._character_visible_cols)
        if dialog.exec() == QDialog.Accepted:
            self._character_dec.update(dialog.values())
            self._character_widths_fitted = False
            self._render_character_table(self._character_last)

    def _apply_character_column_visibility(self) -> None:
        if not hasattr(self, 'character_table'):
            return
        for idx, col in enumerate(CHARACTER_COLUMN_DEFS):
            self.character_table.setColumnHidden(
                idx, col['key'] not in self._character_visible_cols)

    def _apply_character_column_order(self) -> None:
        if not hasattr(self, 'character_table'):
            return
        apply_column_order(
            self.character_table, self._character_col_order,
            CHARACTER_COLUMN_INDEX)

    def _on_character_columns(self) -> None:
        dialog = CharacterColumnDialog(
            self._module_dialog_parent(self.box_character),
            self._character_visible_cols, self._character_col_order)
        if dialog.exec() != QDialog.Accepted:
            return
        self._character_visible_cols = dialog.values()
        # 可见列按对话框中的拖动顺序；隐藏列保持原相对顺序附后
        self._character_col_order = dialog.ordered_keys() + [
            key for key in self._character_col_order
            if key not in self._character_visible_cols]
        save_character_columns(
            self._settings, 'character_table/visible_columns',
            self._character_visible_cols)
        save_column_order(
            self._settings, 'character_table/column_order',
            self._character_col_order)
        self._apply_character_column_visibility()
        self._apply_character_column_order()
        self._character_widths_fitted = False
        self._render_character_table(self._character_last)
        if not self._character_last:
            self._fit_character_columns()

    def _fit_character_columns(self) -> None:
        if not hasattr(self, 'character_table'):
            return
        tbl = self.character_table
        visible = [idx for idx, col in enumerate(CHARACTER_COLUMN_DEFS)
                   if (col['key'] in self._character_visible_cols
                       and not tbl.isColumnHidden(idx))]
        if not visible:
            return
        tbl.resizeColumnsToContents()
        minimums = {
            'row': 38, 'name': 80, 'kind': 72, 'cid': 105, 'profession': 62,
            'level': 72, 'hp': 180, 'sp': 125, 'pos': 70,
            'action_state': 72, 'abnormal_status': 90, 'skill': 145,
            'global_total_damage': 105,
            'detail': 62,
        }
        maximums = {
            'name': 200, 'cid': 230, 'abnormal_status': 230, 'skill': 285,
            'hp': 245, 'sp': 180,
        }
        widths = {}
        for idx in visible:
            key = CHARACTER_COLUMN_DEFS[idx]['key']
            widths[idx] = max(
                minimums.get(key, 58),
                min(tbl.columnWidth(idx) + 8, maximums.get(key, 150)))
        viewport = max(100, tbl.viewport().width() - 2)
        total = sum(widths.values())
        if total < viewport:
            expanding = [idx for idx in visible
                         if CHARACTER_COLUMN_DEFS[idx]['key'] in (
                             'name', 'cid', 'abnormal_status', 'skill')]
            expanding = expanding or [visible[-1]]
            each, remainder = divmod(viewport - total, len(expanding))
            for pos, idx in enumerate(expanding):
                widths[idx] += each + (1 if pos < remainder else 0)
        for idx, width in widths.items():
            tbl.setColumnWidth(idx, width)
        self._character_widths_fitted = True

    def _open_character_detail(self, addr: int) -> None:
        character = next(
            (item for item in self._character_last if item.addr == addr), None)
        if character is None:
            QMessageBox.information(
                self, '干员详情', '该干员已离场或对象已失效。')
            return
        if getattr(character, 'is_global_damage_summary', False):
            dialog = GlobalDamageDetailDialog(
                self._module_dialog_parent(self.box_character_table), character)
            self._global_damage_detail_dialog = dialog
            try:
                dialog.exec()
            finally:
                if self._global_damage_detail_dialog is dialog:
                    self._global_damage_detail_dialog = None
            return
        dialog = CharacterDetailDialog(
            self._module_dialog_parent(self.box_character_table), character)
        self._character_detail_dialog = dialog
        poll = self._enemy_poll
        if poll is not None:
            poll.set_character_detail_target(addr)
        try:
            dialog.exec()
        finally:
            if poll is self._enemy_poll:
                poll.set_character_detail_target(0)
            if self._character_detail_dialog is dialog:
                self._character_detail_dialog = None

    # ================= 定时刷新 =================

    def _tick_fast(self) -> None:
        game = self._provider.get_game_data()
        game_time = _format_game_time(game.get("game_time"))
        self.lbl_game_time_big.setText(game_time)
        fc = game.get("frame_count")
        frame = f"F{int(fc)}" if fc is not None else "—"
        self.lbl_frame_big.setText(frame)
        self.lbl_enemy_compact_game.setText(
            f"游戏时间：{game_time}\n逻辑帧：{frame}")

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
