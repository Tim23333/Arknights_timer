"""Typed old BuffData FB row decoding; preserve packed-byte field offsets."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT.parent/'ark_parser/enemy'))
from extract_enemy_data import FB
from tools.build_chapter01_enemy_sources import bson_source
PATH = ROOT.parent/'data/anon_textassets/buff_table352282.dat'
OUT = ROOT/'packages/campaign/chapter06_cold/source.decoded.json'
FIELDS = [('attributes', 'attributes'), ('buffKey', 'str'), ('loadFromDB', 'bool'), ('isDurableBuff', 'bool'),
    ('isDamageMissable', 'bool'), ('isSilenceable', 'bool'), ('isStunnable', 'bool'), ('isFreezable', 'bool'),
    ('isLevitatable', 'bool'), ('isGroundBoundable', 'bool'), ('statusResistable', 'byte'), ('templateKey', 'str'),
    ('disableOverride', 'bool'), ('overrideKey', 'str'), ('overrideType', 'i32'), ('maxStackCnt', 'i32'),
    ('refreshRemainingTimeWhenStackMax', 'bool'), ('clearAllStackCntWhenTimeUp', 'bool'), ('maxValidStackCnt', 'i32'),
    ('independentCharacterSource', 'bool'), ('overrideEffectKey', 'str'), ('overrideOnEventPriority', 'bool'),
    ('onEventPriority', 'i32'), ('audioSignal', 'str'), ('lifeTimeType', 'byte'), ('takeSnapshotWhenExtend', 'bool'),
    ('durationKey', 'str'), ('lifeTime', 'f32'), ('triggerLifeType', 'byte'), ('triggerCnt', 'i32'),
    ('triggerInterval', 'f32'), ('waitFirstTriggerInterval', 'bool'), ('firstTriggerInterval', 'f32'), ('priority', 'i32')]


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def attrs(f, pos):
    fields = f.table_fields(pos); flags = []; mods = []
    if fields[0] is not None:
        flags = [f.i32(s) for s in f.vector(f.target_of(fields[0]))]
    if len(fields) > 5 and fields[5] is not None:
        for slot in f.vector(f.target_of(fields[5])):
            fs = f.table_fields(f.target_of(slot))
            def value(i, method, default): return getattr(f, method)(fs[i]) if i < len(fs) and fs[i] is not None else default
            mods.append({'attributeType': value(0, 'i32', 0), 'formulaItem': value(1, 'i32', 0),
                'value': value(2, 'f32', 0), 'loadFromBlackboard': bool(f.d[fs[3]]) if len(fs)>3 and fs[3] is not None else False,
                'fetchBaseValueFromSourceEntity': bool(f.d[fs[4]]) if len(fs)>4 and fs[4] is not None else False,
                'field_offsets': fs})
    return {'abnormalFlags': flags, 'attributeModifiers': mods, 'field_offsets': fields}


def build():
    f = FB(PATH); result = {}
    for slot in f.vector(f.target_of(f.table_fields(f.root)[0])):
        entry = f.target_of(slot); pair = f.table_fields(entry); key = f.read_string(f.target_of(pair[0]))
        if key not in ('e2c_cold', 'e2c_freeze', 'c2e_cold[debuff]', 'c2e_freeze'): continue
        pos = f.target_of(pair[1]); fs = f.table_fields(pos); decoded = {}
        for i, (name, kind) in enumerate(FIELDS):
            p = fs[i] if i < len(fs) else None
            if p is None: value = False if kind == 'bool' else None if kind == 'str' else {} if kind == 'attributes' else 0
            elif kind == 'attributes': value = attrs(f, f.target_of(p))
            elif kind == 'str': value = f.read_string(f.target_of(p))
            elif kind == 'bool':
                if f.d[p] not in (0,1): raise ValueError('Invalid packed bool')
                value = f.d[p] == 1
            elif kind == 'byte': value = f.d[p]
            else: value = getattr(f, kind)(p)
            decoded[name] = {'field_index': i, 'offset': p, 'value': value}
        result[key] = {'entry_offset': entry, 'row_offset': pos, 'field_offsets': fs, 'decoded': decoded,
                       'unknown_extra_field_offsets': fs[len(FIELDS):]}
    if set(result) != {'e2c_cold', 'e2c_freeze', 'c2e_cold[debuff]', 'c2e_freeze'}: raise ValueError('Required source rows incomplete')
    cold = result['e2c_cold']['decoded']; frozen = result['e2c_freeze']['decoded']
    if cold['attributes']['value']['abnormalFlags'] != [23] or cold['attributes']['value']['attributeModifiers'][0]['value'] != -30:
        raise ValueError('Source COLD/ASPD evidence differs')
    if frozen['attributes']['value']['abnormalFlags'] != [16] or cold['durationKey']['value'] != 'freeze' or frozen['durationKey']['value'] != 'freeze':
        raise ValueError('Source frozen/duration key differs')
    bson = bson_source({'e2c_cold', 'empty', 'e2c_frozen_atkscale'})
    return {'schema': 'ark-sim/chapter06-cold-typed-source/v1', 'source': {'path': str(PATH), 'sha256': sha(PATH), 'bytes': PATH.stat().st_size},
        'reader': {'path': str(ROOT.parent/'ark_parser/enemy/extract_enemy_data.py'), 'sha256': sha(ROOT.parent/'ark_parser/enemy/extract_enemy_data.py')},
        'builder_sha256': sha(Path(__file__)), 'rows': result, 'bson': bson,
        'schema_policy': 'Old 34-field vtable layout independently anchored by exact keys/BSON/byte packing; lifeTime at27. Later dump remainingTimeKey is not assumed present',
        'field_calibration': {'e2c_cold': {'row': 19324, 'statusResistable': 1, 'lifeTimeType': 1, 'durationKey': 'freeze', 'ASPD_addition': -30},
                              'e2c_freeze': {'row': 19536, 'statusResistable': 2, 'lifeTimeType': 1, 'durationKey': 'freeze', 'FROZEN': 16}},
        'duration_policy': 'Incoming source BB freeze5(normal frstar2) or freeze10(skill/mage/slug) is passed explicitly; no hardcoded duration guessed from zero lifeTime',
        'runtime_authored': False, 'client_verified': False}


if __name__ == '__main__':
    data = build(); OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_bytes((json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode('utf8'))
    print(json.dumps({'sha256': sha(OUT), 'cold_row': 19324, 'frozen_row': 19536, 'duration_key': 'freeze'}))
