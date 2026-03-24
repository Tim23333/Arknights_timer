import os
import sys
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


class TimerDataProvider:
    """Provide real-time game data via the original memory reader."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.process_name = os.getenv("AK_PROCESS_NAME", "MuMuVMMHeadless.exe")
        self.time_address_hex = os.getenv("AK_TIME_ADDRESS", "").strip() or None
        self.reader: Optional[AKMemoryReader] = None
        self._build_reader()

    def _build_reader(self) -> None:
        self.reader = AKMemoryReader(process_name=self.process_name)

    def _ensure_connected(self) -> bool:
        if not self.reader:
            self._build_reader()
        if self.reader.pm:
            return True
        return self.reader.connect()

    def _load_address_if_needed(self) -> bool:
        if not self.reader:
            return False
        if self.reader.time_address:
            return True
        if not self.time_address_hex:
            return False
        return self.reader.set_address(self.time_address_hex)

    def configure(self, process_name: Optional[str], time_address: Optional[str]) -> Dict[str, Any]:
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
            else:
                self._load_address_if_needed()

            return {
                "ok": True,
                "connected": True,
                "configured": bool(self.reader.time_address),
                "process_name": self.process_name,
                "time_address": self.time_address_hex,
                "message": "配置已更新。",
            }

    def get_game_data(self) -> Dict[str, Optional[Any]]:
        with self._lock:
            connected = self._ensure_connected()
            if not connected:
                return {
                    "connected": False,
                    "configured": False,
                    "game_time": None,
                    "frame_count": None,
                    "message": "未连接到目标进程。",
                }

            configured = self._load_address_if_needed()
            if not configured:
                return {
                    "connected": True,
                    "configured": False,
                    "game_time": None,
                    "frame_count": None,
                    "message": "尚未配置时间地址，请先调用配置接口。",
                }

            game_time, frame_count = self.reader.get_game_data()
            if game_time is None or frame_count is None:
                return {
                    "connected": True,
                    "configured": True,
                    "game_time": None,
                    "frame_count": None,
                    "message": "读取失败，请确认游戏正在运行且地址有效。",
                }

            return {
                "connected": True,
                "configured": True,
                "game_time": game_time,
                "frame_count": frame_count,
                "message": "ok",
            }
