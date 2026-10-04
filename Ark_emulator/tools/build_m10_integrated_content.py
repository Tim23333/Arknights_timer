"""Compose current enemy targeting with exact selected resource policies."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = {
    'packages/campaign/squad.m8_targeting_v2.json': 'packages/campaign/squad.m10.json',
    'packages/campaign/mainline_models/level_main_00-10.m8_targeting_v2.json': 'packages/campaign/mainline_models/level_main_00-10.m10.json',
    'packages/campaign/mainline_models/level_main_00-11.m8_targeting_v2.json': 'packages/campaign/mainline_models/level_main_00-11.m10.json',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source):
    source = Path(source); original = json.loads(source.read_bytes()); data = deepcopy(original)
    units = {e['id']: e for e in data['entities']}
    chen = units['unit/char_010_chen']['components']['resources']['sp']
    kalts = units['unit/char_003_kalts']['components']['resources']['sp']['recovery']
    if 'recovery_freeze_abilities' in chen or 'interrupt_abilities' in kalts:
        raise ValueError('resource policy input already configured; explicit merge required')
    chen['recovery_freeze_abilities'] = ['ability/campaign_chen_s1']
    kalts['interrupt_abilities'] = ['ability/kalts_host_s3']
    restored = deepcopy(data)
    restored_units = {e['id']: e for e in restored['entities']}
    restored_units['unit/char_010_chen']['components']['resources']['sp'].pop('recovery_freeze_abilities')
    restored_units['unit/char_003_kalts']['components']['resources']['sp']['recovery'].pop('interrupt_abilities')
    if restored != original:
        raise ValueError('composition changed unrelated actor definitions')
    scene = data.get('scenarioDraft', {})
    spawns = list(scene.get('waves', []))
    for wave in scene.get('timeline', {}).get('waves', []):
        for fragment in wave['fragments']:
            spawns.extend(action['spawn'] for action in fragment['actions'] if action['kind'] == 'spawn')
    offset_routes = 0
    for spawn in spawns:
        route = spawn.get('route', {})
        if any(any((cp.get('reachOffset') or {}).values()) for cp in route.get('checkpoints') or []):
            if 'reach_offset_policy' in route:
                raise ValueError('route offset policy already configured; explicit merge required')
            route['reach_offset_policy'] = {'rule': 'rule/m9_checkpoint_cartesian',
                'parameters': {'axis_signs': {'row': -1, 'col': 1}}}
            offset_routes += 1
    data['manifest']['id'] += '/m10_resources1'
    data['manifest']['version'] += '.resources1'
    data['manifest']['metadata']['m10_resources'] = {'input': str(source.relative_to(ROOT)), 'input_sha256': sha(source),
        'builder_sha256': sha(Path(__file__)), 'candidate_requires': ['resource recovery_freeze_abilities', 'recovery interrupt_abilities'],
        'changed_policies': {'Chen': 'only selected S1 active blocks SP recovery', 'Kalts': 'empty owned-token gate interrupts only S3'},
        'all_other_definitions_equal_before_identity_metadata': True,
        'nonzero_offset_spawn_routes_configured': offset_routes,
        'checkpoint_offset_profile': 'native Cartesian x/y => V2 row-y,col+x; explicit pure rule; source offset preserved',
        'client_pending': ['native AttackAbility SP recovery flag method body', 'native resource-gate interruption event order',
            'native offset steering/arrival algorithm'],
        'formal_stage_approved': False}
    if 'scenarioDraft' in data:
        data['scenarioDraft']['id'] += '/m10_resources1'
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for source, output in OUTPUTS.items():
        data = build(ROOT/source); path = ROOT/output
        if args.check:
            if not path.exists() or json.loads(path.read_bytes()) != data:
                raise SystemExit('M10 integrated content drift: '+output)
        else:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
        print(json.dumps({'output': output, 'input_sha256': sha(ROOT/source), 'formal_stage_approved': False}))


if __name__ == '__main__':
    main()
