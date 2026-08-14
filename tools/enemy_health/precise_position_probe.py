"""Live probe for Unity Transform-backed enemy coordinates.

This diagnostic intentionally does not touch ``Enemy.m_posInLastFrame`` or the
normal polling path.  It starts from UnityEngine.Object.m_CachedPtr (+0x10),
walks a shallow native pointer graph and reports float pairs that look like the
enemy's managed ``VisualObject.mapPosition``.  Once a stable native layout is
confirmed, the small reader will live in ``precise_position.py``; this file is
kept as an update/calibration aid.
"""

from __future__ import annotations

import argparse
import math
import struct
import time
from dataclasses import dataclass

try:
    from .enemy_reader import EnemyReader
except ImportError:  # direct ``python tools/enemy_health/...py`` execution
    from enemy_reader import EnemyReader


@dataclass(frozen=True)
class Candidate:
    path: tuple[int, ...]
    addr: int
    offset: int
    x: float
    y: float

    @property
    def value_addr(self) -> int:
        return self.addr + self.offset


def _qword(data: bytes, offset: int) -> int:
    return struct.unpack_from('<Q', data, offset)[0]


def _floats(data: bytes, offset: int) -> tuple[float, float]:
    return struct.unpack_from('<ff', data, offset)


def _finite_map_pair(x: float, y: float) -> bool:
    return math.isfinite(x) and math.isfinite(y) and abs(x) < 128 and abs(y) < 128


def _region_name(reader: EnemyReader, addr: int) -> str:
    for start, end, perms, name in reader.mc.regions:
        if start <= addr < end:
            return f'{perms} {name or "anonymous"}'
    return 'unmapped'


def _walk_candidates(reader: EnemyReader, root: int, target: tuple[float, float],
                     *, depth: int = 3, block_size: int = 0x200,
                     tolerance: float = 0.35) -> list[Candidate]:
    """Walk native pointers and find adjacent floats close to target.

    Restrict fan-out and remember visited blocks: the aim is layout discovery,
    not a heap scan.  Pointer offsets remain in the result so repeated samples
    can prove whether a candidate updates every logic frame.
    """
    pending = [(root, ())]
    seen: set[int] = set()
    found: list[Candidate] = []
    target_x, target_y = target
    for level in range(depth + 1):
        current, pending = pending, []
        if not current:
            break
        addrs = []
        paths = []
        for addr, path in current:
            aligned = addr & ~7
            if aligned in seen or not reader.mc.is_ptr(aligned):
                continue
            seen.add(aligned)
            addrs.append(aligned)
            paths.append(path)
        blocks = reader._chan.batch_read([(addr, block_size) for addr in addrs])
        for addr, path, data in zip(addrs, paths, blocks):
            if not data:
                continue
            for offset in range(0, len(data) - 7, 4):
                x, y = _floats(data, offset)
                if _finite_map_pair(x, y) and abs(x - target_x) <= tolerance \
                        and abs(y - target_y) <= tolerance:
                    found.append(Candidate(path, addr, offset, x, y))
            if level >= depth:
                continue
            # Native Unity objects mostly use 8-byte aligned pointers.  Limit
            # fan-out per block to keep this probe fast and deterministic.
            children = []
            for offset in range(0, min(len(data), 0x180) - 7, 8):
                ptr = _qword(data, offset)
                if reader.mc.is_ptr(ptr) and ptr not in seen:
                    children.append((ptr, path + (offset,)))
            pending.extend(children[:64])
    unique = {}
    for item in found:
        unique[(item.addr, item.offset)] = item
    return sorted(unique.values(), key=lambda item: (len(item.path), item.path, item.offset))


def _dump_native_graph(reader: EnemyReader, root: int, *, levels: int = 2) -> None:
    """Print a compact native pointer graph when coordinate matching fails."""
    frontier = [(root, ())]
    seen = set()
    print('\n原生指针图（仅用于校准 Unity 版本布局）')
    for level in range(levels + 1):
        current, frontier = frontier, []
        addrs, paths = [], []
        for addr, path in current[:96]:
            if addr in seen or not reader.mc.is_ptr(addr):
                continue
            seen.add(addr)
            addrs.append(addr)
            paths.append(path)
        blocks = reader._chan.batch_read([(addr, 0x100) for addr in addrs])
        for addr, path, data in zip(addrs, paths, blocks):
            if not data:
                continue
            label = ''.join(f'+0x{offset:x}/' for offset in path) or 'root'
            pointers = []
            for offset in range(0, 0x100, 8):
                ptr = _qword(data, offset)
                if reader.mc.is_ptr(ptr):
                    pointers.append((offset, ptr))
            float_preview = []
            for offset in range(0, 0x40, 4):
                value = struct.unpack_from('<f', data, offset)[0]
                if math.isfinite(value) and 0.001 <= abs(value) < 1000:
                    float_preview.append(f'+{offset:x}:{value:.4g}')
            print(f'  L{level} {label:<24} 0x{addr:x} '
                  f'[{_region_name(reader, addr)}] '
                  f'ptrs={" ".join(f"+{o:x}=0x{p:x}" for o, p in pointers[:16]) or "-"} '
                  f'floats={" ".join(float_preview[:12]) or "-"}')
            if level < levels:
                frontier.extend((ptr, path + (offset,)) for offset, ptr in pointers[:32])


def _sample(reader: EnemyReader, candidates: list[Candidate], enemy_addr: int,
            count: int, interval: float, *, wait_for_motion: float = 0.0) -> None:
    reqs = [(enemy_addr + 0x408, 8)] + [(item.value_addr, 8) for item in candidates]
    previous = None
    changed = [0] * len(reqs)
    print('\n连续采样（old=m_posInLastFrame，cN=原生候选）')
    if wait_for_motion > 0:
        print(f'等待坐标开始变化（最长 {wait_for_motion:.1f}s）...')
        deadline = time.monotonic() + wait_for_motion
        baseline = None
        while time.monotonic() < deadline:
            values = reader._chan.batch_read(reqs)
            pairs = [_floats(data, 0) if data else (math.nan, math.nan) for data in values]
            if baseline is None:
                baseline = pairs
            elif any(before != after for before, after in zip(baseline, pairs)):
                print('已检测到移动，开始计数。')
                break
            time.sleep(interval)
        else:
            print('等待期间没有移动，仍执行静态采样。')
    for index in range(count):
        values = reader._chan.batch_read(reqs)
        pairs = [_floats(data, 0) if data else (math.nan, math.nan) for data in values]
        if previous is not None:
            for pos, (before, after) in enumerate(zip(previous, pairs)):
                if before != after:
                    changed[pos] += 1
        if index < 20 or index == count - 1:
            rendered = ' '.join(
                f'{"old" if pos == 0 else f"c{pos - 1}"}={x:.6f},{y:.6f}'
                for pos, (x, y) in enumerate(pairs))
            print(f'{index:03d} {rendered}')
        previous = pairs
        time.sleep(interval)
    print('变化次数:', ' '.join(
        f'{"old" if pos == 0 else f"c{pos - 1}"}={value}'
        for pos, value in enumerate(changed)))


def _unity_transform_candidate(reader: EnemyReader, enemy_addr: int) -> Candidate | None:
    """Resolve the Unity 2021 native Transform local-position entry.

    Layout verified from the Android libunity objects:
      managed Component +0x10 -> native Component
      native Component +0x30 -> native GameObject
      GameObject +0x30 -> component-pair array
      first pair +0x08 -> native Transform
      Transform +0x38/+0x40 -> hierarchy / transform index
      hierarchy +0x18 -> 0x30-byte local TRS array
    """
    blocks = reader._chan.batch_read([(enemy_addr, 0x18)])
    if not blocks[0]:
        return None
    native_component = _qword(blocks[0], 0x10)
    if not reader.mc.is_ptr(native_component):
        return None
    component = reader._chan.batch_read([(native_component, 0x38)])[0]
    if not component:
        return None
    game_object = _qword(component, 0x30)
    if not reader.mc.is_ptr(game_object):
        return None
    game_data = reader._chan.batch_read([(game_object, 0x38)])[0]
    if not game_data:
        return None
    component_pairs = _qword(game_data, 0x30)
    if not reader.mc.is_ptr(component_pairs):
        return None
    pairs = reader._chan.batch_read([(component_pairs, 0x10)])[0]
    if not pairs:
        return None
    transform = _qword(pairs, 0x08)
    if not reader.mc.is_ptr(transform):
        return None
    transform_data = reader._chan.batch_read([(transform, 0x48)])[0]
    if not transform_data:
        return None
    hierarchy = _qword(transform_data, 0x38)
    transform_index = struct.unpack_from('<i', transform_data, 0x40)[0]
    if not reader.mc.is_ptr(hierarchy) or not (0 <= transform_index < 1_000_000):
        return None
    hierarchy_data = reader._chan.batch_read([(hierarchy, 0x28)])[0]
    if not hierarchy_data:
        return None
    trs_array = _qword(hierarchy_data, 0x18)
    if not reader.mc.is_ptr(trs_array):
        return None
    value_addr = trs_array + transform_index * 0x30
    value = reader._chan.batch_read([(value_addr, 0x0c)])[0]
    if not value:
        return None
    x, y = _floats(value, 0)
    if not _finite_map_pair(x, y):
        return None
    return Candidate((0x10, 0x30, 0x30, 0x08, 0x38, 0x18),
                     value_addr, 0, x, y)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='敌人 Unity Transform 精确坐标探针')
    parser.add_argument('--serial', default='127.0.0.1:16384')
    parser.add_argument('--enemy', type=int, default=0,
                        help='选择当前存活敌人的序号（默认 0）')
    parser.add_argument('--depth', type=int, default=3)
    parser.add_argument('--samples', type=int, default=90)
    parser.add_argument('--interval', type=float, default=1 / 120)
    parser.add_argument('--wait-motion', type=float, default=0.0,
                        help='正式采样前等待任一坐标开始变化的秒数')
    args = parser.parse_args(argv)

    reader = EnemyReader(adb_serial=args.serial)
    try:
        reader.connect()
        if not reader.bootstrap():
            raise RuntimeError('敌人地址定位失败')
        snapshot = reader.poll_fast()
        active = [enemy for enemy in snapshot['enemies'] if enemy.addr and enemy.alive]
        if not active:
            raise RuntimeError('当前没有可采样的存活敌人')
        enemy = active[max(0, min(args.enemy, len(active) - 1))]
        header = reader._chan.batch_read([(enemy.addr, 0x18)])[0]
        cached_ptr = _qword(header, 0x10) if header else 0
        if not reader.mc.is_ptr(cached_ptr):
            raise RuntimeError(f'm_CachedPtr 无效: 0x{cached_ptr:x}')
        print(f'敌人: {enemy.name} @ 0x{enemy.addr:x}')
        print(f'旧坐标: ({enemy.pos_x:.6f}, {enemy.pos_y:.6f})')
        print(f'm_CachedPtr: 0x{cached_ptr:x} [{_region_name(reader, cached_ptr)}]')
        unity_candidate = _unity_transform_candidate(reader, enemy.addr)
        if unity_candidate:
            print('Unity Transform localPosition: '
                  f'0x{unity_candidate.value_addr:x} = '
                  f'({unity_candidate.x:.6f}, {unity_candidate.y:.6f})')
            _sample(reader, [unity_candidate], enemy.addr, args.samples, args.interval,
                    wait_for_motion=args.wait_motion)
            return 0
        candidates = _walk_candidates(
            reader, cached_ptr, (enemy.pos_x, enemy.pos_y), depth=args.depth)
        print(f'候选数: {len(candidates)}')
        for index, item in enumerate(candidates[:24]):
            path = ''.join(f' -> +0x{offset:x}' for offset in item.path) or 'root'
            print(f'  c{index}: {path}, value +0x{item.offset:x} '
                  f'@ 0x{item.value_addr:x} = ({item.x:.6f}, {item.y:.6f}) '
                  f'[{_region_name(reader, item.addr)}]')
        if not candidates:
            _dump_native_graph(reader, cached_ptr)
            return 2
        _sample(reader, candidates[:12], enemy.addr, args.samples, args.interval,
                wait_for_motion=args.wait_motion)
        return 0
    finally:
        reader.close()


if __name__ == '__main__':
    raise SystemExit(main())
