"""Optional per-frame enemy coordinates from Unity's native Transform.

``Enemy.m_posInLastFrame`` is intentionally left untouched: the game refreshes
that field through a five-tick ticker.  This reader follows the same source used
by ``VisualObject.mapPosition`` (``transform.localPosition``) and publishes it
as a separate value.  It never estimates or falls back to the old coordinate.
"""

from __future__ import annotations

import math
import struct


class PrecisePositionReader:
    MANAGED_CACHED_PTR = 0x10
    COMPONENT_GAME_OBJECT = 0x30
    GAME_OBJECT_COMPONENTS = 0x30
    COMPONENT_PAIR_NATIVE_COMPONENT = 0x08
    TRANSFORM_HIERARCHY = 0x38
    TRANSFORM_INDEX = 0x40
    HIERARCHY_LOCAL_TRS_ARRAY = 0x18
    LOCAL_TRS_STRIDE = 0x30
    MAX_TRANSFORM_INDEX = 1_000_000

    def __init__(self, memcore, channel):
        self.mc = memcore
        self.channel = channel
        self._value_addrs: dict[int, int] = {}

    def clear(self) -> None:
        self._value_addrs.clear()

    def discard(self, enemy_addr: int) -> None:
        self._value_addrs.pop(int(enemy_addr), None)

    @staticmethod
    def _u64(data: bytes, offset: int) -> int:
        return struct.unpack_from('<Q', data, offset)[0]

    @staticmethod
    def _valid_position(x: float, y: float) -> bool:
        return (math.isfinite(x) and math.isfinite(y)
                and abs(x) < 128.0 and abs(y) < 128.0)

    def _pointers(self, sources, offset, size):
        # 保留与 sources 相同的下标，但不要把空/失效指针提交给设备端帧计划。
        # 这样某一个敌人的链断开不会错位到下一个敌人，也不会产生 0x30 一类
        # 无意义的低地址读取。
        result = [0] * len(sources)
        valid_indices = [
            index for index, source in enumerate(sources)
            if self.mc.is_ptr(int(source))
        ]
        requests = [(int(sources[index]) + offset, size)
                    for index in valid_indices]
        values = self.channel.batch_read(requests) if requests else []
        for index, data in zip(valid_indices, values):
            result[index] = self._u64(data, 0) if data else 0
        return result

    def _blocks(self, sources, size):
        result = [None] * len(sources)
        valid_indices = [
            index for index, source in enumerate(sources)
            if self.mc.is_ptr(int(source))
        ]
        requests = [(int(sources[index]), size) for index in valid_indices]
        values = self.channel.batch_read(requests) if requests else []
        for index, data in zip(valid_indices, values):
            result[index] = data
        return result

    def discover(self, enemy_addrs) -> dict[int, int]:
        """Resolve native local-position addresses for previously unseen enemies."""
        enemies = [int(addr) for addr in enemy_addrs
                   if self.mc.is_ptr(int(addr)) and int(addr) not in self._value_addrs]
        if not enemies:
            return dict(self._value_addrs)

        components = self._pointers(enemies, self.MANAGED_CACHED_PTR, 8)
        game_objects = self._pointers(components, self.COMPONENT_GAME_OBJECT, 8)
        pair_arrays = self._pointers(game_objects, self.GAME_OBJECT_COMPONENTS, 8)
        transforms = self._pointers(
            pair_arrays, self.COMPONENT_PAIR_NATIVE_COMPONENT, 8)
        transform_data = self._blocks(transforms, self.TRANSFORM_INDEX + 4)

        hierarchies, indices, owners = [], [], []
        for enemy, data in zip(enemies, transform_data):
            hierarchy = self._u64(data, self.TRANSFORM_HIERARCHY) if data else 0
            index = (struct.unpack_from('<i', data, self.TRANSFORM_INDEX)[0]
                     if data else -1)
            if (self.mc.is_ptr(hierarchy)
                    and 0 <= index < self.MAX_TRANSFORM_INDEX):
                owners.append(enemy)
                hierarchies.append(hierarchy)
                indices.append(index)

        arrays = self._pointers(
            hierarchies, self.HIERARCHY_LOCAL_TRS_ARRAY, 8)
        for enemy, array, index in zip(owners, arrays, indices):
            if self.mc.is_ptr(array):
                self._value_addrs[enemy] = array + index * self.LOCAL_TRS_STRIDE
        return dict(self._value_addrs)

    def read(self, enemy_addrs) -> dict[int, tuple[float, float]]:
        """Read current Transform positions; invalid chains are omitted."""
        enemies = [int(addr) for addr in enemy_addrs if self.mc.is_ptr(int(addr))]
        self.discover(enemies)
        present = set(enemies)
        for enemy in tuple(self._value_addrs):
            if enemy not in present:
                self._value_addrs.pop(enemy, None)

        resolved = [enemy for enemy in enemies if enemy in self._value_addrs]
        values = self.channel.batch_read([
            (self._value_addrs[enemy], 8) for enemy in resolved
        ]) if resolved else []
        result = {}
        for enemy, data in zip(resolved, values):
            if not data:
                self._value_addrs.pop(enemy, None)
                continue
            x, y = struct.unpack_from('<ff', data, 0)
            if self._valid_position(x, y):
                result[enemy] = (x, y)
            else:
                self._value_addrs.pop(enemy, None)
        return result
