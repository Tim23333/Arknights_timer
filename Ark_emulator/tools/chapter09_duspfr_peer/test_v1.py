from tools.chapter09_duspfr_peer.fixture import *
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=33791137)
def events(s,t):return [(e['time'],thaw(e['payload'])) for e in s.session.events if e['type']==t]
def ep(s):return s.ctx.get('player',('runtime','elemental'))['remaining']['FIRE']
def proof(p,name,splits,end):
 a=create(p);a.advance(end);b=create(p);LOG.mkdir(parents=True,exist_ok=True);pins=[]
 for i,t in enumerate(splits):
  b.advance(t-b.session.time);path=LOG/(name+str(i)+'.checkpoint.json');pin=write_ordered(path,b.checkpoint());pins.append(pin);b=Engine.restore(b.program,load_bound(path,pin),providers=REG)
 b.advance(end-b.session.time);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot();REPORT.mkdir(parents=True,exist_ok=True);(REPORT/(name+'.json')).write_text(json.dumps({'core':CORE,'actual_CPP_head_full_equal':True,'CP_SHAs':pins,'input_digest':digest(p),'events':len(a.session.events)},indent=2),encoding='utf8');return a

def test_flame_first20_compound_packets_flight_repeat_and_caststate_deadline():
 p=scene();s=create(p);s.advance(17);assert s.ctx.resources.current('player','hp')==HP;s.advance(1);assert abs(s.ctx.resources.current('player','hp')-(HP-54.6))<1e-8;assert ep(s)==9958
 s=proof(p,'twenty_repeat',[16,190,319],620);assert [t for t,x in events(s,'ability.started') if x['ability']==FLAME]==[0,618];packets=events(s,'damage.accepted');assert [t for t,_ in packets]==list(range(17,318,15));assert len(packets)==21;assert abs(s.ctx.resources.current('player','hp')-(HP-1146.6))<1e-8;assert ep(s)==9118
 p=scene(pos=(5,5.9));s=proof(p,'twenty_distance_point9',[16,190,319],620);assert [t for t,_ in events(s,'damage.accepted')]==list(range(18,318,15));assert len(events(s,'damage.accepted'))==20;assert abs(s.ctx.resources.current('player','hp')-(HP-1092))<1e-8;assert ep(s)==9160

def test_distinct_trigger1_target2_live_moving_and_ground_masks():
 p=scene(pos=(5,6.2));s=create(p);s.advance(8);assert not s.ctx.get('source',('runtime','casts'),{})
 p=scene(pos=(5,5.8));p['scenarioDraft']['commands']=[{'at':10,'action':'skill','source':'player','ability':'ability/peer/move'}];s=proof(p,'trigger_target_moving',[11,18],40);assert [t for t,x in events(s,'ability.started') if x['ability']==FLAME]==[0];assert s.ctx.resources.current('player','hp')<HP;assert s.ctx.get('player',('spatial','position'))['col']==6.7
 for change in [{'motion':2},{'category':2},{'target_free':True},{'camouflage':True},{'abnormal_flags':[9]}]:
  p=scene();p['entities'][-1]['components']['selection_state'].update(change);s=create(p);s.advance(10);assert not s.ctx.get('source',('runtime','casts'),{});assert not events(s,'damage.accepted')

def test_blocked_native13_ticks_physical_and_unblock_route():
 p=scene(pos=(5,5),source_flags=(12,));p['entities'][-1]['components']['deployable']={'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'};p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':'WALK','startPosition':{'row':5,'col':5},'endPosition':{'row':5,'col':9},'checkpoints':[]};s=create(p);s.ctx.spatial.blocking();assert s.ctx.spatial.blocked_by('source')==s.session.world.resolve('player');s.advance(13);assert s.ctx.resources.current('player','hp')==HP;s.advance(1);assert s.ctx.resources.current('player','hp')==HP-563
 s=proof(p,'blocked',[7,14],31);starts=[t for t,x in events(s,'ability.started') if x['ability']=='ability/ch9/duspfr/blocked_attack'];assert starts==[1];assert [t for t,x in events(s,'damage.accepted')]==[14];assert 14-starts[0]==13
 s.ctx.lifecycle.retire('player','withdrawn');s.advance(65);assert s.ctx.spatial.blocked_by('source') is None;assert s.ctx.get('source',('spatial','position'))['col']>5

@pytest.mark.parametrize('flag',[0,12])
def test_actual_external_stun_silence_interrupts_and_resets_cooldown(flag):
 p=scene();p['buffs'][-1]['selection_flags']['abnormal_flags']=[flag];p['scenarioDraft']['commands']=[{'at':29,'action':'skill','source':'player','ability':'ability/peer/control_source'}];s=proof(p,'control_'+str(flag),[20,30],60);assert events(s,'command.accepted');assert len(events(s,'damage.accepted'))==1;assert ep(s)==9958;assert s.ctx.get('source',('runtime','casts'))=={};assert s.ctx.get('source',('runtime','cooldowns',FLAME))==329

def test_target_health_first_lethal_and_retire_release():
 s=proof(scene(hp=41),'target_lethal',[16],40);assert not s.ctx.alive('player');assert ep(s)==10000;assert s.ctx.get('source',('runtime','casts'))=={}
 p=scene();p['scenarioDraft']['scheduledEffects']=[{'at':26,'effect':{'op':'retire','target':3,'parameters':{'reason':'withdrawn'}}}];s=proof(p,'target_retire',[20,27],50);assert len(events(s,'damage.accepted'))==1;assert ep(s)==9958;assert s.ctx.get('source',('runtime','casts'))=={}

def test_deadboom_five_parallel_none_suicide34_native500_positive_pillar_chain():
 p=scene(atk=500,pos=(6.4,5),death_at=11,pillar=True,other=True);s=create(p);s.advance(12);assert s.ctx.resources.current('source','hp')==0 and s.ctx.alive('source');starts=[(t,x) for t,x in events(s,'ability.started') if x['source']==s.session.world.resolve('source')];assert len(starts)==5 and {t for t,_ in starts}=={11};s.advance(30);assert s.ctx.resources.current('pillar','hp')==4500;assert s.ctx.depletion.state('pillar')['stage']=='collapsing';assert s.ctx.resources.current('other','hp')==0 and s.ctx.alive('other');assert s.ctx.resources.current('player','hp')==HP-325;assert ep(s)==10000;s.advance(4);assert not s.ctx.alive('source');death=[(t,x) for t,x in events(s,'instant_kill.executed') if x.get('cause')=='duspfr_suicide' and x['target']==s.session.world.resolve('source')];assert death[0][0]==45 and death[0][1]['source'] is None
 s=proof(p,'death_chain',[12,43,46],100);assert not s.ctx.alive('other');assert len(events(s,'tile.token_created'))==2;assert ep(s)==10000

def test_silenced_zero_or_removed_trait_has_no_deadboom_permission():
 for flag,remove in [(12,False),(0,True)]:
  p=scene(pos=(6.4,5),death_at=11,source_flags=(flag,));
  if remove:p['entities'][0]['components']['buffs']['initial']=[]
  s=create(p);s.advance(50);assert not s.ctx.alive('source');assert not any('/dead_' in x['ability'] for _,x in events(s,'ability.started'))

def test_local_dead_damage_rule_scope_is_actual_and_CPP_head():
 p=scene(atk=500,pos=(6.4,5),death_at=11);p['rules'].append({'id':'rule/peer/local_dead_packet','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'packet','expression':"{'accepted': True, 'amount': 113, 'allocations': [], 'events': []}"}],'output':'nodes.packet'}});a=next(x for x in p['abilities'] if x['id'].endswith('/dead_Damage'));a['rules']={'damage.pipeline':'rule/peer/local_dead_packet'};s=proof(p,'local_rule_scope',[12,42],60);assert s.ctx.resources.current('player','hp')==HP-113;assert ep(s)==10000

def actor_cp(cp,alias):return next(x for x in cp['kernel']['world']['entities'] if x['id']==cp['kernel']['world']['aliases'][alias])
def test_positive_pillar_restore_lease_HP_generation_source_event_proof_strict():
 s=create(scene(atk=500,pos=(6.4,5),death_at=11,pillar=True));s.advance(43);cp=s.checkpoint();assert s.ctx.resources.current('pillar','hp')==4500;assert Engine.restore(s.program,deepcopy(cp),providers=REG).checkpoint()==cp
 for change in ['lease','hp','generation','source_fp','source_value','source_event_time','source_event_cause']:
  bad=deepcopy(cp);owner=actor_cp(bad,'pillar');state=owner['components']['runtime']['depletion']
  if change=='lease':state['lease']=None
  elif change=='hp':owner['components']['resources']['hp']['current']=4499
  elif change=='generation':
   state['generation']+=1;state['lease']['generation']+=1
   for task in bad['kernel']['scheduler']['tasks']:
    if task['kind']=='domain.depletion.action' and task['payload']['owner']==owner['id']:task['payload']['generation']+=1
  else:
   c=next(iter(actor_cp(bad,'source')['components']['runtime']['casts'].values()));event=bad['kernel']['events']['records'][c['depletion_timing_source_event']-1]
   if change=='source_fp':c['depletion_timing_source_fingerprint']='0'*64
   elif change=='source_value':event['payload']['view']['components']['attributes']['base']['atk']+=17
   elif change=='source_event_time':event['time']+=1
   else:event['cause']=None
  assert bad['attribute_cache']==cp['attribute_cache']
  with pytest.raises(ValueError):Engine.restore(s.program,bad,providers=REG)
 assert guard()==START

def test_owned_start_late_random_fault_full_atomic_rollback_and_zero_HP_no_borrow():
 p=scene(pos=(6.4,5));a=next(x for x in p['abilities'] if x['id'].endswith('/dead_Damage'));a['activation']['on_start']=[{'op':'random','stream':'peer.dead_fault','probability':1,'on_success':[{'op':'modify_resource','resource':'missing','amount':1}]}];s=create(p);s.ctx.attributes.value('source','atk');before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.effects.execute('player',['source'],{'op':'damage','damage_type':'true','scale':1})
 assert s.checkpoint()==before
 s=create(scene(pos=(6.4,5),death_at=11));s.advance(12);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.resources.adjust('source','hp',1)
 assert s.checkpoint()==before
 cast=next(iter(s.ctx.get('source',('runtime','casts')).values()))
 with pytest.raises(ValueError):s.ctx.effects.execute('source',['source'],{'op':'retire','target':'source'},cast=deepcopy(cast))
 assert s.checkpoint()==before

def test_current_module_source_and_core_guard():assert guard()==START
