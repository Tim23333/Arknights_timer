from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.tile_targets import query
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def fixture(limit=2,expression='inputs.tile.buildableType == 1'):
 source={'id':'unit/peer/source','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':150,'atk':0}},'resources':{'hp':{'initial':150,'capacity':150,'role':'health'},'sp':{'initial':5,'capacity':5}},'abilities':['ability/peer/seal'],'lifecycle':{'policy':'policy/ark_lifecycle'},'spatial':{}}}
 hero={'id':'unit/peer/hero','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':100,'atk':0,'block_count':0}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'abilities':[],'lifecycle':{'policy':'policy/ark_lifecycle'},'deployable':{'base_cost':0,'cooldown_seconds':0,'terrain':'ground','parameters':{'max_instances':3}},'spatial':{}}}
 token={'id':'unit/peer/token','kind':'entity','tags':['neutral_token'],'components':{'tile_occupancy':{'blocks_deployment':True,'exclusive':True,'targetable':False,'withdrawable':False},'spatial':{}}}
 selector={'eligibility_expression':expression,'parameters':{},'limit':limit,'selection':'row_major','stream':None}
 effect={'op':'spawn_on_tiles','definition':token['id'],'parameters':{'cells':'captured','recheck':False,'occupant_expression':"'player' in inputs.candidate.tags",'occupant_parameters':{},'instant_kill':{'cause':'independent_tile_probe','skip_rebirth':False},'on_owner_retire':'retain'}}
 ability={'id':'ability/peer/seal','kind':'ability','tile_selector':selector,'activation':{'mode':'manual','costs':[{'resource':'sp','amount':1}],'parameters':{'requires_targets':True}},'timeline':[{'at':7,'effect':effect}]}
 return {'manifest':{'requires':['preset/ark_standard']},'definitions':[source,hero,token,ability],'scenarioDraft':{'id':'scene/peer/tiles','ruleset':'ruleset/ark_standard','roster':[hero['id']],'map':{'rows':1,'cols':4,'tiles':[{'buildableType':0,'passableMask':1}]+[{'buildableType':1,'passableMask':1} for _ in range(3)]},'resources':{'life':{'initial':99999,'capacity':99999},'dp':{'initial':25,'capacity':99}},'objectives':{'life_resource':'life'},'initialEntities':[{'definition':source['id'],'instanceAlias':'source','position':{'row':0,'col':0}},{'definition':hero['id'],'instanceAlias':'hero','position':{'row':0,'col':1}}]}}
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=9707)
def capture(s,label):CAPTURES.append({'case':label,'commands':s.export_replay(),'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot()})
def test_public_limit0_requires_targets_rejects_before_cost_cast_or_selection():
 s=make(fixture(0));s.submit({'action':'skill','source':'source','ability':'ability/peer/seal'},at=0);s.advance(1);capture(s,'limit0_requires_targets')
 assert s.ctx.resources.current('source','sp')==5
 assert not [e for e in s.session.events if e['type'] in ['ability.started','tile.selection']]
 assert any(e['type']=='command.rejected' for e in s.session.events)
def test_forged_tile_cast_without_active_owner_cannot_kill_or_spawn():
 s=make(fixture());ability=s.program.definitions['ability/peer/seal'];before=s.checkpoint();rejected=False
 try:s.ctx.effects.execute('source',[],ability['timeline'][0]['effect'],ability=ability,cast={'id':'cast/2/999','ability':ability['id'],'tile_targets':[{'row':0,'col':1}]})
 except ValueError:rejected=True
 capture(s,'forged_cast');assert rejected and s.checkpoint()==before
def test_expired_tile_cast_cannot_borrow_new_cells_and_spawn():
 s=make(fixture(1));s.ctx.abilities.start('source','ability/peer/seal');cast=deepcopy(next(iter(s.ctx.get('source',('runtime','casts')).values())));s.advance(8)
 assert not s.ctx.get('source',('runtime','casts'));cast['tile_targets']=[{'row':0,'col':3}];ability=s.program.definitions['ability/peer/seal'];before=s.checkpoint();rejected=False
 try:s.ctx.effects.execute('source',[],ability['timeline'][0]['effect'],ability=ability,cast=cast)
 except ValueError:rejected=True
 capture(s,'expired_cast');assert rejected and s.checkpoint()==before
def test_empty_candidate_pool_and_numeric_expression_reject_without_cost_or_rng():
 for expression in ['False','1']:
  s=make(fixture(2,expression));before=s.checkpoint()
  with pytest.raises(ValueError):s.ctx.abilities.start('source','ability/peer/seal')
  assert s.checkpoint()==before;capture(s,'query_empty_or_nonbool_'+expression)
def test_pure_query_public_source_withdraw_interrupts_captured_tiles_and_replays(tmp_path):
 s=make(fixture());ability=s.program.definitions['ability/peer/seal'];before=s.checkpoint();cells=query(s.ctx,'source',ability['tile_selector']);assert cells==[{'row':0,'col':i} for i in [1,2,3]] and s.checkpoint()==before
 s.submit({'action':'skill','source':'source','ability':'ability/peer/seal'},at=0);s.submit({'action':'withdraw','source':'source'},at=5);s.advance(3);pin=write_ordered(tmp_path/'cast.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cast.json',pin));s.advance(6);r.advance(6)
 assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot();capture(s,'withdraw_before_tiles')
 assert not any(e['definition_id']=='unit/peer/token' for e in s.session.world.entities()) and s.ctx.alive('hero')
 assert s.ctx.resources.current('system/battle','dp')==25 and s.ctx.resources.current('source','sp')==4
def test_live_cell_occupancy_does_not_change_passability_or_cost_stock_and_tokens_are_unselectable(tmp_path):
 s=make(fixture());s.submit({'action':'skill','source':'source','ability':'ability/peer/seal'},at=0);s.advance(8);pin=write_ordered(tmp_path/'spawn.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'spawn.json',pin));s.advance(2);r.advance(2)
 assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot();capture(s,'no_terrain_or_cost')
 tokens=[e for e in s.session.world.entities() if e['definition_id']=='unit/peer/token'];assert len(tokens)==2
 assert all(not s.ctx.selectable(t['id']) and not s.ctx.effect_target_available(t['id']) for t in tokens)
 assert all(s.ctx.spatial.grid.passable(0,i) and s.ctx.spatial.grid.tile(0,i)['buildableType']==1 for i in [1,2])
 assert s.ctx.resources.current('system/battle','dp')==25
@pytest.mark.parametrize('value',[True,False,1,None])
def test_effective_occupancy_override_malformed_flags_reject_before_actor_creation(value):
 s=make(fixture());before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.lifecycle.create('unit/peer/token',{'row':0,'col':3},component_overrides={'tile_occupancy':{'targetable':value,'exclusive':'yes'}})
 assert s.checkpoint()==before
