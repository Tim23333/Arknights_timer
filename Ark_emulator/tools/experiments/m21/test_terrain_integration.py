"""Owned terrain executable witnesses; only this candidate is imported."""
import sys
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3]
CANDIDATE=ROOT.parent/'unpack_work/campaign_m21_integration_candidate'
sys.path.insert(0,str(CANDIDATE))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==CANDIDATE/'ark_sim'
sys.path.append(str(ROOT))
from tools.experiments.m15_peer import verify as h
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.terrain import validate_spec
from ark_sim.domains.spatial import GridTopology
from ark_sim.tools.replay import replay
h.PACKAGE=ROOT/'packages/campaign/chapter01_devices/emp.terrain.json'

def layer(key='patch',priority=0,**values):return {'key':key,'priority':priority,'values':values}
def effect(spec,target='source'):return {'op':'apply_terrain_overlay','target':target,'parameters':spec}
def fixture():
    p=h.generic_data();p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:1]
    c=p['entities'][0]['components'];c['resources']['sp']['initial']=5
    p['entities'].append({'id':'unit/card','kind':'entity','tags':['ally'],'components':{
        'spatial':{},'attributes':{'base':{'max_hp':10}},'resources':{'hp':{'initial':10,'capacity':10}},
        'lifecycle':{'policy':'policy/ark_lifecycle'},'deployable':{'base_cost':0,'cooldown_seconds':0,'terrain':'ground'}}})
    p['scenarioDraft']['roster']=['unit/card']
    return p
def add_skill(p,name,fx,unit='unit/chapter01_emp'):
    a='ability/terrain/'+name;next(e for e in p['entities'] if e['id']==unit)['components'].setdefault('abilities',[]).append(a)
    p['abilities'].append({'id':a,'kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':fx}]});return a
def roundtrip(s):
    r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_emp_birth_getter_pure_and_withdraw_restores():
    s=h.make(fixture());g=s.ctx.spatial.grid;before=s.checkpoint()
    for _ in range(3):
        t=g.tile(5,5);assert t['buildableType']==0 and t['passableMask']==1 and abs(t['physicalHeight']-.4)<1e-7 and t['movementCost']==3 and g.passable(5,5)
    assert before==s.checkpoint() # pure reads log/RNG/tasks/state unchanged
    s.submit({'action':'deploy','definition':'unit/card','position':{'row':5,'col':5}},at=0)
    s.submit({'action':'withdraw','source':'device'},at=1)
    s.submit({'action':'deploy','definition':'unit/card','position':{'row':5,'col':5},'alias':'card'},at=2)
    s.advance(3);assert s.ctx.alive('card') and g.tile(5,5)=={'tileKey':'tile_floor','passableMask':1,'buildableType':1}
    assert any(e['type']=='command.rejected' and e['payload']['reason']=='not_buildable' for e in s.session.events)
    assert s.ctx.get('system/battle',('state','terrain','layers'))=={};roundtrip(s)
def test_owned_overlap_priority_replace_and_remove_only_owner():
    p=fixture();p['entities'].append({'id':'unit/layer','kind':'entity','tags':['ally'],'components':{
       'spatial':{},'terrain_overlays':[layer('same',10,buildableType=2,physicalHeight=2)],'abilities':[]}})
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/layer','instanceAlias':'upper','position':{'row':5,'col':5}})
    a=add_skill(p,'replace',effect(layer('same',10,buildableType=3,physicalHeight=3)),'unit/layer')
    b=add_skill(p,'remove',{'op':'remove_terrain_overlay','parameters':{'key':'same'}},'unit/layer')
    s=h.make(p);assert s.ctx.spatial.grid.tile(5,5)['physicalHeight']==2
    h.command(s,'upper',a,0);h.command(s,'upper',b,1);s.advance(2)
    assert abs(s.ctx.spatial.grid.tile(5,5)['physicalHeight']-.4)<1e-7
    state=s.ctx.get('system/battle',('state','terrain'));assert len(state['layers'])==1 and state['next_id']==4
    roundtrip(s)
def test_weighted_path_real_cost_and_custom_rule():
    p=fixture();p['scenarioDraft']['map']={'rows':3,'cols':3}
    p['scenarioDraft']['initialEntities'][0]['position']={'row':1,'col':1}
    s=h.make(p);path=s.ctx.spatial.grid.path({'row':1,'col':0},{'row':1,'col':2})
    assert path==[{'row':0,'col':0},{'row':0,'col':1},{'row':0,'col':2},{'row':1,'col':2}] # equal cost4; heap(row,col) deterministic tie
    p['rules'].append({'id':'rule/terrain_cost','kind':'calculation_rule','extends':'rule/ark_terrain_tile_options','parameters':{'obstacle_like_cost':1}})
    p['entities'][0]['components']['terrain_overlays'][0]['rule']='rule/terrain_cost'
    s=h.make(p);path=s.ctx.spatial.grid.path({'row':1,'col':0},{'row':1,'col':2})
    assert path==[{'row':1,'col':1},{'row':1,'col':2}]
    assert s.ctx.spatial.grid.tile(1,1)['movementCost']==1
def test_atomic_effect_failure_layers_counter_cache_rng_jobs():
    s=h.make(fixture());before=s.checkpoint()
    fx=effect(layer('extra',4,passableMask=0));fx['effects']=[{'op':'random','stream':'imp','probability':.5,'on_success':[{'op':'emit','event':'probe'}]},
        {'op':'modify_resource','resource':'absent','delta':1}]
    with pytest.raises(ValueError):s.ctx.effects.execute('device',['device'],fx)
    assert s.checkpoint()==before and s.ctx.spatial.grid.passable(5,5)
def test_owner_child_retire_cleans_layers_immediately():
    p=fixture();p['entities'].append({'id':'unit/child','kind':'entity','tags':['ally'],'components':{
      'spatial':{},'terrain_overlays':[layer('child',2,buildableType=2)],'resources':{'hp':{'initial':20,'capacity':20}}}})
    a=add_skill(p,'spawn',{'op':'spawn','definition':'unit/child','position':{'row':5,'col':5},'owner':'source',
        'parameters':{'on_owner_retire':'remove'},'lifetime_seconds':20})
    s=h.make(p);h.command(s,'device',a,0);s.submit({'action':'withdraw','source':'device'},at=1);s.advance(2)
    assert not s.ctx.get('system/battle',('state','terrain','layers'))
    child=next(e for e in s.session.world.entities() if e['definition_id']=='unit/child');assert not s.ctx.alive(child['id'])
    assert not any(t['kind']=='domain.entity.expire' for t in s.session.scheduler.pending);roundtrip(s)
@pytest.mark.parametrize('spec',[layer(priority=True,passableMask=1),layer(passableMask=True),layer(buildableType=4),
    layer(physicalHeight=float('nan')),layer(unknown=1),dict(layer(passableMask=1),preserve=['passableMask']),
    dict(layer(passableMask=1),preserve=['unknown']),dict(layer(passableMask=1),position={'row':.5,'col':2})])
def test_unknown_invalid_fields_fail_compile(spec):
    p=fixture();add_skill(p,'bad',effect(spec))
    with pytest.raises((ValueError,TypeError)):Compiler().compile(p)
def test_no_overlay_no_extra_events():
    p=fixture();p['entities'][0]['components'].pop('terrain_overlays')
    s=h.make(p);assert s.ctx.terrain is None;s.advance(2);assert not any(e['type'].startswith('terrain.') for e in s.session.events)

def test_actual_route_cached_path_blocked_then_resumes_after_remove():
    p=fixture();p['scenarioDraft']['map']={'rows':1,'cols':6};p['scenarioDraft']['initialEntities'][0]['position']={'row':0,'col':5}
    p['entities'].append({'id':'unit/walker','kind':'entity','tags':['enemy','ground'],'components':{
        'attributes':{'base':{'move_speed':3}},'spatial':{},'resources':{'hp':{'initial':50,'capacity':50}},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    route={'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':4},'checkpoints':[],'motionMode':0}
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/walker','instanceAlias':'walker','position':{'row':0,'col':0},'route':route})
    spec=dict(layer('wall',10,passableMask=0),position={'row':0,'col':2})
    a=add_skill(p,'wall',effect(spec));b=add_skill(p,'unwall',{'op':'remove_terrain_overlay','parameters':{'key':'wall'}})
    for ability in p['abilities']:
        if ability['id'] in (a,b):
            ability['activation']['on_start']=[ability['timeline'][0]['effect']];ability['timeline']=[]
    s=h.make(p);h.command(s,'device',a,1);h.command(s,'device',b,5)
    s.advance(1);assert s.ctx.get('walker',('spatial','movement_path')) # actual cached route exists
    stopped=s.ctx.get('walker',('spatial','position'));s.advance(4)
    assert s.ctx.get('walker',('spatial','position'))==stopped and not s.ctx.spatial.grid.passable(0,2)
    assert len([e for e in s.session.events if e['type']=='movement.terrain_blocked'])==1
    s.advance(2);assert s.ctx.get('walker',('spatial','position'))['col']>stopped['col'] and s.ctx.spatial.grid.passable(0,2)
    roundtrip(s)

def test_dynamic_rule_at_tick_cache_restore_and_effective_map_agree():
    p=fixture();p['rules'].append({'id':'rule/dynamic_terrain','kind':'calculation_rule','contract':'terrain.tile_options',
      'implementation':{'type':'expression','expression':"{'tileKey':'tile_floor','passableMask':1,'buildableType':0,'groundPassable':context.time < 2,'movementCost':1}"}})
    p['entities'][0]['components']['terrain_overlays'][0]['rule']='rule/dynamic_terrain'
    s=h.make(p);cp=s.checkpoint();assert s.ctx.spatial.grid.passable(5,5)
    s.advance(3);assert not s.ctx.spatial.grid.passable(5,5) and not s.ctx.spatial.map_definition['tiles'][5*11+5]['groundPassable']
    assert s.ctx.get('system/battle',('state','terrain','revision'))==2
    r=Engine.restore(s.program,cp);assert r.ctx.spatial.grid.passable(5,5);r.advance(3);assert r.snapshot()==s.snapshot();roundtrip(s)

def test_owner_death_removes_layer_without_healing_or_HP_reset():
    p=fixture();p['entities'][0]['components']['buffs']['initial']=[]
    a=add_skill(p,'fatal',{'op':'modify_resource','resource':'hp','value':0})
    s=h.make(p);h.command(s,'device',a,0);s.advance(1)
    assert not s.ctx.alive('device') and s.ctx.resources.current('device','hp')==0
    assert not s.ctx.get('system/battle',('state','terrain','layers')) and s.ctx.spatial.grid.tile(5,5)['buildableType']==1
    roundtrip(s)

def test_retire_failure_restores_layers_and_path_queries():
    s=h.make(fixture());cp=s.checkpoint();before=s.ctx.spatial.grid.tile(5,5)
    fx={'op':'retire','parameters':{'reason':'dead'},'effects':[{'op':'modify_resource','resource':'absent','delta':1}]}
    with pytest.raises(ValueError):s.ctx.effects.execute('device',['device'],fx)
    assert s.checkpoint()==cp and s.ctx.spatial.grid.tile(5,5)==before and s.ctx.alive('device')

def test_static_cell_outside_and_fractional_initial_fail_compile():
    for cell in ({'row':8,'col':1},{'row':-1,'col':1},{'row':1.5,'col':1}):
        p=fixture();p['scenarioDraft']['initialEntities'][0]['position']=cell
        with pytest.raises(ValueError):Compiler().compile(p)
        p=fixture();add_skill(p,'badcell',effect(dict(layer(passableMask=0),position=cell)))
        with pytest.raises(ValueError):Compiler().compile(p)

def test_advanced_mask_consumer_and_height_data_preservation():
    p=fixture();p['entities'][0]['components']['terrain_overlays'][0]['values']['advancedBuildMask']=0
    p['entities'][0]['components'].pop('deployable') # isolate mask decision from occupied-cell decision
    p['entities'][0]['components']['terrain_overlays'][0]['preserve'].remove('advancedBuildMask')
    c=next(e for e in p['entities'] if e['id']=='unit/card')['components'];c['deployable']['parameters']={'advanced_build_mask':1}
    p['entities'][0]['components']['terrain_overlays'][0]['values']['buildableType']=1
    s=h.make(p);s.submit({'action':'deploy','definition':'unit/card','position':{'row':5,'col':5}},at=0);s.advance(1)
    assert any(e['type']=='command.rejected' and e['payload']['reason']=='advanced_not_buildable' for e in s.session.events)
    assert abs(s.ctx.spatial.grid.tile(5,5)['physicalHeight']-.4)<1e-7
    roundtrip(s)

def test_same_priority_stable_new_sequence_and_owner_keys():
    p=fixture();p['entities'].append({'id':'unit/upper','kind':'entity','tags':['ally'],'components':{
        'spatial':{},'terrain_overlays':[layer('native_trap_mode',0,physicalHeight=2)]}})
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/upper','position':{'row':5,'col':5},'instanceAlias':'upper'})
    a=add_skill(p,'replace_low',effect(layer('native_trap_mode',0,physicalHeight=3)))
    s=h.make(p);assert s.ctx.spatial.grid.tile(5,5)['physicalHeight']==2
    h.command(s,'device',a,0);s.advance(1);assert s.ctx.spatial.grid.tile(5,5)['physicalHeight']==3
    s.submit({'action':'withdraw','source':'device'},at=1);s.advance(1)
    assert s.ctx.spatial.grid.tile(5,5)['physicalHeight']==2 and len(s.ctx.get('system/battle',('state','terrain','layers')))==1
    roundtrip(s)

def test_mismatched_overlap_rule_creation_fully_rolls_back():
    p=fixture();p['rules'].append({'id':'rule/otherterrain','kind':'calculation_rule','extends':'rule/ark_terrain_tile_options'})
    p['entities'].append({'id':'unit/upper','kind':'entity','tags':['ally'],'components':{'spatial':{},
        'terrain_overlays':[dict(layer('upper',1,buildableType=2),rule='rule/otherterrain')]}})
    p['entities'][0]['components']['terrain_overlays'][0]['rule']='rule/ark_terrain_tile_options'
    p['scenarioDraft']['roster'].append('unit/upper')
    s=h.make(p);cp=s.checkpoint()
    with pytest.raises(ValueError,match='coherent'):s.ctx.lifecycle.create('unit/upper',position={'row':5,'col':5})
    assert s.checkpoint()==cp

def test_control_and_scheduled_battle_source_require_actor_context():
    for op in [effect(layer(buildableType=0)),{'op':'remove_terrain_overlay','parameters':{'key':'x'}}]:
        p=fixture();p['scenarioDraft']['scheduledEffects']=[{'at':0,'effect':op}]
        with pytest.raises(ValueError):Compiler().compile(p)
        p=fixture();p['controls']=[{'id':'control/terrain','kind':'control','clock_policy':'logical','ack_policy':'immediate',
          'steps':[{'kind':'effects','effects':[op]}]}]
        p['scenarioDraft'].pop('waves',None);p['scenarioDraft']['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear',
          'waves':[{'fragments':[{'actions':[{'kind':'control','definition':'control/terrain'}]}]}]}
        with pytest.raises(ValueError):Compiler().compile(p)
    s=h.make(fixture());cp=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.terrain.apply('system/battle',layer(buildableType=0))
    assert s.checkpoint()==cp

def test_custom_invalid_rule_output_does_not_leak_layers_or_sequence():
    p=fixture();p['rules'].append({'id':'rule/badterrain','kind':'calculation_rule','contract':'terrain.tile_options',
        'implementation':{'type':'expression','expression':"{'groundPassable':True,'movementCost':0,'unknown':True}"}})
    p['entities'][0]['components']['terrain_overlays'][0]['rule']='rule/badterrain'
    with pytest.raises(ValueError):h.make(p)
    p=fixture();a=add_skill(p,'badRule',effect(dict(layer('bad',2,buildableType=1),rule='rule/badterrain')))
    p['rules'].append({'id':'rule/badterrain','kind':'calculation_rule','contract':'terrain.tile_options',
        'implementation':{'type':'expression','expression':"{'groundPassable':True,'movementCost':0}"}})
    s=h.make(p);cp=s.checkpoint()
    fx=effect(dict(layer('bad',2,buildableType=1),rule='rule/badterrain'))
    with pytest.raises(ValueError):s.ctx.effects.execute('device',['device'],fx)
    assert s.checkpoint()==cp

def test_explicit_control_all_actor_overlay_and_cleanup_command_replay():
    p=fixture();p['selectors'].append({'id':'selector/terrain_device','kind':'selector','region':{'type':'all'},
        'filters':[{'tag':'device'},{'state':'alive'}],'limit':None})
    apply=dict(effect(layer('controlled',4,buildableType=2),target='selected'),selector='selector/terrain_device')
    remove={'op':'remove_terrain_overlay','selector':'selector/terrain_device','parameters':{'key':'controlled'}}
    p['controls']=[{'id':'control/terrain','kind':'control','clock_policy':'logical','ack_policy':'immediate',
      'steps':[{'kind':'effects','effects':[apply]},{'kind':'delay','seconds':.1},{'kind':'effects','effects':[remove]}]}]
    p['scenarioDraft'].pop('waves',None);p['scenarioDraft']['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear',
      'waves':[{'fragments':[{'actions':[{'kind':'control','definition':'control/terrain','instanceAlias':'controller'}]}]}]}
    s=h.make(p);s.advance(1);assert s.ctx.spatial.grid.tile(5,5)['buildableType']==2
    s.advance(4);assert s.ctx.spatial.grid.tile(5,5)['buildableType']==0
    assert s.ctx.controls.instance('controller')['status']=='completed';roundtrip(s)

def test_emp_preserves_declared_base_pass_heighttype_and_advanced():
    p=fixture();tiles=[{'tileKey':'tile_floor','passableMask':3,'buildableType':3,'heightType':'HIGHLAND','advancedBuildMask':2} for _ in range(88)]
    p['scenarioDraft']['map']['tiles']=tiles
    s=h.make(p);t=s.ctx.spatial.grid.tile(5,5)
    assert t['passableMask']==3 and t['heightType']=='HIGHLAND' and t['advancedBuildMask']==2 and t['buildableType']==0
    assert s.ctx.spatial.grid.passable(5,5)
    s.submit({'action':'withdraw','source':'device'},at=0);s.advance(1)
    assert s.ctx.spatial.grid.tile(5,5)==tiles[60];roundtrip(s)
