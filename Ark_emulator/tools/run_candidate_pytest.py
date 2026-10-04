"""Run an explicit test selection with a verified isolated V2 implementation."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('selection', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    selection = args.selection[1:] if args.selection[:1] == ['--'] else args.selection
    if not selection:
        raise ValueError('explicit pytest selection required')
    candidate = args.runtime_root.resolve()
    sys.path.insert(0, str(candidate)); sys.path.insert(1, str(ROOT)); sys.path.insert(2, str(ROOT/'tests_v2'))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    if not Path(ark_sim.__file__).resolve().is_relative_to(candidate):
        raise ValueError('selected candidate was not actually imported')
    before = implementation_digest()
    print(json.dumps({'runtime_module': ark_sim.__file__, 'implementation_before': before, 'selection': selection}), flush=True)
    import pytest
    code = int(pytest.main(selection))
    after = implementation_digest()
    result = {'schema': 'ark-sim/isolated-test-run/v1', 'passed': code == 0 and before == after,
        'exit_code': code, 'implementation_before': before, 'implementation_after': after,
        'runtime_module': ark_sim.__file__, 'selection': selection, 'candidate_only': True,
        'source_runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'formal_stage_approved': False}
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    if before != after:
        raise RuntimeError('candidate implementation changed during tests')
    raise SystemExit(code)


if __name__ == '__main__':
    main()
