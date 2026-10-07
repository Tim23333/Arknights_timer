"""Opt-in finite resource packets use actual cast/task identities, no damage integral."""
from collections.abc import Mapping
from ark_sim.contracts import thaw,digest

def is_resource(d):return d.get('effect',{}).get('op')=='modify_resource'
def validate(d):
 if not is_resource(d):return
 if d.get('damage_integral') is not False or 'hit_interval_seconds' not in d:raise ValueError('Resource channel requires explicit packet clock and damage_integral false')
 if d.get('lifecycle',{}).get('source_hidden')!='cancel' or d.get('lifecycle',{}).get('target_hidden')!='cancel':raise ValueError('Resource channels require explicit hidden-owner cancellation')
 effect=d['effect']
 if effect.get('target','selected') not in ('selected','target'):raise ValueError('Resource channel packet must bind actual selected target')
 if not isinstance(effect.get('resource'),str) or not effect['resource']:raise ValueError('Resource channel requires declared nonempty resource key')
 from ark_sim.content.schemas import validate_effect,DEFAULT_CAPABILITIES
 validate_effect(effect,'resource_channel.effect',DEFAULT_CAPABILITIES)

def stamp(ctx,ref):
 actor=ctx.entity(ref);runtime=actor['components']['runtime'];return {'id':ref,'definition':actor['definition_id'],'life':runtime.get('lifecycle_generation',0),'death':runtime.get('death_generation',0)}

def issue(system,x,d):
 session=system.ctx.session;task=session.current_task;cast=system.ctx.abilities._active(x['source'],x['cast'])
 if task is None or task['kind']!='domain.ability.effect' or task['payload'].get('source')!=x['source'] or task['payload'].get('cast')!=x['cast'] or task['id']not in cast['tasks']:raise ValueError('Resource channel launch requires actual owned ability effect task')
 def declared(value):
  if isinstance(value,Mapping):return value.get('op')=='begin_attachment' and value.get('attachment')==d['id'] or any(declared(v) for v in value.values())
  if isinstance(value,(list,tuple)):return any(declared(v) for v in value)
  return False
 if not declared(task['payload']['effect']) or x['ability']not in system.ctx.get(x['source'],('abilities',),[]):raise ValueError('Resource channel begin is not declared by actual possessed ability effect')
 x['resource_origin']={'source_stamp':stamp(system.ctx,x['source']),'target_stamp':stamp(system.ctx,x['target']),'launch_task':thaw(task),'profile_digest':digest(d)}
 ident=session.emit('attachment.resource.issued',{'attachment':x['id'],'origin':x['resource_origin'],'initial':thaw(x)},x['cause']);x['resource_issued_event']=ident

def seal(system,x):
 if 'resource_origin' not in x:return
 snapshot=thaw(x);snapshot.pop('resource_record_event',None)
 ident=system.ctx.session.emit('attachment.resource.record',{'attachment':x['id'],'issued':x['resource_issued_event'],'state':snapshot},x['cause']);x['resource_record_event']=ident

def task_allowed(system,x,payload):
 task=system.ctx.session.current_task
 return task is not None and task['kind']=='domain.attachment.step' and task['payload']==payload and payload=={'attachment':x['id'],'generation':x['generation']} and task['id']==x['task'] and task['at']==x['due']==system.ctx.session.time and task['seq']==x['task_seq'] and task['phase']==x['phase']

def validate_restored(system):
 ctx=system.ctx;instances=system.state()['instances'];resource=[x for x in instances.values() if is_resource(system.profile(x))]
 if not resource and not any(is_resource(d) for d in ctx.program.definitions.values() if d.get('kind')=='attachment'):return
 events={e['id']:e for e in ctx.session.events};tasks={t['id']:t for t in ctx.session.scheduler.pending};owned=set();latest={}
 for e in events.values():
  if e['type']=='attachment.resource.issued' and e['payload']['attachment']not in instances:raise ValueError('Resource channel actual issued epoch lost instance')
  if e['type']=='attachment.resource.record':latest[e['payload']['attachment']]=e
 for x in resource:
  d=system.profile(x);validate(d);origin=x.get('resource_origin');issued=events.get(x.get('resource_issued_event'));record=latest.get(x['id'])
  if not isinstance(origin,Mapping) or issued is None or issued['type']!='attachment.resource.issued' or digest(origin)!=digest(issued['payload']['origin']) or digest(d)!=origin['profile_digest'] or record is None or record['id']!=x.get('resource_record_event'):raise ValueError('Resource channel immutable issuance/state record missing')
  initial=issued['payload']['initial']
  if issued['time']!=x['born'] or issued.get('cause')!=x['cause'] or issued['payload']['attachment']!=x['id'] or record.get('cause')!=x['cause'] or record['payload']['issued']!=issued['id'] or not x['born']<=record['time']<=ctx.session.time:raise ValueError('Resource channel actual event identity/time/cause binding invalid')
  if any(x[k]!=initial[k] for k in ['id','source','target','cast','ability','definition','born','start','flight_expires','cause']):raise ValueError('Resource channel immutable launch fields differ')
  current=thaw(x);current.pop('resource_record_event')
  if digest(current)!=digest(record['payload']['state']):raise ValueError('Resource channel runtime differs from actual record')
  if not x['active']:continue
  if stamp(ctx,x['source'])!=origin['source_stamp'] or stamp(ctx,x['target'])!=origin['target_stamp'] or system.invalid(x) is not None:raise ValueError('Resource channel active owner/target/cast scope invalid')
  cast=ctx.abilities._active(x['source'],x['cast'])
  if cast is None or cast['ability']!=x['ability'] or not system.ctx.program.definitions[x['ability']].get('wait_for_channels'):raise ValueError('Resource channel needs actual declared waiting cast')
  task=tasks.get(x['task']);owned.add(x['task'])
  if task is None or task['kind']!='domain.attachment.step' or task['payload']!={'attachment':x['id'],'generation':x['generation']} or task['at']!=x['due'] or task['seq']!=x['task_seq'] or task['phase']!=x['phase']:raise ValueError('Resource channel owned pending task missing/mismatched')
  if x['packets']<0 or (d['max_packets'] is not None and x['packets']>=d['max_packets']):raise ValueError('Resource channel active packet count invalid')
 issued_ids={e['payload']['attachment'] for e in events.values() if e['type']=='attachment.resource.issued'}
 for t in tasks.values():
  if t['kind']=='domain.attachment.step' and t['payload'].get('attachment')in issued_ids and t['payload'].get('attachment')not in instances:raise ValueError('Orphan resource task lost instance')
  if t['kind']=='domain.attachment.step' and t['payload'].get('attachment') in {x['id'] for x in resource} and t['id']not in owned:raise ValueError('Orphan resource channel task')
