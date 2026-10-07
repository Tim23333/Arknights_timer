import sys,os,json,copy,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_owned_interrupt_callbacks_v1_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from ark_sim.domains.owned_interrupt_callbacks import dispatch
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.campaign_owned_interrupt_callbacks_v1.fixture import package,AID,BID
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/campaign_owned_interrupt_callbacks_v1';FACT={};RESULT=[];CP=[]
def create(p):return Engine.create(Compiler().compile(p),seed=937173)
def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json') and 'validation' not in p.parts}
def cpp(p,label):
 a=create(p);a.advance(50);b=create(p)
 for tick in [14,22,24]:
  b.advance(tick-b.session.time);f=LOG/(label+str(tick)+'.checkpoint.json');h=write_ordered(f,b.checkpoint());CP.append({'path':str(f),'sha256':h,'bytes':f.stat().st_size});before=b.checkpoint();b=Engine.restore(b.program,load_bound(f,h));assert b.checkpoint()==before
 b.advance(50-b.session.time);head=replay(a.program,a.export_replay());assert a.checkpoint()==b.checkpoint()==head.checkpoint();assert list(a.session.events)==list(b.session.events)==list(head.session.events);return a
def actual(kind):
 s=cpp(package(kind),kind);ledger=thaw(s.ctx.get('system/battle',('owned_interrupt_callbacks',),{}));FACT[kind]={'a':s.ctx.resources.current('a','coil_q'),'b':s.ctx.resources.current('b','coil_q'),'ledger':ledger,'source_hp':s.ctx.resources.current('source','hp')};assert FACT[kind]['a']==45 and FACT[kind]['b']==11.75 and len(ledger['instances'])==1;assert FACT[kind]['source_hp']==(0 if kind=='dead' else 503)
def inactive_default():
 for opt,eligible in [(False,True),(True,False)]:
  s=create(package('dead',opt,eligible));s.advance(50);key=str((opt,eligible));FACT[key]={'b':s.ctx.resources.current('b','coil_q'),'ledger':s.ctx.get('system/battle',('owned_interrupt_callbacks',),{})};assert FACT[key]['b']==19 and not FACT[key]['ledger']
def tamper():
 s=create(package());s.advance(24);c=s.checkpoint();system=next(e for e in c['kernel']['world']['entities'] if e['id']==s.session.world.resolve('system/battle'));row=next(iter(system['components']['owned_interrupt_callbacks']['instances'].values()));facts=[]
 for label in ['missing','UID','generation','cast','cause','stamp']:
  b=copy.deepcopy(c);sysrow=next(e for e in b['kernel']['world']['entities'] if e['id']==s.session.world.resolve('system/battle'));rr=next(iter(sysrow['components']['owned_interrupt_callbacks']['instances'].values()))
  if label=='missing':sysrow['components'].pop('owned_interrupt_callbacks')
  elif label=='UID':rr['buff']['id']='buff/copied'
  elif label=='generation':rr['buff']['generation']+=1
  elif label=='cast':rr['cast']['id']='cast/copied'
  elif label=='cause':rr['event_cause']=1
  elif label=='stamp':rr['stamp']['life']+=1
  try:Engine.restore(s.program,b)
  except Exception as e:facts.append({'case':label,'rejected':True,'error':str(e)})
  else:facts.append({'case':label,'rejected':False})
 b=copy.deepcopy(c);system=next(e for e in b['kernel']['world']['entities'] if e['id']==s.session.world.resolve('system/battle'));rr=next(iter(system['components']['owned_interrupt_callbacks']['instances'].values()));rr['buff']['generation']+=1
 for e in b['kernel']['events']:
  if e['id']==rr['issued_event']:e['payload']['buff']['generation']+=1
 try:Engine.restore(s.program,b)
 except Exception as e:facts.append({'case':'coherent_buff_generation_and_issued_record','rejected':True,'error':str(e)})
 else:facts.append({'case':'coherent_buff_generation_and_issued_record','rejected':False})
 FACT['tamper']=facts;assert all(x['rejected'] for x in facts)
 before=s.checkpoint()
 try:dispatch(s.ctx.abilities,[row],row['event'],None)
 except ValueError as e:FACT['direct']=str(e)
 else:raise AssertionError('Direct callback permitted')
 assert s.checkpoint()==before
 before=s.checkpoint()
 try:s.ctx.effects.execute(s.session.world.resolve('source'),[s.session.world.resolve('b')],row['subscription']['effects'][0],cast={'owned_interrupt_callback':{'id':row['id'],'issued':row['issued_event'],'effect_index':0}})
 except ValueError as e:FACT['fake_cast']=str(e)
 else:raise AssertionError('Copied metadata effect permitted')
 assert s.checkpoint()==before

def fault():
 p=package();killer=next(e for e in p['entities'] if e['id']=='unit/owned_irq/killer');a=next(a for a in p['abilities'] if a['id']=='ability/owned_irq/kill');hit=a['timeline'][0]['effect'];a['timeline'][0]['effect']={'op':'random','stream':'owned_irq/fault','probability':1,'on_success':[{'op':'random','stream':'owned_irq/fault','probability':1,'on_success':[hit]}]};sub=p['buffs'][0]['events'][0];sub['effects'].insert(1,{'op':'modify_resource','resource':'ABSENT','delta':2,'selector':'selector/owned_irq/live'});s=create(p);captures=[]
 def stores():return {'world':s.session.world.snapshot(),'jobs':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'events':thaw(list(s.session.events)),'cache':s.ctx.attributes.checkpoint_cache()}
 def capture():
  t=s.session.current_task
  if t and t['kind']=='domain.ability.effect' and t['at']==23:return {'depth':s.session._atomic_depth,'before':stores(),'task':thaw(t)}
 def restore(saved):
  if saved:captures.append({'depth':saved['depth'],'before':saved['before'],'after':stores(),'task':saved['task']})
 s.session.register_atomic_participant('owned-irq-fault',capture,restore)
 try:s.advance(50)
 except Exception as e:FACT['fault_error']={'type':type(e).__name__,'message':str(e)}
 else:raise AssertionError('Actual callback fault not reached')
 outer=[r for r in captures if r['depth']==0];FACT['fault']={'outer':len(outer),'five_stores_equal':[r['before']==r['after'] for r in outer],'task':[r['task'] for r in outer]};assert outer and all(r['before']==r['after'] for r in outer) and 'ABSENT' in FACT['fault_error']['message']

BEFORE=guard()
for name,fn in [('actual_dead_dynamic_selector_CPPhead',lambda:actual('dead')),('actual_control_dynamic_selector_once_CPPhead',lambda:actual('control')),('default_and_explicit_inactive_never_revive',inactive_default),('restore_actual_ownership_and_direct_metadata_reject',tamper),('late_callback_debit_plus_two_RNG_atomic_five_stores',fault)]:
 try:fn();RESULT.append({'case':name,'passed':True})
 except Exception:RESULT.append({'case':name,'passed':False,'traceback':traceback.format_exc()})
 after=guard();r={'core':implementation_digest(),'actual_exit':0 if all(x['passed'] for x in RESULT) and BEFORE==after else 1,'source_before':BEFORE,'source_after':after,'source_guard_equal':BEFORE==after,'results':RESULT,'facts':FACT,'CP':CP,'comparison_exclusions':[]};(OUT/'author.correct.v2.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print(json.dumps({'exit':r['actual_exit'],'results':RESULT}));raise SystemExit(r['actual_exit'])
