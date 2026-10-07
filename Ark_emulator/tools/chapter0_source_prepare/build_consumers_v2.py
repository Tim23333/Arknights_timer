"""Source time-mode/max-scale clock rules over unchanged V1 enemy bodies."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2];sys.path.insert(0, str(ROOT))
PARENT = ROOT / 'packages/campaign/chapter0_consumers/enemies.module.v1.json'
SOURCE = ROOT / 'packages/campaign/chapter0_source_prepare/enemies.native.v1.json'
PARENT_SHA = '233febf961d1194e190776dde854cc1af9c77787b7a7a55bb1cca460f10eed45'
SOURCE_SHA = 'ad8a610ad5b3fbebe16a000f5098084accab4a346492dd686e937f22925fe360'


def build():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(PARENT) == PARENT_SHA and sha(SOURCE) == SOURCE_SHA
    original = json.loads(PARENT.read_bytes());source = json.loads(SOURCE.read_bytes())
    package = deepcopy(original);package['rules'] = []
    changes = {}
    for ability in package['abilities']:
        raw = ability['metadata']['native_owned_node']['raw']
        assert raw['_timeMode'] == 0 and raw['_affectedBySlowDown'] == 1
        cap = raw['_maxAnimScale'];assert type(cap) in (int, float)
        clock = 'rule/ch0/native_clock/' + ability['id'].replace('/', '_')
        old = deepcopy(ability)
        for contract, input_name, suffix in [('ability.windup', 'timing_parameters', 'hit'),
                                              ('ability.duration', 'duration_parameters', 'full')]:
            rid = clock + '/' + suffix
            package['rules'].append({'id': rid, 'kind': 'rule', 'contract': contract,
                                     'parameters': {'minimum': .1, 'maximum': cap},
                                     'implementation': {'type': 'expression', 'expression':
                                         f'inputs.{input_name}.seconds / max(params.minimum, min(inputs.attributes.attack_speed_ratio, params.maximum) if params.maximum > 0 else inputs.attributes.attack_speed_ratio)'},
                                     'metadata': {'native_time_mode': 0, 'native_maxAnimScale': cap,
                                                  'native_affectedBySlowDown': 1,
                                                  'reference_policy': 'Replaceable FROM_ATTACK_SPEED divisor model following source MIN_ANIM_SCALE and serialized cap; native GetTimeScale method body not recovered',
                                                  'client_formula_verified': False}})
            ability.setdefault('rules', {})[contract] = rid
        changes[ability['id']] = {'before': old, 'after': deepcopy(ability)}
    assert package['entities'] == original['entities'] and package['selectors'] == original['selectors']
    restored = deepcopy(package);restored.pop('rules')
    restored['abilities'] = [changes[a['id']]['before'] for a in restored['abilities']]
    assert restored == original
    package['manifest']['metadata']['clock_binding_v2'] = {
        'parent_sha256': PARENT_SHA, 'source_sha256': SOURCE_SHA,
        'explicit_ability_changes': changes, 'original_HP_stats_intervals_hit_offsets_preserved': True,
        'calculation_methods_customizable': ['ability.windup', 'ability.duration'],
        'raw_float32_cap_preserved': True, 'model_approved': False, 'client_verified': False}
    return package


if __name__ == '__main__':
    p = build();out = ROOT / 'packages/campaign/chapter0_consumers/enemies.module.v2.json'
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'sha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'entities': len(p['entities']),
                      'timing_rules': len(p['rules']), 'parent_HP_stats_preserved': True, 'model_approved': False}))
