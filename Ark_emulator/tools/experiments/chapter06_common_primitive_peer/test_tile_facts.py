from copy import deepcopy
from ark_sim import Compiler,Engine
from ark_sim.domains.tile_targets import query
INPUTS=[];CAPTURES=[]
def package():
 entities=[];initial=[]
 for i,side,mask in [(0,1,2),(1,0,1),(2,0,5),(3,1,1),(4,0,4)]:
  id='unit/peer/fact'+str(i);entities.append({'id':id,'kind':'entity','components':{'selection_state':{'side':side,'unit_type':mask,'motion':1,'category':1},'spatial':{}}});initial.append({'definition':id,'instanceAlias':'actor'+str(i),'position':{'row':0,'col':i}})
 return {'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'entities':entities,'scenarioDraft':{'id':'scene/peer/facts','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':5},'objectives':{},'initialEntities':initial}}
def test_pure_actual_side_bit_facts_include_maskfive_and_keep_enemy_character_token():
 p=package();INPUTS.append(deepcopy(p));s=Engine.create(Compiler().compile(p));spec={'eligibility_expression':'[params.side,params.bit] not in inputs.occupied_side_unit_type_bits','parameters':{'side':0,'bit':1},'limit':5,'selection':'uniform_without_replacement','stream':'peer/tile'};before=s.checkpoint();cells=query(s.ctx,'actor0',spec);assert cells==[{'row':0,'col':0},{'row':0,'col':3},{'row':0,'col':4}] and s.checkpoint()==before
 CAPTURES.append({'input':p,'spec':spec,'cells':cells,'checkpoint':s.checkpoint()})
def test_projection_carries_all_actual_states_and_strict_bit_pair_not_deployable_inference():
 p=package();INPUTS.append(deepcopy(p));s=Engine.create(Compiler().compile(p));spec={'eligibility_expression':'inputs.occupant_selection_states[0].unit_type == params.mask','parameters':{'mask':5},'limit':5,'selection':'row_major','stream':None};before=s.checkpoint();assert query(s.ctx,'actor0',spec)==[{'row':0,'col':2}] and s.checkpoint()==before
 CAPTURES.append({'input':p,'spec':spec,'checkpoint':s.checkpoint()})
