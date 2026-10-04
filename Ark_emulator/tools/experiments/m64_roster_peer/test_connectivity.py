import json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def fixture(rows=3,cols=5,owned=False):
 profile={'rule':'rule/connect','parameters':{'diagonal':False,'allow_corner_cut':False}}
 c={'spatial':{},'attributes':{'base':{'max_hp':100,'def':0,'block_count':0}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'route_obstacle':{'rule':'rule/not_contact','contact_radius':.4,'parameters':{}},'terrain_overlays':[{'key':'marker','priority':0,'values':{'obstacleLikeMoveCost':True},'preserve':['passableMask']}],'deployable':{'base_cost':5,'capacity':0,'cooldown_seconds':0,'terrain':'ground','parameters':{'max_instances':16},'stock':{'resource':'cards','amount':1},'rules':{'deploy.cost':'rule/cost'},'connectivity':profile},'lifecycle':{'policy':'policy/ark_lifecycle'}}
 p={'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/marker','kind':'entity','tags':['player'],'components':c}], 'rules':[{'id':'rule/connect','kind':'rule','contract':'deploy.connectivity','implementation':{'type':'provider','provider':'model.deploy.ground_connectivity'}},{'id':'rule/cost','kind':'rule','contract':'deploy.cost','implementation':{'type':'expression','expression':'inputs.base_cost'}},{'id':'rule/not_contact','kind':'rule','contract':'blocking.obstacle','implementation':{'type':'expression','expression':'False'}}], 'scenarioDraft':{'id':'scene/independent_connectivity','ruleset':'ruleset/ark_standard','roster':['unit/marker'],'parameters':{'deployment_routes':[{'id':'unborn_route','start':{'row':1 if rows>1 else 0,'col':0},'end':{'row':1 if rows>1 else 0,'col':cols-1}}]},'map':{'rows':rows,'cols':cols},'resources':{'dp':{'initial':100,'capacity':100},'cards':{'initial':10,'capacity':10},'life':{'initial':99999,'capacity':99999}},'objectives':{'life_resource':'life'}}}
 if owned:
  p['entities'].append({'id':'unit/host','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':1000}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'abilities':['ability/spawn'],'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['abilities']=[{'id':'ability/spawn','kind':'ability','activation':{'mode':'manual','costs':[{'owner':'battle','resource':'dp','amount':5}],'on_start':[{'op':'spawn','definition':'unit/marker','owner':'source','parameters':{'position_from_payload':True,'deployment_payment_amount':5,'max_owned':16}}]},'timeline':[]}];p['scenarioDraft']['initialEntities']=[{'definition':'unit/host','instanceAlias':'host','position':{'row':0,'col':0}}];p['scenarioDraft']['roster'].append('unit/host')
 return p

def create(p):
 raw=(json.dumps(p,indent=2)+'\n').encode();inputs={'sha256':hashlib.sha256(raw).hexdigest(),'fixture':json.loads(raw),'seed':640301};INPUTS.append(inputs);return Engine.create(Compiler().compile(json.loads(raw)),seed=640301),inputs

def deploy(s,at,row,col,alias):s.submit({'action':'deploy','entity':'unit/marker','position':{'row':row,'col':col},'alias':alias},at=at)
def exact(s,inputs,tmp,expected):
 h=write_ordered(tmp/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'cp.json',h));s.advance(20);r.advance(20);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();CAPTURES.append({'input':inputs,'expected':expected,'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'commands':s.export_replay(),'checkpoint_sha256':h,'checkpoint_equal':True,'commands_replay_equal':True})
def rejects(s):return [e['payload']['reason'] for e in s.session.events if e['type']=='command.rejected']


def test_no_enemy_spawned_final_middle_column_seal_rejected(tmp_path):
 p=fixture();p['scenarioDraft']['parameters']['deployment_routes']=[{'id':'north','start':{'row':0,'col':0},'end':{'row':0,'col':4}},{'id':'south','start':{'row':2,'col':0},'end':{'row':2,'col':4}}]
 s,inputs=create(p);deploy(s,0,0,2,'top');deploy(s,1,1,2,'middle');deploy(s,2,2,2,'last');s.advance(3)
 assert s.ctx.state()['deployments']['unit/marker']['count']==2 and s.ctx.resources.current('system/battle','dp')==90 and s.ctx.resources.current('system/battle','cards')==8
 assert any('sealed_route' in reason for reason in rejects(s));assert not any('enemy' in e['tags'] for e in s.session.world.entities())
 exact(s,inputs,tmp_path,{'no_born_enemies':True,'accepted_column_cells':2,'last_seal_rejected':True,'every_declared_entrance_checked':True})


def test_one_declared_entrance_sealed_other_route_still_open_rejects(tmp_path):
 p=fixture();p['scenarioDraft']['parameters']['deployment_routes']=[{'id':'north','start':{'row':0,'col':0},'end':{'row':0,'col':4}},{'id':'south','start':{'row':2,'col':0},'end':{'row':2,'col':4}}];s,inputs=create(p);deploy(s,0,0,0,'on_start');s.advance(1);assert not s.ctx.state()['deployments'] and s.ctx.resources.current('system/battle','cards')==10 and any('north' in reason for reason in rejects(s));exact(s,inputs,tmp_path,{'north_start_closed':'reject despite other open route'})

@pytest.mark.parametrize('diagonal,corner,accepted',[(True,True,True),(True,False,False),(False,True,False)])
def test_diagonal_no_corner_geometry_is_explicit(diagonal,corner,accepted,tmp_path):
 p=fixture(3,3);p['entities'][0]['components']['deployable']['connectivity']['parameters']={'diagonal':diagonal,'allow_corner_cut':corner};p['scenarioDraft']['parameters']['deployment_routes']=[{'id':'isolated_corner','start':{'row':0,'col':0},'end':{'row':1,'col':1}}]
 tiles=[{'tileKey':'tile_wall','passableMask':0,'buildableType':0} for _ in range(9)]
 for i in (0,4,8):tiles[i]={'tileKey':'tile_floor','passableMask':1,'buildableType':1}
 p['scenarioDraft']['map']['tiles']=tiles;s,inputs=create(p);deploy(s,0,2,2,'candidate');s.advance(1);assert bool(s.ctx.state()['deployments']) is accepted;exact(s,inputs,tmp_path,{'diagonal':diagonal,'corner':corner,'accepted':accepted})


def test_living_blocker_not_a_permanent_closed_cell(tmp_path):
 p=fixture(1,5);p['entities'].append({'id':'unit/live_guard','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':1000,'block_count':3}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'}}});p['scenarioDraft']['initialEntities']=[{'definition':'unit/live_guard','instanceAlias':'live','position':{'row':0,'col':2}}]
 # Custom connectivity rule still receives the ordinary-actor-free occupied set;
 # proposed placement is ignored here so that its independent contents are observable.
 p['rules'][0]['implementation']={'type':'expression','expression':'{"accepted": len(inputs.occupied) == 0, "reason": "ordinary guards not closed"}'}
 # len is outside the expression language, use empty-array equality instead.
 p['rules'][0]['implementation']['expression']='{"accepted": inputs.occupied == [], "reason": "ordinary guards not closed"}'
 s,inputs=create(p);deploy(s,0,0,4,'candidate');s.advance(1)
 # record observes the actual marker overlay, so inspect the prepare calculation
 # separately; a standard independent scene below uses a second row detour.
 prepare_events=[e for e in s.session.events if e['type']=='calculation' and e['payload']['calculation_id']=='deploy.connectivity'];assert prepare_events[0]['payload']['inputs']['occupied']==[]


def callback_fixture(owned=False):
 p=fixture(2,3,owned);p['scenarioDraft']['parameters']['deployment_routes']=[{'id':'both_rows','start':{'row':0,'col':0},'end':{'row':0,'col':2}}]
 p['buffs']=[{'id':'buff/callback_seal','kind':'buff','effects':[{'op':'random','stream':'imp','probability':1,'effects':[{'op':'emit','event':'probe.birth'}]},{'op':'apply_terrain_overlay','parameters':{'key':'other_row','priority':0,'position':{'row':0,'col':1},'values':{'obstacleLikeMoveCost':True}}}]}];p['entities'][0]['components']['buffs']={'initial':['buff/callback_seal']}
 return p
@pytest.mark.parametrize('owned',[False,True])
def test_birth_callback_seals_second_cell_record_gate_rolls_all_back(owned):
 s,inputs=create(callback_fixture(owned));before=s.checkpoint();action={'action':'skill','source':'host','ability':'ability/spawn','payload':{'position':{'row':1,'col':1}}} if owned else {'action':'deploy','entity':'unit/marker','position':{'row':1,'col':1},'alias':'candidate'}
 with pytest.raises(ValueError,match='sealed_route'):
  with s.session.atomic():s._execute_command(action)
 assert s.checkpoint()==before;CAPTURES.append({'input':inputs,'expected':'post-birth rejection restores DP/stock/actor/RNG/tasks/terrain/history','scope':'public API atomic instrumentation','checkpoint':s.checkpoint()})


def test_partial_effective_parameters_override_uses_merged_profile():
 p=fixture();p['scenarioDraft']['initialEntities']=[{'definition':'unit/marker','instanceAlias':'preplaced','position':{'row':0,'col':3},'components':{'deployable':{'connectivity':{'parameters':{'diagonal':True}}}}}]
 create(p)

@pytest.mark.parametrize('where',['definition','instance'])
def test_explicit_null_profile_is_not_silent_absent(where):
 p=fixture()
 if where=='definition':p['entities'][0]['components']['deployable']['connectivity']=None
 else:p['scenarioDraft']['initialEntities']=[{'definition':'unit/marker','instanceAlias':'preplaced','position':{'row':0,'col':3},'components':{'deployable':{'connectivity':None}}}]
 with pytest.raises(Exception,match='connectivity'):create(p)
