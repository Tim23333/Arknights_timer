"""Fresh source-only peer of v3; no ballista runtime or Root fixture reuse."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from tools.build_reference_stage_scenario_v4 import compose
from tools.build_reference_stage_scenario_v2 import compose as old_compose

ROOT = Path(__file__).resolve().parents[3]


def source(code): return json.loads((ROOT/'packages/campaign/native_reference'/('level_main_'+code+'.json')).read_bytes())


def profile(n):
    rows = len(n['mapData']['map']); records = []
    for bucket in ('characterInsts', 'tokenInsts'):
        for i, rec in enumerate(n['predefines'].get(bucket) or []):
            e = {'definition': 'unit/peer/predefined', 'position': {'row': rows-1-rec['position']['row'], 'col': rec['position']['col']},
                 'facing': rec['direction'].lower(), 'parameters': {'native_bucket': bucket, 'native_instance': deepcopy(rec)}}
            if rec['hidden']:
                e.update(active=False, registration_key=rec['alias'], instanceAlias=rec['alias'])
            else: e['instanceAlias'] = 'visible/'+bucket+'/'+str(i)
            records.append(e)
    return {'native_predefines': deepcopy(n['predefines']), 'initial_entities': records, 'card_bindings': [], 'resources': {}}


def converted(n, p):
    b = {r['id']: {'unit': 'unit/peer/'+r['id'], 'motion': 'WALK'} for r in n['enemyDbRefs']}
    tiles = {'tile_telin': {'type': 'route_checkpoint_portal', 'role': 'entry'}, 'tile_telout': {'type': 'route_checkpoint_portal', 'role': 'exit'}}
    return compose(n, 'peer', b, tiles, predefined_profile=p)


def projected(n):
    # Nonempty branches must be converted separately; retain original source.
    n = deepcopy(n); n['branches'] = None; return n


def test_exact_adapter_byte_guards():
    assert hashlib.sha256((ROOT/'tools/build_reference_stage_scenario_v3.py').read_bytes()).hexdigest() == '85017cfda3a47c707ee16e7608afdda711333a68a32d2c8e9c2c5ddb316a8386'
    assert hashlib.sha256((ROOT/'tools/build_reference_stage_scenario_v2.py').read_bytes()).hexdigest() == 'f9a2814f444549e66839be0709dcce65284f4c8a7a2254b84ccdd59ceab787cb'


def test_visible_5_9_v2_exact_output_equivalence():
    n = source('05-09'); p = profile(n); new = converted(n, p)
    b = {r['id']: {'unit': 'unit/peer/'+r['id'], 'motion': 'WALK'} for r in n['enemyDbRefs']}
    tiles = {'tile_telin': {'type': 'route_checkpoint_portal', 'role': 'entry'}, 'tile_telout': {'type': 'route_checkpoint_portal', 'role': 'exit'}}
    assert new == old_compose(n, 'peer', b, tiles, predefined_profile=p)
    assert len(new[0]['initialEntities']) == 4 and all(e.get('active', True) is True for e in new[0]['initialEntities'])


@pytest.mark.parametrize('code,count,predefs', [('05-09', 51, 4), ('05-10', 73, 10)])
def test_fresh_source_waves_routes_options_runes_and_all_predefines_preserved(code, count, predefs):
    original = source(code); n = projected(original); p = profile(n); scene, controls = converted(n, p)
    assert scene['metadata']['native_predefines'] == original['predefines']
    assert scene['metadata']['native_options'] == original['options']
    assert [x['raw'] for x in scene['metadata']['rune_policy']] == original['runes']
    assert scene['resources']['dp']['initial'] == original['options']['initialCost']
    assert scene['resources']['life']['initial'] == 3 and scene['parameters']['deploy_capacity'] == original['options']['characterLimit']
    assert len(scene['initialEntities']) == predefs
    rows = len(original['mapData']['map']); spawn_count = 0
    for wi, wave in enumerate(original['waves']):
        out = scene['timeline']['waves'][wi]
        assert (out['pre_delay_seconds'], out['post_delay_seconds'], out['max_wait_seconds']) == (wave['preDelay'], wave['postDelay'], wave['maxTimeWaitingForNextWave'])
        for fi, frag in enumerate(wave['fragments']):
            actual = out['fragments'][fi]; assert actual['pre_delay_seconds'] == frag['preDelay']
            for ai, native in enumerate(frag['actions']):
                a = actual['actions'][ai]; assert a['metadata']['native_action'] == native
                assert (a['count'], a['managed'], a['delay_seconds'], a['interval_seconds']) == (native['count'], native['managedByScheduler'], native['preDelay'], native['interval'])
                if native['actionType'] == 'SPAWN':
                    spawn_count += native['count']; ir = a['spawn']['route']; raw = original['routes'][native['routeIndex']]
                    assert ir['startPosition'] == {'row': rows-1-raw['startPosition']['row'], 'col': raw['startPosition']['col']}
                    assert ir['endPosition'] == {'row': rows-1-raw['endPosition']['row'], 'col': raw['endPosition']['col']}
                    for actual_cp, native_cp in zip(ir['checkpoints'], raw.get('checkpoints') or []):
                        expected = deepcopy(native_cp)
                        if expected.get('position') is not None: expected['position']['row'] = rows-1-expected['position']['row']
                        assert actual_cp == expected
    assert spawn_count == count
    for rec, actual in zip(original['predefines']['tokenInsts'], scene['initialEntities']):
        assert actual['parameters']['native_instance'] == rec
        assert actual['position'] == {'row': rows-1-rec['position']['row'], 'col': rec['position']['col']}
        assert actual['facing'] == rec['direction'].lower()
        if rec['hidden']: assert actual['active'] is False and actual['registration_key'] == actual['instanceAlias'] == rec['alias']


def test_complete_5_10_branch_is_explicitly_rejected_not_silently_omitted():
    n = source('05-10')
    with pytest.raises(ValueError, match='branches'): converted(n, profile(n))


@pytest.mark.parametrize('active', [0, 1, True, None])
def test_wrong_hidden_active_not_bool_false_rejected(active):
    n = projected(source('05-10')); p = profile(n); p['initial_entities'][0]['active'] = active
    with pytest.raises(ValueError): converted(n, p)


@pytest.mark.parametrize('field', ['registration_key', 'instanceAlias'])
def test_wrong_registration_or_alias_rejected(field):
    n = projected(source('05-10')); p = profile(n); p['initial_entities'][0][field] = 'wrong'
    with pytest.raises(ValueError): converted(n, p)


def test_visible_cannot_be_authored_dormant():
    n = source('05-09'); p = profile(n); p['initial_entities'][0]['active'] = False
    with pytest.raises(ValueError): converted(n, p)


@pytest.mark.parametrize('hidden', [0, 1, 'true', None])
def test_native_wrong_hidden_type_rejected(hidden):
    n = projected(source('05-10')); n['predefines']['tokenInsts'][0]['hidden'] = hidden
    p = profile(n)
    with pytest.raises(ValueError): converted(n, p)


def test_duplicate_native_alias_rejected_even_exact_profiles():
    n = projected(source('05-10')); n['predefines']['tokenInsts'][1]['alias'] = n['predefines']['tokenInsts'][0]['alias']
    p = profile(n)
    with pytest.raises(ValueError): converted(n, p)
