"""Rebind an unchanged source stage to an explicitly frozen successor core.

This prepares input only. Mechanism, full-suite, baseline and whole-stage
acceptance remain separate proofs with their original runtime identities.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PARENT_CORE = '9a7d4a01b7fe0a8d77a39e4b280b330e65670349b6fb2716c1319dabcc491ed9'
PARENT_SHA = '7afc5aa0b3ef49d1333b788aa78e464460e68072ff57e0086607eae8949cccee'
REVIEW_SHA = 'ee5509ec8b05ee0aae018109ce89bf8c913daa87d8789fd1fffe2e095a092982'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def prepare(runtime, core, parent, review):
    import ark_sim
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter10_stage_assembly_v1.providers import providers
    runtime = runtime.resolve()
    if Path(ark_sim.__file__).resolve().parent != runtime / 'ark_sim' or implementation_digest() != core:
        raise ValueError('Actual imported runtime differs from the frozen successor')
    if core == PARENT_CORE:
        raise ValueError('Successor must have its own implementation identity')
    if sha(parent) != PARENT_SHA or sha(review) != REVIEW_SHA:
        raise ValueError('Source draft or independent typed review changed')
    audited = load(review)
    if not (audited['actual_exit'] == 0 and audited['source_only_approved']
            and audited['source_equal'] and audited['required_runtime'] == PARENT_CORE
            and len(audited['results']) == 5 and all(r['passed'] for r in audited['results'])):
        raise ValueError('Original source review is incomplete')
    for path, expected in audited['source_before'].items():
        if sha(path) != expected:
            raise ValueError('Original reviewed source drifted: ' + path)
    original = load(parent)
    for path, expected in original['manifest']['metadata']['source_locks'].items():
        if sha(path) != expected:
            raise ValueError('Consumed source changed: ' + path)
    package = deepcopy(original)
    metadata = package['manifest']['metadata']
    if metadata['required_runtime'] != PARENT_CORE:
        raise ValueError('Parent runtime declaration differs')
    metadata['required_runtime'] = core
    metadata['successor_source_binding'] = {
        'parent': str(parent.resolve()), 'parent_sha256': PARENT_SHA,
        'parent_runtime': PARENT_CORE, 'successor_runtime': core,
        'source_review': str(review.resolve()), 'source_review_sha256': REVIEW_SHA,
        'source_review_scope': 'Original unchanged battle inputs only',
        'battle_inputs_changed': False, 'runtime_validation_pending': True,
        'whole_stage_executed': False, 'client_verified': False,
    }
    restored = deepcopy(package)
    restored['manifest']['metadata']['required_runtime'] = PARENT_CORE
    del restored['manifest']['metadata']['successor_source_binding']
    if restored != original:
        raise ValueError('Successor changed battle content')
    program = Compiler(providers=providers()).compile(package)
    if implementation_digest() != core:
        raise ValueError('Runtime identity changed during compile')
    return package, program.fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--expected-core', required=True)
    parser.add_argument('--parent', type=Path, default=ROOT / 'packages/campaign/chapter10_stage_models/level_main_10-14.source_draft.v2.life99999.json')
    parser.add_argument('--review', type=Path, default=ROOT / 'validation/campaign/chapter10_stage_source_peer_v1/source.review.v3.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.receipt.exists():
        raise FileExistsError('Preserve previous source and proof identities')
    sys.path.insert(0, str(args.runtime_root.resolve()))
    sys.path.insert(1, str(ROOT))
    package, fingerprint = prepare(args.runtime_root, args.expected_core, args.parent, args.review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(package, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')
    receipt = {'schema': 'ark-sim/source-stage-successor-input/v1',
               'runtime': args.expected_core, 'program': fingerprint,
               'parent_sha256': sha(args.parent), 'source_review_sha256': sha(args.review),
               'output': str(args.output.resolve()), 'output_sha256': sha(args.output),
               'unchanged_battle_inputs': True, 'compiled': True,
               'model_approved': False, 'whole_run_started': False, 'client_verified': False}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
