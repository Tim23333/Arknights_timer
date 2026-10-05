"""Explicit source integration correction; never alter frozen V4 input."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parent = ROOT / 'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v4.life99999.json'
    p = json.loads(parent.read_bytes()); originals = {}
    rule = 'rule/ch9/blocked_input'
    for name in ('duholy', 'dushdo'):
        selector = next(d for d in p['definitions'] if d['id'] == 'selector/ch9/coupled/' + name + '/blocker')
        originals[selector['id']] = deepcopy(selector)
        selector['eligibility']['rule'] = rule
        selector['metadata'] = {'input_target_source': 2,
            'reference_policy': 'Actual obstacle blocker input can be attacked despite category4; ordinary range category masks unchanged',
            'native_wrapper_body_verified': False}
    p['definitions'].append({'id': rule, 'kind': 'rule', 'contract': 'targeting.eligibility',
        'parameters': {'obstacle_category': 4, 'enemy_index': 1, 'ally_index': 0},
        'implementation': {'type': 'provider', 'provider': 'reference.ch9.blocked_input'}})
    p['manifest']['metadata']['blocked_input_reference'] = {'parent_sha': hashlib.sha256(parent.read_bytes()).hexdigest(),
        'original_selectors': originals, 'native_selectTargetSource': 'INPUT_TARGET=2',
        'reference_url': 'https://prts.wiki/w/战场废墟', 'native_wrapper_body_verified': False,
        'only_actual_blocked_obstacle_exception': True, 'whole_stage': False}
    out = parent.with_name('level_main_09-16.native_draft.v5.life99999.json')
    assert not out.exists(); out.write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'stage_sha': hashlib.sha256(out.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
