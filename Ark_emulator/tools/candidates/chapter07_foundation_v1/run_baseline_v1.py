"""Execute original 0-1/custom baseline after loading an exact candidate."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--expected-core', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runtime, out = args.runtime_root.resolve(), args.output.resolve()
    assert not out.exists() and not out.with_suffix('.identity.json').exists()
    sys.path.insert(0, str(runtime))
    sys.path.insert(1, str(ROOT))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent == runtime / 'ark_sim'
    assert implementation_digest() == args.expected_core
    from tools import verify_v2_baseline as baseline
    paths = [p for p in (runtime / 'ark_sim').rglob('*')
             if p.suffix in ('.py', '.json') and '__pycache__' not in p.parts]
    paths += [Path(__file__), Path(baseline.__file__),
              ROOT / 'packages/ark_content/level_main_00_01.json',
              ROOT / 'scenarios/level_main_00_01/commands.json',
              ROOT / 'packages/custom/custom_guard.json']
    before = {str(p): sha(p) for p in paths}
    original_argv = sys.argv
    code = 0
    try:
        sys.argv = [str(baseline.__file__), '--output', str(out)]
        baseline.main()
    except Exception:
        code = 1
        raise
    finally:
        sys.argv = original_argv
        after = {str(p): sha(p) for p in paths}
        actual = {name: str(Path(module.__file__).resolve())
                  for name, module in sys.modules.items()
                  if name.startswith('ark_sim') and getattr(module, '__file__', None)}
        stable = (before == after and implementation_digest() == args.expected_core
                  and all(Path(p).is_relative_to(runtime / 'ark_sim') for p in actual.values()))
        data = json.loads(out.read_bytes()) if out.exists() else {}
        out.parent.mkdir(parents=True, exist_ok=True)
        guard = out.with_suffix('.identity.json')
        guard.write_text(json.dumps({'passed': code == 0 and data.get('passed') is True and stable,
            'exit_code': code, 'implementation_sha256': args.expected_core,
            'source_at_start': before, 'source_at_completion': after,
            'actual_modules': actual, 'identity_stable': stable,
            'baseline_sha256': sha(out) if out.exists() else None}, indent=2) + '\n', encoding='utf8')
        print(json.dumps({'guard_sha': sha(guard), 'stable': stable, 'exit': code}), flush=True)
    assert stable and data.get('passed') is True


if __name__ == '__main__':
    main()
