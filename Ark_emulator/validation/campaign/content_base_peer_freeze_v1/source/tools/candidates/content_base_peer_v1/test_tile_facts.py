"""Independent source/state classifications: no deployment or ID guesses."""
import json,sys
from copy import deepcopy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_content_base_v1_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.domains.tile_targets import query
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/content_base_tile_peer_v1'
def spec(expr):return {'eligibility_expression':expr,'parameters':{},'limit':99,'selection':'uniform_without_replacement','stream':'peer/never_drawn_in_query'}
def package():
 rows=[('source',1,2,0,0),('player_char',0,1,0,1),('player_token',0,4,0,2),('enemy_char',1,1,1,0),('enemy_token',1,4,1,1),('player_compound',0,5,1,2)];entities=[];initial=[]
 for name,side,unit_type,row,col in rows:
  entities.append({'id':'unit/peer/'+name,'kind':'entity','tags':['peer_occupant'],'components':{'attributes':{'base':{}},'selection_state':{'side':side,'unit_type':unit_type},'spatial':{}}});initial.append({'definition':'unit/peer/'+name,'instanceAlias':name,'position':{'row':row,'col':col}})
 return {'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'entities':entities,'scenarioDraft':{'id':'scene/peer/typed_tiles','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':3},'objectives':{},'initialEntities':initial}}
def test_query_side0_character_bit_excludes_non_deployable_and_compound5_only():
 s=Engine.create(Compiler().compile(package()));before=s.checkpoint();assert query(s.ctx,'source',spec('[0,1] not in inputs.occupied_side_unit_type_bits'))==[{'row':0,'col':0},{'row':0,'col':2},{'row':1,'col':0},{'row':1,'col':1}];assert s.checkpoint()==before
def test_enemy_side_character_and_tokens_are_preserved_no_deployable_heuristic():
 s=Engine.create(Compiler().compile(package()));before=s.checkpoint();assert query(s.ctx,'source',spec('[1,1] in inputs.occupied_side_unit_type_bits'))==[{'row':1,'col':0}];assert query(s.ctx,'source',spec('[0,4] in inputs.occupied_side_unit_type_bits'))==[{'row':0,'col':2},{'row':1,'col':2}];assert query(s.ctx,'source',spec('[1,4] in inputs.occupied_side_unit_type_bits'))==[{'row':1,'col':1}];assert s.checkpoint()==before
def test_zero_unit_type_does_not_fabricate_character_bit():
 p=package();p['entities'][1]['components']['selection_state']['unit_type']=0;s=Engine.create(Compiler().compile(p));assert {'row':0,'col':1} in query(s.ctx,'source',spec('[0,1] not in inputs.occupied_side_unit_type_bits'))
@pytest.mark.parametrize('field,value',[('unit_type',True),('side',True),('unit_type',8),('unit_type',-1)])
def test_typed_projection_rejects_bad_state_no_query_writes(field,value):
 s=Engine.create(Compiler().compile(package()));s.ctx.set('player_char',('selection_state',field),value);before=s.checkpoint()
 with pytest.raises(ValueError):query(s.ctx,'source',spec('True'))
 assert s.checkpoint()==before
def test_query_strict_bool_result_and_not_rng_sampling():
 s=Engine.create(Compiler().compile(package()));before=s.checkpoint()
 with pytest.raises(ValueError):query(s.ctx,'source',spec('1'))
 assert s.checkpoint()==before
def test_query_own_CP_head_projection_values_without_mutation():
 p=package();program=Compiler().compile(p);s=Engine.create(program);s.session.advance(5);OUT.mkdir(parents=True,exist_ok=True);cp=OUT/'actual5.cp.json';assert not cp.exists();h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.session.advance(6);r.session.advance(6);head=replay(program,s.export_replay());assert s.snapshot()==r.snapshot()==head.snapshot();before=s.checkpoint();expr=spec('[0,1] not in inputs.occupied_side_unit_type_bits');expected=[{'row':0,'col':0},{'row':0,'col':2},{'row':1,'col':0},{'row':1,'col':1}];assert query(s.ctx,'source',expr)==query(r.ctx,'source',expr)==query(head.ctx,'source',expr)==expected;assert s.checkpoint()==before;(OUT/'actual.json').write_text(json.dumps({'input':p,'cp_sha':h,'expected':expected,'snapshot':s.snapshot()},indent=2)+'\n',encoding='utf8',newline='')
