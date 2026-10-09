"""Extract only declared fields/enums needed by the Android readers.

Uses the same v29 metadata/registration layouts as Il2CppDumper. It avoids
unrelated protected RGCTX/method tables. Every offset comes from the APK's
ARM64 ELF field-offset array; PC fields are never substituted.
"""
from pathlib import Path
import struct

from tools.enemy_health.update_from_unpack import FIELD_MAP, ENUM_MAP
from tools.game_update.metadata import normalize_metadata


def decode_metadata(source: Path, output: Path) -> dict:
    raw = source.read_bytes()
    if struct.unpack_from('<I', raw)[0] == 0xFAB11BAF:
        return {'path': str(source), 'transformation': 'none'}
    data = bytearray(raw)
    # Observed mmap page transform: first page plus pages 1..4 of each 64KiB block.
    for start in [0, *range(0x1000, len(raw), 0x10000)]:
        length = 0x1000 if start == 0 else 0x4000
        end = min(start + length, len(raw))
        data[start:end] = bytes(value ^ 0x66 for value in raw[start:end])
    struct.pack_into('<II', data, 0, 0xFAB11BAF, 29)
    header = struct.unpack_from('<68I', data)
    if header[2] not in (256, 272) or (header[41] % 88 and header[41] % 92):
        raise ValueError('Unsupported Android metadata transform/layout')
    for index in range(2, header[2] // 4, 2):
        if header[index] + header[index + 1] > len(data):
            raise ValueError('Decoded metadata range outside file')
    stride = 88 if header[41] % 88 == 0 else 92
    count = header[41] // stride
    for index in range(count):
        offset = header[40] + index * stride
        name, namespace = struct.unpack_from('<2I', data, offset)
        token = struct.unpack_from('<I', data, offset + stride - 4)[0]
        if name >= header[7] or namespace >= header[7] or token >> 24 != 2:
            raise ValueError(f'Decoded Android type definition invalid: {index}')
    output.write_bytes(data)
    normalized = normalize_metadata(output, output.with_name('metadata_normalized.dat'))
    return {'path': normalized['path'], 'transformation': 'v29_xor66_mmap_pages',
            'page_size': 4096, 'block_size': 65536, 'type_count': count,
            'record_normalization': normalized}


class ElfFields:
    def __init__(self, path: Path, count: int):
        self.data = path.read_bytes()
        header = struct.unpack_from('<16sHHIQQQIHHHHHH', self.data)
        if header[0][:6] != b'\x7fELF\x02\x01' or header[2] != 183:
            raise ValueError('Expected little-endian ARM64 ELF')
        self.segments = [struct.unpack_from('<IIQQQQQQ', self.data,
                                           header[5] + i * header[9])
                         for i in range(header[10])]
        needle = struct.pack('<Q', count)
        position = 0
        candidates = []
        while (position := self.data.find(needle, position)) >= 0:
            if position >= 80 and position % 8 == 0:
                try:
                    values = struct.unpack_from('<16Q', self.data, position - 80)
                    if values[10] == values[12] == count and 0 < values[6] < 1000000:
                        self.offset(values[11], count * 8)
                        self.offset(values[7], values[6] * 8)
                        candidates.append((position - 80, values))
                except (ValueError, struct.error):
                    pass
            position += 1
        if len(candidates) != 1:
            raise ValueError(f'Expected one validated metadata registration, found {len(candidates)}')
        self.registration_offset, values = candidates[0]
        self.field_arrays = struct.unpack_from(f'<{count}Q', self.data,
                                               self.offset(values[11], count * 8))
        self.types = struct.unpack_from(f'<{values[6]}Q', self.data,
                                       self.offset(values[7], values[6] * 8))

    def offset(self, address: int, size: int = 1) -> int:
        for segment in self.segments:
            if (segment[0] == 1 and segment[3] <= address
                    and address + size <= segment[3] + segment[5]):
                return address - segment[3] + segment[2]
        raise ValueError(f'ELF address outside file-backed segment: {address:x}')

    def type(self, index: int):
        if not 0 <= index < len(self.types):
            raise ValueError('Invalid IL2CPP type index')
        return struct.unpack_from('<QI', self.data, self.offset(self.types[index], 12))


def extract_fields(binary: Path, metadata: Path, output: Path,
                   *, read_memory=None, load_bias: int = 0) -> dict:
    data = metadata.read_bytes()
    header = struct.unpack_from('<64I', data)
    if header[:2] != (0xFAB11BAF, 29) or header[41] % 88:
        raise ValueError('Field extractor supports validated v29/88 metadata only')
    count = header[41] // 88
    elf = ElfFields(binary, count)
    field_arrays = elf.field_arrays
    if read_memory is not None:
        reg_va = next(elf.registration_offset - p[2] + p[3]
                      for p in elf.segments if p[0] == 1
                      and p[2] <= elf.registration_offset < p[2] + p[5])
        block = read_memory(load_bias + reg_va, 128)
        registration = struct.unpack('<16Q', block)
        if registration[10] != count or registration[12] != count:
            raise ValueError('Live metadata registration does not match APK')
        field_arrays = struct.unpack(f'<{count}Q', read_memory(registration[11], count * 8))

    def string(index):
        if index >= header[7]:
            raise ValueError('Invalid metadata string index')
        start = header[6] + index
        end = data.find(b'\0', start, header[6] + header[7])
        if end < 0:
            raise ValueError('Unterminated metadata string')
        return data[start:end].decode('utf-8')

    records = [struct.unpack_from('<16I8H2I', data, header[40] + i * 88)
               for i in range(count)]
    names = {}

    def type_name(index, seen=None):
        if index in names:
            return names[index]
        seen = set() if seen is None else seen
        if index in seen:
            raise ValueError('Cyclic declaring type')
        seen.add(index)
        record = records[index]
        name, namespace = string(record[0]), string(record[1])
        if record[3] != 0xFFFFFFFF:
            parent, _ = elf.type(record[3])
            if not 0 <= parent < count:
                raise ValueError('Invalid declaring type definition')
            name = type_name(parent, seen)[1] + '.' + name
        names[index] = (namespace, name)
        return names[index]

    wanted = {(ns, name) for ns, name, mapping in FIELD_MAP.values()} | set(ENUM_MAP.values())
    wanted |= {('Torappu.Battle', 'BattleLogger'), ('', 'BattleLogger.LogItem'),
               ('', 'BattleLogger.CharInfo'), ('', 'BattleController.ReplayController')}
    default_values = {}
    for off in range(header[16], header[16] + header[17], 12):
        field, typ, value = struct.unpack_from('<3i', data, off)
        default_values[field] = (typ, value)
    lines = ['// Field-only extraction from the current Android APK. No method/RGCTX inference.']
    emitted = []
    for index, record in enumerate(records):
        key = type_name(index)
        if key not in wanted:
            continue
        is_enum = bool(record[24] & 2)
        field_start, field_count = record[8], record[18]
        if field_count and field_start == 0xFFFFFFFF:
            raise ValueError('Invalid field start')
        lines += [f'// Namespace: {key[0]}',
                  f'public {"enum" if is_enum else "class"} {key[1]}', '{']
        field_block = None
        if not is_enum and field_count and field_arrays[index]:
            if read_memory is not None:
                field_block = read_memory(field_arrays[index], field_count * 4)
            else:
                offset = elf.offset(field_arrays[index], field_count * 4)
                field_block = elf.data[offset:offset + field_count * 4]
        for j in range(field_count):
            fi = field_start + j
            name_index, typ, token = struct.unpack_from('<3I', data, header[24] + fi * 12)
            name = string(name_index)
            _, bits = elf.type(typ)
            if is_enum:
                if fi not in default_values:
                    continue
                _, vi = default_values[fi]
                value = data[header[18] + vi]
                if value >= 128:
                    raise ValueError(f'Unsupported large enum literal: {key}.{name}')
                value = (value >> 1) ^ -(value & 1)
                lines.append(f'    public const {key[1]} {name} = {value};')
            else:
                if field_block is None:
                    continue
                value = struct.unpack_from('<i', field_block, j * 4)[0]
                if value < 0:
                    continue
                if record[24] & 1 and not bits & 0x10:
                    value -= 16
                if not 0 <= value <= 0x10000:
                    raise ValueError(f'Invalid field offset: {key}.{name}')
                lines.append(f'    public int {name}; // 0x{value:X}')
        lines.append('}')
        emitted.append('.'.join(part for part in key if part))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return {'type_count': count, 'registration_file_offset': hex(elf.registration_offset),
            'emitted_types': emitted, 'mode': 'live_field_only' if read_memory else 'field_only'}
