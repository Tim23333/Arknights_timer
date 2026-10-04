"""Keep a compact per-case result before the managed command cleans captures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    import pytest
    guard_paths = [Path(__file__), ROOT / 'tools/chapter09_linked_elemental/test_author_v2.py', ROOT / 'tools/chapter09_linked_elemental/fixture_v2.py']
    runtime = ROOT.parent / 'unpack_work/campaign_c9_linked_elemental_v2_candidate'
    guard_paths += list((runtime / 'ark_sim').rglob('*.py'))
    guard = lambda: {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in guard_paths}
    before = guard()
    cases = []
    class Capture:
        def pytest_runtest_logreport(self, report):
            if report.when == 'call' or report.failed:
                cases.append({'case': report.nodeid, 'outcome': report.outcome,
                              'failure': str(report.longrepr) if report.failed else None})
    run = Path(os.environ['ARKSIM_RUN_DIR'])
    started = time.monotonic()
    code = int(pytest.main(['tools/chapter09_linked_elemental/test_author_v2.py', '-q', '--tb=short',
                           '--basetemp', str(run / 'temp'), '-o', 'cache_dir=' + str(run / 'cache')], plugins=[Capture()]))
    after = guard()
    result = {'passed': code == 0 and before == after, 'identity_stable': before == after, 'guards_before': before, 'guards_after': after, 'actual_exit': code, 'cases': cases,
              'elapsed_seconds': time.monotonic() - started, 'whole_stage_verified': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    return code or (0 if before == after else 2)


if __name__ == '__main__':
    raise SystemExit(main())
