from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from ark_sim.domains.spatial import GridTopology,UnreachablePathError
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def fixture():
 tiles=[{'tileKey':'tile_floor','buildableType':1,'passableMask':1,'heightType':0,'blackboard':None,'effects':None} for i in range(6)]
 profiles={}
 for idx,key,mask,build in [(1,'tile/peer/arbitrary_fence_walk',1,1),(4,'tile/peer/arbitrary_road_blocked',2,0)]:
  tiles[idx]={'tileKey':key,'buildableType':build,'passableMask':mask,'heightType':0,'blackboard':[],'effects':{}}
  profiles[key]={'type':'declared_static_tile','expected_options':{'buildableType':build,'passableMask':mask,'heightType':0},'expected_blackboard':[],'expected_effects':{}}
 return {'schemaVersion':2,'manifest':{'id':'package/peer/staticjoint','requires':['preset/ark_standard']},'entities':[{'id':'unit/peer/hero','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':333,'block_count':1}},'resources':{'hp':{'initial':333,'capacity':333,'role':'health'}},'spatial':{},'deployable':{'base_cost':7,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'}}}], 'scenarioDraft':{'id':'scene/peer/staticjoint','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':2,'cols':3,'tiles':tiles,'tile_mechanics':profiles},'parameters':{'deploy_capacity':1},'resources':{'dp':{'initial':20,'capacity':20}},'roster':['unit/peer/hero']}}
def compile(p):INPUTS.append(deepcopy(p));return Compiler().compile(p)
def test_arbitrary_name_explicit_mask_and_build_public_deploy_disk_head(tmp_path):
 p=fixture();s=Engine.create(compile(p));grid=s.ctx.spatial.grid
 assert grid.passable(0,1) and not grid.passable(1,1)
 assert grid.path({'row':0,'col':0},{'row':0,'col':2})==[{'row':0,'col':1},{'row':0,'col':2}]
 s.submit({'action':'deploy','definition':'unit/peer/hero','alias':'actual','position':{'row':0,'col':1},'facing':'left'},at=2);s.advance(1)
 path=tmp_path/'static_predeploy.json';digest=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,digest));s.advance(5);r.advance(5);head=replay(s.program,s.export_replay())
 assert s.ctx.active('actual') and s.ctx.resources.current('battle','dp')==13
 assert s.checkpoint()==r.checkpoint()==head.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(head.session.events))
 CAPTURES.append({'input':p,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'checkpoint':s.checkpoint(),'snapshot':s.snapshot()})
@pytest.mark.parametrize('case',['bool_mask','float_mask','mismatched_mask','nonempty_board','nonempty_effects','missing_profile','unknown_profile','empty_data_type_mismatch'])
def test_invalid_source_profile_rejected_without_erasing_map(case):
 p=fixture();m=p['scenarioDraft']['map'];tile=m['tiles'][1];profile=m['tile_mechanics'][tile['tileKey']]
 if case=='bool_mask':tile['passableMask']=True
 elif case=='float_mask':tile['passableMask']=1.0
 elif case=='mismatched_mask':tile['passableMask']=3
 elif case=='nonempty_board':tile['blackboard']=[{'key':'unknown','value':1}];profile['expected_blackboard']=deepcopy(tile['blackboard'])
 elif case=='nonempty_effects':tile['effects']={'a':1};profile['expected_effects']={'a':1}
 elif case=='missing_profile':m['tile_mechanics'].clear()
 elif case=='unknown_profile':profile['type']='static_unimplemented'
 else:tile['blackboard']={}
 with pytest.raises(ValueError):compile(p)
