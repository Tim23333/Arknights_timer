"""Run the actual default V2 baseline with fixed-directory automatic cleanup."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    from ark_sim.adapters.api import implementation_digest
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = args.output or ROOT / f'validation/reports/primary_v2_baseline_{stamp}.json'
    if output.exists():
        raise FileExistsError('Preserve previous baseline reports')
    run_dir = Path('E:/ArkSimLogs/runs') / ('primary_v2_baseline_' + stamp)
    command = [sys.executable, str(ROOT / 'tools/run_with_log_cleanup.py'), '--run-dir', str(run_dir), '--',
               sys.executable, str(ROOT / 'tools/chapter10_stage_assembly_v2/verify_baseline_v2.py'),
               '--runtime-root', str(ROOT), '--expected-core', implementation_digest(), '--output', str(output)]
    return subprocess.call(command, cwd=ROOT)


if __name__ == '__main__':
    raise SystemExit(main())
