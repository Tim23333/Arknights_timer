import json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[]
def fixture(rows=1):
 barrier={'id':'unit/barrier','kind':'entity','tags':['player','barrier'],'components':{'spatial':{},'selection_state':{'side':0,'motion':1,'category':4},'attributes':{'base':{'max_hp':90,'def':0,'block_count':0}},'resources':{'hp':{'initial':90,'capacity':90,'role':'health'}},'route_obstacle':{'rule':'rule/contact','contact_radius':.45,'parameters':{}},'terrain_overlays':[{'key':'cost','values':{'obstacleLikeMoveCost':True},'preserve':['passableMask'],'priority':0}], 'lifecycle':{'policy':'policy/ark_lifecycle'},'deployable':{'base_cost':1,'capacity':0,'cooldown_seconds':0,'terrain':'ground','parameters':{'max_instances':3}}}}
 mover={'id':'unit/mover','kind':'entity','tags':['enemy'],'components':{'spatial':{},'selection_state':{'side':1,'motion':1,'category':1},'attributes':{'base':{'max_hp':1000,'atk':90,'def':0,'block_cost':1,'move_speed':3,'attack_interval':1}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'abilities':['ability/hit'],'behavior':{'machine':'behavior/mover'},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 return {'manifest':{'requires':['preset/ark_standard']},'entities':[barrier,mover],'rules':[{'id':'rule/contact','kind':'rule','contract':'blocking.obstacle','implementation':{'type':'expression','expression':'inputs.source.components.selection_state.side != inputs.obstacle.components.selection_state.side'}}],'selectors':[{'id':'selector/block','kind':'selector','region':{'type':'all','blocked_only':True},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1}],'abilities':[{'id':'ability/hit','kind':'ability','selector':'selector/block','activation':{'mode':'automatic_attack'},'timeline':[{'at_seconds':.1,'effect':{'op':'damage','damage_type':'physical','scale':1}}]}],'behaviors':[{'id':'behavior/mover','kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'attack','selector':'selector/block'}],'cast_groups':[{'key':'attack','abilities':['ability/hit']}],'parameters':{'target_key':'attack','blocked_target':True,'stop_on_target':False,'stop_cast_groups':['attack']}}]}}],'scenarioDraft':{'id':'scene/peer55','ruleset':'ruleset/ark_standard','roster':['unit/barrier'],'resources':{'dp':{'initial':10,'capacity':10},'life':{'initial':99999,'capacity':99999}},'objectives':{'life_resource':'life'},'map':{'rows':rows,'cols':4},'waves':[{'at':2,'definition':'unit/mover','instanceAlias':'mover','position':{'row':0,'col':0},'route':{'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':3},'checkpoints':[]}}]}}
def make(p):
 raw=(json.dumps(p,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':55019,'fixture':json.loads(raw)});return Engine.create(Compiler().compile(json.loads(raw)),seed=55019)
def deploy(s,row=0,col=1):s.submit({'action':'deploy','entity':'unit/barrier','alias':'barrier','position':{'row':row,'col':col}},at=0)
def exact(s,tmp_path):
 h=write_ordered(tmp_path/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'cp.json',h));s.advance(40);r.advance(40);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_chosen_single_path_90_damage_death_restores_layer_and_real_exit(tmp_path):
 s=make(fixture());deploy(s);s.advance(11);assert s.ctx.spatial.blocked_by('mover')==s.session.world.resolve('barrier');exact(s,tmp_path)
 assert not s.ctx.alive('barrier') and s.ctx.resources.current('barrier','hp')==0 and s.ctx.state()['leaks']==1 and s.ctx.resources.current('system/battle','life')==99998
 assert s.ctx.state()['terrain']['layers']=={}
def test_weighted_detour_cost100_keeps_source_category4_and_offpath_alive(tmp_path):
 p=fixture(2);p['entities'][0]['components']['terrain_overlays'][0]['rule']='rule/cost';p['rules'].append({'id':'rule/cost','kind':'rule','contract':'terrain.tile_options','implementation':{'type':'provider','provider':'ark.terrain.tile_options'},'parameters':{'obstacle_like_cost':100}});s=make(p);deploy(s);s.advance(30);exact(s,tmp_path)
 assert s.ctx.alive('barrier') and s.ctx.resources.current('barrier','hp')==90 and s.ctx.get('barrier',('selection_state','category'))==4
 assert not any(e['type']=='calculation' and e['payload']['calculation_id']=='blocking.obstacle' for e in s.session.events)
def test_near_but_not_on_selected_route_is_not_targeted():
 s=make(fixture(2));deploy(s,1,1);s.advance(55);assert s.ctx.resources.current('barrier','hp')==90 and s.ctx.state()['leaks']==1
def test_ordinary_character_blocks_first_with_distinct_obstacle_capacity_zero():
 p=fixture();hero={'id':'unit/ordinary','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':10000,'def':0,'block_count':1}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'}}};p['entities'].append(hero);p['scenarioDraft']['initialEntities']=[{'definition':hero['id'],'instanceAlias':'ordinary','position':{'row':0,'col':0}}]
 s=make(p);deploy(s);s.advance(10);assert s.ctx.spatial.blocked_by('mover')==s.session.world.resolve('ordinary') and s.ctx.resources.current('barrier','hp')==90
def test_two_movers_share_obstacle_no_character_slot_count():
 p=fixture();p['entities'][1]['components']['attributes']['base']['atk']=1;p['scenarioDraft']['waves'].append(deepcopy(p['scenarioDraft']['waves'][0]));p['scenarioDraft']['waves'][-1]['instanceAlias']='mover2';s=make(p);deploy(s);s.advance(13)
 assert s.ctx.spatial.blocked_by('mover')==s.ctx.spatial.blocked_by('mover2')==s.session.world.resolve('barrier')
def test_actual_rule_failure_on_public_deploy_is_atomic_all_world_rng_tasks():
 p=fixture();p['scenarioDraft']['waves']=[];p['scenarioDraft']['initialEntities']=[{'definition':'unit/mover','instanceAlias':'mover','position':{'row':0,'col':1},'route':{'motionMode':0,'startPosition':{'row':0,'col':1},'endPosition':{'row':0,'col':3},'checkpoints':[]}}];p['rules'][0]['implementation']['expression']='1 / 0';s=make(p);before=s.checkpoint()
 with pytest.raises(Exception):
  with s.session.atomic():s._execute_command({'action':'deploy','entity':'unit/barrier','position':{'row':0,'col':1}})
 assert s.checkpoint()==before and not s.ctx.spatial._blocking_reconciling

def test_legal_toggle_child_callback_retiring_obstacle_cannot_leave_stale_relations():
 p=fixture();p['entities'][1]['components']['attributes']['base']['atk']=1;p['scenarioDraft']['waves'].append(deepcopy(p['scenarioDraft']['waves'][0]));p['scenarioDraft']['waves'][-1]['instanceAlias']='mover2'
 p['buffs']=[{'id':'buff/watch','kind':'buff','toggle':{'rule':'rule/not_held','buff':'buff/watch_child','initial_enabled':True,'restore_delay_seconds':3,'events':[{'event':'blocking.changed','owner_role':'target'}]}},{'id':'buff/watch_child','kind':'buff','stacking':{'mode':'independent'},'on_remove':[{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}]}]
 p['rules'].append({'id':'rule/not_held','kind':'rule','contract':'passive.toggle','implementation':{'type':'expression','expression':'False'}})
 p['selectors'].append({'id':'selector/setup','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}]});p['abilities'].append({'id':'ability/setup','kind':'ability','selector':'selector/setup','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/watch'}]},'timeline':[]});p['entities'][0]['components']['abilities']=['ability/setup']
 s=make(p);deploy(s);s.submit({'action':'skill','source':'barrier','ability':'ability/setup'},at=3);s.advance(13)
 assert not s.ctx.alive('barrier')
 assert s.ctx.spatial.blocked_by('mover') is None and s.ctx.spatial.blocked_by('mover2') is None
 retired=next(e for e in s.session.events if e['type']=='entity.withdrawn' and e['payload']['target']==s.session.world.resolve('barrier'))
 assert not any(e['type']=='blocking.changed' and e['id']>retired['id'] and e['payload'].get('source')==s.session.world.resolve('barrier') for e in s.session.events)


def watched(effects, two=True, rows=2):
 p=fixture(rows);p['entities'][1]['components']['attributes']['base']['atk']=1
 if two:
  p['scenarioDraft']['waves'].append(deepcopy(p['scenarioDraft']['waves'][0]));p['scenarioDraft']['waves'][-1]['instanceAlias']='mover2'
 p['buffs']=[{'id':'buff/watch','kind':'buff','toggle':{'rule':'rule/not_held','buff':'buff/watch_child','initial_enabled':True,'restore_delay_seconds':3,'events':[{'event':'blocking.changed','owner_role':'target'}]}},{'id':'buff/watch_child','kind':'buff','stacking':{'mode':'independent'},'on_remove':effects}]
 p['rules'].append({'id':'rule/not_held','kind':'rule','contract':'passive.toggle','implementation':{'type':'expression','expression':'False'}})
 p['selectors'].append({'id':'selector/setup','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}]});p['abilities'].append({'id':'ability/setup','kind':'ability','selector':'selector/setup','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/watch'}]},'timeline':[]});p['entities'][0]['components']['abilities']=['ability/setup']
 return p

def test_public_callback_moving_obstacle_offpath_releases_same_pass(tmp_path):
 s=make(watched([{'op':'move','target':'source','position':{'row':1,'col':1}}]));deploy(s);s.submit({'action':'skill','source':'barrier','ability':'ability/setup'},at=3);s.advance(13)
 assert s.ctx.alive('barrier') and s.ctx.get('barrier',('spatial','position'))=={'row':1,'col':1}
 assert s.ctx.spatial.blocked_by('mover') is None and s.ctx.spatial.blocked_by('mover2') is None
 exact(s,tmp_path)

def test_public_callback_retiring_mover_cannot_publish_later_relation(tmp_path):
 s=make(watched([{'op':'retire','target':'selected','parameters':{'reason':'withdrawn'}}]));deploy(s);s.submit({'action':'skill','source':'barrier','ability':'ability/setup'},at=3);s.advance(13)
 assert not s.ctx.alive('mover') and not s.ctx.alive('mover2')
 for alias in ('mover','mover2'):
  ref=s.session.world.resolve(alias);e=next(e for e in s.session.events if e['type']=='entity.withdrawn' and e['payload']['target']==ref)
  assert not any(x['type']=='blocking.changed' and x['id']>e['id'] and x['payload'].get('target')==ref and x['payload'].get('source') is not None for x in s.session.events)
 exact(s,tmp_path)

def test_reentrant_callback_new_relation_is_not_overwritten_and_guards_reset():
 # Instrumentation invokes the public movement API during the synchronous
 # event boundary. This tests callback control flow, not command replay.
 s=make(fixture(2));deploy(s);s.advance(3);ref=s.session.world.resolve('mover');bar=s.session.world.resolve('barrier')
 old=s.ctx.emit;calls=[]
 def callback(kind,payload,*args,**kwargs):
  result=old(kind,payload,*args,**kwargs)
  if kind=='blocking.changed' and payload.get('source')==bar and not calls:
   calls.append(1);s.ctx.movement.displace(bar,bar,{'position':{'row':1,'col':1}},{});s.ctx.spatial.blocking()
  return result
 s.ctx.emit=callback;s.advance(10)
 assert calls==[1] and s.ctx.spatial.blocked_by(ref) is None
 assert not s.ctx.spatial._blocking_reconciling and not s.ctx.spatial._blocking_requested

def test_callback_rule_failure_restores_world_and_private_queue_then_retry():
 s=make(fixture());deploy(s);s.advance(3);s.ctx.set('mover',('spatial','position'),{'row':0,'col':.7});s.ctx.set('mover',('spatial','movement_path'),[{'row':0,'col':1},{'row':0,'col':2},{'row':0,'col':3}]);old=s.ctx.emit;before=s.checkpoint()
 def fail(kind,payload,*args,**kwargs):
  result=old(kind,payload,*args,**kwargs)
  if kind=='blocking.changed' and payload.get('source') is not None:
   s.ctx.spatial.blocking();s.session.random.sample('imp');raise ValueError('callback failure')
  return result
 s.ctx.emit=fail
 with pytest.raises(ValueError,match='callback failure'):
  s.ctx.spatial.blocking()
 assert s.checkpoint()==before and not s.ctx.spatial._blocking_reconciling and not s.ctx.spatial._blocking_requested
 s.ctx.emit=old;s.ctx.spatial.blocking();assert s.ctx.spatial.blocked_by('mover')==s.session.world.resolve('barrier')


def ready_two():
 p=fixture(2);p['entities'][0]['components']['route_obstacle']['contact_radius']=.8;p['scenarioDraft']['waves'].append(deepcopy(p['scenarioDraft']['waves'][0]));p['scenarioDraft']['waves'][-1]['instanceAlias']='mover2'
 s=make(p);deploy(s);s.advance(3)
 for alias in ('mover','mover2'):
  s.ctx.set(alias,('spatial','position'),{'row':0,'col':.4});s.ctx.set(alias,('spatial','movement_path'),[{'row':0,'col':1},{'row':0,'col':2},{'row':0,'col':3}])
 return s

def test_first_mover_callback_retires_later_captured_mover():
 s=ready_two();old=s.ctx.emit;m2=s.session.world.resolve('mover2');calls=[]
 def callback(kind,payload,*a,**kw):
  result=old(kind,payload,*a,**kw)
  if kind=='blocking.changed' and payload.get('source') is not None and not calls:
   calls.append(1);s.ctx.lifecycle.retire(m2,'withdrawn')
  return result
 s.ctx.emit=callback;s.ctx.spatial.blocking()
 retired=next(e for e in s.session.events if e['type']=='entity.withdrawn' and e['payload']['target']==m2)
 assert not s.ctx.active(m2) and not any(e['id']>retired['id'] and e['type']=='blocking.changed' and e['payload'].get('target')==m2 and e['payload'].get('source') is not None for e in s.session.events)

@pytest.mark.parametrize('field,value',[('route_hidden',True),('forced_motion',{'instrumentation':True}),('movement_path',[{'row':1,'col':2}])])
def test_callback_invalidates_current_motion_or_actual_remaining_path(field,value):
 s=ready_two();old=s.ctx.emit;calls=[];ref=s.session.world.resolve('mover')
 def callback(kind,payload,*a,**kw):
  result=old(kind,payload,*a,**kw)
  if kind=='blocking.changed' and payload.get('target')==ref and payload.get('source') is not None and not calls:
   calls.append(1);s.ctx.set(ref,('spatial',field),value);s.ctx.spatial.blocking()
  return result
 s.ctx.emit=callback;s.ctx.spatial.blocking()
 assert calls==[1] and s.ctx.spatial.blocked_by(ref) is None and not s.ctx.spatial._blocking_requested

def test_second_clear_callback_reentrant_new_normal_relation_survives():
 p=fixture(2);p['entities'].append({'id':'unit/hero','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':1000,'block_count':1}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'}}});p['scenarioDraft']['initialEntities']=[{'definition':'unit/hero','instanceAlias':'hero','position':{'row':1,'col':3}}]
 s=make(p);deploy(s);s.advance(3);ref=s.session.world.resolve('mover');bar=s.session.world.resolve('barrier');hero=s.session.world.resolve('hero');s.ctx.set(ref,('spatial','position'),{'row':0,'col':.7});s.ctx.set(ref,('spatial','movement_path'),[{'row':0,'col':1},{'row':0,'col':2},{'row':0,'col':3}]);old=s.ctx.emit;seen=[]
 def callback(kind,payload,*a,**kw):
  result=old(kind,payload,*a,**kw)
  if kind=='blocking.changed' and payload.get('target')==ref:
   if payload.get('source')==bar and not seen:
    seen.append('bar');s.ctx.movement.displace(bar,bar,{'position':{'row':1,'col':1}},{});s.ctx.spatial.blocking()
   elif payload.get('source') is None and seen==['bar']:
    seen.append('clear');s.ctx.movement.displace(hero,hero,{'position':{'row':0,'col':.7}},{});s.ctx.spatial.blocking()
  return result
 s.ctx.emit=callback;s.ctx.spatial.blocking()
 assert seen==['bar','clear'] and s.ctx.spatial.blocked_by(ref)==hero and not s.ctx.spatial._blocking_requested
