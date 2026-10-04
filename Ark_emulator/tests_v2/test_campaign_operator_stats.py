"""Pinned source endpoints, explicit model stats and rejecting counterexamples."""
import copy
from fractions import Fraction
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('campaign_operator_stats',ROOT/'tools/normalize_campaign_operators.py')
tool=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


@pytest.fixture(scope='module')
def inputs():
    characters,skills,lock=tool.load_sources()
    roster=tool.read_json(ROOT/'packages/campaign/roster.reference.json')
    return characters,skills,lock,roster


@pytest.fixture
def myrtle(inputs):
    characters,_,_,roster=inputs
    row=next(r for r in roster['roster'] if r['character_id']=='char_151_myrtle')
    return copy.deepcopy(characters[row['character_id']]),copy.deepcopy(row['config'])


def test_real_source_e2_endpoint_stats(myrtle):
    character,config=myrtle
    config['trust_percent']=0
    config['level']=1
    result=tool.compute_stats(character,config)
    assert {k:result['model_stats'][k] for k in ('maxHp','atk','def')}=={'maxHp':1142,'atk':436,'def':255}
    config['level']=70
    result=tool.compute_stats(character,config)
    assert {k:result['model_stats'][k] for k in ('maxHp','atk','def')}=={'maxHp':1565,'atk':520,'def':300}
    assert result['growth_inputs']['alpha_numerator']==1
    assert result['growth_inputs']['alpha_denominator']==1


def test_real_trust_is_nonzero_and_cap_is_explicit_model(myrtle):
    character,config=myrtle
    result=tool.compute_stats(character,config)
    assert result['model_stats']['def']==350
    assert result['components']['def']['favor']=={'numerator':50,'denominator':1}
    assert result['trust_native_level']=={'numerator':50,'denominator':1}
    config['trust_percent']=50
    assert tool.compute_stats(character,config)['model_stats']['def']==325
    config['trust_percent']=200
    assert tool.compute_stats(character,config)['model_stats']['def']==350
    assert result['client_formula_verified'] is False


def test_missing_favor_is_rejected_instead_of_zero(myrtle):
    character,config=myrtle
    character['favorKeyFrames']=None
    with pytest.raises(tool.NormalizationError,match='refusing zero-trust fallback'):
        tool.compute_stats(character,config)


@pytest.mark.parametrize('field,value', [('level',71),('level',0),('level',True),('elite_phase',3),
                                       ('potential',2),('potential_rank',1),('trust_percent',201),
                                       ('trust_percent',-1),('equipment_id','uniequip_001_myrtle'),
                                       ('equipment_level',1),('skill_level_index',8),('mastery',2)])
def test_illegal_campaign_configs_rejected(myrtle,field,value):
    character,config=myrtle
    config[field]=value
    with pytest.raises(tool.NormalizationError):
        tool.compute_stats(character,config)


def test_selected_skill_index_is_character_zero_based_not_skill_rank(inputs):
    characters,skills,_,roster=inputs
    result=tool.normalize_operator(roster['roster'][0],characters['char_151_myrtle'],skills)
    selected=result['selected_skill']
    assert selected['character_skill_index']==1
    assert selected['native_level_index']==9
    assert selected['skill_id']=='skchr_myrtle_2'
    assert selected['level']['spData']['spCost']==24
    assert selected['level']['spData']['initSp']==10
    assert selected['level']['spData']['spType']=='INCREASE_WITH_TIME'


def test_unknown_or_missing_skill_level_rejected(inputs):
    characters,skills,_,roster=inputs
    row=copy.deepcopy(roster['roster'][0])
    row['config']['skill_id']='skchr_nonexistent_2'
    with pytest.raises(tool.NormalizationError,match='not uniquely present'):
        tool.normalize_operator(row,characters['char_151_myrtle'],skills)
    row=roster['roster'][0]
    changed={**skills,'skchr_myrtle_2':{'levels':skills['skchr_myrtle_2']['levels'][:9]}}
    with pytest.raises(tool.NormalizationError,match='level index missing'):
        tool.normalize_operator(row,characters['char_151_myrtle'],changed)


def test_potential_talent_upgrade_not_active_at_potential1(inputs):
    characters,skills,_,roster=inputs
    result=tool.normalize_operator(roster['roster'][0],characters['char_151_myrtle'],skills)
    talent=result['talents'][0]
    assert talent['selected_candidate']['blackboard']==[{'key':'hp_recovery_per_sec','value':25.0,'valueStr':None}]
    assert len(talent['unlocked_candidates'])==1
    assert any(c['blackboard'][0]['value']==28.0 for c in result['raw_character']['talents'][0]['candidates'])


def test_rounding_counterexample_and_exact_intermediate_are_explicit():
    assert tool.half_away_integer(Fraction(5,2))==3  # Python round(2.5) would produce2.
    assert tool.half_away_integer(Fraction(-5,2))==-3
    assert tool.half_away_integer(Fraction(12,5))==2
    frames=[{'level':1,'data':{'atk':10}},{'level':4,'data':{'atk':12}}]
    values,inputs=tool.interpolate(frames,2)
    assert values['atk']==Fraction(32,3)
    assert inputs=={'lower_level':1,'upper_level':4,'alpha_numerator':1,'alpha_denominator':3}
    assert tool.ROUNDING_PROFILE['client_formula_verified'] is False


def test_token_null_skill_ids_are_preserved_not_synthesized():
    result=tool.build()
    token=result['dependent_characters']['token_10002_kalts_mon3tr']
    assert token['null_skill_id_slots']==[0,1,2]
    assert token['raw_skills']=={}
    assert token['status']=='source_only_owner_growth_and_trust_inheritance_pending'
    assert 'sktok_weedy_token' in result['linked_token_skills']
    assert result['linked_token_skills']['sktok_weedy_token']['runtime_token_binding_status']=='pending'


def test_missing_sp_parameter_is_rejected(inputs):
    characters,skills,_,roster=inputs
    changed={**skills,'skchr_myrtle_2':copy.deepcopy(skills['skchr_myrtle_2'])}
    del changed['skchr_myrtle_2']['levels'][9]['spData']['spCost']
    with pytest.raises(tool.NormalizationError,match='SP field missing'):
        tool.normalize_operator(roster['roster'][0],characters['char_151_myrtle'],changed)


def test_committed_normalization_matches_complete_source_rebuild():
    assert tool.read_json(tool.OUTPUT)==tool.build()


def test_cache_sha_mismatch_is_fatal_without_network(tmp_path,monkeypatch,inputs):
    _,_,lock,_=inputs
    bad_cache=tmp_path/'cache';bad_cache.mkdir()
    (bad_cache/'character_table.json').write_text('{}',encoding='utf8')
    monkeypatch.setattr(tool,'CACHE',bad_cache)
    with pytest.raises(tool.NormalizationError):
        tool.load_sources()
