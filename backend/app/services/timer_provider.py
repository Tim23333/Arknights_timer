import os
import sys
import bisect
import math
from array import array
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


# 保存整场战斗内每个不同逻辑帧。两个连续数组每条样本固定 16 字节：
# 即使按 120 帧/秒持续一小时也约 6.6 MiB；检测到新一局后自动清空。
FRAME_MATCH_EXACT_EPSILON = 0.000005

# 关卡切换检测阈值：time 严格归 0（新关卡载入等待期，保持 0）判定
GAME_TIME_RESET_THRESHOLD = 0.001


class TimerDataProvider:
    """
    游戏时间/帧：通过 apply_hook() 接收寻址工具推送的配置，refresh_sample() 做内存采样。
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self.process_name: str = os.getenv("AK_PROCESS_NAME", "MuMuVMMHeadless.exe")
        self.time_address_hex: Optional[str] = os.getenv("AK_TIME_ADDRESS", "").strip() or None
        self.reader: Optional[AKMemoryReader] = None
        # guest 侧读取路径：configure_guest() 注入后优先于此路径采样。
        # 默认 None = 未启用，行为与旧版完全一致（走宿主 pymem 路径）。
        self._guest_reader: Optional[object] = None
        # 关卡切换检测：static_fields 时钟归 0（新关卡开始）判定用
        self._game_time_reset = False
        self._pending_reset_emit = False  # 归0待广播标志（锁外触发订阅者）
        # 时间值变动检测：首次自动刷新需 guest 就绪 且 时间值已变动（进关卡开始走秒）
        self._last_seen_game_time: Optional[float] = None
        self._game_time_moved = False
        # 归0事件广播：订阅者列表（广播机制，非定向推送）
        self._reset_subscribers: list = []
        self._reset_lock = RLock()
        self._frame_times = array("d")
        self._frame_counts = array("Q")
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
        self._clear_frame_timeline()

    def _clear_frame_timeline(self) -> None:
        # array.array 没有 list.clear()；切片删除在所有受支持的 Python
        # 版本以及 PyInstaller 冻结环境中都可用，并保持原数组对象不变。
        del self._frame_times[:]
        del self._frame_counts[:]

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
            if self._frame_times:
                last_time = self._frame_times[-1]
                last_frame = self._frame_counts[-1]
                if frame_count < last_frame or game_time + FRAME_MATCH_EXACT_EPSILON < last_time:
                    self._clear_frame_timeline()
                elif frame_count == last_frame:
                    # fixedPlayTime 与 fixedFrameCnt 同步更新；同帧高频采样没有新信息。
                    return
            self._frame_times.append(game_time)
            self._frame_counts.append(frame_count)

    def get_frame_for_game_time(self, game_time: float) -> Optional[Dict[str, Any]]:
        """从本局完整缓存解析指定游戏时间对应的逻辑帧。

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
            times = self._frame_times[:]
            frames = self._frame_counts[:]
        return self._resolve_frame_from_samples(target, times, frames)

    def get_frames_for_game_times(self, game_times) -> list:
        """批量解析事件时间；只复制一次紧凑数组，避免逐事件重复加锁。"""
        with self._lock:
            times = self._frame_times[:]
            frames = self._frame_counts[:]
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
            out.append(self._resolve_frame_from_samples(target, times, frames))
        return out

    @staticmethod
    def _resolve_frame_from_samples(target, times, frames):
        if not times or len(times) != len(frames):
            return None

        idx = bisect.bisect_left(times, target)
        nearest_indices = [i for i in (idx - 1, idx) if 0 <= i < len(times)]
        nearest = min(nearest_indices, key=lambda i: abs(times[i] - target))
        sample_time = times[nearest]
        sample_frame = frames[nearest]
        delta = target - sample_time
        if abs(delta) <= FRAME_MATCH_EXACT_EPSILON:
            return {
                "frame": sample_frame,
                "source": "timerCacheExact",
                "sampleTime": round(sample_time, 6),
                "timeDelta": round(delta, 6),
            }

        if 0 < idx < len(times):
            left_time, left_frame = times[idx - 1], frames[idx - 1]
            right_time, right_frame = times[idx], frames[idx]
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
        """供状态/测试查看本局缓存边界，不暴露可变数组。"""
        with self._lock:
            return {
                "size": len(self._frame_times),
                "maxSize": None,
                "storageBytes": (len(self._frame_times) * self._frame_times.itemsize
                                 + len(self._frame_counts) * self._frame_counts.itemsize),
                "oldestTime": self._frame_times[0] if self._frame_times else None,
                "newestTime": self._frame_times[-1] if self._frame_times else None,
            }

    def configure_guest(self, reader: object) -> None:
        """注入 guest 侧时钟读取器，此后 refresh_sample() 优先走 guest 路径。

        Args:
            reader: 带 ``read_battle_clock() -> (frame:int, time:float)`` 的对象。
        """
        with self._lock:
            self._guest_reader = reader
            self._clear_frame_timeline()

    def subscribe_game_time_reset(self, callback) -> None:
        """注册时钟归 0（新关卡开始）事件回调；广播机制，可多订阅者。

        Args:
            callback: 无参可调用对象；在归 0 检测到时被调用（调用线程为
                refresh_sample 所在线程，订阅者需自行保证线程安全）。
        """
        with self._reset_lock:
            if callback not in self._reset_subscribers:
                self._reset_subscribers.append(callback)

    def unsubscribe_game_time_reset(self, callback) -> None:
        """注销归 0 事件回调（幂等）。"""
        with self._reset_lock:
            if callback in self._reset_subscribers:
                self._reset_subscribers.remove(callback)

    def _emit_reset_broadcast(self) -> None:
        """广播归 0 事件给所有订阅者。

        复制订阅者快照后在锁外依次调用回调；调用线程为 refresh_sample
        所在线程（非 Qt 主线程），订阅者需自行保证线程安全（如用
        QTimer.singleShot 回主线程）。
        """
        with self._reset_lock:
            subscribers = list(self._reset_subscribers)
        for cb in subscribers:
            try:
                cb()
            except Exception:
                # 单个订阅者异常不影响其他订阅者；不抛给调用方
                pass

    def clear_guest(self) -> None:
        """清除 guest 读取器，refresh_sample() 回退到宿主 pymem 路径。"""
        with self._lock:
            self._guest_reader = None
            self._clear_frame_timeline()
            self._game_time_reset = False

    def consume_game_time_reset(self) -> bool:
        """消费并清除"时钟归 0"标志；返回此前是否检测到新关卡开始。

        UI 在检测到归 0 后调用，防止同一重置被重复触发。
        """
        with self._lock:
            reset = self._game_time_reset
            self._game_time_reset = False
            return reset

    def game_time_moved(self) -> bool:
        """是否已检测到游戏时间值变动（进关卡开始走秒）。

        首次自动刷新需 guest 就绪 且 时间值已变动；主界面空壳时钟恒 0
        不动，不满足此条件。
        """
        with self._lock:
            return self._game_time_moved

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
            self._clear_frame_timeline()

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
        pending_emit = False
        with self._lock:
            # guest 侧路径：auto_addressing 开启时注入，优先于此采样。
            if self._guest_reader is not None:
                result = self._refresh_sample_guest()
                # 归0广播：标记后锁外触发订阅者（避免在锁内执行回调导致死锁）
                if self._pending_reset_emit:
                    self._pending_reset_emit = False
                    pending_emit = True
                # 锁外广播由本方法返回前统一处理，这里不提前 return
                if pending_emit:
                    self._emit_reset_broadcast()
                return result

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

    def _refresh_sample_guest(self) -> Dict[str, Any]:
        """guest 侧采样：读 BattleController static_fields 的 frame/time。

        与宿主路径共用 _record_frame_sample / _game_cache，保证后续
        get_frame_for_game_time / get_frame_timeline_stats / WS 推送零改动。

        // NOTICE: code review LOW2 —— 本方法在 refresh_sample 的 _lock 内做
        // memsrv TCP 读（设备断连时可阻塞到超时）。宿主路径 get_game_data()
        // 同样持锁做 I/O，属既有模式，且正常读仅数 ms，故维持现状；
        // 若 guest 路径出现反复断连场景，再把读移出锁。
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            result = self._guest_reader.read_battle_clock()
            if result is None:
                raise ValueError("guest 时钟读取返回空")
            frame_count, game_time = result
        except Exception as exc:
            # 每 200 次失败打一次日志（避免高频刷屏）；last_error 由 reader 记录
            self._guest_fail_count = getattr(self, "_guest_fail_count", 0) + 1
            if self._guest_fail_count % 200 == 1:
                last_err = getattr(self._guest_reader, "last_error", "")
                print(f"[自动寻址] guest 读取失败: {exc} | {last_err}", flush=True)
            self._game_cache = {
                **self._game_cache,
                "connected": True,
                "game_time": None,
                "frame_count": None,
                "message": f"guest 时钟读取失败：{exc}",
                "last_refresh": now,
            }
            return {"ok": False, "message": self._game_cache["message"]}

        if game_time is None or frame_count is None:
            self._game_cache = {
                **self._game_cache,
                "connected": True,
                "game_time": None,
                "frame_count": None,
                "message": "guest 时钟未初始化（未进关卡？）。",
                "last_refresh": now,
            }
            return {"ok": False, "message": self._game_cache["message"]}

        # 时间值变动检测：首次自动刷新需 guest 就绪 且 时间值已变动（进关卡开始走秒）。
        # 主界面空壳时钟恒 0 不动，不视为"已进关卡"，避免误触发首次刷新。
        if (self._last_seen_game_time is not None
                and abs(game_time - self._last_seen_game_time) > 1e-6
                and game_time > GAME_TIME_RESET_THRESHOLD):
            self._game_time_moved = True
        self._last_seen_game_time = game_time

        # 关卡切换检测：static_fields 时钟严格归 0（新关卡载入等待期，保持 0）
        # 仅当已进过关卡（game_time_moved）后，归 0 才视为"关卡切换"广播；
        # 主界面空壳时钟恒 0，game_time_moved 未置位，不广播避免误触发刷新。
        if game_time < GAME_TIME_RESET_THRESHOLD:
            if self._game_time_moved:
                if not self._game_time_reset:
                    print(f"[自动寻址] 检测到时钟归0: cur={game_time:.6f}，"
                          "判定新关卡开始", flush=True)
                    # 标记待广播（锁外由 refresh_sample 执行订阅者回调，避免死锁）
                    self._pending_reset_emit = True
                self._game_time_reset = True
            else:
                # 未进关卡（主界面空壳），恒 0 不置归0标志
                self._game_time_reset = False
        else:
            # time 恢复累计 → 解除归0标记，武装下次关卡切换
            self._game_time_reset = False

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
