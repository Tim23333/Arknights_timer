"""Observation reads must not mutate model state or invent absent fields."""
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
sys.path.insert(0,str(RUNTIME))
from tools.experiments.m26.test_decisions import fixture,make
from tools.export_campaign_model_trace import read_field


def test_export_reads_actual_hp_position_and_rng_without_trace_or_state_change():
    s=make(fixture());s.advance(7);before=s.checkpoint()
    assert read_field(s,{'kind':'resource','entity':'target','resource':'hp'})==80
    assert read_field(s,{'kind':'entity_component','entity':'enemy','path':['spatial','position','col']})==0
    rng=read_field(s,{'kind':'random_state'});assert rng==s.checkpoint()['kernel']['random']
    assert s.checkpoint()==before


def test_missing_component_or_unknown_observation_rejected():
    s=make(fixture());before=s.checkpoint()
    with pytest.raises(ValueError,match='absent'):read_field(s,{'kind':'entity_component','entity':'target','path':['spatial','does_not_exist']})
    with pytest.raises(ValueError,match='Unknown'):read_field(s,{'kind':'native_state'})
    assert s.checkpoint()==before
