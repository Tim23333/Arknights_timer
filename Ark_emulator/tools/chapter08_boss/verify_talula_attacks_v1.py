"""Record actual two-mode author tests with immutable source/core/helper pins."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pytest
import ark_sim
from ark_sim.adapters.api import implementation_digest
from tools.chapter08_boss.build_talula_attacks_v1 import OUT, sha, CORE


def main():
    assert implementation_digest() == CORE
    module = json.loads(OUT.read_bytes())
    paths = list((ROOT/'ark_sim').rglob('*.py'))+list((ROOT/'ark_sim').rglob('*.json'))
    paths += list((ROOT/'tools/chapter08_boss').glob('*.py'))+[OUT,ROOT/'tools/campaign_ordered_checkpoint.py']
    paths += [ROOT/p for p in module['manifest']['metadata']['source_locks']]
    before = {str(p):sha(p) for p in paths}
    start = time.monotonic()
    code = int(pytest.main([str(ROOT/'tools/chapter08_boss/test_talula_attacks_v1.py'), '-q']))
    after = {str(p):sha(p) for p in paths}
    assert before == after and implementation_digest() == CORE
    dest = ROOT/'validation/campaign/chapter08_talula_attacks_author_v1/verification.json'
    assert not dest.exists()
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = {'passed':code == 0, 'actual_exit':code, 'core':CORE, 'runtime':ark_sim.__file__, 'module_sha':sha(OUT),
        'source_before':before, 'source_after':after, 'elapsed_seconds':time.monotonic()-start,
        'scope':'Two source mode attacks, real blocking40frame PURE1500/shared135clock, ranged30frame homing10/.40000000596 current ATK/RES, live RES43, ASPD2, native side/motion/category/free/camo/range gates and CP/head full state/events.',
        'complete_boss':False, 'whole_stage_executed':False, 'independent_reviewed':False, 'client_verified':False}
    dest.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'actual_exit':code,'verification_sha':sha(dest)}))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
