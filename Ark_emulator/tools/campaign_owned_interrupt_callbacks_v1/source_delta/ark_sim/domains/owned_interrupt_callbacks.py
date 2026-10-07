"""Finite synchronous Buff callbacks captured only from actual owned interrupts."""
from ark_sim.contracts import thaw,digest
from ark_sim.rules.expressions import evaluate_expression

def stamp(ctx,ref):
 a=ctx.entity(ref);r=a['components']['runtime'];s={'id':a['id'],'definition':a['definition_id'],'life':r.get('life_generation',0),'death':r.get('death_generation',0)}
 if any(type(s[k])is not int or s[k]<0 for k in ('id','life','death')):raise ValueError('Owned callback source stamp is strict nonnegative integer')
 return s

def event(ctx,ref,index=None):
 if type(ref)is not int or ref<1:raise ValueError('Owned callback actual event ID invalid')
 e=index.get(ref) if index is not None else ctx.session._events._records[ref-1] if ref<=len(ctx.session._events._records) else None
 if e is None or e['id']!=ref:raise ValueError('Owned callback actual event absent')
 return e

def capture(system,source,cast,reason):
 ctx=system.ctx
 if not system._owned_interrupt_enabled:return []
 actual=system._active(source,cast['id'])
 if actual is None or actual!=cast or cast['ability'] not in ctx.get(source,('abilities',),[]):raise ValueError('Owned callback requires actual currently possessed cast')
 rows=[];payload={'source':source,'ability':cast['ability'],'cast':cast['id'],'reason':reason}
 for b in ctx.get(source,('buffs','instances'),[]):
  if b['source']!=source or b['target']!=source or b['expires_at'] is not None and ctx.session.time>=b['expires_at']:continue
  definition=ctx.program.definitions[b['definition']]
  for index,sub in enumerate(definition.get('events',[])):
   declaration=sub.get('owned_callback')
   if declaration is None or declaration['ability']!=cast['ability']:continue
   if not ctx.active(source) and not declaration['allow_owner_inactive']:continue
   if not ctx.buffs.applicability.active(b):continue
   context={'time':ctx.session.time,'owner':ctx.entity(source),'source':ctx.entity(source),'target':ctx.entity(source)}
   if sub.get('condition') and not evaluate_expression(sub['condition'],{'event':'ability.interrupted','payload':payload,'buff':b},sub.get('parameters',{}),context):continue
   rows.append({'source':source,'source_snapshot':thaw(ctx.entity(source)),'stamp':stamp(ctx,source),'cast':thaw(cast),'buff':thaw(b),'subscription_index':index,'subscription':thaw(sub),'captured_at':ctx.session.time,'payload':payload})
 if len(rows)>128:raise ValueError('Owned interrupt callback count exceeds finite bound')
 return rows

def dispatch(system,rows,ref,token):
 if token is not system._owned_interrupt_token or not system._owned_interrupt_scopes or system._owned_interrupt_scopes[-1]!={'rows':rows,'event':ref,'used':False}:raise ValueError('Owned interrupt event/cast data cannot grant callback capability')
 system._owned_interrupt_scopes[-1]['used']=True
 ctx=system.ctx;e=event(ctx,ref)
 for row in rows:
  if e['type']!='ability.interrupted' or e['time']!=row['captured_at'] or thaw(e['payload'])!=row['payload'] or stamp(ctx,row['source'])!=row['stamp']:raise ValueError('Owned callback actual interrupt/source incarnation differs')
  definition=ctx.program.definitions[row['buff']['definition']];sub=definition['events'][row['subscription_index']]
  if digest(sub)!=digest(row['subscription']) or row['buff']['source']!=row['source'] or row['buff']['target']!=row['source']:raise ValueError('Owned callback captured Buff declaration differs')
  state=ctx.get('system/battle',('owned_interrupt_callbacks',),{'next_id':1,'instances':{}});key='owned_interrupt/'+str(state['next_id']);record={**row,'id':key,'event':ref,'event_cause':e.get('cause'),'state':'issued','effects_digest':digest(sub['effects'])}
  issued=ctx.session.emit('buff.owned_interrupt.issued',record,cause=ref);record['issued_event']=issued;state['next_id']+=1;state['instances'][key]=record;ctx.set('system/battle',('owned_interrupt_callbacks',),state)
  for index,effect in enumerate(sub['effects']):
   scope={'source':row['source'],'id':key,'issued':issued,'effect_index':index,'effect':thaw(effect)};system._owned_interrupt_effect_scopes.append(scope)
   try:ctx.effects.execute(row['source'],[row['source']],thaw(effect),cast={'owned_interrupt_callback':{'id':key,'issued':issued,'effect_index':index}},cause=ref)
   finally:system._owned_interrupt_effect_scopes.pop()
  state=ctx.get('system/battle',('owned_interrupt_callbacks',));record=state['instances'][key];record['state']='complete';completed=ctx.session.emit('buff.owned_interrupt.complete',{'id':key,'issued':issued,'source':row['source'],'stamp':row['stamp']},cause=issued);record['completed_event']=completed;state['instances'][key]=record;ctx.set('system/battle',('owned_interrupt_callbacks',),state)

def effect_allowed(system,source,effect,cast):
 scopes=system._owned_interrupt_effect_scopes;tag=cast.get('owned_interrupt_callback')
 if not tag or not scopes:return False
 scope=scopes[-1]
 return source==scope['source'] and tag=={'id':scope['id'],'issued':scope['issued'],'effect_index':scope['effect_index']} and digest(effect)==digest(scope['effect'])

def selector_source_allowed(system,source,selector,effect):
 scopes=system._owned_interrupt_effect_scopes
 if not scopes:return False
 scope=scopes[-1];ctx=system.ctx;row=ctx.get('system/battle',('owned_interrupt_callbacks','instances',scope['id']))
 return bool(row and source==scope['source'] and digest(effect or {})==digest(scope['effect']) and scope['effect'].get('selector')==selector['id'] and row['subscription']['owned_callback']['allow_owner_inactive'] and row['subscription']['owned_callback']['selector_timing']=='live_at_event' and row['captured_at']==ctx.session.time and stamp(ctx,source)==row['stamp'])

def application(system,instance):
 ctx=system.ctx;subs=[thaw(s) for s in ctx.program.definitions[instance['definition']].get('events',[]) if s.get('owned_callback')]
 if not subs:return
 keys=['id','definition','source','target','generation','started_at','expires_at','stacks']
 core={k:instance[k] for k in keys}
 ref=ctx.session.emit('buff.owned_interrupt.application',{'instance':core,'subscriptions_digest':digest(subs),'source_stamp':stamp(ctx,instance['source']),'owner_stamp':stamp(ctx,instance['target'])})
 rows=ctx.get(instance['target'],('buffs','instances'),[])
 for b in rows:
  if b['id']==instance['id']:b['owned_interrupt_application_event']=ref
 ctx.set(instance['target'],('buffs','instances'),rows)

def target_allowed(ctx,source,target,effect):
 if effect['op']=='modify_resource':
  resource=effect['resource'];spec=ctx.get(target,('resources',resource,'spec'),{})
  if resource==ctx.health_resource(target) or spec.get('role')=='health':raise ValueError('Owned inactive-owner callback cannot modify health')
 elif effect['op']=='remove_buff':
  if target!=source:raise ValueError('Owned callback cleanup is bounded to its holder')
 else:raise ValueError('Owned inactive-owner callback only permits declared nonhealth resource/holder cleanup')

def validate_restored(system):
 ctx=system.ctx;state=ctx.get('system/battle',('owned_interrupt_callbacks',));enabled=system._owned_interrupt_enabled
 if not enabled:
  if state:raise ValueError('Owned callback ledger lacks declared feature')
  return
 index={e['id']:e for e in ctx.session.events};issued={e['id']:e for e in index.values() if e['type']=='buff.owned_interrupt.issued'}
 if state is None:
  if issued:raise ValueError('Owned callback ledger removed')
  return
 if type(state['next_id'])is not int or state['next_id']!=len(state['instances'])+1:raise ValueError('Owned callback ledger sequence differs')
 refs=set()
 for key,row in state['instances'].items():
  refs.add(row['issued_event']);e=event(ctx,row['event'],index);record=event(ctx,row['issued_event'],index);complete=event(ctx,row['completed_event'],index);initial=thaw(row)
  for k in ['issued_event','completed_event']:initial.pop(k)
  initial['state']='issued'
  if row['id']!=key or row['state']!='complete' or record['type']!='buff.owned_interrupt.issued' or thaw(record['payload'])!=initial or record.get('cause')!=row['event'] or e['type']!='ability.interrupted' or e['time']!=row['captured_at'] or thaw(e['payload'])!=row['payload'] or e.get('cause')!=row['event_cause']:raise ValueError('Owned callback immutable capture/interrupt proof differs')
  sub=ctx.program.definitions[row['buff']['definition']]['events'][row['subscription_index']];declaration=sub['owned_callback'];source=row['source'];a=ctx.entity(source)
  if digest(sub)!=digest(row['subscription']) or digest(sub['effects'])!=row['effects_digest'] or row['buff']['source']!=source or row['buff']['target']!=source or row['cast']['source']!=source or row['cast']['id']!=row['payload']['cast'] or row['cast']['ability']!=declaration['ability'] or row['stamp']!={'id':source,'definition':row['source_snapshot']['definition_id'],'life':row['source_snapshot']['components']['runtime'].get('life_generation',0),'death':row['source_snapshot']['components']['runtime'].get('death_generation',0)} or row['cast']['ability'] not in row['source_snapshot']['components']['abilities'] or row['buff']['expires_at'] is not None and row['captured_at']>=row['buff']['expires_at']:raise ValueError('Owned callback captured Buff/cast/source lifetime differs')
  application_event=event(ctx,row['buff']['owned_interrupt_application_event'],index);keys=['id','definition','source','target','generation','started_at','expires_at','stacks'];core={k:row['buff'][k] for k in keys};subs=[thaw(x) for x in ctx.program.definitions[row['buff']['definition']].get('events',[]) if x.get('owned_callback')]
  if application_event['type']!='buff.owned_interrupt.application' or application_event['time']!=row['buff']['started_at'] or thaw(application_event['payload']['instance'])!=core or application_event['payload']['subscriptions_digest']!=digest(subs) or not row['buff'].get('applicability',{}).get('active',True):raise ValueError('Owned callback actual Buff application UID/generation/lifetime differs')
  if complete['type']!='buff.owned_interrupt.complete' or complete['time']!=row['captured_at'] or thaw(complete['payload'])!={'id':key,'issued':row['issued_event'],'source':source,'stamp':row['stamp']} or complete.get('cause')!=row['issued_event']:raise ValueError('Owned callback complete event differs')
 if refs!=set(issued):raise ValueError('Owned callback orphan/missing historical ledger')
