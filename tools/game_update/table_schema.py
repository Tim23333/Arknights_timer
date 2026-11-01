"""C# declaration order is the verified ordinal source for these resource tables."""
from pathlib import Path

from tools.enemy_health.update_from_unpack import parse_dump
from tools.game_data import sha256_file


def build_table_schema(dump: Path) -> dict:
    classes, _ = parse_dump(dump)
    result = {}
    for name in ('StageData', 'AttributesData'):
        fields = classes.get(('Torappu', name))
        if not fields:
            raise ValueError(f'Missing table schema source: Torappu.{name}')
        aliases = {'S_extraCondition': 'extraCondition', 'S_extraInfo': 'extraInfo'}
        result[name] = [aliases.get(field, field) for field in fields
                        if field not in ('ZERO', 's_fieldMetas') and '__Hotfix' not in field]
    return {'schema_version': 1, 'source_sha256': sha256_file(dump), 'classes': result}
