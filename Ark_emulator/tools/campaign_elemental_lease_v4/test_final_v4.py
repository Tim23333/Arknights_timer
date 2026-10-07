import sys,os,json,traceback,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_elemental_lease_v4_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_elemental_lease_v4.fixture import package
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/campaign_elemental_lease_v4';RESULT=[];FACT={};ART=[];REG=BUILTIN_PROVIDERS

def create(p=None):return Engine.create(Compiler().compile(p or package()),providers=REG,seed=42371797)
def cpp():
 p=package();a=create(p);a.advance(130);b=create(p)
 for t in [0,10,50,92,94,130]:
  b.advance(t-b.session.time);f=LOG/(str(t)+'.checkpoint.json');h=write_ordered(f,b.checkpoint());ART.append({'path':str(f),'sha256':h,'bytes':f.stat().st_size});before=b.checkpoint();b=Engine.restore(b.program,load_bound(f,h),providers=REG);assert b.checkpoint()==before
 h=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==h.checkpoint();FACT['CPP_head']=True;FACT['endstate']=thaw(a.ctx.get('target',('runtime','elemental')))

def negatives():
 s=create();s.advance(10);cp=s.checkpoint();facts=[]
 for field in ['remaining','due','generation','task','seq','provenance']:
  bad=deepcopy(cp);actor=next(e for e in bad['kernel']['world']['entities'] if e['id']==2);state=actor['components']['runtime']['elemental'];lease=state['break']
  if field=='remaining':state['remaining']['EMBER']=1
  elif field=='provenance':lease['provenance']['request']['raw_amount']=1
  else:lease[field]+=1
  try:Engine.restore(s.program,bad,providers=REG)
  except Exception as e:facts.append({'field':field,'rejected':True,'message':str(e)})
  else:facts.append({'field':field,'rejected':False})
 FACT['six_rejections']=facts;assert all(x['rejected'] for x in facts)

def direct():
 s=create();s.advance(10);state=s.ctx.get('target',('runtime','elemental'));before=s.checkpoint();s.ctx.elemental.expire(s.session,{'target':2,'generation':state['generation']});assert before==s.checkpoint();FACT['direct_expiry_noop_full_equal']=True

def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json') and 'validation' not in p.parts}
def state_actor(cp):return next(e for e in cp['kernel']['world']['entities'] if e['id']==2)['components']['runtime']['elemental']
def coherent():
 s=create();s.advance(10);cp=s.checkpoint();facts=[]
 for label in ['duequeue','generationpayload','provenance','missingseal','extra_bar','bar_over_capacity','lasttime','orphan_task']:
  bad=deepcopy(cp);state=state_actor(bad);lease=state['break']
  if label=='duequeue':
   lease['due']+=1
   next(t for t in bad['kernel']['scheduler']['tasks'] if t['id']==lease['task'])['at']+=1
  elif label=='generationpayload':
   state['generation']+=1;lease['generation']+=1
   next(t for t in bad['kernel']['scheduler']['tasks'] if t['id']==lease['task'])['payload']['generation']+=1
  elif label=='provenance':lease['provenance']['source_snapshot']['components']['attributes']['base']['atk']+=1
  elif label=='missingseal':state['audit_event']=None
  elif label=='extra_bar':state['remaining']['UNDECLARED']=1
  elif label=='bar_over_capacity':state['remaining']['VOID']=1032
  elif label=='lasttime':state['last_time']-=1
  else:bad['kernel']['scheduler']['tasks']=[t for t in bad['kernel']['scheduler']['tasks'] if t['id']!=lease['task']]
  try:Engine.restore(s.program,bad,providers=REG)
  except Exception as e:facts.append({'case':label,'rejected':True,'type':type(e).__name__,'message':str(e)})
  else:facts.append({'case':label,'rejected':False})
 FACT['coherent_and_bounds']=facts;assert all(f['rejected'] for f in facts)
 before=s.checkpoint();lease=s.ctx.get('target',('runtime','elemental'))['break']
 try:s.ctx.elemental.callbacks(2,'EMBER',deepcopy(lease),'on_end',lease['break_event'])
 except ValueError as e:FACT['direct_callback_rejected']=str(e)
 else:raise AssertionError('Lease data granted callback scope')
 assert before==s.checkpoint()

def amount_rule_recovery():
 p=package();p['rules'].append({'id':'rule/elemental_v4/packet','kind':'rule','contract':'elemental.packet','implementation':{'type':'expression','expression':'inputs.source_attributes.atk * inputs.request.parameters.scale'}});p['abilities'][0]['timeline'][0]['effect']={'op':'elemental_damage','element':'VOID','amount_rule':'rule/elemental_v4/packet','parameters':{'scale':.5}}
 a=create(p);a.advance(40);b=create(p)
 for tick in [10,22,40]:
  b.advance(tick-b.session.time);before=b.checkpoint();b=Engine.restore(b.program,before,providers=REG);assert b.checkpoint()==before
 h=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==h.checkpoint();state=thaw(a.ctx.get('target',('runtime','elemental')));FACT['amount_rule_recovery']={'state':state,'expected_VOID':1031-797*.5+7*(39-9)/30};assert abs(state['remaining']['VOID']-FACT['amount_rule_recovery']['expected_VOID'])<1e-8

def owner_changes():
 for label,tick in [('beforebreak',4),('duringbreak',10)]:
  p=package();p['scenarioDraft']['scheduledEffects']=[{'at':tick,'effect':{'op':'retire','target':2,'parameters':{'reason':'withdraw'}}}];s=create(p);s.advance(20);cp=s.checkpoint();r=Engine.restore(s.program,cp,providers=REG);assert r.checkpoint()==cp;FACT['owner_'+label]={'state':thaw(s.ctx.get('target',('runtime','elemental'))),'alive':s.ctx.alive('target')}
 p=package();p['entities'][0]['components']['lifecycle']['revive']={'once':True,'hp_ratio':1,'delay_seconds':.5};# verify declaration only if supported, no fabricated actor resurrection
 # Independent redeploy creates a new declared instance; retired prior owner keeps its original epoch.
 p=package();p['scenarioDraft']['scheduledEffects']=[{'at':10,'effect':{'op':'retire','target':2,'parameters':{'reason':'withdraw'}}}];p['entities'][0]['components']['deployable']={'base_cost':0,'terrain':'both','capacity':1};p['scenarioDraft']['resources']['dp']={'initial':12,'capacity':99};p['scenarioDraft']['commands'].append({'at':12,'action':'deploy','definition':'unit/elemental_v4/target','alias':'newtarget','position':{'row':1,'col':1}});s=create(p);s.advance(20);cp=s.checkpoint();r=Engine.restore(s.program,cp,providers=REG);assert cp==r.checkpoint();new=thaw(s.ctx.get('newtarget',('runtime','elemental')));FACT['new_instance']={'state':new,'id':s.session.world.resolve('newtarget')};assert new['generation']==0 and new['break'] is None

def quantum_phase():
 p=package();p['rulesets']=[{'id':'ruleset/elemental_v4/quantum','kind':'ruleset','extends':'ruleset/ark_standard','quantum':1/17}];p['scenarioDraft']['ruleset']='ruleset/elemental_v4/quantum';s=create(p);s.advance(11);before=s.checkpoint();r=Engine.restore(s.program,before,providers=REG);assert before==r.checkpoint();due=s.ctx.get('target',('runtime','elemental'))['break']['due'];FACT['quantum_17']={'due':due,'last_time':s.ctx.get('target',('runtime','elemental'))['last_time']};assert due==9+47
 # Finished state must keep actual final recovery clock, not assume active time-1.
 s.ctx.elemental.tick(s.session);boundary=s.checkpoint();r=Engine.restore(s.program,boundary,providers=REG);assert r.checkpoint()==boundary;FACT['legitimate_same_time_boundary_tick_restore']=True
 s.ctx.state_update(finished=True);s.advance(1);before=s.checkpoint();r=Engine.restore(s.program,before,providers=REG);assert before==r.checkpoint();FACT['finished_restore_equal']=True

def fault_end():
 p=package();p['entities'][0]['components']['elemental']['elements']['EMBER']['on_end']=[{'op':'random','stream':'elemental/v4/end_fault','probability':1,'on_success':[{'op':'modify_resource','target':'source','resource':'MISSING','delta':1}]}];s=create(p);s.advance(92);proof=[]
 def stores():return {'world':s.session.world.snapshot(),'jobs':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'events':thaw(list(s.session.events)),'cache':s.ctx.attributes.checkpoint_cache()}
 def capture():return {'depth':s.session._atomic_depth,'task':s.session.current_task,'data':stores()} if s.session.current_task and s.session.current_task['kind']=='domain.elemental.expire' else None
 def restore(saved):
  if saved is not None:proof.append({'depth':saved['depth'],'task':saved['task'],'before':saved['data'],'after':stores()})
 s.session.register_atomic_participant('elemental.v4.endfault.observe',capture,restore);before=s.checkpoint()
 try:s.advance(1)
 except Exception as e:FACT['fault_error']={'type':type(e).__name__,'message':str(e)};assert 'MISSING' in str(e)
 else:raise AssertionError('Owned actual on_end fault path not reached')
 outer=next(x for x in proof if x['depth']==0);equal={k:outer['before'][k]==outer['after'][k] for k in outer['before']};FACT['fault_five_stores']=equal;assert all(equal.values());r=Engine.restore(s.program,before,providers=REG);assert r.checkpoint()==before
BEFORE=guard()
for name,fn in [('legitimate_CPP_head_pure_restore',cpp),('six_original_counter_reject',negatives),('direct_expiry_noop',direct),('coherent_original_events_retained_bounds_keys',coherent),('amount_rule_and_nonzero_recovery_CPP',amount_rule_recovery),('owner_cancel_and_new_instance_restore',owner_changes),('alternate_quantum_and_finished_clock',quantum_phase),('actual_owned_on_end_fault_five_stores',fault_end)]:
 try:fn();RESULT.append({'case':name,'passed':True})
 except Exception:RESULT.append({'case':name,'passed':False,'traceback':traceback.format_exc()})
 after=guard();r={'core':implementation_digest(),'actual_exit':0 if all(x['passed'] for x in RESULT) and BEFORE==after else 1,'results':RESULT,'facts':FACT,'artifacts':ART,'source_before':BEFORE,'source_after':after,'source_guard_equal':BEFORE==after,'comparison_exclusions':[]};(OUT/'author.final.v4.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print(json.dumps({'actual_exit':r['actual_exit'],'results':RESULT}));raise SystemExit(r['actual_exit'])
