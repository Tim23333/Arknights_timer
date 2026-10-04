from copy import deepcopy
from pathlib import Path
import json
import pytest
from tools.campaign_runthrough_progress_v3 import validate_native_overlay
ROOT=Path(__file__).resolve().parents[1]


def fixture():
    package=json.loads((ROOT/'packages/campaign/runthrough/level_main_04-09.m96.v6.life99999.json').read_bytes())
    parent=json.loads((ROOT/'packages/campaign/chapter04_stage_models/level_main_04-09.m96.reference_model.json').read_bytes())
    commands=ROOT/'scenarios/campaign/chapter04/04-09/commands.public_v6.json'
    return package,parent,commands


def test_real_registered_overlay_keeps_entire_native_scene_and_definitions():
    p,parent,commands=fixture();profile=validate_native_overlay(p,parent,commands)
    assert profile['source_births']==49 and profile['deploy_capacity']==8 and len(profile['fixed12'])==12


@pytest.mark.parametrize('where',['HP','DP','slots','native_wave','profile_command_sha','provenance_life','roster'])
def test_other_data_or_provenance_change_never_accepted(where):
    p,parent,commands=fixture();scene=p['scenarioDraft']
    if where=='HP':
        unit=next(d for d in p['definitions'] if d['kind']=='entity' and 'max_hp' in d['components'].get('attributes',{}).get('base',{}))
        unit['components']['attributes']['base']['max_hp']+=1
    elif where=='DP':scene['resources']['dp']['initial']+=1
    elif where=='slots':scene['parameters']['deploy_capacity']+=1
    elif where=='native_wave':scene['timeline']['waves'][0]['fragments'][0]['actions'][0]['count']=99
    elif where=='profile_command_sha':scene['metadata']['runthrough_profile']['public_commands_sha256']='0'*64
    elif where=='provenance_life':p['manifest']['metadata']['goal_base_life_authoring']['native']['initial']+=1
    else:scene['metadata']['runthrough_profile']['fixed12'].reverse()
    with pytest.raises(ValueError):validate_native_overlay(p,parent,commands)
