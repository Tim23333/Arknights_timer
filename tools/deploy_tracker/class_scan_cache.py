"""Bounded, process-scoped hints for IL2CPP class discovery.

No entity addresses or gameplay values are cached. Every hit re-reads class
identity; callers still scan live objects and validate ownership normally.
"""
from collections import OrderedDict
from threading import Lock
import struct

_entries = OrderedDict()
_lock = Lock()
_LIMIT = 64


def _key(mc, namespace, names):
    birth = getattr(mc, 'process_instance', None)
    if not isinstance(birth, tuple) or len(birth) != 2 or not all(birth):
        return None
    return (getattr(mc, 'adb_serial', ''), getattr(mc, 'package', ''),
            getattr(mc, 'pid', None), birth, namespace, tuple(sorted(names)))


def remember(mc, namespace, classes):
    # Store each class separately so an enemy-only lookup can reuse deploy's
    # combined BattleController/BattleInOut discovery without retaining a heap.
    with _lock:
        for name in set(classes.values()):
            key = _key(mc, namespace, (name,))
            if key is None:
                return
            addresses = tuple(address for address, value in classes.items() if value == name)
            if len(addresses) > 256:
                continue  # Do not retain an unexpectedly large metadata result.
            _entries[key] = addresses
            _entries.move_to_end(key)
        while len(_entries) > _LIMIT:
            _entries.popitem(last=False)


def lookup(mc, namespace, names, read_many):
    keys = [_key(mc, namespace, (name,)) for name in names]
    if not keys or any(key is None for key in keys):
        return None
    with _lock:
        groups = [_entries.get(key) for key in keys]
    if any(not group for group in groups):
        return None
    classes = {address: name for name, group in zip(names, groups) for address in group}
    try:
        if any(not mc.is_ptr(address) for address in classes):
            raise ValueError('invalid class address')
        headers = read_many([(address + 0x10, 16) for address in classes])
        if len(headers) != len(classes) or any(raw is None or len(raw) != 16 for raw in headers):
            raise ValueError('short class header')
        pointers = [pointer for raw in headers for pointer in struct.unpack('<QQ', raw)]
        if any(not mc.is_ptr(pointer) for pointer in pointers):
            raise ValueError('invalid metadata pointer')
        strings = read_many([(pointer, 128) for pointer in pointers])
        expected = [value for name in classes.values() for value in (name, namespace)]
        if len(strings) != len(expected) or any(
            raw is None or b'\0' not in raw or raw.split(b'\0', 1)[0] != value.encode('ascii')
            for raw, value in zip(strings, expected)
        ):
            raise ValueError('class identity changed')
    except (ValueError, OSError, RuntimeError, struct.error):
        with _lock:
            for key in keys:
                _entries.pop(key, None)
        return None
    return classes
