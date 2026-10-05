from tools.chapter09_depletion_peer_joint.fixture import *
from ark_sim.contracts import digest,thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
import pytest,json

def create(p):return Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=49111)
def events(s,kind):return [(e['time'],thaw(e['payload'])) for e in s.session.events if e['type']==kind]
def owner(cp):return next(e for e in cp['kernel']['world']['entities'] if e['definition_id']=='unit/peer/owner')
def lease(cp):return owner(cp)['components']['runtime']['depletion']['lease']
def tasks(cp):return cp['kernel']['scheduler']['tasks']
def natural():
 s=create(fixture());s.advance(12);return s,s.checkpoint()
def proof(p,name,split,end):
 a=create(p);a.advance(split);LOG.mkdir(parents=True,exist_ok=True);f=LOG/(name+'.checkpoint.json');pin=write_ordered(f,a.checkpoint());b=Engine.restore(a.program,load_bound(f,pin),providers=REG);a.advance(end-split);b.advance(end-split);c=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==c.checkpoint();assert list(a.session.events)==list(b.session.events)==list(c.session.events);assert a.session.scheduler.pending==b.session.scheduler.pending==c.session.scheduler.pending;assert a.session.random.snapshot()==b.session.random.snapshot()==c.session.random.snapshot();REPORT.mkdir(exist_ok=True);(REPORT/(name+'.json')).write_text(json.dumps({'core':CORE,'actual_CPP_head_full_equal':True,'CP_SHA':pin,'input_digest':digest(p),'events':len(a.session.events)},indent=2),encoding='utf8');return a
@pytest.mark.parametrize('custom,mark,ready',[(False,17,79),(True,20,113)])
def test_finite_actual_damage_custom_health_nested_provider_context_and_clock_CPP(custom,mark,ready):
 s=proof(fixture(custom),'legal_'+str(custom),12,ready+2);assert not events(s,'command.rejected');assert s.ctx.resources.current('owner','vital')==0;assert s.ctx.alive('owner');assert s.ctx.depletion.state(s.session.world.resolve('owner'))['stage']=='ready';assert [t for t,_ in events(s,'peer.zero.mark')]==[mark];assert [t for t,_ in events(s,'peer.zero.ready')]==[ready];assert [x['actual_health_loss'] for _,x in events(s,'depletion.started') if 'actual_health_loss' in x]==[]
 provenance=events(s,'depletion.started')[0][1]['provenance'];assert provenance['operation']=='damage';assert provenance['health_before']==49 and provenance['health_after']==0 and provenance['actual_health_loss']==49 and provenance['requested_change']==-293


def test_declared_due_queue_coherent_clock_and_issued_tampering_reject():
 s,cp=natural();bad=deepcopy(cp);row=lease(bad)['actions']['1'];row['due']+=1;next(t for t in tasks(bad) if t['id']==row['task'])['at']+=1
 with pytest.raises(ValueError):Engine.restore(s.program,bad,providers=REG)
 bad=deepcopy(cp);row=lease(bad)['actions']['1'];row['due']+=1;next(t for t in tasks(bad) if t['id']==row['task'])['at']+=1;timing=bad['kernel']['events']['records'][row['time_event']-1];timing['payload']['value']+=1;timing['payload']['trace']['value']+=1;timing['payload']['trace']['raw']+=1;bad['kernel']['events']['records'][row['issued_event']-1]['payload']['due']+=1
 with pytest.raises(ValueError):Engine.restore(s.program,bad,providers=REG)


def test_done_key_slot_phase_seq_stage_provenance_are_bound_to_actual_lineage():
 s,cp=natural();mutations=['done','key','slot','phase','seq','stage','provenance']
 for change in mutations:
  bad=deepcopy(cp);row=lease(bad)['actions']['1']
  if change=='done':row['done']=True
  if change=='key':row['key']='mark'
  if change=='slot':lease(bad)['actions']['7']=lease(bad)['actions'].pop('1')
  if change=='phase':row['phase']=0
  if change=='seq':row['seq']+=1;next(t for t in tasks(bad) if t['id']==row['task'])['seq']+=1
  if change=='stage':owner(bad)['components']['runtime']['depletion']['stage']='ready'
  if change=='provenance':lease(bad)['provenance']['source']=2
  with pytest.raises(ValueError):Engine.restore(s.program,bad,providers=REG)


def test_direct_dispatch_and_forged_cast_cannot_borrow_zero_HP_callback_authority():
 s,cp=natural();ref=s.session.world.resolve('owner');s.ctx.depletion._dispatch(ref,1,'0');assert s.checkpoint()==cp
 with pytest.raises(ValueError):s.ctx.effects.execute('owner',['owner'],{'op':'emit','event':'peer.forged'},cast={'depletion_action':{'owner':ref,'generation':1,'slot':'0'}})
 assert s.checkpoint()==cp;s.ctx.effects.execute('owner',['owner'],{'op':'emit','event':'peer.unscoped'});assert s.checkpoint()==cp
 with pytest.raises(ValueError):s.ctx.resources.adjust('owner','vital',value=1)
 assert s.checkpoint()==cp


def test_raw_resource_zero_with_fake_operation_cannot_acquire_damage_plan():
 p=fixture();p['scenarioDraft']['commands']=[{'at':11,'action':'skill','source':'caster','ability':'ability/peer/raw_zero'}];s=proof(p,'resource_zero',12,20);assert not events(s,'depletion.started');assert not s.ctx.alive('owner');assert not events(s,'peer.zero.mark')


def test_retire_cancels_real_pending_tasks_and_prevents_future_callbacks_CPP():
 p=fixture();p['scenarioDraft']['scheduledEffects']=[{'at':30,'effect':{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}}];s=proof(p,'retire_cancel',18,90);assert not s.ctx.alive('owner');assert [t for t,_ in events(s,'peer.zero.mark')]==[17];assert not events(s,'peer.zero.ready');assert not any(t['kind']=='domain.depletion.action' for t in s.session.scheduler.pending);assert s.ctx.depletion.state(s.session.world.resolve('owner'))['lease'] is None


def test_late_callback_random_and_positive_health_fault_roll_back_entire_owned_callback():
 s=create(fixture(fault=True));old=s.session._handlers['domain.depletion.action'];checked=[]
 def callback(session,payload):
  s.ctx.attributes.value('owner','atk');before=session.snapshot();cache=s.ctx.attributes.checkpoint_cache();cursor=s.ctx.last_calculation_event_id
  try:return old(session,payload)
  except ValueError:
   assert session.snapshot()==before;assert s.ctx.attributes.checkpoint_cache()==cache;assert s.ctx.last_calculation_event_id==cursor;checked.append(True);raise
 s.session._handlers['domain.depletion.action']=callback
 with pytest.raises(ValueError,match='cannot restore positive health'):s.advance(18)
 assert checked==[True];assert not events(s,'peer.pre_error');assert s.session.random.samples==();assert not s.ctx.depletion.state(s.session.world.resolve('owner'))['lease']['actions']['0']['done'];assert s.ctx.resources.current('owner','vital')==0


def test_generation_zero_with_existing_lease_rejects_and_source_current_guard():
 s,cp=natural();bad=deepcopy(cp);owner(bad)['components']['runtime']['depletion']['generation']=0
 with pytest.raises(ValueError):Engine.restore(s.program,bad,providers=REG)
 assert guard()==START


def test_mandatory_lease_absent_alive_zero_HP_restore_must_fail_closed():
 s,cp=natural();bad=deepcopy(cp);owner(bad)['components']['runtime']['depletion']['lease']=None;assert bad['attribute_cache']==cp['attribute_cache'];assert all(cp['kernel'][k]==bad['kernel'][k] for k in ['events','scheduler','random'])
 accepted=False
 try:r=Engine.restore(s.program,bad,providers=REG);accepted=True
 except ValueError:pass
 if accepted:
  r.advance(90);REPORT.mkdir(exist_ok=True);(REPORT/'mandatory_lease.actual.failed.json').write_text(json.dumps({'core':CORE,'restore_accepted':True,'only_changed':'runtime.depletion.lease=None','natural_cache_entries':len(cp['attribute_cache']['entries']),'cache_not_deleted':True,'queue_RNG_events_preserved':True,'HP':r.ctx.resources.current('owner','vital'),'alive':r.ctx.alive('owner'),'stage':r.ctx.depletion.state(r.session.world.resolve('owner')),'ready_callback_times':[t for t,_ in events(r,'peer.zero.ready')],'source_guard':guard()==START},indent=2),encoding='utf8')
 assert not accepted


def test_zero_generation_with_no_lease_and_orphan_task_restore_fail_closed():
 s,cp=natural();bad=deepcopy(cp);state=owner(bad)['components']['runtime']['depletion'];state['generation']=0;state['lease']=None
 with pytest.raises(ValueError):Engine.restore(s.program,bad,providers=REG)
 healthy=create(fixture());good=healthy.checkpoint();orphan=deepcopy(good);scheduled=next(t for t in tasks(cp) if t['kind']=='domain.depletion.action');job=deepcopy(scheduled);job['id']=orphan['kernel']['scheduler']['next_id'];job['seq']=orphan['kernel']['scheduler']['next_seq'];orphan['kernel']['scheduler']['next_id']+=1;orphan['kernel']['scheduler']['next_seq']+=1;tasks(orphan).append(job)
 with pytest.raises(ValueError):Engine.restore(healthy.program,orphan,providers=REG)

def test_coherent_generation_changes_cannot_rewrite_original_started_and_issued_lineage():
 s,cp=natural();bad=deepcopy(cp);state=owner(bad)['components']['runtime']['depletion'];state['generation']+=1;state['lease']['generation']+=1
 for job in tasks(bad):
  if job['kind']=='domain.depletion.action':job['payload']['generation']+=1
 with pytest.raises(ValueError):Engine.restore(s.program,bad,providers=REG)
 assert guard()==START
