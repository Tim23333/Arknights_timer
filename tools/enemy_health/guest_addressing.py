# -*- coding: utf-8 -*-
"""guest 侧 BattleController 时钟寻址器。

插件「启用自动寻址」使用的独立定位器：通过 memsrv 读 Android 游戏进程
（guest 侧），定位 ``BattleController.static_fields``，从而拿到 frame/time
地址。定位一次后跨场景（主界面/战斗）稳定复用，直至游戏进程重启。

与宿主侧寻址工具（tools/timer，pymem 读 MuMuVMMHeadless.exe）不同：
本模块走 guest 侧（adb + memsrv），复用作者 enemy_health 现成的
Il2CppClass/对象扫描链，不自造扫描逻辑。

链路：
  MemCore.connect() -> DeployTrackerReader.scan_classes('BattleController')
  -> Il2CppClass（只定位类，不依赖战斗实例，也不扫实例堆）
  -> Il2CppClass +0xB8 (STATIC_FIELDS) -> static_fields
  -> static_fields +0x14 (FIXED_FRAME_COUNT) = frame 地址
  -> static_fields +0x28 (FIXED_PLAY_TIME_FLOAT) = time 地址

// NOTICE:
// 端口隔离（code review LOW1）：GuestBattleClock 的读取通道沿用 MemCore 默认
// 27271、定位经 DeployTrackerReader 固定 27273，与敌人/部署功能通道共存。
// 原因是端口隔离需改 MemCore.__init__（加 port 参数）与 DeployTrackerReader
// _get_channel，侵入作者核心类；而 nc -L 按连接 fork，功能上不冲突。
// 生命周期检查单独使用 27275 和独立工作线程，避免其多次读取占用时钟 socket 锁。
// 两条链仅共享短临界区内的有效性标记，不共享读取事务或伪造同帧快照。
"""
from __future__ import annotations

import struct
import threading
import time
from typing import Optional, Tuple

from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader
from tools.enemy_health import game_structs as gs
from tools.enemy_health.memcore import DEFAULT_PKG, MemCore, TcpChannel


class _LifecycleTcpChannel(TcpChannel):
    """Owner shutdown is final; ordinary IO errors may still reconnect.

    A lifecycle sample performs several reads without holding the clock state
    lock. Closing between reads must not let its remaining local reference
    resurrect a retired device connection. Never change TcpChannel's shared
    self-healing behavior for the enemy/deploy/other readers.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._permanent_stop = threading.Event()

    def _check_stopped(self):
        if self._permanent_stop.is_set():
            raise RuntimeError('生命周期 TCP 通道已永久关闭')

    def open(self):
        self._check_stopped()
        try:
            super().open()
        finally:
            # close may race with an open already in progress. Reclaim the
            # late socket too, without waiting on a possibly blocked read lock.
            if self._permanent_stop.is_set():
                super().close()
        self._check_stopped()

    def _batch_read_live(self, requests):
        self._check_stopped()
        return super()._batch_read_live(requests)

    def close_permanently(self):
        self._permanent_stop.set()
        super().close()


class GuestBattleClock:
    """guest 侧战斗时钟读取器：定位 static_fields 并每 tick 读 frame/time。

    Use when:
    - 插件「启用自动寻址」开启，需要免宿主侧扫描直接读游戏时钟。
    - 主界面定位一次、进战斗后持续走秒（地址跨场景稳定）。

    Expects:
    - 模拟器已启动、游戏进程已到主界面（空壳也可定位，frame/time=0）。
    - memsrv 可部署（adb root / MuMu 默认支持）。

    Returns:
    - ``locate()``: bool，是否成功锁定 static_fields。
    - ``read_battle_clock()``: (frame:int, time:float)，读失败返回 None。
    """

    #: 时钟块读取大小（frame@0 + FP@4 + float@0x14，一次原子读）
    CLOCK_READ_SIZE = 0x18

    #: 连续读取失败多少次后标记地址失效（触发重新寻址）
    INVALIDATE_AFTER_FAILS = 5

    def __init__(self, adb_serial: Optional[str] = None,
                 package: str = DEFAULT_PKG,
                 adb_path: Optional[str] = None) -> None:
        self.mc = MemCore(adb_path=adb_path, package=package,
                          adb_serial=adb_serial)
        self.static_fields: int = 0
        self.frame_addr: int = 0
        self.time_addr: int = 0
        self._consecutive_fails = 0
        #: 最近一次 locate() 失败的原因（诊断用）
        self.last_error: str = ""
        self.lifecycle = None
        self.lifecycle_tracker = None
        self._lifecycle_due = 0.0
        self._lifecycle_sampled = 0.0
        self._lifecycle_process_due = 0.0
        self.lifecycle_error = ''
        self._init_lifecycle_state()

    def _init_lifecycle_state(self):
        self._lifecycle_lock = threading.Lock()
        self._lifecycle_revision = 0
        self._lifecycle_battle_revision = 0
        self._lifecycle_require_ack = False
        self._lifecycle_ack = None
        self._lifecycle_channel = None
        self._closed = False

    # ---------- 定位 ----------

    def locate(self) -> bool:
        """扫描 BattleController，锁定 static_fields 的 frame/time 地址。"""
        if self._closed:
            self.last_error = '寻址已取消：时钟读取器已关闭'
            return False
        pid = self.mc.connect()
        if self._closed:
            # connect may finish after owner cancellation; reclaim its late IO.
            self.mc.close()
            self.last_error = '寻址已取消：时钟读取器已关闭'
            return False
        if not pid:
            self.last_error = f"memsrv 连接失败（未获得游戏 PID）"
            return False
        locator = DeployTrackerReader(self.mc)
        locator.set_status_callback(lambda m: None)
        try:
            classes = locator.scan_classes(("BattleController",))
        except Exception as exc:
            self.last_error = f"BattleController 类扫描异常：{exc}"
            return False
        finally:
            locator.close()
        if not classes:
            self.last_error = "未扫描到 BattleController 类（游戏未启动/未进主界面？）"
            return False
        for klass in classes:
            if not self.mc.is_ptr(klass):
                continue
            sf = self.mc.read_ptr(
                klass + gs.Il2CppClassFields.STATIC_FIELDS)
            if not self.mc.is_ptr(sf):
                continue
            self.static_fields = sf
            self.frame_addr = sf + gs.BattleControllerStaticFields.FIXED_FRAME_COUNT
            # time_addr（+0x28 float）仅作诊断保留：读取路径实际从 frame_addr
            # 起一次原子读 frame u32(+0x14) + FIXED_PLAY_TIME FP(+0x18)。
            self.time_addr = sf + gs.BattleControllerStaticFields.FIXED_PLAY_TIME_FLOAT
            self.last_error = ""
            # Optional lifecycle enrichment never prevents the original clock
            # from working on unsupported game versions/layouts.
            lifecycle_locator = DeployTrackerReader(self.mc)
            try:
                from .battle_lifecycle import locate_lifecycle, LifecycleTracker
                self.lifecycle = locate_lifecycle(self.mc, klass, lifecycle_locator)
                self.lifecycle_tracker = LifecycleTracker()
            except Exception as exc:
                self.lifecycle = None
                self.lifecycle_tracker = None
                print(f'[关卡生命周期] 定位不可用，保留时钟检测：{exc}', flush=True)
            finally:
                lifecycle_locator.close()
            with self._lifecycle_lock:
                cancelled = self._closed
                if not cancelled and self.lifecycle is not None:
                    # Constructor has no IO. Register under the same short lock
                    # as close, then open outside it so shutdown never waits on
                    # device communication. A registered channel has a final gate.
                    channel = _LifecycleTcpChannel(self.mc, port=27275)
                    self._lifecycle_channel = channel
            if cancelled:
                # Also cover the unsupported-layout fallback: a late default
                # read may have reconnected mc while discovery was cancelling.
                self.mc.close()
                self.last_error = '寻址已取消：时钟读取器已关闭'
                return False
            if self.lifecycle is not None:
                # Dedicated socket/lock: moving IO to a thread alone would still
                # serialize the clock behind lifecycle reads on the same channel.
                from tools.stage_global_state.memory import MemoryAccess
                try:
                    channel.open()
                    with self._lifecycle_lock:
                        if self._closed:
                            raise RuntimeError('时钟读取器已关闭')
                        self.lifecycle.m = MemoryAccess(self.mc, channel)
                except Exception as exc:
                    self.last_error = f'生命周期独立通道不可用：{exc}'
                    self.close()
                    return False
            return not self._closed
        self.last_error = "扫到 BattleController 对象但无法解析 static_fields"
        return False

    # ---------- 读取 ----------

    def poll_lifecycle(self):
        """Single lifecycle worker owns IO/tracker; clock only reads short state."""
        if not hasattr(self, '_lifecycle_lock'):  # legacy standalone fixtures
            self._init_lifecycle_state()
        if self.lifecycle is None or self._closed:
            return []
        now = time.monotonic()
        if now < self._lifecycle_due:
            return []
        # Metadata addresses are process-scoped; check birth independently of
        # transient scene reads. Unknown identity is not a confirmed restart.
        if now >= self._lifecycle_process_due:
            self._lifecycle_process_due = now + 5.0
            try:
                stat = self.mc.shell(f'cat /proc/{int(self.mc.pid)}/stat', timeout=2)
                birth = int(stat.rsplit(')', 1)[1].split()[19])
                if birth <= 0:
                    raise ValueError('invalid process birth')
                identity = getattr(self.mc, 'process_instance', None)
                expected = getattr(self, '_lifecycle_process_birth', None)
                if expected is None and identity:
                    expected = identity[1]
                if expected is not None and birth != expected:
                    self.static_fields = 0
                self._lifecycle_process_birth = birth
                self._lifecycle_process_unknown = False
            except Exception:
                # Keep addresses, but do not publish a clock while process
                # identity is unknown. Retry cheaply without a full heap scan.
                self._lifecycle_process_unknown = True
                self._lifecycle_process_due = now + .5
        try:
            if not self.static_fields:
                raise RuntimeError('game_process_changed')
            if getattr(self, '_lifecycle_process_unknown', False):
                raise RuntimeError('game_process_unknown')
            value = self.lifecycle.sample()
            self.lifecycle_error = ''
        except Exception as exc:
            value = None
            self.lifecycle_error = str(exc)
        with self._lifecycle_lock:
            if self._closed:
                return []
            before = (self.lifecycle_tracker.ready, self.lifecycle_tracker.active)
            events = self.lifecycle_tracker.observe(value)
            if events:
                self._lifecycle_battle_revision += 1
            # Retry the owner handoff after a transient invalid observation.
            # Retries are not new battles and must not advance the identity.
            identity = (self._lifecycle_battle_revision, self.lifecycle_tracker.active)
            if (self.lifecycle_tracker.ready and self._lifecycle_require_ack
                    and self._lifecycle_ack != identity and 'ready' not in events):
                events.append('ready')
            if before != (self.lifecycle_tracker.ready, self.lifecycle_tracker.active):
                self._lifecycle_revision += 1
            # Age from read start, not completion: a long stalled check cannot
            # rejuvenate a stale observation after it finally returns.
            self._lifecycle_sampled = now
            self._lifecycle_due = time.monotonic() + self.lifecycle_tracker.interval
        return events

    def lifecycle_ready(self):
        return self.lifecycle_token(require_ack=False) is not None

    def lifecycle_token(self, *, require_ack=True):
        """Non-IO validity token, invalidated on unknown/exit/new battle/close."""
        with self._lifecycle_lock:
            if (self._closed or not self.lifecycle_tracker or not self.lifecycle_tracker.ready
                    or getattr(self, '_lifecycle_process_unknown', False)
                    or time.monotonic() - self._lifecycle_sampled >= 1.0):
                return None
            identity = (self._lifecycle_battle_revision, self.lifecycle_tracker.active)
            if require_ack and self._lifecycle_require_ack and self._lifecycle_ack != identity:
                return None
            return (self._lifecycle_revision, *identity)

    def require_lifecycle_ack(self):
        """Desktop opts in before binding this clock to either worker."""
        with self._lifecycle_lock:
            self._lifecycle_require_ack = True
            self._lifecycle_ack = None

    def acknowledge_lifecycle(self, token):
        """Only the Qt session owner may unblock a still-current ready event."""
        with self._lifecycle_lock:
            current = (self._lifecycle_revision, self._lifecycle_battle_revision,
                       self.lifecycle_tracker.active) if self.lifecycle_tracker else None
            if token is None or token != current or self._closed or not self.lifecycle_tracker.ready:
                return False
            self._lifecycle_ack = token[1:]
            return True

    def read_battle_clock(self) -> Optional[Tuple[int, float]]:
        """读 static_fields 的 frame/time 原子快照。

        Returns:
            (frame:int, time:float)，地址未锁定或读取失败返回 None。
            连续失败 ``INVALIDATE_AFTER_FAILS`` 次后置 static_fields=0，
            视为地址失效（游戏进程可能已重启），需重新 locate()。
        """
        if self._closed or not self.static_fields:
            self.last_error = "static_fields 未锁定（需先 locate()）"
            return None
        token = self.lifecycle_token() if self.lifecycle is not None else None
        if self.lifecycle is not None and token is None:
            # Known menu/exit or unknown lifecycle must not publish the static
            # clock left behind by the previous battle as a current reading.
            self.last_error = '等待当前关卡就绪或生命周期读取确认'
            return None
        raw = self.mc.read(self.frame_addr, self.CLOCK_READ_SIZE)
        if self._closed or (self.lifecycle is not None and token != self.lifecycle_token()):
            self.last_error = '时钟读取期间关卡状态失效或变化'
            return None
        if not raw or len(raw) < self.CLOCK_READ_SIZE:
            self.last_error = f"时钟块读取失败（frame_addr={hex(self.frame_addr)}）"
            return self._on_read_fail()
        decoded = self._decode_clock_snapshot(raw)
        if decoded is None:
            self.last_error = "时钟块解码失败（time 越界）"
            return self._on_read_fail()
        self._consecutive_fails = 0
        self.last_error = ""
        return decoded

    @staticmethod
    def _decode_clock_snapshot(raw: bytes) -> Optional[Tuple[int, float]]:
        """解码 static_fields+0x14 起的 frame/time 原子快照。

        Before:
        - ``raw`` 为 frame(u32) + FP(u64) 的 8 字节起步（可含后续字段）。

        After:
        - 返回 ``(frame:int, time:float)``；time 越界或字节不足返回 None。
        """
        if not raw or len(raw) < 8:
            return None
        frame = struct.unpack_from("<I", raw, 0)[0]
        time = gs.fp_to_float(struct.unpack_from("<Q", raw, 4)[0])
        if not (-1.0 <= time <= 864000.0):
            return None
        return frame, time

    def _on_read_fail(self) -> None:
        """连续读取失败计数；达阈值后标记地址失效并返回 None。"""
        self._consecutive_fails += 1
        if self._consecutive_fails >= self.INVALIDATE_AFTER_FAILS:
            self.static_fields = 0
            self.frame_addr = 0
            self.time_addr = 0
        return None

    def is_stage_locked(self) -> bool:
        """static_fields 是否已锁定（可用于判断是否已寻址）。"""
        return bool(self.static_fields)

    def close(self) -> None:
        """关闭 memsrv 连接（若有）。"""
        with self._lifecycle_lock:
            if self._closed:
                return
            self._closed = True
            self._lifecycle_revision += 1
        try:
            if self._lifecycle_channel is not None:
                self._lifecycle_channel.close_permanently()
        except Exception:
            pass
        try:
            self.mc.close()
        except Exception:
            pass


__all__ = ["GuestBattleClock"]
