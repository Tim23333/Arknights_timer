"""Capture real source ore consumer tests with unchanged runtime/source guards."""
import hashlib
import json
import sys
from pathlib import Path
import pytest
from ark_sim.adapters.api import implementation_digest

ROOT = Path(__file__).resolve().parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    tests = [Path(__file__).with_name('test_mine_cards_burst_v2.py'),Path(__file__).with_name('test_mine_cards_v2.py')]
    paths = list((ROOT / 'ark_sim').rglob('*.py')) + list((ROOT / 'ark_sim').rglob('*.json'))
    paths += [p for p in Path(__file__).parent.glob('*.py')]
    paths += [ROOT / 'packages/campaign/chapter07_predefines/source.v4.reference.json',
              ROOT / 'packages/campaign/chapter07_predefines_consumer/mine.module.v2.json',
              ROOT.parent / 'unpack_work/campaign_tables/range_table.reference_56a.json',
              ROOT / 'tools/campaign_ordered_checkpoint.py']
    before = {str(p): sha(p) for p in paths if '__pycache__' not in p.parts}
    core = implementation_digest()
    rows = []

    class Capture:
        def pytest_runtest_logreport(self, report):
            if report.when == 'call':
                rows.append({'case': report.nodeid, 'outcome': report.outcome,
                             'failure': str(report.longrepr) if report.failed else None})

    code = int(pytest.main([*map(str, tests), '-q', '--tb=short'], plugins=[Capture()]))
    after = {str(p): sha(Path(p)) for p in before}
    stable = before == after and implementation_digest() == core
    out = ROOT / 'validation/campaign/chapter07_mine_consumer_v2/verification.json'
    assert not out.exists()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'core': core, 'actual_exit': code,
        'passed': code == 0 and stable, 'guards_start': before, 'guards_end': after,
        'guards_equal': stable, 'cases': rows,
        'scope': 'Source mode20/SP25 independent, fixed fee5/stock15/slot0/max1/refund0/retirecooldown7/publicrejections atomic and orderedfragileactorNORMAL explosion, CP/head. Frame tick0 reference749 for750 recovery steps, radiuscentrepostfilter and nativeend/cancel pending; no full device/stage assertion.',
        'complete_source_consumer': False, 'whole_stage_executed': False,
        'independent_reviewed': False, 'client_verified': False}, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'sha': sha(out), 'passed': code == 0 and stable,
                      'cases': len(rows), 'core': core}))
    raise SystemExit(0 if code == 0 and stable else 1)


if __name__ == '__main__':
    main()
