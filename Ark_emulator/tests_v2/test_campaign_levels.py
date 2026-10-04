"""Local binary recovery vs separately downloaded immutable native references."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("extract_campaign_levels", ROOT / "tools/extract_campaign_levels.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)
SOURCE = ROOT.parent / "unpack_work/release_20260831/base_raw"
REFERENCE = ROOT / "packages/campaign/native_reference"


@pytest.fixture(scope="module")
def recovered():
    catalog=json.loads((ROOT/'packages/campaign/mainline_catalog.json').read_text(encoding='utf8'))
    return {r['level_id']: tool.extract(SOURCE/(r['level_id']+'.dat'),REFERENCE/(r['level_id']+'.json'))
            for r in catalog['stages'] if r['selected']}


@pytest.mark.parametrize("lid", ('level_main_00-10','level_main_00-11','level_main_01-11','level_main_01-12'))
def test_core_is_decoded_from_binary_and_matches_reference(recovered,lid):
    result = recovered[lid]
    report = result['_recovery']
    assert report['core_status']=='reference_verified'
    assert report['status']=='partial'  # Full root schema has not been validated.
    assert report['differences']==[]
    assert report['core_exact_equal'] is True
    assert report['issues']==[]
    assert report['source_sha256']==tool.sha(SOURCE/(lid+'.dat'))
    assert report['reference_sha256']==tool.sha(REFERENCE/(lid+'.json'))
    assert report['payload_offset']==152
    assert report['v2_status']=='not_validated'
    reference=json.loads((REFERENCE/(lid+'.json')).read_text(encoding='utf8'))
    assert tool.canonical_core(result)==tool.canonical_core(reference)


def test_recovered_walk_route_and_grid_are_not_zero_fallback(recovered):
    result = recovered['level_main_00-10']
    assert len(result['mapData']['map'])==9
    assert len(result['mapData']['map'][0])==13
    assert result['mapData']['map'][0]==list(range(104,117))
    route = result['routes'][1]
    assert route['motionMode']=='WALK'
    assert route['startPosition']=={'row':4,'col':0}
    assert route['endPosition']=={'row':4,'col':12}
    assert [c['position'] for c in route['checkpoints']]==[
        {'row':4,'col':8},{'row':3,'col':8},{'row':3,'col':10},{'row':4,'col':10}]
    assert all(c['type']=='MOVE' and c['time']==0 for c in route['checkpoints'])


def test_placeholder_route_indices_are_preserved(recovered):
    result = recovered['level_main_00-10']
    assert result['routes'][0]['motionMode']=='E_NUM'
    assert result['routes'][0]['checkpoints'] is None
    assert 0 not in result['_recovery']['spawn_route_indices']
    assert len(result['routes'])==19


def test_complete_predefines_are_recovered(recovered):
    pre = recovered['level_main_01-11']['predefines']
    assert len(pre['characterCards'])==12
    entity = pre['characterInsts'][0]
    assert entity['inst']['characterKey']=='char_211_adnach'
    assert entity['position']=={'row':3,'col':6}
    assert entity['direction']=='RIGHT' and entity['hidden'] is True
    trap = recovered['level_main_01-12']['predefines']['tokenInsts'][0]
    assert trap['inst']['characterKey']=='trap_002_emp'
    assert trap['inst']['level']==10
    assert trap['position']=={'row':2,'col':5}
    assert trap['direction']=='UP'


def test_wave_default_route_and_pre_delay_are_explicit(recovered):
    action = recovered['level_main_00-10']['waves'][0]['fragments'][0]['actions'][0]
    assert action['actionType']=='STORY'
    assert action['routeIndex']==0 and action['preDelay']==0.0
    assert action['managedByScheduler'] is True
    assert action['count']==1


def test_missing_reference_does_not_supply_coordinates():
    result = tool.extract(SOURCE/'level_main_00-10.dat')
    assert result['_recovery']['core_status']=='decoded_unverified'
    assert result['routes'][1]['startPosition']=={'row':4,'col':0}
    assert 'reference_path' not in result['_recovery']


def test_missing_coordinate_table_is_fatal():
    decoder=tool.Decoder(None,None)
    with pytest.raises(tool.RecoveryError,match='refusing to fabricate'):
        decoder.point(None)


def test_wrong_named_asset_and_truncation_are_rejected():
    data=(SOURCE/'level_main_00-10.dat').read_bytes()
    with pytest.raises(tool.RecoveryError,match='name mismatch'):
        tool.payload(data,'level_main_00-11')
    with pytest.raises(tool.RecoveryError,match='Truncated'):
        tool.payload(data[:100],'level_main_00-10')


def test_comparison_exposes_coordinate_change(recovered):
    reference=json.loads((REFERENCE/'level_main_00-10.json').read_text(encoding='utf8'))
    reference['routes'][1]['startPosition']['row']=99
    differences=tool.compare_core(recovered['level_main_00-10'],reference)
    assert any(d['path']=='routes[1].startPosition.row' for d in differences)


def test_all_36_selected_native_cores_exactly_match_pinned_references(recovered):
    assert len(recovered)==36
    for lid,result in recovered.items():
        reference=json.loads((REFERENCE/(lid+'.json')).read_text(encoding='utf8'))
        assert tool.canonical_core(result)==tool.canonical_core(reference),lid
        assert result['_recovery']['core_exact_equal'] is True,lid
        assert result['_recovery']['core_status']=='reference_verified',lid
        assert result['_recovery']['issues']==[],lid


def test_legacy_tile_blackboard_values_are_decoded_not_advanced_mask(recovered):
    tile=recovered['level_main_02-09']['mapData']['tiles'][36]
    assert tile['blackboard']==[{'key':'atk_scale','value':1.7,'valueStr':None},
                               {'key':'attack_speed','value':-20.0,'valueStr':None}]
    assert 'advancedBuildableMask' not in tile


def test_predefined_override_and_token_card_prefix_are_calibrated(recovered):
    entity=recovered['level_main_13-18']['predefines']['tokenInsts'][0]
    assert entity['overrideSkillBlackboard']==[{'key':'branch_id','value':0.0,'valueStr':'bmbcar1'}]
    card=recovered['level_main_03-07']['predefines']['tokenCards'][0]
    assert card['initialCnt']==5
    assert card['hidden'] is False
    assert recovered['level_main_10-14']['mapData']['tags']==['main_10']
