"""Normalize the observed Arknights v29 extended type-definition record.

Il2CppDumper v6.7.46 expects 88-byte v29 definitions. This client uses a
92-byte record with one extra 32-bit field immediately before the counts.
Only a cache copy is rewritten; original binaries remain the source of record.
Layout reference: Perfare/Il2CppDumper Il2Cpp/MetadataClass.cs.
"""
from pathlib import Path
import struct


def normalize_metadata(source: Path, output: Path) -> dict:
    data = source.read_bytes()
    if len(data) < 272:
        raise ValueError('Truncated IL2CPP metadata header')
    header = list(struct.unpack_from('<68I', data))
    if header[:2] != [0xFAB11BAF, 29]:
        return {'normalized': False, 'path': str(source), 'reason': 'non-v29 metadata'}
    start, size = header[40:42]
    if start + size > len(data):
        raise ValueError('Invalid metadata type-definition range')
    if size % 88 == 0:
        return {'normalized': False, 'path': str(source), 'record_size': 88}
    if size % 92:
        raise ValueError('Unsupported v29 metadata type-definition layout')
    count = size // 92
    # Reject other layouts instead of guessing where their additional field lives.
    for index in range(count):
        token = struct.unpack_from('<I', data, start + index * 92 + 88)[0]
        name, namespace = struct.unpack_from('<2I', data, start + index * 92)
        if token != 0x02000000 + index + 1 and token >> 24 != 2:
            raise ValueError(f'Invalid extended type token at {index}')
        if name >= header[7] or namespace >= header[7]:
            raise ValueError(f'Invalid extended type name at {index}')
    records = b''.join(data[start + i * 92:start + i * 92 + 64]
                       + data[start + i * 92 + 68:start + (i + 1) * 92]
                       for i in range(count))
    delta = size - len(records)
    normalized = bytearray(data[:start] + records + data[start + size:])
    for index in range(2, len(header), 2):
        if header[index] >= start + size:
            header[index] -= delta
    header[41] = len(records)
    struct.pack_into('<68I', normalized, 0, *header)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(normalized)
    return {'normalized': True, 'path': str(output), 'source_record_size': 92,
            'record_size': 88, 'type_count': count, 'removed_field_offset': 64}
