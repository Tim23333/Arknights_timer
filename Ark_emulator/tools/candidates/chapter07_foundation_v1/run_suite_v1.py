"""Run unchanged V2 suite against a pinned isolated foundation runtime."""
import argparse
import ast
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_sources():
    pending = list((ROOT / 'tests_v2').glob('*.py'))
    found = set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_bytes())):
            modules = []
            if isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
                if node.module == 'tools':
                    modules += ['tools.' + a.name for a in node.names]
            for module in modules:
                if module.startswith('tools.'):
                    child = (ROOT / Path(*module.split('.'))).with_suffix('.py')
                    if child.is_file():
                        pending.append(child)
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-root', required=True, type=Path)
    parser.add_argument('--expected-core', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    runtime = args.runtime_root.resolve()
    output = args.output.resolve()
    assert not output.exists()
    sys.path.insert(0, str(runtime))
    sys.path.insert(1, str(ROOT))
    sys.path.insert(2, str(ROOT / 'tests_v2'))
    os.environ['ARKSIM_M10_REVIEW_ROOT'] = str(runtime)
    os.environ['CAMPAIGN_SUMMON_PACKAGE'] = str(
        ROOT / 'packages/campaign/mainline_models/level_main_00-10.m12_projection.json')
    import ark_sim
    import pytest
    from ark_sim.adapters.api import implementation_digest
    assert implementation_digest() == args.expected_core
    assert Path(ark_sim.__file__).resolve().parent == runtime / 'ark_sim'
    paths = [p for p in (runtime / 'ark_sim').rglob('*')
             if p.suffix in ('.py', '.json') and '__pycache__' not in p.parts]
    paths += list(test_sources()) + [Path(__file__),
        Path(os.environ['CAMPAIGN_SUMMON_PACKAGE']),
        runtime / 'ark_emulator/levels/packs/level_main_00-01.json']
    paths = sorted(set(paths))
    before = {str(p): sha(p) for p in paths}
    cases, skipped = [], []

    class Capture:
        def pytest_collectreport(self, report):
            if report.skipped:
                skipped.append({'nodeid': report.nodeid, 'reason': str(report.longrepr)})

        def pytest_runtest_logreport(self, report):
            if report.when == 'call':
                cases.append({'case': report.nodeid, 'outcome': report.outcome,
                              'seconds': report.duration,
                              'failure': str(report.longrepr) if report.failed else None})

    output.parent.mkdir(parents=True, exist_ok=True)
    startfile = output.with_suffix('.start.json')
    assert not startfile.exists()
    startfile.write_text(json.dumps({'core': args.expected_core, 'guards': before},
                                   indent=2) + '\n', encoding='utf8')
    start = time.monotonic()
    code = int(pytest.main(['tests_v2', '-q', '--tb=short'], plugins=[Capture()]))
    after = {str(p): sha(p) for p in paths}
    actual = {name: str(Path(module.__file__).resolve())
              for name, module in sys.modules.items()
              if name.startswith('ark_sim') and getattr(module, '__file__', None)}
    stable = (before == after and implementation_digest() == args.expected_core
              and all(Path(p).is_relative_to(runtime / 'ark_sim') for p in actual.values()))
    passed = (code == 0 and stable and len(cases) == 1219 and not skipped
              and all(c['outcome'] == 'passed' for c in cases))
    output.write_text(json.dumps({
        'passed': passed, 'core': args.expected_core, 'exitcode': code,
        'elapsed_seconds': time.monotonic() - start,
        'cases': cases, 'guards_start': before, 'guards_end': after,
        'actual_modules': actual, 'identity_stable': stable,
        'collection_skips': skipped, 'original_expectations_changed': False,
        'full_stage_executed': False, 'client_verified': False,
    }, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': passed, 'exit': code, 'cases': len(cases),
                      'stable': stable, 'sha': sha(output)}), flush=True)
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
