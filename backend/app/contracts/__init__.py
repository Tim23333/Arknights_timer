"""Immutable packaged contracts; no validator or network lookup in the frame loop.

Only local ``#/$defs`` references are resolved. JSON Schema is the authority for
new field paths, routing and duplicate-source policies, not a second registry.
"""
from __future__ import annotations

import copy
import json
import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _schema():
    # Frozen modules are imported as app.*, while the data bundle destination
    # is backend/app/contracts. Do not assume those two __file__ paths match.
    # _MEIPASS is permitted for this immutable asset, never writable storage.
    path = (Path(sys._MEIPASS) / 'backend/app/contracts/stage_global.schema.json'
            if getattr(sys, 'frozen', False)
            else Path(__file__).with_name('stage_global.schema.json'))
    return json.loads(path.read_text(encoding='utf-8'))


def stage_global_contract():
    """Return an independent document for tooling and contract tests."""
    return copy.deepcopy(_schema())


def contract_specs():
    return tuple({'id': item['x-field-id'], 'domain': 'stage_global',
                  'group': item['x-capture-group'], 'paths': list(item['x-paths']),
                  'label': item['title'], 'dependencies': list(item['x-dependencies']),
                  'source_fields': copy.deepcopy(item['x-source-fields']), 'topic': item['x-topic'],
                  'null_reasons': list(_schema()['x-valid-null-reasons'].get(item['x-field-id'], ())),
                  'defaults': dict(item['x-defaults'])}
                 for item in _schema()['x-fields'])


@lru_cache(maxsize=1)
def _specs_by_id():
    return {spec['id']: spec for spec in contract_specs()}


def contract_value_paths(field_id, value):
    """Split composite state/nextWave values, never copy a scalar to two paths."""
    spec = _specs_by_id()[field_id]
    if len(spec['paths']) == 1:
        return {spec['paths'][0]: value}
    if value is None:
        if field_id == 'stage_global.nextWave':
            return {'waves.next': None, 'waves.nextSelection': 'unknown'}
        return {path: None for path in spec['paths']}
    if not isinstance(value, dict):
        raise ValueError(f'{field_id} requires a composite object')
    return {path: value.get(path.rsplit('.', 1)[-1]) for path in spec['paths']}


def _resolve(schema):
    ref = schema.get('$ref')
    if ref is None:
        return schema
    if not ref.startswith('#/$defs/'):
        raise ValueError('Only contract-local definitions are allowed')
    resolved = _schema()
    for component in ref[2:].split('/'):
        resolved = resolved[component]
    return resolved


def _shape(path):
    node = _schema()
    for component in path.split('.'):
        node = _resolve(node)['properties'][component]
    return node


def _nullable(schema):
    schema = _resolve(schema)
    types = schema.get('type', ())
    return (types == 'null' or 'null' in types
            or None in schema.get('enum', ())
            or any(_nullable(part) for part in schema.get('anyOf', ())))


def _public(value, schema, depth=0):
    """Whitelist payload shape cheaply; full semantic checks stay in tests.

    Invalid primitive values become null. Unknown object keys (including raw
    pointers in reader internals) never cross this boundary.
    """
    if depth > 16:
        return None
    schema = _resolve(schema)
    if value is None:
        return None
    if 'anyOf' in schema:
        schema = _resolve(next(part for part in schema['anyOf'] if part.get('type') != 'null'))
    if 'enum' in schema and value not in schema['enum']:
        return None
    if 'const' in schema and value != schema['const']:
        return None
    if 'type' not in schema and ('enum' in schema or 'const' in schema):
        return value
    types = schema.get('type', ())
    types = [types] if isinstance(types, str) else types
    if isinstance(value, dict) and 'object' in types:
        properties = schema.get('properties', {})
        extra = schema.get('additionalProperties', False)
        result = {}
        for key, item in value.items():
            if key not in properties and not isinstance(extra, dict):
                continue
            child = properties.get(key, extra)
            parsed = _public(item, child, depth + 1)
            if parsed is not None or _nullable(child):
                result[key] = parsed
        if any(key not in result for key in schema.get('required', ())):
            return None
        return result
    if isinstance(value, list) and 'array' in types:
        child = schema.get('items', {})
        result = [_public(item, child, depth + 1) for item in value]
        if any(item is None for item in result) and not _nullable(child):
            return None
        return result
    if type(value) is bool:
        return value if 'boolean' in types else None
    if type(value) is int:
        valid = 'integer' in types or 'number' in types
        return value if valid and schema.get('minimum', value) <= value <= schema.get('maximum', value) else None
    if type(value) is float:
        import math
        valid = 'number' in types and math.isfinite(value)
        return value if valid and schema.get('minimum', value) <= value <= schema.get('maximum', value) else None
    if isinstance(value, str):
        return value if 'string' in types else None
    return None


def public_contract_value(field_id, value):
    paths = contract_value_paths(field_id, value)
    shaped = {path: _public(item, _shape(path)) for path, item in paths.items()}
    if len(shaped) == 1:
        return next(iter(shaped.values()))
    return {path.rsplit('.', 1)[-1]: item for path, item in shaped.items()}
