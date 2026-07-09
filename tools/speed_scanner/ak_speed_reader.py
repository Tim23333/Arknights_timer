import struct
import pymem
import pymem.exception


# BattleController 实例内字段偏移（基于 dump.cs:317378-317388）
OFFSET_M_STATE = 0x22C           # int32 (State: NONE=0, INITED=1, PLAYING=2, FINISHED=3)
OFFSET_M_SPEED_LEVEL = 0x234     # int32 (SpeedLevel: SLOW=0, STANDARD=1, FAST=2, SUPER_FAST=3)

# SpeedLevel 枚举值
SPEED_SLOW_MOTION = 0
SPEED_STANDARD = 1
SPEED_FAST = 2
SPEED_SUPER_FAST = 3

SPEED_NAMES = {
    SPEED_SLOW_MOTION: "慢动作",
    SPEED_STANDARD: "1倍速",
    SPEED_FAST: "2倍速",
    SPEED_SUPER_FAST: "超级快",
}

# State 枚举值
STATE_NONE = 0
STATE_INITED = 1
STATE_PLAYING = 2
STATE_FINISHED = 3


class AKSpeedReader:
    def __init__(self, process_name="MuMuVMMHeadless.exe"):
        self.process_name = process_name
        self.pm = None
        self.speed_address = None      # m_speedLevel 绝对地址 (int32)
        self.timescale_address = None  # Time.timeScale 绝对地址 (float32)

    def connect(self):
        """附加到目标进程"""
        try:
            self.pm = pymem.Pymem(self.process_name)
            return True
        except pymem.exception.ProcessNotFound:
            self.pm = None
            return False

    def set_speed_address(self, address_hex_str):
        """设置 m_speedLevel 地址"""
        try:
            clean_str = address_hex_str.strip().replace("0x", "").replace("0X", "")
            self.speed_address = int(clean_str, 16)
            return True
        except ValueError:
            return False

    def set_timescale_address(self, address_hex_str):
        """设置 Time.timeScale 地址"""
        try:
            clean_str = address_hex_str.strip().replace("0x", "").replace("0X", "")
            self.timescale_address = int(clean_str, 16)
            return True
        except ValueError:
            return False

    def _read_int32(self, addr):
        try:
            return self.pm.read_int(addr)
        except pymem.exception.MemoryReadError:
            return None

    def _read_float(self, addr):
        try:
            return self.pm.read_float(addr)
        except pymem.exception.MemoryReadError:
            return None

    def get_speed_level(self):
        """读取当前倍速等级 (0/1/2/3)，失败返回 None"""
        if not self.pm or not self.speed_address:
            return None
        val = self._read_int32(self.speed_address)
        if val is not None and val in SPEED_NAMES:
            return val
        return None

    def get_timescale(self):
        """读取 Time.timeScale (float)，失败返回 None"""
        if not self.pm or not self.timescale_address:
            return None
        val = self._read_float(self.timescale_address)
        if val is not None and 0.0 <= val <= 10.0:
            return val
        return None

    def get_pause_state(self):
        """
        通过 Time.timeScale 判断暂停状态。
        timeScale == 0.0 → 暂停
        timeScale > 0.0  → 播放中
        返回: True=暂停, False=未暂停, None=读取失败
        """
        ts = self.get_timescale()
        if ts is None:
            return None
        return ts < 0.01  # 接近 0 视为暂停

    def get_game_state(self):
        """读取战斗状态 (0=NONE, 1=INITED, 2=PLAYING, 3=FINISHED)"""
        if not self.pm or not self.speed_address:
            return None
        return self._read_int32(self.speed_address + (OFFSET_M_STATE - OFFSET_M_SPEED_LEVEL))

    def get_all(self):
        """返回完整的倍速 + 暂停数据"""
        speed = self.get_speed_level()
        ts = self.get_timescale()
        paused = self.get_pause_state()
        state = self.get_game_state()
        return {
            "speed_level": speed,
            "speed_name": SPEED_NAMES.get(speed, "未知") if speed is not None else "未知",
            "timescale": ts,
            "is_paused": paused,
            "game_state": state,
        }
