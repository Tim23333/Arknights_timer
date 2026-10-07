"""Declared post-channel finish owns an actual completion event and task."""
from ark_sim.contracts import thaw,digest
from collections.abc import Mapping

def spec(ability):return ability.get('channel_completion')
def event(ctx,ref,index=None):
 if type(ref)is not int or ref<1:raise ValueError('Channel phase event ID invalid')
 e=index.get(ref) if index is not None else ctx.session._events._records[ref-1] if ref<=len(ctx.session._events._records) else None
 if e is None or e['id']!=ref:raise ValueError('Channel phase actual event unavailable')
 return e

def clock(ctx,contract,inputs,source=None,ability=None):
 ability=ability or {};scope={'scenario':ctx.program.scenario.get('rules',{}),'source':ctx.definition_bindings(source),'target':{},'owner':{},'component':{},'attribute_or_resource':{},'ability':ability.get('rules',{}),'effect':{}}
 view={'time':ctx.session.time,'seconds':ctx.session.time*ctx.session.quantum,'quantum':ctx.session.quantum,'source':thaw(ctx.entity(source)) if source is not None else {},'target':{},'owner':{}}
 value=ctx.calc(contract,inputs,source=source,ability=ability);e=event(ctx,ctx.last_calculation_event_id)
 return value,{'event':e['id'],'cause':e.get('cause'),'contract':contract,'inputs':thaw(inputs),'scope':thaw(scope),'context':view,'ability':ability.get('id'),'source':source,'value':thaw(value),'runtime':ctx.rules.fingerprint}

def validate_clock(ctx,row,index):
 from .context import compact_trace
 e=event(ctx,row['event'],index);view=row['context'];ability=ctx.program.definitions[row['ability']] if row['ability'] else {}
 raw=view['source'];bindings={**ctx.program.definitions.get(raw.get('definition_id'),{}).get('rules',{}),**raw.get('components',{}).get('runtime',{}).get('rule_bindings',{})} if raw else {}
 expected={'scenario':ctx.program.scenario.get('rules',{}),'source':bindings,'target':{},'owner':{},'component':{},'attribute_or_resource':{},'ability':ability.get('rules',{}),'effect':{}}
 if digest(expected)!=digest(row['scope']) or e['type']!='calculation' or e.get('cause')!=row['cause'] or e['time']!=view['time'] or view['seconds']!=view['time']*ctx.session.quantum or view['quantum']!=ctx.session.quantum or e['payload']['source']!=row['source'] or e['payload']['target'] is not None or row['runtime']!=ctx.rules.fingerprint or e['payload']['calculation_id']!=row['contract'] or e['payload']['value']!=row['value']:raise ValueError('Channel post clock actual event/context/cause differs')
 old=ctx.session._capturing_atomic;ctx.session._capturing_atomic=True
 try:result=ctx.rules.evaluate(row['contract'],row['inputs'],scope=row['scope'],context=view)
 finally:ctx.session._capturing_atomic=old
 trace=result.trace if ctx.program.ruleset.get('parameters',{}).get('trace_mode','compact')=='full' else compact_trace(result.trace)
 if result.rule_id!=e['payload']['rule_id'] or digest(result.value)!=digest(row['value']) or digest(trace)!=digest(e['payload']['trace']):raise ValueError('Channel post pure clock trace/binding/value differs')

def authorize_completion(system,source,cast,attachment,completed_event,token):
 attachments=system.ctx.attachments;scopes=attachments._completion_scopes if attachments is not None else [];x=attachments.current(attachment) if attachments is not None else None
 if token is not getattr(attachments,'_completion_capability',None) or not scopes or x is None:raise ValueError('Channel completion evidence does not grant live stop capability')
 scope=scopes[-1]
 if scope!={'source':source,'cast':cast['id'],'attachment':attachment,'event':completed_event,'generation':x['generation'],'used':False} or completed_event in cast.get('channel_completed_events',[]):raise ValueError('Channel completion current owned stop scope already consumed or differs')
 return scope

def completed(system,source,cast,attachment,completed_event,token=None):
 scope=authorize_completion(system,source,cast,attachment,completed_event,token)

 ctx=system.ctx;session=ctx.session;ability=ctx.program.definitions[cast['ability']];s=spec(ability)
 if s is None:return False
 x=ctx.attachments.current(attachment);e=event(ctx,completed_event)
 if x is None or x['active'] or x['source']!=source or x['cast']!=cast['id'] or x['ability']!=cast['ability'] or e['type']!='attachment.finished' or e['time']!=session.time or e['payload']!={'attachment':attachment,'source':source,'target':x['target'],'cast':cast['id'],'reason':x['reason'],'packets':x['packets']} or e.get('cause')!=x['cause']:raise ValueError('Channel phase requires actual just-completed owned attachment')
 if any(event(ctx,ref)['payload']['attachment']==attachment for ref in cast.get('channel_completed_events',[])):raise ValueError('Owned attachment end cannot be consumed twice')
 cast.setdefault('channel_completed_events',[]).append(completed_event)
 scope['used']=True
 if cast['pending_channels'] or cast.get('pending_projectiles',0):ctx.set(source,('runtime','casts',cast['id']),cast);return True
 ctx.emit('ability.channel_last.ended',{'source':source,'ability':cast['ability'],'cast':cast['id'],'attachment':attachment,'reason':x['reason'],'completed_events':thaw(cast['channel_completed_events'])},cause=completed_event)
 seconds,recovery_proof=clock(ctx,'ability.recovery',{'attributes':ctx.attributes.values(source),'animation':{},'recovery_parameters':{'seconds':s['post_delay_seconds']}},source,ability)
 calculation=recovery_proof['event']
 if type(seconds)not in (int,float) or seconds<0:raise ValueError('Channel post recovery must be nonnegative')
 units,quantization_proof=clock(ctx,'time.quantize',{'seconds':seconds,'quantum':session.quantum,'rounding':{'mode':'ceil'}});quantization=quantization_proof['event'];due=session.time+units
 for task in list(session.scheduler.pending):
  if task['id'] in cast['tasks'] and task['kind']=='domain.ability.finish':session.cancel(task['id'])
 payload={'source':source,'cast':cast['id']};task_id=session.schedule('domain.ability.finish',payload,due,phase=ctx.effect_phase);task=next(t for t in session.scheduler.pending if t['id']==task_id)
 lease={'source':source,'cast':cast['id'],'ability':cast['ability'],'owner_stamp':{'id':source,'definition':ctx.entity(source)['definition_id'],'life':ctx.get(source,('runtime','life_generation'),0),'death':ctx.get(source,('runtime','death_generation'),0)},'completed_events':thaw(cast['channel_completed_events']),'started_at':session.time,'seconds':seconds,'units':units,'calculation':calculation,'quantization':quantization,'task':thaw(task),'declaration_digest':digest(s),'clock_proofs':[recovery_proof,quantization_proof]}
 issued=ctx.emit('ability.channel_post.issued',lease,cause=completed_event);cast['channel_post']={**lease,'issued':issued};cast['finish_at']=due;cast['finish_requested']=False;cast['tasks'].append(task_id);ctx.set(source,('runtime','casts',cast['id']),cast)
 ctx.emit('ability.channel_post.started',{'source':source,'cast':cast['id'],'ability':cast['ability'],'due':due,'task':task_id},cause=issued)
 return True

def actual_dispatch(system,task):
 session=system.ctx.session
 return bool(task and session._advancing and session._active_key==session.scheduler.key(task) and task['id'] not in {t['id'] for t in session.scheduler.pending})

def finish_allowed(system,source,cast,payload):
 lease=cast.get('channel_post')
 if lease is None:return False
 task=system.ctx.session.current_task
 return actual_dispatch(system,task) and thaw(task)==lease['task'] and payload==task['payload'] and system.ctx.session.time==task['at']==cast['finish_at']

def validate_restored(system):
 ctx=system.ctx
 if not any(spec(d) for d in ctx.program.definitions.values() if d.get('kind')=='ability'):return
 events={e['id']:e for e in ctx.session.events};tasks={t['id']:t for t in ctx.session.scheduler.pending};owned=set();live={}
 for actor in ctx.session.world.entities():
  for cast in actor['components'].get('runtime',{}).get('casts',{}).values():
   if not spec(ctx.program.definitions[cast['ability']]):continue
   active_channels=[x for x in ctx.attachments.state()['instances'].values() if x['active'] and x['source']==actor['id'] and x['cast']==cast['id']]
   if cast.get('pending_channels')!=len(active_channels):raise ValueError('Channel post actual pending channel count differs')
   lease=cast.get('channel_post')
   if lease is None:
    if cast.get('channel_completed_events') and not cast.get('pending_channels'):raise ValueError('Channel post missing active lease')
    continue
   live[(actor['id'],cast['id'])]=lease
   issued=event(ctx,lease['issued'],events);expected=thaw(lease);expected.pop('issued')
   if issued['type']!='ability.channel_post.issued' or issued['time']!=lease['started_at'] or thaw(issued['payload'])!=expected or issued.get('cause')!=lease['completed_events'][-1]:raise ValueError('Channel post immutable issued proof differs')
   s=spec(ctx.program.definitions[cast['ability']]);stamp={'id':actor['id'],'definition':actor['definition_id'],'life':actor['components']['runtime'].get('life_generation',0),'death':actor['components']['runtime'].get('death_generation',0)}
   if lease['source']!=actor['id'] or lease['cast']!=cast['id'] or lease['ability']!=cast['ability'] or lease['owner_stamp']!=stamp or lease['declaration_digest']!=digest(s) or cast['pending_channels']!=0 or cast.get('pending_projectiles',0) or cast['finish_at']!=lease['task']['at'] or cast.get('channel_completed_events')!=lease['completed_events']:raise ValueError('Channel post declaration/owner/cast scope differs')
   if len(set(lease['completed_events']))!=len(lease['completed_events']):raise ValueError('Channel post duplicate completion event')
   if len({event(ctx,ref,events)['payload']['attachment'] for ref in lease['completed_events']})!=len(lease['completed_events']):raise ValueError('Channel post duplicate owned attachment end')
   for ref in lease['completed_events']:
    e=event(ctx,ref,events)
    x=ctx.attachments.current(e['payload'].get('attachment'))
    if x is None or x['active'] or x['ability']!=cast['ability'] or e['type']!='attachment.finished' or thaw(e['payload'])!={'attachment':x['id'],'source':actor['id'],'target':x['target'],'cast':cast['id'],'reason':x['reason'],'packets':x['packets']} or e.get('cause')!=x['cause'] or e['time']>lease['started_at']:raise ValueError('Channel post missing actual attachment end lineage')
   if event(ctx,lease['completed_events'][-1],events)['time']!=lease['started_at']:raise ValueError('Channel post last actual completion time differs')
   if len(lease['clock_proofs'])!=2:raise ValueError('Channel post full clock proofs required')
   for proof in lease['clock_proofs']:validate_clock(ctx,proof,events)
   recovery,quant=lease['clock_proofs']
   if recovery['inputs']['recovery_parameters']!={'seconds':s['post_delay_seconds']} or recovery['ability']!=cast['ability'] or recovery['source']!=actor['id'] or recovery['event']!=lease['calculation'] or quant['event']!=lease['quantization'] or quant['inputs']!={'seconds':lease['seconds'],'quantum':ctx.session.quantum,'rounding':{'mode':'ceil'}}:raise ValueError('Channel post declared clock operand lineage differs')
   calculation=event(ctx,lease['calculation'],events);quantization=event(ctx,lease['quantization'],events)
   if calculation['type']!='calculation' or calculation['payload']['calculation_id']!='ability.recovery' or calculation['payload']['source']!=actor['id'] or calculation['payload']['value']!=lease['seconds'] or quantization['type']!='calculation' or quantization['payload']['calculation_id']!='time.quantize' or quantization['payload']['value']!=lease['units'] or lease['task']['at']!=lease['started_at']+lease['units']:raise ValueError('Channel post actual clock calculation proof differs')
   actual=tasks.get(lease['task']['id']);owned.add(lease['task']['id'])
   if actual is None or thaw(actual)!=lease['task'] or actual['id'] not in cast['tasks'] or actual['kind']!='domain.ability.finish' or actual['phase']!=ctx.session.scheduler.rank(ctx.effect_phase) or actual['payload']!={'source':actor['id'],'cast':cast['id']} or actual['at']<ctx.session.time:raise ValueError('Channel post actual owned finish task differs')
 for t in tasks.values():
  if t['kind']=='domain.ability.finish' and (t['payload'].get('source'),t['payload'].get('cast')) in live and t['id'] not in owned:raise ValueError('Channel post orphan/duplicate finish task')
 terminal={}
 for e in events.values():
  if e['type'] in ('ability.finished','ability.interrupted'):terminal.setdefault((e['payload']['source'],e['payload']['cast']),[]).append(e['time'])
 for e in events.values():
  if e['type']!='ability.channel_post.issued':continue
  key=(e['payload']['source'],e['payload']['cast'])
  if key in live:continue
  if not any(t>=e['time'] for t in terminal.get(key,[])):raise ValueError('Channel post historical lease erased without actual finish/interruption')
