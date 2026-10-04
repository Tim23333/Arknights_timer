import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m34_effective_static_field_candidate';sys.path.insert(0,str(RUNTIME))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from static_overrides_m34 import scene
CORE='937983fdab0a7e897f16f139a75f9d4c985a3049c026ec44682c4351c9da1c3e'
def make(p):
 assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';return Engine.create(Compiler().compile(p),seed=3401)
def cp(s):
 r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
@pytest.mark.parametrize('placement',['wave','timeline'])
@pytest.mark.parametrize('override',[{'abilities':['ability/illegal_owner']},{'spatial':{'route':{'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':3},'checkpoints':[]}}}])
def test_effective_wave_and_timeline_static_rejected(placement,override):
 p=scene();entry={'definition':'unit/owner','position':{'row':0,'col':0},'components':override}
 if placement=='wave':p['scenarioDraft']['waves']=[entry]
 else:p['scenarioDraft']['timeline']={'policy':'time_only','negative_timeout_policy':'skip_wait','waves':[{'pre_delay_seconds':0,'post_delay_seconds':0,'max_wait_seconds':0,'fragments':[{'pre_delay_seconds':0,'actions':[{'kind':'spawn','delay_seconds':0,'count':1,'interval_seconds':0,'managed':False,'blocks_wave':False,'blocks_fragment':False,'spawn':entry}]}]}]}
 with pytest.raises(ValueError,match='static tile field'):Compiler().compile(p)
@pytest.mark.parametrize('change',[{'tags':['player']},{'tags':[]},{'parameters':{'owner':'target'}},{'route':{'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':3},'checkpoints':[]}}])
def test_initial_role_route_owner_parameters_rejected(change):
 p=scene();p['scenarioDraft']['initialEntities'].append({'definition':'unit/owner','position':{'row':0,'col':0},**change})
 with pytest.raises(ValueError):Compiler().compile(p)
def test_actual_lifecycle_caller_override_and_owner_reject_atomic():
 s=make(scene());before=s.checkpoint()
 for kwargs in [{'component_overrides':{'abilities':['ability/illegal_owner']}},{'route':{'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':3},'checkpoints':[]}},{'tags':['player']},{'owner':'target'}]:
  with pytest.raises(ValueError):s.ctx.lifecycle.create('unit/owner',{'row':0,'col':0},**kwargs)
  assert s.checkpoint()==before

def regen_scene(ttl=None):
 p=scene();p['entities'][1]['components']['attributes']['base']['regen']=0;p['entities'][1]['components']['resources']['hp'].update(initial=40,recovery_rule='rule/regen',recovery={'mode':'continuous'});p['rules']=[{'id':'rule/regen','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.current + inputs.delta_seconds * inputs.attributes.regen'}}];p['buffs'][1]['modifiers']=[{'attribute':'regen','layer':'flat','value':10}]
 if ttl is not None:p['buffs'][0]['duration_seconds']=ttl
 p['entities'][1]['components']['abilities']=['ability/in','ability/out'];p['abilities']+=[{'id':'ability/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':col}}]},'timeline':[]} for name,col in [('in',1),('out',2)]];return p

def test_public_entry_exit_exact_healing_and_owner_isolation():
 s=make(regen_scene());owner=s.ctx.state()['tile_fields']['0:1']['owner'];s.submit({'action':'skill','source':'target','ability':'ability/in'},at=3);s.submit({'action':'skill','source':'target','ability':'ability/out'},at=33);s.advance(35);assert s.ctx.resources.current('target','hp')==pytest.approx(50);assert s.ctx.get(owner,('buffs','instances'))[0]['aura_members']=={};assert s.ctx.get(owner,('spatial','position'))=={'row':0,'col':1};cp(s)
def test_halfopen_parent_lifetime_removes_child_but_keeps_static_owner():
 s=make(regen_scene(.2));owner=s.ctx.state()['tile_fields']['0:1']['owner'];s.submit({'action':'skill','source':'target','ability':'ability/in'},at=3);s.advance(7);assert s.ctx.resources.current('target','hp')==pytest.approx(41);assert s.ctx.get('target',('buffs','instances'),[])==[];assert s.ctx.alive(owner) and s.ctx.get(owner,('spatial','position'))=={'row':0,'col':1};cp(s)
def test_cell_owners_have_independent_membership():
 p=regen_scene();p['scenarioDraft']['map']['tiles'][2]=deepcopy(p['scenarioDraft']['map']['tiles'][1]);s=make(p);fields=s.ctx.state()['tile_fields'];assert fields['0:1']['owner']!=fields['0:2']['owner'];s.advance(3);assert s.ctx.resources.current('target','hp')==pytest.approx(41);assert not s.ctx.get(fields['0:1']['owner'],('buffs','instances'))[0]['aura_members'];cp(s)
@pytest.mark.parametrize('change',[lambda p:p['scenarioDraft']['map']['tiles'][1].update(blackboard=[{'key':'x','value':True}]),lambda p:p['scenarioDraft']['map']['tiles'][1].update(blackboard=[{'key':'x','value':1},{'key':'x','value':1}]),lambda p:p['scenarioDraft']['map']['tiles'][1].update(blackboard=[{'key':'x','value':1,'valueStr':'text'}]),lambda p:p['scenarioDraft']['map']['tile_mechanics']['custom_field'].update(definition='ability/illegal_owner')])
def test_blackboard_mismatch_duplicate_string_wrong_ref_rejected(change):
 p=scene();change(p)
 with pytest.raises(ValueError):Compiler().compile(p)
def test_reference_like_board_keys_are_data_and_owner_not_area_member():
 p=scene();p['scenarioDraft']['map']['tile_mechanics']['custom_field']['expected_blackboard']={'provider':1,'rule':2};p['scenarioDraft']['map']['tiles'][1]['blackboard']={'provider':1,'rule':2};p['entities'][1]['components']['abilities']=['ability/area'];p['abilities'].append({'id':'ability/area','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'area','center':'source','radius':4,'effects':[{'op':'damage','damage_type':'true'}]}]},'timeline':[]});s=make(p);owner=s.ctx.state()['tile_fields']['0:1']['owner'];assert not s.ctx.selectable(owner);s.submit({'action':'skill','source':'target','ability':'ability/area'},at=0);s.advance(1);assert all(owner not in e['payload']['members'] for e in s.session.events if e['type']=='area.resolved');assert s.ctx.resources.current(owner,'hp')==1;cp(s)

def test_list_reference_keys_and_area_isolation_have_actual_consumer():
 p=scene();p['scenarioDraft']['map']['tile_mechanics']['custom_field']['expected_blackboard']={'provider':1,'rule':2};p['scenarioDraft']['map']['tiles'][1]['blackboard']=[{'key':'provider','value':1},{'key':'rule','value':2}];p['entities'][1]['components']['attributes']['base']['atk']=10;p['entities'][1]['components']['abilities']=['ability/area'];p['abilities'].append({'id':'ability/area','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'area','center':'source','radius':4,'effects':[{'op':'damage','damage_type':'true'}]}]},'timeline':[]});s=make(p);owner=s.ctx.state()['tile_fields']['0:1']['owner'];s.submit({'action':'skill','source':'target','ability':'ability/area'},at=0);s.advance(1);areas=[e for e in s.session.events if e['type']=='area.resolved'];assert len(areas)==1 and list(areas[0]['payload']['members'])==[s.session.world.resolve('target')];assert s.ctx.resources.current(owner,'hp')==1 and s.ctx.resources.current('target','hp')==90;cp(s)
def test_public_direct_field_ability_is_rejected_by_definition_role():
 p=scene();p['entities'][0]['dependencies']=['ability/illegal_owner'];s=make(p);owner=s.ctx.state()['tile_fields']['0:1']['owner'];before=s.checkpoint()
 with pytest.raises(ValueError,match='Static tile field'):s.ctx.abilities.start(owner,'ability/illegal_owner')
 assert s.checkpoint()==before
