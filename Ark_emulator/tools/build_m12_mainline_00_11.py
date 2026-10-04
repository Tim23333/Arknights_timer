"""Apply the reviewed synchronous NoBlock and grid profiles to frozen 0-11."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'packages/campaign/mainline_models/level_main_00-11.m10.json'
BASELINE = ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json'
OUTPUT = ROOT/'packages/campaign/mainline_models/level_main_00-11.m12_projection.json'
PIN_BASELINE = '0fbba3f0548d2efaef97d7c1be98a620e65b6408755bfddbd49a132ef72fddf4'
PIN_SOURCE = 'ecc12e950bcc8f1861116892001d16af456c665e9789f29bec5e6214f74c3717'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    if sha(SOURCE) != PIN_SOURCE:
        raise ValueError('Frozen M10 0-11 input changed')
    if sha(BASELINE) != PIN_BASELINE:
        raise ValueError('Reviewed 0-10 source changed')
    original = json.loads(SOURCE.read_bytes())
    data = deepcopy(original)
    known = json.loads(BASELINE.read_bytes())
    # Take only the two already-reviewed mathematical changes. The timeline,
    # offsets, enemy data and selected twelve-person profile stay untouched.
    aid = 'ability/campaign_myrtle_s2'
    bid = 'buff/campaign_myrtle_no_block'
    for section, ref in [('abilities', aid), ('buffs', bid)]:
        current = next(d for d in data[section] if d['id'] == ref)
        final = next(d for d in known[section] if d['id'] == ref)
        current.clear()
        current.update(deepcopy(final))
    operator_definitions = {}
    for key in ('entities', 'abilities', 'buffs', 'selectors', 'rules'):
        # Stage-specific enemies and their native timing metadata remain from
        # 0-11. Every non-enemy definition is identical to reviewed 0-10.
        current = {d['id']: d for d in data[key] if '/enemy_' not in d['id']}
        reviewed = {d['id']: d for d in known[key] if '/enemy_' not in d['id']}
        if current != reviewed:
            raise ValueError('0-11 operator closure differs from reviewed 0-10: '+key)
        operator_definitions[key] = sorted(current)
    restored = deepcopy(data)
    for section, ref in [('abilities', aid), ('buffs', bid)]:
        index = next(i for i, d in enumerate(restored[section]) if d['id'] == ref)
        restored[section][index] = deepcopy(next(d for d in original[section] if d['id'] == ref))
    if restored != original:
        raise ValueError('Composition changed fields outside the two reviewed definitions')
    if data['scenarioDraft'] != original['scenarioDraft']:
        raise ValueError('0-11 scenario changed while composing actor profiles')
    for wave in data['scenarioDraft']['timeline']['waves']:
        for fragment in wave['fragments']:
            for action in fragment['actions']:
                if action['kind'] == 'spawn':
                    route = action['spawn'].get('route', {})
                    if any(any((cp.get('reachOffset') or {}).values()) for cp in route.get('checkpoints') or []):
                        if route.get('reach_offset_policy') != {'rule': 'rule/m9_checkpoint_cartesian',
                                'parameters': {'axis_signs': {'row': -1, 'col': 1}}}:
                            raise ValueError('0-11 nonzero checkpoint offsets lack explicit policy')
    meta = data['manifest']['metadata']
    meta['M12_current_00_11'] = {
        'source': SOURCE.relative_to(ROOT).as_posix(), 'source_sha256': sha(SOURCE),
        'reviewed_actor_source': BASELINE.relative_to(ROOT).as_posix(),
        'reviewed_actor_source_sha256': PIN_BASELINE, 'builder_sha256': sha(Path(__file__)),
        'changed_actor_definitions': [aid, bid], 'all_operator_definitions_equal_reviewed_00_10': True,
        'shared_operator_closure': operator_definitions,
        'scenario_timeline_routes_offsets_controls_unchanged': True,
        'grid_profile': 'standard_grid_cells_floor_coordinate_plus_half_v1',
        'native_comparator_and_FSM': 'client_pending', 'formal_approval': False}
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2)+'\n').encode('utf8')
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_bytes() != raw:
            raise ValueError('Current 0-11 content changed')
    else:
        OUTPUT.write_bytes(raw)
    print(json.dumps({'output': str(OUTPUT), 'sha256': sha(OUTPUT), 'formal_approval': False}))


if __name__ == '__main__':
    main()
