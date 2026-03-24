import json
import os
import sys
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Optional


def _bootstrap_import_path() -> None:
    candidate_roots = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate_roots.append(Path(meipass))
        candidate_roots.append(Path(sys.executable).resolve().parent)
    else:
        candidate_roots.append(Path(__file__).resolve().parents[3])

    for root in candidate_roots:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)


_bootstrap_import_path()
from tools.timer.ak_memory_reader import AKMemoryReader


def _hook_path() -> Path:
    """与 tools/timer 写入路径一致：backend/data/timer_hook.json"""
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / "data" / "timer_hook.json"


class TimerDataProvider:
    """
    游戏时间/帧：仅在调用 refresh_from_hook_file 时读取内存；数据来自寻址工具写入的 timer_hook.json。
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self.process_name = os.getenv("AK_PROCESS_NAME", "MuMuVMMHeadless.exe")
        self.time_address_hex: Optional[str] = os.getenv("AK_TIME_ADDRESS", "").strip() or None
        self.reader: Optional[AKMemoryReader] = None
        self._game_cache: Dict[str, Any] = {
            "connected": False,
            "configured": False,
            "game_time": None,
            "frame_count": None,
            "message": "请先运行「打开寻址工具」完成扫描；完成后在本窗口点击「刷新游戏状态」。",
            "last_refresh": None,
        }
        self._build_reader()

    def _build_reader(self) -> None:
        self.reader = AKMemoryReader(process_name=self.process_name)

    def _ensure_connected(self) -> bool:
        if not self.reader:
            self._build_reader()
        if self.reader.pm:
            return True
        return self.reader.connect()

    def configure(self, process_name: Optional[str], time_address: Optional[str]) -> Dict[str, Any]:
        """保留给脚本/测试；桌面端主要使用 refresh_from_hook_file。"""
        with self._lock:
            if process_name:
                process_name = process_name.strip()
            if time_address:
                time_address = time_address.strip()

            if process_name and process_name != self.process_name:
                self.process_name = process_name
                self._build_reader()

            connected = self._ensure_connected()
            if not connected:
                return {
                    "ok": False,
                    "connected": False,
                    "configured": False,
                    "process_name": self.process_name,
                    "message": "进程连接失败，请检查模拟器进程名和权限。",
                }

            if time_address:
                if not self.reader.set_address(time_address):
                    return {
                        "ok": False,
                        "connected": True,
                        "configured": False,
                        "process_name": self.process_name,
                        "message": "时间地址格式无效，请传入十六进制地址。",
                    }
                self.time_address_hex = hex(self.reader.time_address)
            elif self.time_address_hex and self.reader:
                self.reader.set_address(self.time_address_hex)

            return {
                "ok": True,
                "connected": True,
                "configured": bool(self.reader and self.reader.time_address),
                "process_name": self.process_name,
                "time_address": self.time_address_hex,
                "message": "配置已更新。",
            }

    def refresh_from_hook_file(self) -> Dict[str, Any]:
        """读取 timer_hook.json 并单次采样游戏时间、逻辑帧，更新缓存。"""
        with self._lock:
            path = _hook_path()
            if not path.is_file():
                self._game_cache = {
                    **self._game_cache,
                    "connected": False,
                    "configured": False,
                    "game_time": None,
                    "frame_count": None,
                    "message": f"未找到配置文件：{path}\n请先运行寻址工具并完成地址选择。",
                    "last_refresh": None,
                }
                return {"ok": False, "message": self._game_cache["message"]}

            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                msg = f"读取配置失败：{e}"
                self._game_cache = {**self._game_cache, "message": msg, "last_refresh": None}
                return {"ok": False, "message": msg}

            pn = (raw.get("process_name") or "").strip()
            addr = (raw.get("time_address") or "").strip()
            if not pn or not addr:
                msg = "timer_hook.json 缺少 process_name 或 time_address。"
                self._game_cache = {**self._game_cache, "message": msg, "last_refresh": None}
                return {"ok": False, "message": msg}

            self.process_name = pn
            self._build_reader()
            self.time_address_hex = addr

            if not self._ensure_connected():
                self._game_cache = {
                    "connected": False,
                    "configured": False,
                    "game_time": None,
                    "frame_count": None,
                    "message": "无法附加到进程，请确认模拟器已启动并以管理员运行寻址工具后重试。",
                    "last_refresh": None,
                }
                return {"ok": False, "message": self._game_cache["message"]}

            if not self.reader.set_address(addr):
                self._game_cache = {
                    "connected": True,
                    "configured": False,
                    "game_time": None,
                    "frame_count": None,
                    "message": "时间地址无效，请在寻址工具中重新确认地址。",
                    "last_refresh": None,
                }
                return {"ok": False, "message": self._game_cache["message"]}

            game_time, frame_count = self.reader.get_game_data()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if game_time is None or frame_count is None:
                self._game_cache = {
                    "connected": True,
                    "configured": True,
                    "game_time": None,
                    "frame_count": None,
                    "message": "读取内存失败，请确认对局进行中且地址仍有效。",
                    "last_refresh": now,
                }
                return {"ok": False, "message": self._game_cache["message"]}

            self._game_cache = {
                "connected": True,
                "configured": True,
                "game_time": game_time,
                "frame_count": frame_count,
                "message": "ok",
                "last_refresh": now,
            }
            return {
                "ok": True,
                "message": "已更新游戏时间 / 逻辑帧。",
                "game_time": game_time,
                "frame_count": frame_count,
            }

    def get_game_data(self) -> Dict[str, Optional[Any]]:
        """返回最近一次「刷新游戏状态」的采样，不会在后台持续读内存。"""
        with self._lock:
            return dict(self._game_cache)
