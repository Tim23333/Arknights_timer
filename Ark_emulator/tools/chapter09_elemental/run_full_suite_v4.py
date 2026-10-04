"""Run all original checks with the exact new catalog schema expectation."""
import argparse
import ast
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD_CASE = 'tests_v2/test_rules.py::test_catalog_has_98_contracts_and_is_immutable'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
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
                modules = [entry.name for entry in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
                if node.module == 'tools':
                    modules += ['tools.' + entry.name for entry in node.names]
            for module in modules:
                if module.startswith('tools.'):
                    child = (ROOT / Path(*module.split('.'))).with_suffix('.py')
                    if child.is_file():
                        pending.append(child)
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--expected-core', required=True)
    parser.add_argument('--output', type=Path, required=True)
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
    from tools.chapter09_elemental.catalog_v1 import (
        test_catalog_is_exact_previous99_plus_elemental6_and_readonly as replacement)
    assert Path(ark_sim.__file__).resolve().parent == runtime / 'ark_sim'
    assert implementation_digest() == args.expected_core
    files = sources() | {Path(__file__), ROOT / 'tools/chapter09_elemental/catalog_v1.py',
                        ROOT / 'tools/chapter09_elemental/catalog.locks.json',
                        ROOT / 'tools/chapter09_elemental/contracts.parent99.json', ROOT / 'tools/chapter09_elemental/contracts.elemental6.json',
                        Path(os.environ['CAMPAIGN_SUMMON_PACKAGE']),
                        runtime / 'ark_emulator/levels/packs/level_main_00-01.json'}
    files.update(path for path in (runtime / 'ark_sim').rglob('*')
                 if path.is_file() and path.suffix in ('.py', '.json'))
    guard = lambda: {str(path): sha(path) for path in sorted(files)}
    before = guard()
    cases, skipped, replacements = [], [], []

    class Capture:
        def pytest_collection_modifyitems(self, session, config, items):
            for item in items:
                if item.nodeid == OLD_CASE:
                    item.obj = replacement
                    replacements.append({'original_nodeid': item.nodeid,
                                         'actual_function': replacement.__module__ + '.' + replacement.__name__})
            assert len(replacements) == 1, 'Expected one exact catalog expectation update'

        def pytest_collectreport(self, report):
            if report.skipped:
                skipped.append({'nodeid': report.nodeid, 'reason': str(report.longrepr)})

        def pytest_runtest_logreport(self, report):
            if report.when == 'call':
                cases.append({'case': report.nodeid, 'outcome': report.outcome,
                              'seconds': report.duration,
                              'failure': str(report.longrepr) if report.failed else None})
                if report.failed:
                    print('\nFailure observed: ' + report.nodeid, flush=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    startfile = output.with_suffix('.start.json')
    assert not startfile.exists()
    startfile.write_text(json.dumps({'core': args.expected_core, 'guards': before,
                                    'catalog_expectation_replacement': OLD_CASE}, indent=2) + '\n', encoding='utf8')
    started = time.monotonic()
    code = int(pytest.main(['tests_v2', '-q', '--tb=short', '--basetemp', str(Path('E:/ArkSimLogs/runs/chapter09_elemental_full_v3/temp')), '-o', 'cache_dir=E:/ArkSimLogs/runs/chapter09_elemental_full_v3/cache'], plugins=[Capture()]))
    after = guard()
    actual = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
              if name.startswith('ark_sim') and getattr(module, '__file__', None)}
    stable = before == after and implementation_digest() == args.expected_core and all(
        Path(path).is_relative_to(runtime / 'ark_sim') for path in actual.values())
    passed = code == 0 and stable and len(cases) == 1219 and not skipped and all(
        case['outcome'] == 'passed' for case in cases)
    report = {'passed': passed, 'core': args.expected_core, 'exitcode': code,
              'elapsed_seconds': time.monotonic() - started, 'cases': cases,
              'guards_start': before, 'guards_end': after, 'identity_stable': stable,
              'actual_modules': actual, 'collection_skips': skipped,
              'original_expectations_changed': True, 'expectation_replacements': replacements,
              'change_reason': 'Six elemental contracts extend exact prior99 catalog; no original definition changed',
              'all_other_1218_expectations_unchanged': True,
              'full_stage_executed': False, 'client_verified': False}
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': passed, 'exit': code, 'cases': len(cases),
                      'stable': stable, 'sha': sha(output)}), flush=True)
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
