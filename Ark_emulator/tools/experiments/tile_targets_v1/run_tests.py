import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT.parent / 'unpack_work/campaign_tile_targets_v10_candidate'
sys.path.insert(0, str(RUNTIME)); sys.path.insert(1, str(ROOT))
import pytest
from ark_sim.adapters.api import implementation_digest
PIN = '2eeca1dc0a9a02f2ba42aed2285d0ea89062029de8e2c58506c30e41472462cb'
assert implementation_digest() == PIN
cases = []
class Reports:
    def pytest_runtest_logreport(self, report):
        if report.when == 'call':
            cases.append({'case': report.nodeid, 'outcome': report.outcome,
                'failure': str(report.longrepr) if report.failed else None})
code = int(pytest.main([str(Path(__file__).with_name('test_tile_targets.py')), '-q', '--tb=short'], plugins=[Reports()]))
assert implementation_digest() == PIN
target = ROOT / 'validation/campaign/tile_targets_v1/author_tests_v10.json'
with target.open('x', encoding='utf8') as f:
    json.dump({'core': PIN, 'exitcode': code, 'cases': cases, 'client_verified': False}, f, indent=2)
raise SystemExit(code)
