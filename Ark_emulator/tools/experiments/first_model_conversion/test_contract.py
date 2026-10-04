"""Negative source/contract cases; no campaign runner mutation or receipt."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools import build_first_model_conversion as b
from tools.validate_first_model_conversion import validate,validate_schema


@pytest.fixture(scope='module')
def inputs():return b.read(b.ROOT/'packages/campaign/native_reference/level_main_00-10.json'),b.read(b.INPUT)


def test_reproducible_draft_and_actual_gate_reject():
    assert validate()['status']=='structurally_valid_draft_still_blocked'
    from tools.campaign_progress import execution_gate,review_gate
    from ark_sim import Compiler
    case={'native_id':'main_00-10','level_id':'level_main_00-10','planned_content':b.relative(b.CONTENT),'planned_commands':b.relative(b.COMMAND_OUTPUT)}
    with pytest.raises(ValueError,match='pending native mechanics'):execution_gate(Compiler().compile(b.CONTENT),case,b.read(b.ROOT/'packages/campaign/roster.reference.json'))
    with pytest.raises(ValueError,match='independent conversion review receipt'):review_gate(case,b.read(b.ROOT/'packages/campaign/roster.reference.json'))


@pytest.mark.parametrize('mutation', ['unknown_option','active_option','map_effect','palette_mask','wave_population','random_action','route_offset','route_motion','control_key','enemy_level'])
def test_native_changes_are_not_silently_ignored(inputs,mutation):
    native,model=map(deepcopy,inputs)
    if mutation=='unknown_option':native['options']['newMathKnob']=1
    elif mutation=='active_option':native['options']['maxPlayTime']=10
    elif mutation=='map_effect':native['mapData']['effects']=[{'key':'active'}]
    elif mutation=='palette_mask':native['mapData']['tiles'][0]['playerSideMask']='PLAYER'
    elif mutation=='wave_population':native['waves'][0]['fragments'][1]['actions'][0]['count']+=1
    elif mutation=='random_action':native['waves'][0]['fragments'][1]['actions'][0]['randomType']='RANDOM'
    elif mutation=='route_offset':native['routes'][1]['checkpoints'][0]['reachOffset']['x']=.2
    elif mutation=='route_motion':native['routes'][1]['motionMode']='FLY'
    elif mutation=='control_key':native['waves'][0]['fragments'][0]['actions'][0]['key']='other_story'
    elif mutation=='enemy_level':native['enemyDbRefs'][0]['level']=1
    with pytest.raises(ValueError):b.stage_audit(native,model,b.ROOT/'packages/campaign/native_reference/level_main_00-10.json')


def test_every_stage_leaf_has_exact_source_pointer(inputs):
    native,model=inputs;path=b.ROOT/'packages/campaign/native_reference/level_main_00-10.json'
    rows=b.stage_audit(native,model,path)
    assert {x['native_pointer'] for x in rows}=={p for p,v in b.leaves(native)}
    assert all(x['source_sha256']==b.sha(path) and x['consumer'] and x['criterion'] for x in rows)


def test_schema_rejects_profile_and_self_approval():
    c=b.read(b.CONTENT)['scenarioDraft']['metadata']['campaign'];s=b.read(b.SCHEMA)
    for key,value in [('native_spawn_count',34),('formal_approval',True),('review_receipt',True)]:
        changed=deepcopy(c);changed[key]=value
        with pytest.raises(ValueError):validate_schema(changed,s)


def test_historical_pass_cannot_be_current_mechanism():
    old=b.load_evidence(b.ROOT/'validation/campaign/canonical_kalts_witness.m10_f6bb.json',b.INPUT_SHA)
    assert old['passed'] and not old['current_case_eligible']
