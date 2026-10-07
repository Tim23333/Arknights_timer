"""Add fixed-roster EP receivers to unchanged chapter9 source assemblies."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CORE = '94d2f5cfcc42f8845c6cb23643f1910aa94a78115a60d83813d0738df6db8c63'
PARENTS = {
    '09-16': ('v6', 'fca4ad8073d06326d7e33691a724a4818c9a8f052ae9ab95000c4d0fbcc66030'),
    '09-17': ('v4', 'd67ffa32e81b85cd0d65ea2eec685ceb14609e7fd8dcfb0a6e5d43993d6ba97c'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def exact(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)


def build(stage):
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.campaign_elemental_receivers_v1.build import mount
    from tools.chapter09_elemental_successor_v1.providers import providers
    if implementation_digest() != CORE:
        raise ValueError('Explicit frozen successor core required')
    version, expected = PARENTS[stage]
    parent = ROOT / f'packages/campaign/chapter09_stage_models/level_main_{stage}.native_draft.{version}.life99999.finite_run_v1.json'
    if sha(parent) != expected:
        raise ValueError('Preserve frozen chapter9 input identity')
    original = json.loads(parent.read_bytes())
    for path, value in original['manifest']['metadata']['source_locks'].items():
        if sha(path) != value:
            raise ValueError('Original source changed: ' + path)
    package = deepcopy(original)
    roster_path = ROOT / 'packages/campaign/roster/fixed12.m26.reference_module.json'
    roster = json.loads(roster_path.read_bytes())
    roster_actors = {d['id'] for d in roster['definitions'] if d['kind'] == 'entity'}
    actors = [d for d in package['definitions'] if d['kind'] == 'entity' and d['id'] in roster_actors]
    selected = {d['id'] for d in actors}
    if len(selected) != 15 or selected != roster_actors:
        raise ValueError('Exact fixed12 plus three declared summons required')
    if not exact(package['scenarioDraft']['roster'], roster['manifest']['metadata']['roster']):
        raise ValueError('Original fixed12 roster differs')
    owned = {a for d in actors for a in d['components'].get('abilities', [])}
    # mount's skill gate applies only to selected owners. Keep every other
    # actor's skill, including manual boss attacks and devices, unchanged.
    visible = [d for d in package['definitions'] if d['kind'] != 'ability' or d['id'] in owned]
    mounting = {'definitions': visible}
    mount(mounting, entities=selected)
    old_ids = {d['id'] for d in original['definitions']}
    package['definitions'].extend(d for d in mounting['definitions'] if d['id'] not in old_ids)
    current = {d['id']: d for d in package['definitions']}
    changes = {d['id']: {'before': d, 'after': current[d['id']]}
               for d in original['definitions'] if not exact(d, current[d['id']])}
    if any(identifier not in selected | owned for identifier in changes):
        raise ValueError('Elemental mounting modified an unrelated declaration')
    if not exact(package['scenarioDraft'], original['scenarioDraft']):
        raise ValueError('No battle scenario changes are allowed')
    source_paths = [parent, roster_path, Path(__file__), ROOT / 'tools/chapter09_elemental_successor_v1/providers.py',
                    ROOT / 'tools/campaign_elemental_receivers_v1/build.py',
                    ROOT / 'packages/campaign/common_elemental_receivers/source.bson.v2.json']
    metadata = package['manifest']['metadata']
    metadata['required_runtime'] = CORE
    metadata['elemental_successor_binding'] = {
        'parent': str(parent), 'parent_sha256': expected,
        'parent_runtime': original['manifest']['metadata']['required_runtime'],
        'selected_receivers': sorted(selected), 'owned_abilities': sorted(owned),
        'explicit_original_changes': changes,
        'added_definitions': sorted(set(current) - old_ids),
        'source_locks': {str(p): sha(p) for p in source_paths},
        'scenario_type_exact_unchanged': True, 'unrelated_definitions_unchanged': True,
        'only_receiver_profile_SP_freeze_and_owned_skill_gate_added': True,
        'whole_stage_executed': False, 'model_approved': False, 'client_verified': False,
    }
    restored = deepcopy(package)
    restored['definitions'] = [changes[d['id']]['before'] if d['id'] in changes else d
                               for d in restored['definitions'] if d['id'] in old_ids]
    restored['manifest']['metadata']['required_runtime'] = original['manifest']['metadata']['required_runtime']
    del restored['manifest']['metadata']['elemental_successor_binding']
    if not exact(restored, original):
        raise ValueError('Explicit receiver changes cannot reproduce exact original package')
    program = Compiler(providers=providers(stage)).compile(package)
    return package, program.fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--stage', choices=tuple(PARENTS), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.receipt.exists():
        raise FileExistsError('Keep previous stage versions')
    runtime = args.runtime_root.resolve();sys.path.insert(0, str(runtime));sys.path.insert(1, str(ROOT))
    import ark_sim
    if Path(ark_sim.__file__).resolve().parent != runtime / 'ark_sim':
        raise ValueError('Actual imported runtime differs')
    package, program = build(args.stage)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(package, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')
    binding = package['manifest']['metadata']['elemental_successor_binding']
    receipt = {'schema': 'ark-sim/chapter9-elemental-successor-input/v1', 'stage': args.stage, 'core': CORE,
               'output': str(args.output.resolve()), 'output_sha256': sha(args.output), 'program': program,
               'receivers': len(binding['selected_receivers']), 'changed_original_definitions': len(binding['explicit_original_changes']),
               'added_definitions': len(binding['added_definitions']), 'scenario_type_exact_unchanged': True,
               'compiled': True, 'model_approved': False, 'whole_stage_executed': False, 'client_verified': False}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
