"""Real stage scheduling/control counts stay intact under strict conversion."""
import json
from pathlib import Path
import pytest
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m38_integrated_candidate'))
from tools.build_reference_stage_scenario import compose


def source():return json.loads((ROOT/'packages/campaign/native_reference/level_main_02-09.json').read_bytes())
def bindings():
    p=json.loads((ROOT/'packages/campaign/chapter02_units/main_02-09.enemy_binding.plan.json').read_bytes())
    return {r['native_reference']['id']:{'unit':r['unit_definition'],'motion':r['native_motion']} for r in p['five_variant_bindings']}
def profiles():return {key:{'type':'occupancy_buff_field','definition':'unit/probe_'+key,'expected_blackboard':board}
    for key,board in [('tile_hole',{}),('tile_gazebo',{'atk_scale':1.7,'attack_speed':-20.0})]}


def test_actual52_spawns_and7_info_repeats_preserved_without_flattening():
    raw=source();s,c=compose(raw,'level_main_02-09',bindings(),profiles())
    actions=[a for w in s['timeline']['waves'] for f in w['fragments'] for a in f['actions']]
    assert sum(a['count'] for a in actions if a['kind']=='spawn')==52
    assert sum(a['count'] for a in actions if a['kind']=='control')==7 and len(c)==2
    assert len(s['timeline']['waves'][0]['fragments'])==len(raw['waves'][0]['fragments'])
    assert all(a['metadata']['native_action']['managedByScheduler']==a['managed'] for a in actions)
    assert s['resources']['life']['initial']==3 and s['seed']==raw['randomSeed']
    # Diagnostic converter fixture only: missing definitions mean this input
    # cannot compile or claim a hole implementation. Production uses M41.


def test_missing_required_map_mechanic_or_enemy_rejects():
    with pytest.raises(ValueError,match='map mechanics'):compose(source(),'level_main_02-09',bindings(),{})
    b=bindings();b.pop('enemy_1013_airdrp')
    with pytest.raises(ValueError,match='Unbound'):compose(source(),'level_main_02-09',b,profiles())


def test_unknown_action_and_active_rune_are_not_silently_dropped():
    d=source();d['waves'][0]['fragments'][0]['actions'][0]['actionType']='unknown_critical_control'
    with pytest.raises(ValueError,match='Unconverted'):compose(d,'level_main_02-09',bindings(),profiles())
    d=source();d['runes'][0]['difficultyMask']='NORMAL'
    with pytest.raises(ValueError,match='Active native rune'):compose(d,'level_main_02-09',bindings(),profiles())


def test_fake_mechanic_descriptor_rejected_by_actual_profile_validator():
    p=profiles();p['tile_hole']={'type':'unimplemented_marker'}
    with pytest.raises(ValueError,match='unsupported'):compose(source(),'level_main_02-09',bindings(),p)
