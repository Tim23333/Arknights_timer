"""测试版诊断日志：线程安全落盘、独立窗口与一键打包日志。"""
from __future__ import annotations

from collections import deque
import json
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path
import zipfile

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from .version import VERSION, VERSION_LABEL


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def default_log_root() -> Path:
    """返回测试日志目录；优先使用始终可写的 LocalAppData。"""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "ArknightsTimeline" / "logs"
    return Path.cwd() / "logs"


class _DiagnosticTextStream:
    """把 windowed EXE 中的 stdout/stderr 行转入诊断日志。"""

    def __init__(self, manager: "DiagnosticLogManager", source: str) -> None:
        self.manager = manager
        self.source = source
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, text) -> int:
        value = str(text or "")
        if not value:
            return 0
        with self._lock:
            self._buffer += value.replace("\r\n", "\n").replace("\r", "\n")
            parts = self._buffer.split("\n")
            self._buffer = parts.pop()
        for line in parts:
            if line:
                self.manager.log(f"[{self.source}] {line}")
        return len(value)

    def flush(self) -> None:
        with self._lock:
            line, self._buffer = self._buffer, ""
        if line:
            self.manager.log(f"[{self.source}] {line}")

    def isatty(self) -> bool:
        return False

    @property
    def encoding(self) -> str:
        return "utf-8"


class DiagnosticLogManager(QObject):
    """管理单次运行的诊断日志，并生成可直接发送的 ZIP。"""

    line_added = Signal(str)

    def __init__(self, log_root: Path | str | None = None) -> None:
        super().__init__()
        self.log_root = Path(log_root) if log_root else default_log_root()
        self.log_root.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_id = f"{stamp}_{os.getpid()}"
        self.log_path = self.log_root / f"session_{self.session_id}.log"
        self.fault_path = self.log_root / f"fault_{self.session_id}.log"
        self._stream = self.log_path.open("a", encoding="utf-8", buffering=1)
        self._fault_stream = None
        self._lock = threading.RLock()
        self._lines = deque(maxlen=10_000)
        self._context_provider = None
        self._closed = False

    def set_context_provider(self, provider) -> None:
        self._context_provider = provider

    def log(self, *parts) -> str:
        message = " ".join(str(part) for part in parts)
        now = time.time()
        millis = int((now % 1) * 1000)
        thread_name = threading.current_thread().name
        line = (
            f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))}."
            f"{millis:03d}] [{thread_name}] {message}"
        )
        with self._lock:
            if self._closed:
                return line
            self._lines.append(line)
            self._stream.write(line + "\n")
        self.line_added.emit(line)
        return line

    def snapshot_lines(self) -> list[str]:
        with self._lock:
            return list(self._lines)

    def text_stream(self, source: str) -> _DiagnosticTextStream:
        return _DiagnosticTextStream(self, source)

    def enable_fault_handler(self) -> bool:
        try:
            import faulthandler
            self._fault_stream = self.fault_path.open("ab", buffering=0)
            faulthandler.enable(file=self._fault_stream, all_threads=True)
            return True
        except (OSError, RuntimeError, ValueError) as exc:
            self.log("faulthandler 启用失败:", exc)
            return False

    @staticmethod
    def _run_command(command: list[str], timeout: int = 12) -> str:
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, errors="replace",
                timeout=timeout, creationflags=_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"执行失败: {type(exc).__name__}: {exc}"
        output = "\n".join(
            part.strip() for part in (result.stdout, result.stderr) if part.strip())
        return f"exit={result.returncode}\n{output or '(无输出)'}"

    def _context(self) -> dict:
        if not self._context_provider:
            return {}
        try:
            value = self._context_provider()
            return dict(value) if isinstance(value, dict) else {}
        except Exception as exc:
            return {"context_error": f"{type(exc).__name__}: {exc}"}

    def diagnostic_report(self) -> str:
        context = self._context()
        rows = [
            f"ArknightsTimeline {VERSION_LABEL} 测试版诊断信息",
            f"app_version={VERSION}",
            f"generated_at={time.strftime('%Y-%m-%d %H:%M:%S %z')}",
            f"session_id={self.session_id}",
            f"frozen={getattr(sys, 'frozen', False)}",
            f"executable={sys.executable}",
            f"argv={json.dumps(sys.argv, ensure_ascii=False)}",
            f"cwd={os.getcwd()}",
            f"python={sys.version.replace(chr(10), ' ')}",
            f"platform={platform.platform()}",
            f"machine={platform.machine()}",
            f"processor={platform.processor()}",
        ]
        try:
            import PySide6
            rows.append(f"pyside6={PySide6.__version__}")
        except Exception as exc:
            rows.append(f"pyside6=读取失败: {exc}")
        try:
            from tools.enemy_health import game_structs
            rows.append("generated_offsets=" + json.dumps(
                game_structs.GENERATED_OFFSET_INFO, ensure_ascii=False,
                sort_keys=True, default=str))
        except Exception as exc:
            rows.append(f"generated_offsets=读取失败: {exc}")

        rows.extend(("", "[runtime_context]", json.dumps(
            context, ensure_ascii=False, indent=2, sort_keys=True, default=str)))

        adb_path = str(context.get("adb_path") or "")
        adb_serial = str(context.get("adb_serial") or "")
        package = str(context.get("package") or "")
        if adb_path and Path(adb_path).is_file():
            rows.extend(("", "[adb version]", self._run_command([adb_path, "version"])))
            rows.extend(("", "[adb devices -l]",
                         self._run_command([adb_path, "devices", "-l"])))
            rows.extend(("", "[adb forward --list]",
                         self._run_command([adb_path, "forward", "--list"])))
            target = [adb_path]
            if adb_serial:
                target += ["-s", adb_serial]
            rows.extend(("", "[device abi]", self._run_command(
                target + ["shell", "getprop", "ro.product.cpu.abilist"])))
            if package:
                package_dump = self._run_command(
                    target + ["shell", "dumpsys", "package", package])
                selected = [line.strip() for line in package_dump.splitlines()
                            if any(key in line for key in (
                                "exit=", "versionName=", "versionCode=",
                                "primaryCpuAbi=", "secondaryCpuAbi="))]
                rows.extend(("", f"[game package {package}]",
                             "\n".join(selected) or "(未提取到版本字段)"))
        else:
            rows.extend(("", "[adb]", "尚未选择可用的 adb.exe"))
        return "\n".join(rows) + "\n"

    def append_environment_snapshot(self) -> None:
        self.log("========== 环境诊断快照 ==========")
        for line in self.diagnostic_report().splitlines():
            self.log(line)
        self.log("========== 环境诊断结束 ==========")

    def build_package(self, output_path: Path | str | None = None) -> Path:
        with self._lock:
            self._stream.flush()
        if output_path is None:
            stamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = (
                self.log_root
                / f"ArknightsTimeline_{VERSION_LABEL}_diagnostics_{stamp}.zip")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        context = self._context()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(self.log_path, "session.log")
            if self.fault_path.is_file() and self.fault_path.stat().st_size:
                archive.write(self.fault_path, "fault.log")
            archive.writestr("diagnostics.txt", self.diagnostic_report())
            archive.writestr(
                "runtime_context.json",
                json.dumps(context, ensure_ascii=False, indent=2,
                           sort_keys=True, default=str) + "\n",
            )
            try:
                from tools.enemy_health import game_structs
                offsets = Path(game_structs.__file__).with_name("generated_offsets.json")
                if offsets.is_file():
                    archive.write(offsets, "generated_offsets.json")
            except Exception:
                pass
        self.log("诊断日志包已生成:", output)
        return output

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._fault_stream is not None:
                try:
                    import faulthandler
                    faulthandler.disable()
                except (RuntimeError, ValueError):
                    pass
            try:
                self._stream.flush()
                self._stream.close()
            except OSError:
                pass
            if self._fault_stream is not None:
                try:
                    self._fault_stream.close()
                except OSError:
                    pass
                self._fault_stream = None


class DiagnosticLogWindow(QWidget):
    """测试版的独立实时日志窗口；普通关闭只隐藏，主程序退出时销毁。"""

    def __init__(self, manager: DiagnosticLogManager, parent=None) -> None:
        super().__init__(parent, Qt.Window)
        self.manager = manager
        self._allow_close = False
        self.setWindowTitle(
            f"ArknightsTimeline {VERSION_LABEL} 测试版诊断日志")
        self.resize(960, 600)
        self.setMinimumSize(700, 420)

        layout = QVBoxLayout(self)
        title = QLabel(f"ArknightsTimeline {VERSION_LABEL} · 测试版诊断日志")
        title.setObjectName("DiagnosticLogTitle")
        title.setStyleSheet("font-size:18px;font-weight:600;")
        layout.addWidget(title)
        intro = QLabel(
            "此窗口实时记录扫描、ADB、内存通道和异常信息。关闭窗口只会隐藏日志，"
            "不会停止记录。遇到问题后点击“一键打包日志”并发送生成的 ZIP。")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.path_label = QLabel(f"会话日志：{manager.log_path}")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.path_label)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(10_000)
        self.output.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.output.setStyleSheet("font-family:Consolas, 'Microsoft YaHei UI', monospace;")
        existing = manager.snapshot_lines()
        if existing:
            self.output.setPlainText("\n".join(existing))
            self.output.moveCursor(QTextCursor.MoveOperation.End)
        manager.line_added.connect(self.output.appendPlainText)
        layout.addWidget(self.output, 1)

        buttons = QHBoxLayout()
        package_button = QPushButton("一键打包日志")
        package_button.setProperty("buttonRole", "primary")
        package_button.clicked.connect(self._build_package)
        buttons.addWidget(package_button)
        refresh_button = QPushButton("刷新环境信息")
        refresh_button.clicked.connect(self._refresh_environment)
        buttons.addWidget(refresh_button)
        folder_button = QPushButton("打开日志目录")
        folder_button.clicked.connect(self._open_folder)
        buttons.addWidget(folder_button)
        clear_button = QPushButton("清空显示")
        clear_button.clicked.connect(self.output.clear)
        buttons.addWidget(clear_button)
        buttons.addStretch(1)
        hide_button = QPushButton("隐藏窗口")
        hide_button.clicked.connect(self.hide)
        buttons.addWidget(hide_button)
        layout.addLayout(buttons)

    def _build_package(self) -> None:
        try:
            path = self.manager.build_package()
        except Exception as exc:
            self.manager.log("打包诊断日志失败:", type(exc).__name__, exc)
            QMessageBox.critical(self, "打包失败", str(exc))
            return
        QMessageBox.information(
            self, "日志已打包", f"诊断日志包已生成：\n{path}\n\n请把该 ZIP 发给开发者。")

    def _refresh_environment(self) -> None:
        threading.Thread(
            target=self.manager.append_environment_snapshot,
            name="DiagnosticSnapshot", daemon=True,
        ).start()

    def _open_folder(self) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(self.manager.log_root))
            else:
                subprocess.Popen(["xdg-open", str(self.manager.log_root)])
        except OSError as exc:
            QMessageBox.warning(self, "无法打开目录", str(exc))

    def shutdown(self) -> None:
        self._allow_close = True
        self.close()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._allow_close:
            event.accept()
        else:
            event.ignore()
            self.hide()
