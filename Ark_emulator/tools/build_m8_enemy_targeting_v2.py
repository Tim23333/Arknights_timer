"""Correct enemy-source blocker identity in the frozen taunt profile."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORE = 'rule/m8_enemy_taunt_score'
OUTPUTS = {
    'packages/campaign/squad.m8_targeting.json': 'packages/campaign/squad.m8_targeting_v2.json',
    'packages/campaign/mainline_models/level_main_00-10.m8_targeting.json': 'packages/campaign/mainline_models/level_main_00-10.m8_targeting_v2.json',
    'packages/campaign/mainline_models/level_main_00-11.m8_targeting.json': 'packages/campaign/mainline_models/level_main_00-11.m8_targeting_v2.json',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source):
    source = Path(source); data = json.loads(source.read_bytes())
    rule = next(r for r in data['rules'] if r['id'] == SCORE)
    expression = rule['implementation']['expression']
    old = 'inputs.candidate.components.runtime.blocked_by == inputs.source.id'
    if old not in expression:
        raise ValueError('frozen enemy score expression differs')
    rule['implementation']['expression'] = expression.replace(old, 'inputs.source.components.runtime.blocked_by == inputs.candidate.id')
    data['manifest']['id'] += '/blocker_direction2'
    data['manifest']['version'] += '.blocker2'
    data['manifest']['metadata']['m8_enemy_targeting_v2'] = {'input': str(source.relative_to(ROOT)),
        'input_sha256': sha(source), 'builder_sha256': sha(Path(__file__)),
        'enemy_blocker_relation': 'source.runtime.blocked_by == candidate.id',
        'correction': 'enemy source is blocked by player candidate; previous player-side inverse was ineffective',
        'formal_stage_approved': False, 'client_verified': False}
    if 'scenarioDraft' in data:
        data['scenarioDraft']['id'] += '/blocker_direction2'
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for source, output in OUTPUTS.items():
        data = build(ROOT/source); path = ROOT/output
        if args.check:
            if not path.exists() or json.loads(path.read_bytes()) != data:
                raise SystemExit('targeting v2 drift: '+output)
        else:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
        print(output)


if __name__ == '__main__':
    main()
