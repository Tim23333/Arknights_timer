"""Run the production V2 suite with the exact catalog extension expectation."""
import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    from ark_sim.adapters.api import implementation_digest
    core = implementation_digest()
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = args.output or ROOT / f'validation/reports/primary_v2_{timestamp}.json'
    run_dir = Path('E:/ArkSimLogs/runs') / ('primary_v2_' + timestamp)
    command = [sys.executable, str(ROOT / 'tools/run_with_log_cleanup.py'), '--run-dir', str(run_dir), '--',
               sys.executable, str(ROOT / 'tools/chapter09_pillar_v1/run_full_suite_v9.py'),
               '--runtime-root', str(ROOT), '--expected-core', core, '--output', str(output)]
    raise SystemExit(subprocess.call(command, cwd=ROOT))


if __name__ == '__main__':
    main()
