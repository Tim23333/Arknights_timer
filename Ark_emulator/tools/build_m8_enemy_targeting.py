"""Bind an explicit enemy-only taunt score profile to production enemy actors."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SCORE = 'rule/m8_enemy_taunt_score'
OUTPUTS = {
    'packages/campaign/squad.m8_roster.json': 'packages/campaign/squad.m8_targeting.json',
    'packages/campaign/mainline_models/level_main_00-10.m8_roster.json': 'packages/campaign/mainline_models/level_main_00-10.m8_targeting.json',
    'packages/campaign/mainline_models/level_main_00-11.m8_roster.json': 'packages/campaign/mainline_models/level_main_00-11.m8_targeting.json',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source):
    source = Path(source); data = json.loads(source.read_bytes())
    reference = ROOT/'packages/campaign/talents.support.json'
    original = json.loads(reference.read_bytes())
    rule = next(r for r in original['rules'] if r['id'] == 'rule/support_taunt_score')
    rule = deepcopy(rule); rule['id'] = SCORE
    if any(r['id'] == SCORE for r in data['rules']):
        raise ValueError('enemy targeting input already patched')
    data['rules'].append(rule)
    actors = []
    for entity in data['entities']:
        if 'enemy' not in entity.get('tags', []):
            continue
        if entity.get('rules', {}).get('targeting.score'):
            raise ValueError('existing enemy score requires an explicit merge decision')
        entity.setdefault('rules', {})['targeting.score'] = SCORE
        actors.append(entity['id'])
    data['manifest']['id'] += '/enemy_targeting1'
    data['manifest']['version'] += '.targeting1'
    data['manifest']['metadata']['m8_enemy_targeting'] = {'input': str(source.relative_to(ROOT)),
        'input_sha256': sha(source), 'builder_sha256': sha(Path(__file__)), 'score_source_sha256': sha(reference),
        'score_rule': SCORE, 'bound_enemy_definitions': actors,
        'priority_profile': 'blocked weight1e6, base taunt weight1e5, distance then stable actorID',
        'player_selector_bindings_preserved': True,
        'future_enemy_import_requires_same_profile_or_explicit_native_variant_score': True,
        'model_gaps': ['dynamic taunt modifiers/effective attribute score adapter', 'native complete hatred/source comparator'],
        'client_verified': False, 'formal_stage_approved': False}
    if 'scenarioDraft' in data:
        data['scenarioDraft']['id'] += '/enemy_targeting1'
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    from ark_sim import Compiler
    for source, output in OUTPUTS.items():
        data = build(ROOT/source)
        if 'scenarioDraft' in data:
            program = Compiler().compile(data)
            print(json.dumps({'output': output, 'definitions': len(program.definitions), 'fingerprint': program.fingerprint}))
        path = ROOT/output
        if args.check:
            if not path.exists() or json.loads(path.read_bytes()) != data:
                raise SystemExit('enemy targeting drift: '+output)
        else:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


if __name__ == '__main__':
    main()
