"""0-11-specific native consumers; no reuse of flat0-10 stage assumptions."""
from copy import deepcopy
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools import prepare_external_00_11 as b


@pytest.fixture(scope='module')
def data():return b.read(b.NATIVE),b.read(b.SOURCE)


def test_frozen_byte_copy_and_external_gate_is_not_approval():
    from ark_sim import Compiler
    from tools.campaign_model_acceptance import contract_gate
    assert b.CONTENT.read_bytes()==b.SOURCE.read_bytes() and b.COMMANDS.read_bytes()==b.COMMAND_SOURCE.read_bytes()
    c=b.read(b.CONTRACT);case={'native_id':'main_00-11','level_id':'level_main_00-11','expected_native_spawns':37,'native_source_sha256':b.NATIVE_PIN}
    p=Compiler().compile(b.CONTENT);reference=b.read(ROOT/'packages/campaign/roster.reference.json')
    contract_gate(p,case,reference,c,b.PIN,require_witnesses=False)
    with pytest.raises(ValueError,match='executed test references'):contract_gate(p,case,reference,c,b.PIN)
    assert c['source_review_pending'] and not c['formal_approval'] and c['shared_witness_proposals']
    assert all(not refs for refs in c['mechanic_tests'].values())


@pytest.mark.parametrize('change',['flat','managed','blocks_wave','fragment_delay','deadline','offset','population','story_flags','unknown_option','tile_effect'])
def test_changed_native_or_consumers_rejected(data,change):
    native,model=map(deepcopy,data)
    timeline=model['scenarioDraft']['timeline']
    if change=='flat':model['scenarioDraft']['timeline']['waves']=timeline['waves'][:1]
    elif change=='managed':timeline['waves'][0]['fragments'][1]['actions'][0]['managed']=False
    elif change=='blocks_wave':timeline['waves'][0]['fragments'][1]['actions'][0]['blocks_wave']=False
    elif change=='fragment_delay':timeline['waves'][1]['fragments'][0]['pre_delay_seconds']+=1
    elif change=='deadline':native['routes'][13]['checkpoints'][1]['time']=31
    elif change=='offset':
        action=next(a for w in timeline['waves'] for f in w['fragments'] for a in f['actions'] if a.get('kind')=='spawn' and a['spawn']['parameters']['native_route_index']==17)
        action['spawn']['route']['reach_offset_policy']['parameters']['axis_signs']['row']=1
    elif change=='population':timeline['waves'][2]['fragments'][0]['actions'].pop()
    elif change=='story_flags':timeline['waves'][0]['fragments'][0]['actions'][0]['metadata']['native_action']['managedByScheduler']=False
    elif change=='unknown_option':native['options']['unmappedMath']=1
    else:native['mapData']['effects']=[{'type':'active'}]
    with pytest.raises((ValueError,IndexError)):b.native_audit(native,model)


def test_exact_grouping_deadline_and_offset_count(data):
    rows,population,origins,specials,controls=b.native_audit(*data)
    assert sum(population.values())==37 and len(population)==6 and len(origins)==40
    assert len([r for r in specials if r.get('nonzero_offset')])==5
    assert len([r for r in specials if not r.get('nonzero_offset')])==2
    assert {r['route_index'] for r in specials if not r.get('nonzero_offset')}=={13,14}
    assert [r['kind'] for r in controls]==['STORY','DISPLAY_ENEMY_INFO','DISPLAY_ENEMY_INFO']
    assert sum(r['classification']=='gate_contract_gap' for r in rows)==6
    assert all(r['consumer'] and r['criterion'] and r['native_value_sha256'] for r in rows)


def test_scope_proposal_never_relabels_report_or_executes_target():
    path=ROOT/'packages/campaign/conversion_drafts/main_00-11.witness_scope.proposal.json';d=b.read(path)
    assert d['default_cross_package_gate_must_still_reject'] and d['source_report_input_hashes_not_modified'] and not d['formal_approval']
    assert len(d['case_proposals'])==86
    assert all(not r['target_case_executed'] and r['source_content_sha256']!=r['target_content_sha256'] for r in d['case_proposals'])
    multi=[r for r in d['case_proposals'] if r['status']=='multi_fixture_scope_not_proven'];static=[r for r in d['case_proposals'] if r['status']=='not_a_fixture_proof']
    assert len(multi)==5 and len(static)==4
    for r in d['case_proposals']:
        if r['status']=='structural_candidate_requires_review':
            p=r['proof'];assert p['effective_scenario_inputs_equal'] and p['dependency_id_sets_equal'] and p['provider_descriptors_equal']
            assert p['initial_world_equal'] and p['initial_events_equal'] and p['initial_rng_equal']
            assert p['actual_package_loader_anchors_verified'] and not p['changed_reachable_definitions']


def test_actual_enemy_asset_frames_parse_and_map(data):
    native,model=data;rows,locks=b.enemy_sources(model,native)
    assert len({r['consumer'] for r in rows})==6 and rows and locks
