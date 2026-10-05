"""Unchanged isolated-context suite and absent-feature authority checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--runtime-root', type=Path, required=True)
parser.add_argument('--core', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
runtime = args.runtime_root.resolve(); sys.path.insert(0, str(runtime)); sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
import pytest
assert implementation_digest() == args.core
files = [Path(__file__), ROOT / 'tests_v2/test_domain_rules.py']
files += [p for p in (runtime / 'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py', '.json')]
guard = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
before = guard(); cases = []


class Capture:
    def pytest_runtest_logreport(self, report):
        if report.when == 'call' or report.failed:
            cases.append({'case': report.nodeid, 'outcome': report.outcome,
                          'failure': str(report.longrepr) if report.failed else None})


run = Path(os.environ['ARKSIM_RUN_DIR'])
code = int(pytest.main(['tests_v2/test_domain_rules.py', '-q', '--tb=short', '--basetemp', str(run / 'temp')], plugins=[Capture()]))
data = {'schemaVersion': 2, 'entities': [{'id': 'unit/optional/plain', 'kind': 'entity', 'components': {
    'attributes': {'base': {'max_hp': 171}}, 'resources': {'hp': {'role': 'health', 'initial': 171, 'capacity': 171}}, 'spatial': {}}}],
    'scenarioDraft': {'id': 'scene/optional/plain', 'ruleset': 'ruleset/ark_standard', 'map': {'rows': 1, 'cols': 2},
        'initialEntities': [{'definition': 'unit/optional/plain', 'instanceAlias': 'plain', 'position': {'row': 0, 'col': 0}}]}}
sim = Engine.create(Compiler().compile(data)); assert sim.ctx.depletion is None
checks = []
for tag in ('depletion_action', 'depletion_owned'):
    checkpoint = sim.checkpoint()
    try: sim.ctx.effects.execute('plain', ['plain'], {'op': 'emit', 'event': 'optional.forged'}, cast={tag: {'owner': 2}})
    except ValueError: pass
    else: raise AssertionError('Fake callback tag accepted without subsystem')
    assert sim.checkpoint() == checkpoint
    checks.append({'case': tag + '_absent_feature_no_authority', 'passed': True})
after = guard(); result = {'core': args.core, 'actual_exit': code,
    'passed': code == 0 and len(cases) == 46 and all(x['outcome'] == 'passed' for x in cases) and before == after,
    'cases': cases, 'authority_checks': checks, 'source_start': before, 'source_end': after,
    'source_guard_equal': before == after, 'all_comparison_fields_preserved': True}
args.output.parent.mkdir(parents=True, exist_ok=True); assert not args.output.exists()
args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
raise SystemExit(0 if result['passed'] else 1)
