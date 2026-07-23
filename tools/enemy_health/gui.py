# -*- coding: utf-8 -*-
"""敌人实时监控 GUI (PySide6)

一键扫描: 全堆扫描定位敌人列表 (首次/换关卡后需要, 约 1-3 分钟)
实时监控: 常驻 TCP 通道准实时轮询 (0.05-0.1 秒/帧) 展示敌人名称/坐标/血量/属性

运行:
    python -m tools.enemy_health.gui
"""

import sys
import time
import ctypes

if __package__ in (None, ''):  # 允许直接 python gui.py 运行
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    __package__ = 'tools.enemy_health'

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTableWidget, QTableWidgetItem,
    QPlainTextEdit, QHeaderView, QDoubleSpinBox, QStyleFactory,
)

from .enemy_reader import EnemyReader, format_skill_cd
from . import game_structs as gs

STATE_NAMES = {0: 'NONE', 1: 'INITED', 2: '战斗中', 3: '已结束'}


# ============================================================
# 后台线程
# ============================================================
class ScanWorker(QThread):
    """连接 + 定位 (缓存验证或全堆扫描)"""
    log = Signal(str)
    progress = Signal(int, str)
    done = Signal(bool, str)

    def __init__(self, reader, force=False):
        super().__init__()
        self.reader = reader
        self.force = force

    def run(self):
        try:
            self.reader.log = lambda m: self.log.emit(str(m))
            self.reader.progress = lambda pct, desc: self.progress.emit(int(pct), str(desc))
            pid = self.reader.connect()
            self.log.emit(f"游戏 PID = {pid}")
            ok = self.reader.bootstrap(force=self.force)
            if ok:
                self.done.emit(True, f"定位完成, 敌人 {len(self.reader.enemy_addrs)} 个")
            else:
                self.done.emit(False, "定位失败: 请确认已进入关卡且场上有敌人")
        except Exception as e:
            self.done.emit(False, f"出错: {e}")


class PollWorker(QThread):
    """实时轮询"""
    snapshot = Signal(dict)

    def __init__(self, reader, interval=0.1):
        super().__init__()
        self.reader = reader
        self.interval = interval

    def run(self):
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


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    COLS = ['#', '名称', '编号', '敌人ID', '血量', '坐标', '攻击', '防御', '法抗', '移速',
            '攻速', '技能 CD', '状态']

    def __init__(self):
        super().__init__()
        self.setWindowTitle('明日方舟 敌人实时监控')
        self.resize(1024, 640)

        self.reader = EnemyReader(log=lambda m: None)
        self.scan_worker = None
        self.poll_worker = None
        self._row_of = {}        # enemy addr -> 表格行号 (行位置稳定, 新敌人底部新增)
        self._bar_colors = {}    # enemy addr -> 当前血条颜色

        # ---------- 顶部状态 ----------
        top = QHBoxLayout()
        self.lbl_pid = QLabel('未连接')
        self.lbl_state = QLabel('状态: -')
        self.lbl_speed = QLabel('倍速: -')
        self.lbl_time = QLabel('时间: -')
        self.lbl_count = QLabel('敌人数: -')
        for w in (self.lbl_pid, self.lbl_state, self.lbl_speed, self.lbl_time, self.lbl_count):
            top.addWidget(w)
        top.addStretch(1)

        # ---------- 控制行 ----------
        ctrl = QHBoxLayout()
        self.btn_scan = QPushButton('一键扫描')
        self.btn_scan.setToolTip('全堆扫描重新定位敌人列表 (换关卡/重启游戏后使用)')
        self.btn_scan.clicked.connect(self.on_scan)
        self.btn_monitor = QPushButton('开始监控')
        self.btn_monitor.setEnabled(False)
        self.btn_monitor.clicked.connect(self.on_monitor_toggle)
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setDecimals(3)
        self.spin_interval.setRange(0.008, 10.0)
        self.spin_interval.setSingleStep(0.008)
        self.spin_interval.setValue(0.016)
        self.spin_interval.setSuffix(' 秒')
        self.spin_interval.setPrefix('刷新 ')
        self.spin_interval.valueChanged.connect(self.on_interval_changed)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFixedWidth(220)
        ctrl.addWidget(self.btn_scan)
        ctrl.addWidget(self.btn_monitor)
        ctrl.addWidget(self.spin_interval)
        ctrl.addWidget(self.progress)
        ctrl.addStretch(1)

        # ---------- 表格 ----------
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)   # 名称
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)   # 血量条

        # ---------- 日志 ----------
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setFixedHeight(110)

        lay = QVBoxLayout()
        lay.addLayout(top)
        lay.addLayout(ctrl)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.log_view)
        root = QWidget()
        root.setLayout(lay)
        self.setCentralWidget(root)

        # 启动不自动扫描, 点击"一键扫描"按钮后才开始
        self.append_log('就绪。进入关卡且场上有敌人后, 点击"一键扫描"开始定位。')

    # ---------- 日志/进度 ----------

    def append_log(self, msg):
        msg = msg.strip()
        if msg:
            self.log_view.appendPlainText(msg)

    def on_progress(self, pct, desc):
        self.progress.setValue(pct)
        self.progress.setFormat(f'{desc} %p%')

    # ---------- 扫描 ----------

    def _start_scan(self, force):
        self.btn_scan.setEnabled(False)
        self.btn_monitor.setEnabled(False)
        self.progress.setValue(0)
        self.append_log('开始全堆扫描 ...' if force else '尝试使用缓存地址 ...')
        self.scan_worker = ScanWorker(self.reader, force=force)
        self.scan_worker.log.connect(self.append_log)
        self.scan_worker.progress.connect(self.on_progress)
        self.scan_worker.done.connect(self.on_scan_done)
        self.scan_worker.start()

    def on_scan(self):
        self._stop_monitor()
        self.table.setRowCount(0)   # 换关卡重扫: 清掉旧敌人行
        self._row_of.clear()
        self._bar_colors.clear()
        self._start_scan(force=True)

    def on_scan_done(self, ok, msg):
        self.append_log(msg)
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText('重新扫描')
        if ok:
            self.lbl_pid.setText(f"PID={self.reader.mc.pid}")
            self.progress.setValue(100)
            self.progress.setFormat('就绪')
            self._start_monitor()
        else:
            self.progress.setFormat('失败')

    # ---------- 监控 ----------

    def on_monitor_toggle(self):
        if self.poll_worker and self.poll_worker.isRunning():
            self._stop_monitor()
        else:
            self._start_monitor()

    def _start_monitor(self):
        self._stop_monitor()
        self.poll_worker = PollWorker(self.reader, self.spin_interval.value())
        self.poll_worker.snapshot.connect(self.on_snapshot)
        self.poll_worker.start()
        self.btn_monitor.setEnabled(True)
        self.btn_monitor.setText('停止监控')
        self.append_log('实时监控已启动')

    def _stop_monitor(self):
        if self.poll_worker:
            self.poll_worker.requestInterruption()
            self.poll_worker.wait(3000)
            self.poll_worker = None
        self.btn_monitor.setText('开始监控')

    def on_interval_changed(self, v):
        if self.poll_worker:
            self.poll_worker.interval = v

    # ---------- 快照渲染 ----------

    def on_snapshot(self, snap):
        # 渲染节流: 轮询可达 100Hz, 渲染 60fps 足够, 避免 Qt 控件重建成为瓶颈
        now = time.time()
        if snap.get('ok') and now - getattr(self, '_last_render', 0) < 0.016:
            return
        self._last_render = now
        st = STATE_NAMES.get(snap['state'], '?') if snap['state'] >= 0 else '-'
        spd = gs.SpeedLevel.NAMES.get(snap['speed_level'], '?') if snap['speed_level'] >= 0 else '-'
        self.lbl_state.setText(f"状态: {st}")
        self.lbl_speed.setText(f"倍速: {spd} (x{snap['time_scale']:g})")
        t = int(snap['play_time'])
        self.lbl_time.setText(f"时间: {t // 60:02d}:{t % 60:02d}")
        self.lbl_count.setText(f"敌人数: {len(snap['enemies'])}"
                               + (f" · {snap['frame_ms']:.0f}ms/帧" if snap.get('frame_ms') else ''))
        if snap.get('msg'):
            self.append_log(snap['msg'])
        self._render_table(snap['enemies'])

    def _render_table(self, enemies):
        tbl = self.table
        # 增量刷新: 按敌人地址锚定行, 已有行原地更新, 新敌人底部新增,
        # 消失的行才删除——杜绝整表重建导致的闪烁
        tbl.setUpdatesEnabled(False)
        try:
            seen = set()
            for e in enemies:
                seen.add(e.addr)
                row = self._row_of.get(e.addr)
                if row is None:
                    row = tbl.rowCount()
                    tbl.insertRow(row)
                    self._make_row(row, e.addr)
                    self._row_of[e.addr] = row
                self._update_row(row, e)
            gone = [a for a in self._row_of if a not in seen]
            for a in sorted(gone, key=lambda a: -self._row_of[a]):
                tbl.removeRow(self._row_of.pop(a))
                self._bar_colors.pop(a, None)
            if gone:   # removeRow 后行号位移, 依 item(0) 存的 addr 重建映射
                self._row_of = {tbl.item(r, 0).data(Qt.UserRole): r
                                for r in range(tbl.rowCount())}
        finally:
            tbl.setUpdatesEnabled(True)

    def _make_row(self, row, addr):
        tbl = self.table
        for c in range(len(self.COLS)):
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

    def _update_row(self, row, e):
        tbl = self.table

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
        bar.setFormat(f'{int(e.hp)} / {int(e.max_hp)}  %p%')
        ratio = e.hp / e.max_hp if e.max_hp > 0 else 0
        color = '#5cb85c' if ratio > 0.5 else ('#f0ad4e' if ratio > 0.2 else '#d9534f')
        if not e.alive:
            color = '#888888'
        if self._bar_colors.get(e.addr) != color:   # 颜色变化才重设样式 (触发重排版)
            self._bar_colors[e.addr] = color
            bar.setStyleSheet(f'QProgressBar::chunk {{ background-color: {color}; }}')

        setc(5, f'({e.pos_x:.2f}, {e.pos_y:.2f})')
        setc(6, int(e.atk))
        setc(7, int(e.def_))
        setc(8, int(e.res))
        setc(9, f'{e.mspd:.2f}')
        setc(10, int(e.aspd))
        setc(11, format_skill_cd(e.skills))
        setc(12, '存活' if e.alive else ('退场' if e.finish else '阵亡'), grey=not e.alive)

    # ---------- 关闭 ----------

    def closeEvent(self, event):
        self._stop_monitor()
        if self.scan_worker:
            self.scan_worker.wait(2000)
        self.reader.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
