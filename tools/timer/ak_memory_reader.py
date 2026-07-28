import struct

import pymem
import pymem.exception


class AKMemoryReader:
    def __init__(self, process_name="MuMuVMMHeadless.exe"):
        self.process_name = process_name
        self.pm = None
        self.time_address = None
        self.frame_address = None

    def connect(self):
        """尝试附加到目标进程"""
        try:
            self.pm = pymem.Pymem(self.process_name)
            return True
        except pymem.exception.ProcessNotFound:
            self.pm = None
            return False

    def set_address(self, address_hex_str):
        """设置时间地址，并自动计算帧数地址"""
        try:
            clean_str = address_hex_str.strip().replace("0x", "").replace("0X", "")
            self.time_address = int(clean_str, 16)

            # 自动计算帧数地址：时间地址减去 0x14
            self.frame_address = self.time_address - 0x14
            return True
        except ValueError:
            return False

    def get_game_data(self):
        """
        同时读取当前游戏内置时间和逻辑帧数
        :return: (float 时间, int 帧数)，如果读取失败则返回 (None, None)
        """
        if not self.pm or not self.time_address:
            return None, None

        try:
            # frame 与 time 位于同一连续结构 (相差 0x14)。一次 ReadProcessMemory
            # 同时取回，避免两次读取恰好跨越逻辑帧而组成不存在的时间/帧配对。
            raw = self.pm.read_bytes(self.frame_address, 0x18)
            frame_count = struct.unpack_from("<I", raw, 0)[0]
            game_time = struct.unpack_from("<f", raw, 0x14)[0]

            if 0 <= game_time <= 100000:
                return game_time, frame_count
            return None, None
        except pymem.exception.MemoryReadError:
            return None, None
