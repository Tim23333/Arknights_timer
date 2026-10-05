"""Run existing unchanged author cases against the mechanically joined core."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_c9_pillar_channel_joint_v2_candidate'
sys.path.insert(0, str(RUNTIME)); sys.path.insert(1, str(ROOT))
from ark_sim.adapters.api import implementation_digest


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    expected = '4d42e2b6cf646ebe2291d695f82d968e5d4669217069a37bcc8b2babb850f7a4'
    assert implementation_digest() == expected and not args.output.exists()
    tests = ['tools/chapter09_ability_clock_v1/test_clock_v2.py',
        'tools/chapter09_ability_clock_v1/test_flame_channel_v2.py', 'tools/chapter09_pillar_v1/test_cell_fields_v1.py']
    sources = [Path(__file__), *[ROOT / name for name in tests], ROOT / 'tools/chapter09_ability_clock_v1/flame_channel.py',
        ROOT / 'tools/chapter09_pillar_v1/bigforce.py', ROOT / 'tools/chapter09_pillar_v1/build_map_profile.py']
    sources += list((RUNTIME / 'ark_sim').rglob('*.py'))
    guard = lambda: {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    before = guard(); cases = []
    class Capture:
        def pytest_runtest_logreport(self, report):
            if report.when == 'call' or report.failed:
                cases.append({'case': report.nodeid, 'outcome': report.outcome, 'failure': str(report.longrepr) if report.failed else None})
    import pytest
    run = Path(os.environ['ARKSIM_RUN_DIR'])
    code = int(pytest.main([*tests, '-q', '--tb=short', '--basetemp', str(run / 'temp'), '-o', 'cache_dir=' + str(run / 'cache')], plugins=[Capture()]))
    after = guard(); stable = before == after and implementation_digest() == expected
    value = {'passed': code == 0 and stable, 'core': expected, 'actual_exit': code, 'identity_stable': stable,
        'cases': cases, 'guards_before': before, 'guards_after': after, 'whole_stage': False}
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(value, indent=2) + '\n', encoding='utf8')
    return code or (0 if stable else 2)


if __name__ == '__main__': raise SystemExit(main())
