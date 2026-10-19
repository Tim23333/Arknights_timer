"""原生倍率只读入口；仅读机器码，不调用 getter。

指令形状最初依据 Android 2.7.81 现场核验，运行时以指令和归属校验验收。
这里只解码需要的 ADRP/LDR/ADD/BL/MOV，
不引入完整反汇编库，也不按字节扫描猜一个看起来像倍率的浮点数。
"""

import math
import struct

from .memory import ReadFailure


def _signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def _adrp(word, pc, register):
    if word & 0x9F00001F != 0x90000000 | register:
        raise ReadFailure("unsupported_layout")
    immediate = ((word >> 5) & 0x7FFFF) << 2 | ((word >> 29) & 3)
    return (pc & ~0xFFF) + (_signed(immediate, 21) << 12)


def _branch(word, pc):
    if word & 0xFC000000 != 0x94000000:
        raise ReadFailure("unsupported_layout")
    return pc + (_signed(word & 0x3FFFFFF, 26) << 2)


def read_pause(memory, bc):
    """暂停与引擎零倍率独立；集合读失败不推断 false。"""
    pause = memory.pointer(bc + 0x278)
    memory.identity(pause, "EnableStateWithKey`1")
    keys = memory.pointer(pause + 0x10)
    memory.identity(keys, "ListSet`1")
    items = memory.pointer(keys + 0x10)
    memory.identity(items, "List`1")
    count = memory.integer(items + 0x18)
    if not 0 <= count <= 256:
        raise ReadFailure("unsupported_layout")
    return count > 0


class EngineClock:
    def __init__(self, memory):
        self.memory = memory
        self.manager_slot = self.manager = self.field_offset = 0

    def _in_library(self, address, filename):
        return any(
            start <= address < end and name.endswith("/" + filename)
            for start, end, _perms, name in self.memory.mc.regions
        )

    def _code(self, address, size):
        return struct.unpack(f"<{size // 4}I", self.memory.read_code(address, size))

    def resolve_method(self, method, klass):
        """Validate metadata ownership and every instruction in getter chain."""
        m = self.memory
        if (
            m.pointer(method + 0x20) != klass
            or m.cstring(m.pointer(method + 0x18)) != "get_timeScale"
        ):
            raise ReadFailure("unsupported_layout")
        wrapper = m.pointer(method)
        if not self._in_library(wrapper, "libil2cpp.so"):
            raise ReadFailure("unsupported_layout")
        code = self._code(wrapper, 40)
        if (
            code[0] != 0xA9BF7BF3
            or code[8] != 0xA8C17BF3
            or code[9] != 0xD61F0000
            or code[2] & 0xFFC003FF != 0xF9400260
            or code[3] & 0xFF00001F != 0xB5000000
            or code[5] & 0xFFC003FF != 0x91000000
            or code[7] & 0xFFC003FF != 0xF9000260
            or (code[2] >> 10) & 0xFFF != (code[7] >> 10) & 0xFFF
        ):
            raise ReadFailure("unsupported_layout")
        _adrp(code[4], wrapper + 16, 0)
        _branch(code[6], wrapper + 24)
        slot = _adrp(code[1], wrapper + 4, 19) + ((code[2] >> 10) & 0xFFF) * 8
        getter = m.pointer(slot)
        if not self._in_library(getter, "libunity.so"):
            raise ReadFailure("unsupported_layout")
        code = self._code(getter, 20)
        if (
            code[0] != 0xF81F0FFE
            or code[3:] != (0xF84107FE, 0xD65F03C0)
            or code[2] & 0xFFC003FF != 0xBD400000
        ):
            raise ReadFailure("unsupported_layout")
        offset = ((code[2] >> 10) & 0xFFF) * 4
        if offset != 0xFC:
            raise ReadFailure("unsupported_layout")
        manager_getter = _branch(code[1], getter + 4)
        if not self._in_library(manager_getter, "libunity.so"):
            raise ReadFailure("unsupported_layout")
        code = self._code(manager_getter, 20)
        if (
            code[0] != 0xF81F0FFE
            or code[3:] != (0xF84107FE, 0xD65F03C0)
            or code[1] & 0xFFE0001F != 0x52800000
        ):
            raise ReadFailure("unsupported_layout")
        index = (code[1] >> 5) & 0xFFFF
        if index != 7:
            raise ReadFailure("unsupported_layout")
        registry_getter = _branch(code[2], manager_getter + 8)
        if not self._in_library(registry_getter, "libunity.so"):
            raise ReadFailure("unsupported_layout")
        code = self._code(registry_getter, 16)
        if code[1] & 0xFFC003FF != 0x91000108 or code[2:] != (0xF860D900, 0xD65F03C0):
            raise ReadFailure("unsupported_layout")
        table = _adrp(code[0], registry_getter, 8) + ((code[1] >> 10) & 0xFFF)
        manager_slot = table + index * 8
        manager = m.pointer(manager_slot)
        raw = m.read(manager, 0x108)
        fixed, maximum, particle = [
            struct.unpack_from("<f", raw, i)[0] for i in (0x48, 0x100, 0x104)
        ]
        if not (0 < fixed < 1 and 0 < maximum <= 10 and 0 < particle < 1):
            raise ReadFailure("unsupported_layout")
        self.manager_slot, self.manager, self.field_offset = manager_slot, manager, offset
        return self.sample()

    def resolve(self):
        """Locate UnityEngine.Time once, borrowing existing device scanner only."""
        from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader

        m = self.memory
        owner = self

        class BorrowedScanner(DeployTrackerReader):
            def _get_channel(self):
                return owner.memory.channel

            def _read(self, address, size):
                return owner.memory.read(address, size)

            def close(self):
                pass

        scanner = BorrowedScanner(m.mc)
        classes = scanner.scan_classes(("Time",), namespace="UnityEngine") or {}
        if len(classes) != 1:
            raise ReadFailure("unsupported_layout")
        klass = next(iter(classes))
        count = struct.unpack("<H", m.read(klass + 0x120, 2))[0]
        if not 1 <= count <= 128:
            raise ReadFailure("unsupported_layout")
        methods = m.pointer(klass + 0x98)
        pointers = struct.unpack('<' + 'Q' * count, m.read(methods, count * 8))
        valid = [pointer for pointer in pointers if m.mc.is_ptr(pointer)]
        headers = scanner._scan_read_many([(pointer + 0x18, 16) for pointer in valid])
        candidates = [(pointer, struct.unpack('<QQ', raw)[0])
                      for pointer, raw in zip(valid, headers)
                      if raw and len(raw) == 16 and struct.unpack('<QQ', raw)[1] == klass]
        names = scanner._scan_read_many([(name, 128) for _, name in candidates])
        for (candidate, _), name in zip(candidates, names):
            if name and name.split(b'\0', 1)[0] == b'get_timeScale':
                return self.resolve_method(candidate, klass)
        raise ReadFailure("unsupported_layout")

    def sample(self):
        m = self.memory
        if not self.manager_slot or m.pointer(self.manager_slot) != self.manager:
            raise ReadFailure("binding_invalid")
        scale = struct.unpack("<f", m.read(self.manager + self.field_offset, 4))[0]
        if not math.isfinite(scale) or scale < 0:
            raise ReadFailure("read_failed")
        return scale
