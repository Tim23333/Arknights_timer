"""Guard actual partial source recipe execution without claiming complete Boss."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import ark_sim
import pytest
from ark_sim.adapters.api import implementation_digest
from tools.chapter08_boss.build_talula_threshold_v2 import CORE, OUT, sha


def main():
    assert implementation_digest() == CORE
    p = json.loads(OUT.read_bytes())
    paths = list((ROOT/'ark_sim').rglob('*.py'))+list((ROOT/'ark_sim').rglob('*.json'))
    paths += list((ROOT/'tools/chapter08_boss').glob('*.py'))+[OUT, ROOT/'tools/campaign_ordered_checkpoint.py']
    paths += [ROOT/n for n in p['manifest']['metadata']['source_locks']]
    before = {n.relative_to(ROOT).as_posix(): sha(n) for n in paths}
    started = time.monotonic()
    code = int(pytest.main([str(ROOT/'tools/chapter08_boss/test_talula_threshold_v2.py'), '-q']))
    after = {n.relative_to(ROOT).as_posix(): sha(n) for n in paths}
    assert before == after and implementation_digest() == CORE
    dest = ROOT/'validation/campaign/chapter08_talula_threshold_author_v2/verification.json'
    assert not dest.exists()
    dest.parent.mkdir(parents=True, exist_ok=True)
    report = {'passed': code == 0, 'actual_exit': code, 'core': CORE, 'runtime': ark_sim.__file__,
        'module_sha': sha(OUT), 'source_before': before, 'source_after': after, 'elapsed_seconds': time.monotonic()-started,
        'scope': 'Original50000HP once-only threshold at25000 inclusive/25001 reject, actual permanent max1 Buff DEF700→1400 RES50→90, healing and recross never reapply, real lethal actor50000 cancels threshold, ordered CP/head full snapshot/events equality.',
        'remaining_required_consumers': p['manifest']['metadata']['pending_required_consumers'],
        'complete_boss': False, 'whole_stage_executed': False, 'independent_reviewed': False, 'client_verified': False}
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='')
    print(json.dumps({'actual_exit': code, 'verification_sha': sha(dest)}))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
