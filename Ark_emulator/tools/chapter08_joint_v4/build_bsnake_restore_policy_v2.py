"""Bind documented restoration review and actual WaveV4 runtime to new content."""
import json
from pathlib import Path
from tools.chapter08_joint_v4.build_bsnake_restore_policy_v1 import OUT as PARENT, BASE, sha

REVIEW = BASE / 'source.first_restore.review.v1.json'
OUT = BASE / 'four_modes.wave_source.v5.json'


def build():
    p = json.loads(PARENT.read_bytes())
    review = json.loads(REVIEW.read_bytes())
    assert review['status'] == 'native_hpRechargeRatio_amount_mapping_unproven_reference100percent_recommended'
    p['manifest']['id'] = 'package/ch8/bsnake/four_modes_wave_source_v5_review_bound'
    meta = p['manifest']['metadata']
    meta['required_runtime'] = '4bf1cc96ae41f2850b645c25d772ada1d472f7b0202127fff340a4fc2b0b04c3'
    meta['source_locks'].update({str(path.resolve()): sha(path) for path in (PARENT, REVIEW, Path(__file__))})
    meta['first_restoration_policy']['independent_source_review'] = {'path': str(REVIEW), 'sha': sha(REVIEW),
        'status': review['status']}
    return p


if __name__ == '__main__':
    assert not OUT.exists()
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(sha(OUT))
