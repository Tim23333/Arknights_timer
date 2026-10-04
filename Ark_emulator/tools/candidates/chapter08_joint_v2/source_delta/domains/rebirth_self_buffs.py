"""Actual consume callback-issued, persisted self Buff identity; no action privilege."""
from collections.abc import Mapping

def stamp(ctx,ref):return {'life':ctx.get(ref,('runtime','lifecycle_generation'),0),'death':ctx.get(ref,('runtime','death_generation'),0)}
def state_valid(ctx,ref):
 if getattr(ctx,'rebirth',None) is None or not ctx.alive(ref) or ctx.state().get('finished') or ctx.get(ref,('runtime','state'))!='rebirth':return None
 s=ctx.get(ref,('runtime','rebirth'),{});spec=ctx.rebirth._spec(ref)
 if not spec or s.get('phase') not in ('waiting','completing') or type(s.get('generation')) is not int or s['generation']<=0:return None
 if ctx.resources.current(ref,spec['resource'])!=0:return None
 if s['phase']=='waiting':
  callback=any(row==(ref,s['generation'],'waiting') for row in ctx.rebirth._callbacks)
  job=any(t['id']==s.get('task') and t['kind']=='domain.rebirth.finish' and t['at']==s.get('due_at') and t['payload']=={'target':ref,'generation':s['generation']} for t in ctx.session.scheduler.pending)
  task=ctx.session.current_task
  dispatched=task is not None and task['id']==s.get('task') and task['kind']=='domain.rebirth.finish' and task['at']==s.get('due_at') and task['payload']=={'target':ref,'generation':s['generation']}
  if not callback and not job and not dispatched:return None
 elif (ref,s['generation']) not in getattr(ctx.rebirth,'_self_buff_finishing',[]):return None
 return s,spec

def issue(ctx,instance):
 ref=instance['target']
 if instance['source']!=ref:return
 check=state_valid(ctx,ref)
 if check is None:return
 state,spec=check
 if instance['definition'] not in spec.get('retain_buffs',[]) or (ref,state['generation'],'waiting') not in ctx.rebirth._callbacks:return
 # Only the real apply inside the internal begin callback may create/rebind a lease.
 row={'definition':instance['definition'],'instance':instance['id'],'buff_generation':instance['generation'],'source':ref,'target':ref,'rebirth_generation':state['generation'],'incarnation':stamp(ctx,ref)}
 state.setdefault('self_buff_leases',{})[instance['id']]=row;ctx.set(ref,('runtime','rebirth'),state);instance['rebirth_self_lease']=row

def retained(ctx,instance):
 row=instance.get('rebirth_self_lease')
 if not isinstance(row,Mapping) or set(row)!={'definition','instance','buff_generation','source','target','rebirth_generation','incarnation'}:return False
 if any(type(row[k]) is not int for k in ('buff_generation','source','target','rebirth_generation')) or type(row['instance']) is not str:return False
 if not isinstance(row['incarnation'],Mapping) or set(row['incarnation'])!={'life','death'} or any(type(v) is not int or v<0 for v in row['incarnation'].values()):return False
 if type(instance.get('generation')) is not int or type(instance.get('id')) is not str or any(type(instance.get(k)) is not int for k in ('source','target')):return False
 ref=instance['target'];check=state_valid(ctx,ref)
 if check is None:return False
 state,spec=check
 if instance['source']!=ref or instance['definition'] not in spec.get('retain_buffs',[]) or row!=state.get('self_buff_leases',{}).get(instance['id']):return False
 expected={'definition':instance['definition'],'instance':instance['id'],'buff_generation':instance['generation'],'source':ref,'target':ref,'rebirth_generation':state['generation'],'incarnation':stamp(ctx,ref)}
 if row!=expected:return False
 live=next((i for i in ctx.buffs._instances(ref) if i['id']==instance['id']),None)
 if live is None or live['generation']!=instance['generation'] or live.get('rebirth_self_lease')!=row:return False
 return instance.get('expires_at') is None or ctx.session.time<instance['expires_at']


def finish_scope(function):
 def wrapped(system,session,payload):
  ref=None;generation=None;authorized=False
  if isinstance(payload,Mapping) and set(payload)=={'target','generation'} and type(payload['generation']) is int:
   try:
    ref=session.world.resolve(payload['target']);check=state_valid(system.ctx,ref)
   except (KeyError,ValueError,TypeError):check=None
   if check is not None:
    state,_=check;generation=state['generation']
    authorized=state.get('phase')=='waiting' and state.get('self_buff_leases') and payload['generation']==generation and session.time>=state['due_at']
  if not authorized:return function(system,session,payload)
  stack=getattr(system,'_self_buff_finishing',None)
  if stack is None:stack=[];system._self_buff_finishing=stack
  stack.append((ref,generation))
  try:return function(system,session,payload)
  finally:stack.pop()
 return wrapped


def check_refresh(ctx,source,target,existing):
 if existing is None or not retained(ctx,existing):return
 state=ctx.rebirth._state(target)
 if source!=target or (target,state['generation'],'waiting') not in ctx.rebirth._callbacks:
  raise ValueError('Actual rebirth self Buff refresh requires internal begin callback')
