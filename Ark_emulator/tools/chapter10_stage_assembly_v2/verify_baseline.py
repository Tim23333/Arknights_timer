"""Fresh baseline proof under an explicitly selected candidate runtime."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--expected-core', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    runtime = args.runtime_root.resolve()
    sys.path.insert(0, str(runtime))
    sys.path.insert(1, str(ROOT))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    from tools import verify_v2_baseline as baseline
    if Path(ark_sim.__file__).resolve().parent != runtime / 'ark_sim' or implementation_digest() != args.expected_core:
        raise ValueError('Baseline must use the actual declared candidate')
    run = Path(os.environ['ARKSIM_RUN_DIR']).resolve()
    if not run.is_relative_to(Path('E:/ArkSimLogs/runs').resolve()):
        raise ValueError('Baseline raw output requires the fixed cleanup directory')
    guards = [Path(__file__), Path(baseline.__file__),
              ROOT / 'packages/custom/custom_guard.json',
              ROOT / 'packages/ark_content/level_main_00_01.json',
              ROOT / 'scenarios/level_main_00_01/commands.json']
    guards += [p for p in (runtime / 'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py', '.json')]
    before = {str(p): sha(p) for p in guards}
    proof = {'schema': 'ark-sim/candidate-baseline/v1', 'core': args.expected_core,
             'runtime_module': ark_sim.__file__, 'passed': False,
             'scope': 'Fresh 0-1 process, continuation, replay and custom rulesets',
             'whole_target_stage': False, 'client_verified': False,
             'source_before': before}
    try:
        baseline.check_custom(proof)
        baseline.check_level(proof, run / 'baseline.json', 4500, 300)
        proof['passed'] = True
    except Exception:
        proof['error'] = traceback.format_exc()
    proof['source_after'] = {str(p): sha(p) for p in guards}
    proof['actual_modules'] = {name: str(Path(module.__file__).resolve())
                              for name, module in sys.modules.items()
                              if name.startswith('ark_sim') and getattr(module, '__file__', None)}
    proof['core_at_completion'] = implementation_digest()
    proof['identity_stable'] = (proof['source_after'] == before
                                and proof['core_at_completion'] == args.expected_core
                                and all(Path(p).is_relative_to(runtime / 'ark_sim')
                                        for p in proof['actual_modules'].values()))
    proof['passed'] &= proof['identity_stable']
    proof['actual_exit'] = 0 if proof['passed'] else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proof, indent=2, allow_nan=False) + '\n', encoding='utf8')
    print(json.dumps({'passed': proof['passed'], 'actual_exit': proof['actual_exit'], 'error': proof.get('error')}))
    return proof['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
