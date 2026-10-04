from tools.chapter09_joint_peer_v6.fixture import *
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.contracts import digest,Intent,thaw
from ark_sim.kernel import Session
from ark_sim.rules.errors import ExpressionError
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest

def create(p):return Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=240619)
def events(s,kind):return [(x['time'],thaw(x['payload'])) for x in s.session.events if x['type']==kind]
def receipt(name,data):
 REPORT.mkdir(parents=True,exist_ok=True);(REPORT/(name+'.json')).write_text(json.dumps({'runtime':CORE,'fixture_sha':sha(Path(__file__).with_name('fixture.py')),**data},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def cpp(p,name,splits,end):
 pr=Compiler(providers=providers()).compile(p);a=Engine.create(pr,providers=providers(),seed=240619);a.advance(end)
 b=Engine.create(pr,providers=providers(),seed=240619);pins=[]
 for i,t in enumerate(splits):
  b.advance(t-b.session.time);LOG.mkdir(parents=True,exist_ok=True);path=LOG/(name+str(i)+'.checkpoint.json');pin=write_ordered(path,b.checkpoint());pins.append(pin);b=Engine.restore(pr,load_bound(path,pin),providers=providers())
 b.advance(end-b.session.time);c=replay(pr,a.export_replay(),providers=providers())
 assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events)
 assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending
 assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot()
 receipt(name,{'CP_head_full_equal':True,'CP_SHA':pins,'events':len(a.session.events),'RNG_samples':len(a.session.random.samples),'input_digest':digest(p)})
 return a
@pytest.mark.parametrize('distance,moving,reached',[(1,False,2),(3,False,6),(1,True,6)])
def test_compound_motion_clock_packet_clock_and_half_open(distance,moving,reached):
 s=cpp(fixture(distance=distance,moving=moving),'motion_'+str(distance)+str(moving),[1,7,15,29],50)
 assert [t for t,_ in events(s,'attachment.reached')]==[reached]
 assert [t for t,_ in events(s,'damage.accepted')]==[reached,reached+12,reached+24]
 assert [p['amount'] for _,p in events(s,'damage.accepted')]==pytest.approx([109.2]*3)
 assert [(t,p['loss']) for t,p in events(s,'elemental.loss.accepted')]==[(reached,105),(reached+12,105),(reached+24,105)]
 assert [t for t,_ in events(s,'attachment.refreshed')]==[reached,reached+9,reached+18,reached+27]
 assert events(s,'attachment.finished')[-1]==(reached+36,{'attachment':'attachment/1','source':2,'target':3,'cast':'cast/2/1','reason':'complete','packets':3})
 assert s.ctx.resources.current('target','hp')==pytest.approx(12000-3*109.2)
 assert s.ctx.get('target',('runtime','elemental','remaining','burn'))==2685
@pytest.mark.parametrize('duration,count',[(.4,1),(.8,2),(1.2,3)])
def test_deadline_never_delivers_packet_at_exclusive_end(duration,count):
 s=cpp(fixture(duration=duration),'deadline_'+str(count),[1,13],45);assert [t for t,_ in events(s,'damage.accepted')]==[2+12*i for i in range(count)]
 assert len(events(s,'elemental.loss.accepted'))==count;assert events(s,'attachment.finished')[-1][0]==2+12*count
@pytest.mark.parametrize('action,at,count',[('stun',1,0),('stun',5,1),('withdraw',1,0),('withdraw',5,1)])
def test_source_cancel_or_retire_is_owned_and_stops_both_packets(action,at,count):
 p=fixture();p['scenarioDraft']['commands'].append({'at':at,'action':'skill','source':'controller','ability':'ability/peer/foreign_'+action});s=cpp(p,'cancel_'+action+str(at),[1,7,16],35)
 assert not events(s,'command.rejected');assert len(events(s,'damage.accepted'))==len(events(s,'elemental.loss.accepted'))==count
 assert not any(x['active'] for x in s.ctx.attachments.state()['instances'].values())
 assert not any(t['kind']=='domain.attachment.step' for t in s.session.scheduler.pending)

def test_health_death_skips_EP_in_same_compound_packet():
 s=cpp(fixture(hp=50),'target_dead',[1,7],30);assert [p['amount'] for _,p in events(s,'damage.accepted')]==[50];assert not events(s,'elemental.loss.accepted');assert not s.ctx.alive('target');assert s.ctx.get('target',('runtime','elemental','remaining','burn'))==3000

def test_old_integral_profile_without_new_hit_interval_is_compatible():
 p=fixture(duration=.1,integral=True);assert 'hit_interval_seconds' not in p['definitions'][0];s=cpp(p,'old_integral',[1,4],15)
 assert [t for t,_ in events(s,'damage.accepted')]==[2,3,4];assert [p['amount'] for _,p in events(s,'damage.accepted')]==pytest.approx([3.64]*3);assert not events(s,'elemental.loss.accepted')

def cache_scene():
 p=fixture();p['entities'][2]['components']['abilities'].append('ability/peer/grant_sp');p['abilities'].append({'id':'ability/peer/grant_sp','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/source','timeline':[{'at':0,'effect':{'op':'modify_resource','resource':'sp','delta':3}}]});p['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'controller','ability':'ability/peer/grant_sp'}];return p

def test_legal_t7_queries_with_pending_SP_preserve_cache_causes_CP():
 p=cache_scene();a=create(p);a.advance(7);assert any(t['at']==7 and t['kind']=='domain.command' for t in a.session.scheduler.pending)
 assert a.ctx.attributes.value('source','atk')==840;assert a.ctx.attributes.value('source','atk')==840;assert a.ctx.attributes.value('source','max_hp')==7000
 cp=a.checkpoint();assert len(cp['attribute_cache']['entries'])==2;LOG.mkdir(parents=True,exist_ok=True);path=LOG/'cache7.checkpoint.json';pin=write_ordered(path,cp);pr=a.program;b=Engine.restore(pr,load_bound(path,pin),providers=providers())
 assert a.ctx.attributes.value('source','atk')==b.ctx.attributes.value('source','atk')==840
 assert list(a.session.events)==list(b.session.events)
 cached=events(a,'calculation.cached')[-1][1];assert cached['source_event_id']==next(x['source_event_id'] for x in cp['attribute_cache']['entries'] if x['attribute']=='atk')
 a.advance(22);b.advance(22);assert a.checkpoint()==b.checkpoint();assert list(a.session.events)==list(b.session.events);assert a.ctx.resources.current('source','sp')==11
 receipt('cache7',{'actual_CP':True,'complete_events_and_cached_causes_equal':True,'CP_SHA':pin,'events':len(a.session.events)})

def test_nested_atomic_cache_rebinds_actual_World_views_and_full_causal_events():
 a=create(cache_scene());a.advance(7);a.ctx.attributes.value('source','atk');a.ctx.attributes.value('source','max_hp');before=a.checkpoint();old=a.ctx.entity('source')
 with pytest.raises(ValueError,match='outer peer failure'):
  with a.session.atomic():
   a.ctx.set('source',('attributes','base','atk'),999);assert a.ctx.attributes.value('source','atk')==999
   with pytest.raises(RuntimeError,match='inner peer failure'):
    with a.session.atomic():a.ctx.set('source',('attributes','base','atk'),1001);a.ctx.attributes.value('source','atk');a.session.random.sample('peer/rollback');raise RuntimeError('inner peer failure')
   assert a.ctx.attributes.value('source','atk')==999;raise ValueError('outer peer failure')
 assert a.checkpoint()==before;assert a.ctx.entity('source') is not old;assert a.ctx.attributes.value('source','atk')==840
 last=thaw(a.session.events[-1]);assert last['type']=='calculation.cached';assert last['cause']==last['payload']['source_event_id'];assert last['payload']['source_event_id']==next(x['source_event_id'] for x in before['attribute_cache']['entries'] if x['attribute']=='atk')

@pytest.mark.parametrize('tamper',['value','context','scope'])
def test_public_cache_and_event_tamper_re_signed_still_rejects(tamper):
 a=create(cache_scene());a.advance(7);a.ctx.attributes.value('source','atk');cp=a.checkpoint();row=cp['attribute_cache']['entries'][0];event=cp['kernel']['events']['records'][row['source_event_id']-1]
 if tamper=='value':row['value']=900;event['payload']['value']=900;event['payload']['trace']['value']=900;event['payload']['trace']['raw']=900
 if tamper=='context':event['payload']['trace']['context']['attribute_sample_time']=6
 if tamper=='scope':row['effect']={'metadata':{'forged':'scope'}}
 row['event_digest']=digest(event);row['record_digest']=digest({k:v for k,v in row.items() if k!='record_digest'})
 with pytest.raises(ValueError):Engine.restore(a.program,cp,providers=providers())


def test_break_callback_failure_rolls_back_health_EP_cursor_tasks_RNG_and_cached_events():
 s=create(fixture(capacity=100,break_error=True));old=s.session._handlers['domain.attachment.step'];checked=[]
 def inspect_actual_owned_callback(session,payload):
  if session.time!=2:return old(session,payload)
  s.ctx.attributes.value('source','atk');before=session.snapshot();cache=s.ctx.attributes.checkpoint_cache();last=s.ctx.last_calculation_event_id;view=s.ctx.entity('source')
  try:return old(session,payload)
  except ExpressionError as error:
   assert isinstance(error.__cause__,ZeroDivisionError)
   assert session.snapshot()==before;assert s.ctx.attributes.checkpoint_cache()==cache;assert s.ctx.last_calculation_event_id==last;assert s.ctx.entity('source') is not view;checked.append(True);raise
 s.session._handlers['domain.attachment.step']=inspect_actual_owned_callback
 with pytest.raises(ExpressionError,match="division by zero"):s.advance(5)
 assert checked==[True];assert s.ctx.resources.current('target','hp')==12000;assert s.ctx.get('target',('runtime','elemental','remaining','burn'))==100
 assert s.ctx.attachments.state()['instances']['attachment/1']['packets']==0;assert not events(s,'damage.accepted');assert not events(s,'elemental.loss.accepted')
 receipt('callback_rollback',{'actual_owned_task':True,'health_EP_cursor_full_kernel_tasks_RNG_events_and_cache_equal':True,'main_exception':'ExpressionError','original_arithmetic_cause':'ZeroDivisionError'})

MUTATORS=['emit','schedule','create','world_set','rng','reserve_sequence','event_emit','world_restore','random_restore','session_restore']
def primitive_mutator(s,ref,name):
 if name=='emit':return s.emit('peer/forbidden',{})
 if name=='schedule':return s.schedule('peer/noop',{},1)
 if name=='create':return s.world.create('peer/new',{})
 if name=='world_set':return s.world.set(ref,('x',),2)
 if name=='rng':return s.random.sample('peer/forbidden')
 if name=='reserve_sequence':return s.scheduler.reserve_sequence()
 if name=='event_emit':return s._events.emit('peer/forbidden',{},s.time)
 if name=='world_restore':return s.world.restore(s.world.snapshot())
 if name=='random_restore':return s.random.restore(s.random.snapshot())
 if name=='session_restore':return s.restore(s.checkpoint())
@pytest.mark.parametrize('mutator',MUTATORS)
def test_participant_capture_forbids_public_kernel_mutation(mutator):
 s=Session();ref=s.world.create('peer/unit',{'x':1});s.register_handler('peer/noop',lambda s,p:None);before=s.checkpoint();s.register_atomic_participant('peer/capture',lambda:primitive_mutator(s,ref,mutator),lambda x:None)
 with pytest.raises(RuntimeError):
  with s.atomic():pass
 assert s.checkpoint()==before;assert not s._capturing_atomic;s.emit('peer/recovered',{})
@pytest.mark.parametrize('mutator',MUTATORS)
def test_participant_restore_fault_keeps_primary_exception_and_clean_checkpoint_recovers(mutator):
 s=Session();ref=s.world.create('peer/unit',{'x':1});s.register_handler('peer/noop',lambda s,p:None);clean=s.checkpoint();s.register_atomic_participant('peer/restore',lambda:None,lambda state:primitive_mutator(s,ref,mutator))
 with pytest.raises(ValueError,match='primary peer error') as caught:
  with s.atomic():s.world.set(ref,('x',),3);raise ValueError('primary peer error')
 assert caught.value.__cause__ is not None;assert s._atomic_restore_failure;assert s.world.get(ref)['components']['x']==1
 with pytest.raises(RuntimeError):s.emit('peer/blocked',{})
 s.restore(clean);assert not s._atomic_restore_failure;s.emit('peer/healthy',{});assert s.events[-1]['type']=='peer/healthy'

def test_source_start_end_guard():assert guard()==START
