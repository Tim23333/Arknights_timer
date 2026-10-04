"""Native record identities preserve ambiguous aliases without merging actors."""
from copy import deepcopy


def registrations(native_id, native, definitions):
    if not isinstance(native_id, str) or not native_id:
        raise ValueError('Native level ID required')
    rows = len(native['mapData']['map']); records = []; aliases = {}
    directions = {'RIGHT': 'right', 'LEFT': 'left', 'UP': 'up', 'DOWN': 'down'}
    for bucket in ('characterInsts', 'tokenInsts'):
        for index, record in enumerate(native.get('predefines', {}).get(bucket) or []):
            key = record['inst']['characterKey']
            if key not in definitions:
                raise ValueError('Required predefined consumer absent: ' + key)
            raw_position = record['position']
            if any(type(raw_position.get(k)) is not int for k in ('row', 'col')):
                raise ValueError('Source predefined position must use integer coordinates')
            if record['direction'] not in directions or type(record['hidden']) is not bool:
                raise ValueError('Unsupported source predefined direction or hidden state')
            registration_key = native_id + '/' + bucket + '/' + str(index)
            alias = record.get('alias')
            records.append({'native_id': native_id, 'bucket': bucket, 'record_index': index,
                'raw_native': deepcopy(record), 'raw_alias': alias, 'registration_key': registration_key,
                'initial_entity': {'definition': definitions[key], 'registration_key': registration_key,
                    'instanceAlias': None, 'position': {'row': rows - 1 - raw_position['row'], 'col': raw_position['col']},
                    'facing': directions[record['direction']], 'active': not record['hidden']}})
            if alias is not None:
                if not isinstance(alias, str) or not alias:
                    raise ValueError('Raw alias must be nonempty or null')
                aliases.setdefault(alias, []).append(registration_key)
    return {'native_id': native_id, 'records': records, 'aliases': aliases,
            'policy': 'Runtime lookup by native record key; raw aliases remain source data. Ambiguous alias requests reject.'}


def resolve_reference(profile, *, alias=None, record_key=None):
    if (alias is None) == (record_key is None):
        raise ValueError('Exactly one alias or record_key required')
    keys = {r['registration_key'] for r in profile['records']}
    if record_key is not None:
        if not isinstance(record_key, str) or record_key not in keys:
            raise ValueError('Unknown native record identity')
        return record_key
    matches = profile['aliases'].get(alias, [])
    if len(matches) != 1:
        raise ValueError('Native alias is absent or ambiguous; specify the record identity')
    return matches[0]
