"""Keep a compact per-case result before the managed command cleans captures."""
import argparse
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
    cases = []
    class Capture:
        def pytest_runtest_logreport(self, report):
            if report.when == 'call' or report.failed:
                cases.append({'case': report.nodeid, 'outcome': report.outcome,
                              'failure': str(report.longrepr) if report.failed else None})
    run = Path(os.environ['ARKSIM_RUN_DIR'])
    started = time.monotonic()
    code = int(pytest.main(['tools/chapter09_linked_elemental/test_author_v1.py', '-q', '--tb=short',
                           '--basetemp', str(run / 'temp'), '-o', 'cache_dir=' + str(run / 'cache')], plugins=[Capture()]))
    result = {'passed': code == 0, 'actual_exit': code, 'cases': cases,
              'elapsed_seconds': time.monotonic() - started, 'whole_stage_verified': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
