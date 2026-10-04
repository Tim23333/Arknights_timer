"""Independent declared field/query/creation gates; known static flaws separate."""
import json,sys,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m31_tile_field_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.domains.lifecycle import LifecycleSystem
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[]
def fixture():
 p=json.loads((ROOT/'validation/campaign/m31_roster_peer/static_route.fixture.json').read_bytes());p['entities'][0]['components']['spatial']={};p['entities'][0]['components']['attributes']['base'].pop('move_speed');p['entities'][1]['components']['abilities']=['ability/out'];p['abilities']=[{'id':'ability/out','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':2}}]},'timeline':[]}];return p
def make(p,providers=None):
 raw=json.dumps(p,separators=(',',':')).encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'seed':3104,'document':json.loads(raw)});return Engine.create(Compiler(providers=providers).compile(json.loads(raw)),seed=3104,providers=providers)
def test_real_same_cell_member_leaves_and_disk_cp_replay(tmp_path):
 s=make(fixture());s.submit({'action':'skill','source':'target','ability':'ability/out'},at=15);s.advance(8);path=tmp_path/'ordered.json';fp=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,fp));s.advance(10);r.advance(10)
 assert s.ctx.resources.current('target','hp')==415 and s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_arbitrary_declared_circle_is_continuous_geometry_not_forced_grid():
 p=fixture();p['selectors'][0]['region']={'type':'radius','radius':.75};p['scenarioDraft']['initialEntities'][0]['position']['col']=1.6;s=make(p);s.advance(1)
 assert s.ctx.resources.current('target','hp')==401
 assert len(s.ctx.state()['tile_fields'])==1

@pytest.mark.parametrize('change',[lambda p:p['scenarioDraft']['map']['tiles'][1]['blackboard'].append({'key':'unbound','value':1}),lambda p:p['scenarioDraft']['map']['tiles'][1]['blackboard'].append({'key':'rate','value':.03}),lambda p:p['scenarioDraft']['map']['tiles'][1].update(effects=['unconsumed']),lambda p:p['scenarioDraft']['map']['tile_mechanics'].update(unused={'type':'occupancy_buff_field','definition':'ability/out','expected_blackboard':{}})])
def test_unknown_duplicate_effect_and_unused_bad_ref_failfast(change):
 p=fixture();change(p)
 with pytest.raises(ValueError):Compiler().compile(p)

def test_virtual_owner_not_all_query_target_and_data_key_not_ref():
 p=fixture();p['scenarioDraft']['map']['tile_mechanics']['independent_field']['expected_blackboard']={'definition':.03};p['scenarioDraft']['map']['tiles'][1]['blackboard'][0]['key']='definition'
 p['selectors'].append({'id':'selector/all','kind':'selector','region':{'type':'all'}});p['entities'][1]['dependencies']=['selector/all'];s=make(p);owner=s.ctx.state()['tile_fields']['0:1']['owner'];before=s.checkpoint()
 assert s.ctx.active(owner) and not s.ctx.selectable(owner) and not s.ctx.effect_target_available(owner)
 assert s.ctx.spatial.eligible('target','selector/all')==[s.session.world.resolve('target')];assert s.checkpoint()==before

def fail_second(inputs,parameters,context):
 if inputs['source']['components']['spatial']['position']['col']==2:raise ValueError('second field owner selector deliberately fails')
 return [row['id'] for row in inputs['candidates']]
fail_second.version='m31-peer-fail-second-v1'
def test_initialize_multi_cell_atomic_rolls_all_fields_back(monkeypatch):
 p=fixture();p['scenarioDraft']['map']['tiles'][2]=deepcopy(p['scenarioDraft']['map']['tiles'][1]);p['selectors'][0]['provider']='peer.fail_second';providers={**BUILTIN_PROVIDERS,'peer.fail_second':fail_second};seen=[];native=LifecycleSystem.create
 def spy(self,*args,**kwargs):seen.append(self.ctx);return native(self,*args,**kwargs)
 monkeypatch.setattr(LifecycleSystem,'create',spy)
 with pytest.raises(ValueError,match='deliberately fails'):make(p,providers)
 ctx=seen[-1];assert [e['definition_id'] for e in ctx.session.world.entities()]==['system/battle','unit/target']
 assert 'tile_fields' not in ctx.state() and ctx.get('target',('buffs','instances'))==[]
 assert not [e for e in ctx.session.events if e['type']=='entity.created' and e['payload'].get('definition')=='unit/static_field']

def test_portal_profiles_are_distinct_from_adjacent_field_owner_and_hidden_membership():
 p=fixture();m=p['scenarioDraft']['map'];m['tiles'][0]={'tileKey':'peer_entry','passableMask':1,'buildableType':0};m['tiles'][2]={'tileKey':'peer_exit','passableMask':1,'buildableType':0}
 m['tile_mechanics'].update(peer_entry={'type':'route_checkpoint_portal','role':'entry'},peer_exit={'type':'route_checkpoint_portal','role':'exit'})
 p['selectors'][0]['region']['offsets']=[[0,-1]];actor=p['scenarioDraft']['initialEntities'][0];actor['position']['col']=0;p['entities'][1]['components']['attributes']['base']['move_speed']=3
 p['rules'].append({'id':'rule/peer_transition','kind':'rule','contract':'movement.transition','implementation':{'type':'provider','provider':'ark.movement.living_transition'}})
 actor['route']={'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':2},'transition_policy':{'rule':'rule/peer_transition','parameters':{'hidden_effects':'reject','hidden_auras':'suspend','launched_source_effects':'retain','resource_timers':'continue'}},'checkpoints':[{'type':5},{'type':1,'time':.1},{'type':6,'position':{'row':0,'col':2}}]}
 s=make(p);s.advance(1);assert s.ctx.route_hidden('target') and len(s.ctx.state()['tile_fields'])==1
 hp=s.ctx.resources.current('target','hp');assert hp==401
 r=Engine.restore(s.program,s.checkpoint());s.advance(3);r.advance(3)
 assert not s.ctx.route_hidden('target') and s.ctx.resources.current('target','hp')==401
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
