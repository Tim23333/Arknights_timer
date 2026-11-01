import json
import struct
from types import SimpleNamespace

import pytest

from ark_parser.character.extract_character_data import parse_char_attributes
from ark_parser.enemy.extract_enemy_data import STAGE_NAMES, parse_stages
from tools.game_data import table_field_names
from tools.game_update.table_schema import build_table_schema


@pytest.mark.parametrize('new_schema', (False, True))
def test_inserted_stage_map_id_does_not_shift_flags_or_later_strings(new_schema):
    names = list(STAGE_NAMES)
    if new_schema:
        names.insert(names.index('canUseCharm'), 'levelMapId')
    expected = {'canUseCharm': True, 'isStagePatch': True, 'mainStageId': 'main_05-10',
                'useSpecialSizeMapPreview': True}
    if new_schema:
        expected['levelMapId'] = 'map_main_05-10'
    fields = [None] * len(names)
    data = bytearray(1000 + len(names) * 4)
    strings, scalars = {}, {4: 16, 30: 10}
    for name, value in expected.items():
        slot = 1000 + names.index(name) * 4
        fields[names.index(name)] = slot
        if isinstance(value, str):
            strings[slot + 10000] = value
        else:
            scalars[slot] = value
            # Adjacent packed flags are not part of this one-byte boolean.
            struct.pack_into('<I', data, slot, 0x01010001)
    fb = SimpleNamespace(root=0, d=data, table_fields=lambda pos: [4] if pos == 0 else fields,
                         i32=scalars.__getitem__, read_dict=lambda vec: [('main_05-10', 30)],
                         is_table=lambda pos: pos == 40, target_of=lambda pos: pos + 10000,
                         is_string=strings.__contains__, read_string=strings.__getitem__)
    assert parse_stages(fb, names) == {'main_05-10': expected}


@pytest.mark.parametrize('new_schema', (False, True))
def test_inserted_block_volume_preserves_float_attributes_and_boolean_immunity(new_schema):
    values = [('maxHp', 1000), ('damageHitrateMagical', 0.75)]
    if new_schema:
        values.append(('blockVolume', 3))
    values += [('abilityRangeForwardExtend', 1.25), ('slowDown', 0.125), ('stunImmune', True)]
    data = bytearray(4 + len(values) * 4)
    for index, (_, value) in enumerate(values):
        struct.pack_into('<f' if isinstance(value, float) else '<i', data, 4 + index * 4, value)
    fb = SimpleNamespace(size=len(data), d=data,
                         table_fields=lambda pos: list(range(4, len(data), 4)),
                         i32=lambda pos: struct.unpack_from('<i', data, pos)[0])
    assert parse_char_attributes(fb, 0, [name for name, _ in values]) == dict(values)


def test_table_schema_uses_current_declaration_order_and_removes_only_known_static_fields(tmp_path):
    dump = tmp_path / 'dump.cs'
    dump.write_text('// Namespace: Torappu\npublic class StageData\n{\n'
                    ' public string levelMapId; // 0x100\n public int S_extraInfo; // 0x108\n}\n'
                    '// Namespace: Torappu\npublic class AttributesData\n{\n'
                    ' public static int ZERO; // 0x0\n public int maxHp; // 0x10\n'
                    ' public int blockVolume; // 0x1DC\n}\n', encoding='utf-8')
    result = build_table_schema(dump)
    assert result['classes'] == {'StageData': ['levelMapId', 'extraInfo'],
                                 'AttributesData': ['maxHp', 'blockVolume']}
    path = tmp_path / 'table_fields.json'
    path.write_text(json.dumps(result), encoding='utf-8')
    assert table_field_names('AttributesData', ['maxHp'], path) == ['maxHp', 'blockVolume']
    with pytest.raises(ValueError, match='incomplete table field schema'):
        table_field_names('StageData', ['name'], path)


def test_declared_but_missing_schema_cannot_silently_load_legacy_ordinals(tmp_path, monkeypatch):
    (tmp_path / 'manifest.json').write_text(json.dumps({
        'schema_version': 1, 'files': {'schemas/table_fields.json': {}}}), encoding='utf-8')
    monkeypatch.setenv('ARKNIGHTS_GAME_DATA_DIR', str(tmp_path))
    with pytest.raises(FileNotFoundError):
        table_field_names('StageData', STAGE_NAMES)
