"""Independent mask/source binding negatives and actual ground/fly/build geometry."""
import json,sys,math
from copy import deepcopy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.content.compiler import CompileError
from ark_sim.domains.spatial import GridTopology
MODULE=ROOT/'packages/campaign/chapter06_environment_consumer/module.v2.reference.json'
def package():
 source=json.loads(MODULE.read_bytes());m=deepcopy(source['manifest']['metadata']['native_stages']['level_main_06-14']['converted_map']);return {'schemaVersion':2,'manifest':{'id':'package/static/source/tests','requires':['preset/ark_standard']},'scenarioDraft':{'id':'scene/static/source/tests','ruleset':'ruleset/ark_standard','map':m,'objectives':{}}}
def test_actual_fence_three_source_cells_ground_block_fly_allow_and_melee_build():
 p=package();s=Engine.create(Compiler().compile(p));grid=s.ctx.spatial.grid;assert grid.tile(1,2)['passableMask']==2 and grid.tile(1,2)['buildableType']==1;assert not grid.passable(1,2);origin={'row':1,'col':1};target={'row':1,'col':2};stopped,blocked=grid.clip_segment(origin,target,motion_mode=0);assert blocked and stopped['col']==math.nextafter(1.5,-math.inf);flown,blocked=grid.clip_segment(origin,target,motion_mode=1);assert not blocked and flown==target
@pytest.mark.parametrize('field,value',[('passableMask',3),('buildableType',0),('heightType','HIGHLAND'),('blackboard',[{'key':'damage','value':1}]),('effects',[{'key':'unknown'}])])
def test_changed_source_operand_not_silently_accepted(field,value):
 p=package();p['scenarioDraft']['map']['tiles'][14][field]=value
 with pytest.raises(CompileError):Compiler().compile(p)
def test_unknown_name_and_nonempty_profile_data_still_rejected():
 p=package();p['scenarioDraft']['map']['tiles'][14]['tileKey']='unknown_source_tile'
 with pytest.raises(CompileError):Compiler().compile(p)
 p=package();p['scenarioDraft']['map']['tile_mechanics']['tile_fence']['expected_effects']=[{'not_empty':1}]
 with pytest.raises(CompileError):Compiler().compile(p)
def test_runtime_grid_source_masks_checked_without_compiler():
 p=package()['scenarioDraft']['map'];p['tiles'][14]['passableMask']=3
 with pytest.raises(ValueError):GridTopology(p)
