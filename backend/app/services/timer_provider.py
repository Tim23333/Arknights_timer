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
from tools.speed_scanner.ak_speed_reader import AKSpeedReader


class TimerDataProvider:
    """
    游戏时间/帧：通过 apply_hook() 接收寻址工具推送的配置，refresh_sample() 做内存采样。
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self.process_name: str = os.getenv("AK_PROCESS_NAME", "MuMuVMMHeadless.exe")
        self.time_address_hex: Optional[str] = os.getenv("AK_TIME_ADDRESS", "").strip() or None
        self.reader: Optional[AKMemoryReader] = None
        self._game_cache: Dict[str, Any] = {
            "connected": False,
            "configured": False,
            "game_time": None,
            "frame_count": None,
            "message": "请先运行「打开寻址工具」完成扫描。",
            "last_refresh": None,
            # 倍速/暂停
            "speed_level": None,
            "speed_name": "未知",
            "timescale": None,
            "is_paused": None,
        }
        # 倍速/暂停读取器
        self._speed_reader: Optional[AKSpeedReader] = None
        self._speed_configured: bool = False
        self._build_reader()

    def _build_reader(self) -> None:
        self.reader = AKMemoryReader(process_name=self.process_name)

    def _ensure_connected(self) -> bool:
        if not self.reader:
            self._build_reader()
        if self.reader.pm:
            return True
        return self.reader.connect()

    def apply_hook(self, process_name: str, time_address: str) -> Dict[str, Any]:
        """接收寻址工具通过 TCP 推送的 process_name + time_address，配置内存读取。"""
        with self._lock:
            pn = (process_name or "").strip()
            addr = (time_address or "").strip()
            if not pn or not addr:
                msg = "缺少 process_name 或 time_address。"
                self._game_cache = {**self._game_cache, "message": msg, "last_refresh": None}
                return {"ok": False, "message": msg}

            if pn != self.process_name:
                self.process_name = pn
                self._build_reader()

            self.time_address_hex = addr

            if not self._ensure_connected():
                self._game_cache = {
                    "connected": False,
                    "configured": False,
                    "game_time": None,
                    "frame_count": None,
                    "message": "无法附加到进程，请确认模拟器已启动。",
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

            # 首次采样以验证数据可用
            game_time, frame_count = self.reader.get_game_data()
            self._game_cache = {
                "connected": True,
                "configured": True,
                "game_time": game_time,
                "frame_count": frame_count,
                "message": "ok" if game_time is not None else "地址已配置，等待读取内存数据。",
                "last_refresh": datetime.now().strftime("%Y-%m-%d %H:%M:%S") if game_time is not None else None,
            }
            return {
                "ok": True,
                "message": "已接收寻址配置。",
                "process_name": self.process_name,
                "time_address": self.time_address_hex,
            }

    def apply_speed_hook(self, process_name: str, speed_address: str, timescale_address: str) -> Dict[str, Any]:
        """接收倍速寻址工具通过 TCP 推送的 speed_address + timescale_address。"""
        with self._lock:
            pn = (process_name or "").strip()
            sa = (speed_address or "").strip()
            ta = (timescale_address or "").strip()
            if not pn or not sa or not ta:
                return {"ok": False, "message": "缺少参数。"}

            if not self._speed_reader or self._speed_reader.process_name != pn:
                self._speed_reader = AKSpeedReader(process_name=pn)
                if not self._speed_reader.connect():
                    return {"ok": False, "message": "倍速读取器无法附加到进程。"}

            if not self._speed_reader.set_speed_address(sa):
                return {"ok": False, "message": "倍速地址无效。"}
            if not self._speed_reader.set_timescale_address(ta):
                return {"ok": False, "message": "暂停地址无效。"}

            self._speed_configured = True

            # 首次采样验证
            data = self._speed_reader.get_all()
            self._game_cache = {
                **self._game_cache,
                "speed_level": data.get("speed_level"),
                "speed_name": data.get("speed_name", "未知"),
                "timescale": data.get("timescale"),
                "is_paused": data.get("is_paused"),
            }
            return {"ok": True, "message": "已接收倍速/暂停配置。"}

    def refresh_sample(self) -> Dict[str, Any]:
        """仅做内存采样（读 game_time + frame_count + 倍速/暂停），不读文件。需先调用 apply_hook 配置地址。"""
        with self._lock:
            if not self.reader or not self.reader.time_address:
                return {"ok": False, "message": self._game_cache.get("message", "未配置地址。")}

            if not self._ensure_connected():
                self._game_cache = {
                    **self._game_cache,
                    "connected": False,
                    "game_time": None,
                    "frame_count": None,
                    "message": "进程连接断开，请确认模拟器仍在运行。",
                }
                return {"ok": False, "message": self._game_cache["message"]}

            game_time, frame_count = self.reader.get_game_data()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if game_time is None or frame_count is None:
                self._game_cache = {
                    **self._game_cache,
                    "game_time": None,
                    "frame_count": None,
                    "message": "读取内存失败，请确认对局进行中且地址仍有效。",
                    "last_refresh": now,
                }
                return {"ok": False, "message": self._game_cache["message"]}

            # 读取倍速/暂停数据（如果已配置）
            speed_data = {}
            if self._speed_configured and self._speed_reader:
                sd = self._speed_reader.get_all()
                speed_data = {
                    "speed_level": sd.get("speed_level"),
                    "speed_name": sd.get("speed_name", "未知"),
                    "timescale": sd.get("timescale"),
                    "is_paused": sd.get("is_paused"),
                }

            self._game_cache = {
                "connected": True,
                "configured": True,
                "game_time": game_time,
                "frame_count": frame_count,
                "message": "ok",
                "last_refresh": now,
                **speed_data,
            }
            return {"ok": True, "game_time": game_time, "frame_count": frame_count}

    def get_game_data(self) -> Dict[str, Optional[Any]]:
        """返回最近一次采样的缓存。"""
        with self._lock:
            return dict(self._game_cache)
