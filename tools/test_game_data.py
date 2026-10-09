import json
import struct
from pathlib import Path

import pytest

from extract_tables import extract_tables
from tools import game_data
from tools.game_update.metadata import normalize_metadata
from tools.game_update.update import snapshot_android


def bundle(tmp_path, monkeypatch):
    root = tmp_path / 'bundle'
    root.mkdir()
    (root / 'manifest.json').write_text('{"schema_version":1}', encoding='utf-8')
    monkeypatch.setenv(game_data.ENV_NAME, str(root))
    return root


def test_hot_layer_overrides_hash_and_timestamp(tmp_path):
    sources = [tmp_path / 'base', tmp_path / 'hot']
    for directory, table_id, tag in zip(sources, ('character_tableaaaa', 'character_tablebbbb'), (b'old', b'new')):
        directory.mkdir()
        name = table_id.encode()
        (directory / 'table.dat').write_bytes(struct.pack('<I', len(name)) + name + tag)
    output = tmp_path / 'tables'
    rows = extract_tables(sources, output)
    assert [p.name for p in output.iterdir()] == ['character_table.bin']
    assert (output / 'character_table.bin').read_bytes().endswith(b'new')
    assert rows['character_table']['table_id'] == 'character_tablebbbb'


def test_invalid_extraction_preserves_previous_output(tmp_path):
    output = tmp_path / 'tables'
    output.mkdir()
    old = output / 'character_table.bin'
    old.write_bytes(b'previous data')
    with pytest.raises(ValueError, match='preserved'):
        extract_tables([tmp_path / 'missing'], output)
    assert old.read_bytes() == b'previous data'


def test_incomplete_bundle_never_falls_back_to_old_table(tmp_path, monkeypatch):
    bundle(tmp_path, monkeypatch)
    old = tmp_path / 'legacy'
    old.mkdir()
    (old / 'character_tableaaaa.bin').write_bytes(b'old')
    with pytest.raises(FileNotFoundError):
        game_data.table_path('character_table', old)


def test_catalog_overrides_and_fingerprint(tmp_path, monkeypatch):
    root = bundle(tmp_path, monkeypatch)
    (root / 'catalogs').mkdir()
    (root / 'overrides').mkdir()
    (root / 'catalogs/char_names.json').write_text('{"a":"original","b":"kept"}')
    before = game_data.fingerprint()
    (root / 'overrides/char_names.json').write_text('{"a":"edited"}')
    assert game_data.load_catalog('char_names') == {'a': 'edited', 'b': 'kept'}
    assert game_data.fingerprint() != before


def test_offset_platform_cannot_be_changed_by_override(tmp_path, monkeypatch):
    root = bundle(tmp_path, monkeypatch)
    (root / 'offsets').mkdir()
    (root / 'overrides').mkdir()
    (root / 'offsets/android_arm64.json').write_text('{"platform":"android_arm64"}')
    (root / 'overrides/android_arm64.json').write_text('{"platform":"pc_x64"}')
    with pytest.raises(ValueError, match='cannot change platform'):
        game_data.load_offsets('android_arm64')


def test_emulator_snapshot_rejects_phone_before_any_adb_call(tmp_path):
    with pytest.raises(ValueError, match='local emulator'):
        snapshot_android(tmp_path, 'physical-device-serial')


def test_extended_metadata_removes_only_extra_record_field(tmp_path):
    header = [0] * 68
    header[:2] = [0xFAB11BAF, 29]
    header[2], header[6], header[7] = 272, 272, 4
    header[40], header[41] = 276, 92
    header[42], header[43] = 368, 8
    record = bytearray(range(92))
    struct.pack_into('<2I', record, 0, 0, 0)
    struct.pack_into('<I', record, 88, 0x02000001)
    source = tmp_path / 'source.dat'
    source.write_bytes(struct.pack('<68I', *header) + b'A\0\0\0' + record + b'after123')
    output = tmp_path / 'normalized.dat'
    info = normalize_metadata(source, output)
    result = output.read_bytes()
    assert info['normalized']
    assert result[276:364] == record[:64] + record[68:]
    assert struct.unpack_from('<I', result, 42 * 4)[0] == 364
    assert result[364:] == b'after123'
    assert source.read_bytes()[276:368] == record
