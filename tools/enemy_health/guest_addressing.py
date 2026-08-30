# -*- coding: utf-8 -*-
"""guest 侧 BattleController 时钟寻址器。

插件「启用自动寻址」使用的独立定位器：通过 memsrv 读 Android 游戏进程
（guest 侧），定位 ``BattleController.static_fields``，从而拿到 frame/time
地址。定位一次后跨场景（主界面/战斗）稳定复用，直至游戏进程重启。

与宿主侧寻址工具（tools/timer，pymem 读 MuMuVMMHeadless.exe）不同：
本模块走 guest 侧（adb + memsrv），复用作者 enemy_health 现成的
Il2CppClass/对象扫描链，不自造扫描逻辑。

链路：
  MemCore.connect() -> DeployTrackerReader._scan_class_objects('BattleController')
  -> 对象 +0x0 -> Il2CppClass
  -> Il2CppClass +0xB8 (STATIC_FIELDS) -> static_fields
  -> static_fields +0x14 (FIXED_FRAME_COUNT) = frame 地址
  -> static_fields +0x28 (FIXED_PLAY_TIME_FLOAT) = time 地址

// NOTICE:
// 端口隔离（code review LOW1）：GuestBattleClock 的读取通道沿用 MemCore 默认
// 27271、定位经 DeployTrackerReader 固定 27273，与敌人/部署功能通道共存。
// 原因是端口隔离需改 MemCore.__init__（加 port 参数）与 DeployTrackerReader
// _get_channel，侵入作者核心类；而 nc -L 按连接 fork，功能上不冲突。
// 若未来出现通道间互相误伤，再引入独立端口（如 27275）。
"""
from __future__ import annotations

import struct
from typing import Optional, Tuple

from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader
from tools.enemy_health import game_structs as gs
from tools.enemy_health.memcore import DEFAULT_PKG, MemCore


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

    # ---------- 定位 ----------

    def locate(self) -> bool:
        """扫描 BattleController，锁定 static_fields 的 frame/time 地址。"""
        pid = self.mc.connect()
        if not pid:
            self.last_error = f"memsrv 连接失败（未获得游戏 PID）"
            return False
        locator = DeployTrackerReader(self.mc)
        locator.set_status_callback(lambda m: None)
        try:
            objects = locator._scan_class_objects(("BattleController",))
        except Exception as exc:
            self.last_error = f"BattleController 类扫描异常：{exc}"
            return False
        bc_objs = objects.get("BattleController", ())
        if not bc_objs:
            self.last_error = "未扫描到 BattleController 对象（游戏未启动/未进主界面？）"
            return False
        for bc in bc_objs:
            klass = self.mc.read_ptr(bc)
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
            return True
        self.last_error = "扫到 BattleController 对象但无法解析 static_fields"
        return False

    # ---------- 读取 ----------

    def read_battle_clock(self) -> Optional[Tuple[int, float]]:
        """读 static_fields 的 frame/time 原子快照。

        Returns:
            (frame:int, time:float)，地址未锁定或读取失败返回 None。
            连续失败 ``INVALIDATE_AFTER_FAILS`` 次后置 static_fields=0，
            视为地址失效（游戏进程可能已重启），需重新 locate()。
        """
        if not self.static_fields:
            self.last_error = "static_fields 未锁定（需先 locate()）"
            return None
        raw = self.mc.read(self.frame_addr, self.CLOCK_READ_SIZE)
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
        try:
            self.mc.close()
        except Exception:
            pass


__all__ = ["GuestBattleClock"]
