"""Only an explicit runthrough profile over the exact source-stage package."""
import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--commands', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.receipt.exists():
        raise FileExistsError('Preserve previous overlays')
    original = json.loads(args.package.read_bytes())
    package = deepcopy(original)
    scene = package['scenarioDraft']
    assert scene['resources']['life'] == {'initial': 99999, 'capacity': 99999}
    assert scene['resources']['dp']['initial'] == 10 and scene['parameters']['deploy_capacity'] == 8
    assert len(scene['roster']) == 12 and package['manifest']['metadata']['source_births'] == 32
    scene['metadata']['runthrough_profile'] = {
        'base_life_resource': 'life', 'base_life': 99999, 'fixed12': deepcopy(scene['roster']),
        'source_births': 32, 'deploy_capacity': 8, 'public_commands_sha256': sha(args.commands),
        'operator_enemy_HP': 'Original source-derived configuration, no HP override',
        'training_deployment_exception': False, 'client_verified': False,
        'accuracy': 'Source-reference model; complete mechanism and whole-run gates still required',
        'dynamic_birth_accounting': 'Every actual enemy counted; only finite source-authenticated descendants augment native32'}
    restored = deepcopy(package)
    del restored['scenarioDraft']['metadata']['runthrough_profile']
    assert restored == original
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    record = {'schema': 'ark-sim/chapter10-runthrough-overlay/v1',
        'parent': str(args.package.resolve()), 'parent_sha256': sha(args.package),
        'commands': str(args.commands.resolve()), 'commands_sha256': sha(args.commands),
        'output': str(args.output.resolve()), 'output_sha256': sha(args.output),
        'only_metadata_changed': True, 'all_original_battle_inputs_preserved': True,
        'native_births': 32, 'native_DP': 10, 'native_slots': 8, 'base_life': 99999,
        'whole_run_started': False, 'model_approved': False, 'client_verified': False,
        'pending': original['manifest']['metadata'].get('pending_model_gaps', [])}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'only_metadata_changed': True, 'overlay_sha256': record['output_sha256'], 'whole_run_started': False}))


if __name__ == '__main__':
    main()
