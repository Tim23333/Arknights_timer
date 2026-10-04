"""Actual author execution with source/core/helper start and end guards."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import ark_sim
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.chapter08_ordinary.build_uterer_v1 import CORE, OUT, sha


def main():
    assert implementation_digest() == CORE
    module = json.loads(OUT.read_bytes())
    paths = list((ROOT/'ark_sim').rglob('*.py'))+list((ROOT/'ark_sim').rglob('*.json'))
    paths += list((ROOT/'tools/chapter08_ordinary').glob('*.py'))+[OUT, ROOT/'tools/campaign_ordered_checkpoint.py']
    paths += [ROOT/p for p in module['manifest']['metadata']['source_locks']]
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    started = time.monotonic()
    code = int(pytest.main([str(ROOT/'tools/chapter08_ordinary/test_uterer_v3.py'), '-q']))
    after = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    assert before == after and implementation_digest() == CORE
    dest = ROOT/'validation/campaign/chapter08_uterer_author_v3/verification.json'
    assert not dest.exists()
    dest.parent.mkdir(parents=True, exist_ok=True)
    report = {'schema': 'ark-sim/source-consumer-execution/v1', 'passed': code == 0, 'actual_exit': code,
        'core': CORE, 'runtime': ark_sim.__file__, 'source_before': before, 'source_after': after,
        'module_sha': sha(OUT), 'selected_tests': 'tools/chapter08_ordinary/test_uterer_v3.py',
        'elapsed_seconds': time.monotonic()-started,
        'scope': 'Exact uterer source/base HP3500/ATK380/DEF100/RES20/move1.7; real blocked OnAttack12/cycle45, current DEF137/237→243/143, real public ASPD3→4/15, DP7, withdrawal/retirement, death, full snapshot+event CP/head equality.',
        'independent_reviewed': False, 'whole_stage_executed': False, 'client_verified': False}
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='')
    print(json.dumps({'actual_exit': code, 'verification_sha': sha(dest)}))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
