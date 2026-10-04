"""Consume exact nativebranch profiles around the strict base stage converter."""
from copy import deepcopy
from tools.chapter06_review.stage_converter_v7 import exact
from tools.chapter08_joint_v4.stage_converter_reusable_v2 import compose as base


def compose(native, native_id, bindings, tile_profiles, *, branch_profile, predefined_profile,
            story_key_profile=None, story_controls=None, opera_controls=None):
    assert isinstance(branch_profile, dict) and 'runtime_branch' in branch_profile
    assert set(native['branches']) == set(branch_profile['runtime_branch']) == {'bsnake_flame'}
    raw = native['branches']['bsnake_flame']
    phases = branch_profile['runtime_branch']['bsnake_flame']['phases']
    assert len(raw['phases']) == len(phases) == 7
    assert branch_profile['runtime_branch']['bsnake_flame']['loop'] is True
    for original, converted in zip(raw['phases'], phases):
        assert type(original['preDelay']) in (int, float) and converted['pre_delay_seconds'] == original['preDelay']
        assert len(original['actions']) == len(converted['actions'])
        for source, action in zip(original['actions'], converted['actions']):
            assert source['actionType'] == 'ACTIVATE_PREDEFINED' and type(source['count']) is int and source['count'] == 1
            assert source['managedByScheduler'] is True and source['refreshType'] == source['randomType'] == 'ALWAYS'
            assert source['interval'] == 0 and source['blockFragment'] is False and source['forceBlockWaveInBranch'] is False
            assert action == {'delay_seconds': source['preDelay'], 'effects': [
                {'op': 'activate_predefined', 'target': 'battle', 'parameters': {'key': source['key']}}]}
    assert exact(predefined_profile['native_predefines'], native['predefines'])
    assert exact(predefined_profile['initial_entities'], branch_profile['initial_entities'])
    from ark_sim.domains.predefined_reactivation import validate
    for item in predefined_profile['initial_entities']:
        validate(item['reactivation'])
        assert item['active'] is False and item.get('instanceAlias') is None
    for bucket in ('characterInsts', 'tokenInsts'):
        raw_rows = native['predefines'].get(bucket) or []
        converted_rows = [item for item in predefined_profile['initial_entities']
                          if item.get('parameters', {}).get('native_bucket') == bucket]
        assert len(raw_rows) == len(converted_rows)
        assert all(exact(raw, item['parameters']['native_instance']) for raw, item in zip(raw_rows, converted_rows))
    view = deepcopy(native)
    view['branches'] = None
    hard = view.get('hardPredefines')
    if hard is not None:
        assert set(hard) == {'characterInsts', 'tokenInsts', 'characterCards', 'tokenCards'}
        assert all(value in (None, [], {}) for value in hard.values())
        view['hardPredefines'] = None
    scene, controls = base(view, native_id, bindings, tile_profiles, story_key_profile=story_key_profile,
                           story_controls=story_controls, predefined_profile=predefined_profile, opera_controls=opera_controls)
    scene['branches'] = deepcopy(branch_profile['runtime_branch'])
    scene.setdefault('metadata', {})['active_source_branches'] = {
        'native': deepcopy(native['branches']), 'runtime_loop': True,
        'run_horizon_policy': deepcopy(branch_profile['run_horizon_policy']),
        'conversion': 'Each exact nativeaction consumes one explicit runtimeaction; native loop flag from source Summon/Trigger',
    }
    scene['metadata']['empty_hard_predefines'] = {'native': deepcopy(hard), 'selected_normal_difficulty': 1}
    return scene, controls
