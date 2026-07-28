import os
import sys
import bisect
import math
from collections import deque
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Deque, Dict, Optional, Tuple


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


# 只保存不同的逻辑帧。按 30-120 逻辑帧/秒计算，可覆盖约 34-136 秒；
# Python 对象总占用约数百 KB，且 deque.maxlen 保证不会随关卡时长增长。
FRAME_TIMELINE_MAX_SAMPLES = 4096
FRAME_MATCH_EXACT_EPSILON = 0.000005


class TimerDataProvider:
    """
    游戏时间/帧：通过 apply_hook() 接收寻址工具推送的配置，refresh_sample() 做内存采样。
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self.process_name: str = os.getenv("AK_PROCESS_NAME", "MuMuVMMHeadless.exe")
        self.time_address_hex: Optional[str] = os.getenv("AK_TIME_ADDRESS", "").strip() or None
        self.reader: Optional[AKMemoryReader] = None
        self._frame_timeline: Deque[Tuple[float, int]] = deque(
            maxlen=FRAME_TIMELINE_MAX_SAMPLES)
        self._game_cache: Dict[str, Any] = {
            "connected": False,
            "configured": False,
            "game_time": None,
            "frame_count": None,
            "message": "请先运行「打开寻址工具」完成扫描。",
            "last_refresh": None,
        }
        self._build_reader()

    def _build_reader(self) -> None:
        self.reader = AKMemoryReader(process_name=self.process_name)
        self._frame_timeline.clear()

    def _record_frame_sample(self, game_time: float, frame_count: int) -> None:
        """记录一组原子读取的时间/帧；同帧去重，新一局自动清空旧样本。"""
        try:
            game_time = float(game_time)
            frame_count = int(frame_count)
        except (TypeError, ValueError):
            return
        if not math.isfinite(game_time) or game_time < 0 or frame_count < 0:
            return
        with self._lock:
            if self._frame_timeline:
                last_time, last_frame = self._frame_timeline[-1]
                if frame_count < last_frame or game_time + FRAME_MATCH_EXACT_EPSILON < last_time:
                    self._frame_timeline.clear()
                elif frame_count == last_frame:
                    # fixedPlayTime 与 fixedFrameCnt 同步更新；同帧高频采样没有新信息。
                    return
            self._frame_timeline.append((game_time, frame_count))

    def get_frame_for_game_time(self, game_time: float) -> Optional[Dict[str, Any]]:
        """从有界缓存解析指定游戏时间对应的逻辑帧。

        优先返回完全匹配的实测帧；若采样恰好跳过目标帧，则只在相邻实测样本
        之间线性补帧。目标落在缓存范围外时返回 None，等待下一轮采样，不用
        相邻帧冒充精确结果。
        """
        try:
            target = float(game_time)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(target) or target < 0:
            return None
        with self._lock:
            samples = list(self._frame_timeline)
        return self._resolve_frame_from_samples(target, samples)

    def get_frames_for_game_times(self, game_times) -> list:
        """批量解析事件时间；只复制一次缓存，避免大量代理日志反复复制 deque。"""
        with self._lock:
            samples = list(self._frame_timeline)
        out = []
        for value in game_times:
            try:
                target = float(value)
            except (TypeError, ValueError):
                out.append(None)
                continue
            if not math.isfinite(target) or target < 0:
                out.append(None)
                continue
            out.append(self._resolve_frame_from_samples(target, samples))
        return out

    @staticmethod
    def _resolve_frame_from_samples(target, samples):
        if not samples:
            return None

        times = [sample[0] for sample in samples]
        idx = bisect.bisect_left(times, target)
        nearest_indices = [i for i in (idx - 1, idx) if 0 <= i < len(samples)]
        nearest = min(nearest_indices, key=lambda i: abs(times[i] - target))
        sample_time, sample_frame = samples[nearest]
        delta = target - sample_time
        if abs(delta) <= FRAME_MATCH_EXACT_EPSILON:
            return {
                "frame": sample_frame,
                "source": "timerCacheExact",
                "sampleTime": round(sample_time, 6),
                "timeDelta": round(delta, 6),
            }

        if 0 < idx < len(samples):
            left_time, left_frame = samples[idx - 1]
            right_time, right_frame = samples[idx]
            time_span = right_time - left_time
            frame_span = right_frame - left_frame
            if time_span > 0 and frame_span > 0:
                frame = round(left_frame + (target - left_time) * frame_span / time_span)
                if left_frame <= frame <= right_frame:
                    frame_time = left_time + (frame - left_frame) * time_span / frame_span
                    return {
                        "frame": int(frame),
                        "source": "timerCacheInterpolated",
                        "sampleTime": round(frame_time, 6),
                        "timeDelta": round(target - frame_time, 6),
                    }

        return None

    def get_frame_timeline_stats(self) -> Dict[str, Any]:
        """供状态/测试查看缓存边界，不暴露可变 deque。"""
        with self._lock:
            return {
                "size": len(self._frame_timeline),
                "maxSize": FRAME_TIMELINE_MAX_SAMPLES,
                "oldestTime": self._frame_timeline[0][0] if self._frame_timeline else None,
                "newestTime": self._frame_timeline[-1][0] if self._frame_timeline else None,
            }

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
            self._frame_timeline.clear()

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
            if game_time is not None and frame_count is not None:
                self._record_frame_sample(game_time, frame_count)
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

    def refresh_sample(self) -> Dict[str, Any]:
        """仅做内存采样（读 game_time + frame_count），不读文件。需先调用 apply_hook 配置地址。"""
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

            self._record_frame_sample(game_time, frame_count)

            self._game_cache = {
                "connected": True,
                "configured": True,
                "game_time": game_time,
                "frame_count": frame_count,
                "message": "ok",
                "last_refresh": now,
            }
            return {"ok": True, "game_time": game_time, "frame_count": frame_count}

    def get_game_data(self) -> Dict[str, Optional[Any]]:
        """返回最近一次采样的缓存。"""
        with self._lock:
            return dict(self._game_cache)
