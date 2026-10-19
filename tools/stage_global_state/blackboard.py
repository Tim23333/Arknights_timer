"""Bounded tile parameter reads, sharing the existing guarded memory channel.

Android 2.7.81: TileData.blackboard is List<DataPair>; Tile.m_blackboard is
Torappu.Blackboard with the same List header. These are parameters, not proof
of a tile's current mode. No addresses or cross-frame value cache are exposed.
"""
import math
import struct

from .memory import ReadFailure


def read_boards(memory, addresses, *, runtime=False):
    """Return pointer→entries; null pointers mean known absence, not read failure.

    One failed batch rejects its blackboards, not the caller's basic map. Header
    rechecks bypass resident values to detect concurrent List mutations.
    """
    pointers = list(dict.fromkeys(addresses))
    if len(pointers) > 16384:
        raise ReadFailure('unsupported_layout')
    result = {0: None}
    active = [p for p in pointers if p]
    if any(not memory.mc.is_ptr(p) for p in active):
        raise ReadFailure('binding_invalid')
    blocks = memory.read_many([(p, 0x20) for p in active])
    headers, counts, arrays = [], [], []
    for raw in blocks:
        klass = struct.unpack_from('<Q', raw)[0]
        name, namespace = memory.class_identity(klass)
        expected = ('Blackboard', 'Torappu') if runtime else ('List`1', 'System.Collections.Generic')
        if (name, namespace) != expected:
            raise ReadFailure('unsupported_layout')
        items, count, _version = struct.unpack_from('<Qii', raw, 0x10)
        if not 0 <= count <= 256 or (count and not memory.mc.is_ptr(items)):
            raise ReadFailure('unsupported_layout')
        arrays.append(items); counts.append(count); headers.append(raw[0x10:0x20])
    if sum(counts) > 32768:
        raise ReadFailure('unsupported_layout')
    capacities = iter(memory.read_many([(a + 0x18, 4) for a, n in zip(arrays, counts) if n]))
    for count in counts:
        if count and not count <= struct.unpack('<i', next(capacities))[0] <= 65536:
            raise ReadFailure('unsupported_layout')
    bodies = iter(memory.read_many([(a + 0x20, n * 0x18) for a, n in zip(arrays, counts) if n]))
    decoded, string_addresses = [], []
    for count in counts:
        entries = list(struct.iter_unpack('<Qf4xQ', next(bodies))) if count else []
        if any(not key or not math.isfinite(value) for key, value, _ in entries):
            raise ReadFailure('unsupported_layout')
        decoded.append(entries)
        string_addresses.extend(p for key, _, text in entries for p in (key, text))
    strings = memory.strings(string_addresses, limit=2048)
    for pointer, entries in zip(active, decoded):
        keys = [strings[key] for key, _, _ in entries]
        if any(not key for key in keys) or len(set(keys)) != len(keys):
            raise ReadFailure('unsupported_layout')
        result[pointer] = [{'key': strings[key], 'value': value, 'valueStr': strings[text]}
                           for key, value, text in entries]
    if memory.read_many([(p + 0x10, 16) for p in active], structural_check=True) != headers:
        raise ReadFailure('binding_invalid')
    return result


def board_fields(value=None, *, runtime=False, reason=''):
    """Do not label a successfully read parameter set as dynamic mode state."""
    return {'blackboard': value, 'blackboardMeta': {
        'state': 'unavailable' if reason else 'absent' if value is None else 'available',
        'source': 'runtime_parameters' if runtime else 'initial_configuration',
        'reason': reason}}
