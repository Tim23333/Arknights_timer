"""Finite opt-in exact-zero terminal activity; no ordinary HP0 activity permission."""
import math
from collections.abc import Mapping
from contextlib import contextmanager
from ark_sim.contracts import thaw

def validate(cfg,components=None,definitions=None):
 if not isinstance(cfg,Mapping) or set(cfg)-{'mode','counts','duration_seconds','owned_abilities','retained_buffs','on_enter','completion_buffs'} or not {'mode','counts','duration_seconds','owned_abilities','retained_buffs','on_enter'}<=set(cfg) or cfg['mode']!='terminal_active':raise ValueError('Exact finite terminal_active spec required')
 counts=cfg['counts']
 if not isinstance(counts,(list,tuple)) or not counts or len(counts)>32 or any(type(x) is not int or x<=0 for x in counts) or len(set(counts))!=len(counts):raise ValueError('Terminal counts finite unique positive integers')
 duration=cfg['duration_seconds']
 if type(duration) not in (int,float) or not math.isfinite(duration) or not 0<duration<=86400:raise ValueError('Terminal duration finite bounded positive')
 for key in ('owned_abilities','retained_buffs'):
  ids=cfg[key]
  if not isinstance(ids,(list,tuple)) or len(ids)>32 or len(set(ids))!=len(ids) or any(type(x) is not str or not x for x in ids):raise ValueError('Terminal finite unique IDs required')
 if not cfg['owned_abilities']:raise ValueError('Terminal owned actions required')
 completion=cfg.get('completion_buffs',[])
 if not isinstance(completion,(list,tuple)) or any(type(x) is not str for x in completion) or len(set(completion))!=len(completion) or set(completion)-set(cfg['retained_buffs']):raise ValueError('Terminal completion Buffs require finite retained IDs')
 if components is not None and set(cfg['owned_abilities'])-set(components.get('abilities',[])):raise ValueError('Terminal actions must be own')
 if definitions is not None:
  for x in cfg['owned_abilities']:
   if definitions.get(x,{}).get('kind')!='ability' or definitions[x].get('activation',{}).get('mode')=='automatic_attack':raise ValueError('Terminal action requires owned nonordinary ability')
  for x in cfg['retained_buffs']:
   if definitions.get(x,{}).get('kind')!='buff':raise ValueError('Terminal retained Buff requires definition')
 from ark_sim.content.schemas import validate_effect,DEFAULT_CAPABILITIES
 if not isinstance(cfg['on_enter'],(list,tuple)):raise ValueError('Terminal on_enter effects required')
 for i,e in enumerate(cfg['on_enter']):validate_effect(e,'terminal.on_enter['+str(i)+']',DEFAULT_CAPABILITIES)

def cfg(ctx,ref):return ctx.get(ref,('rebirth','zero_restore_lifecycle'))
def stamp(ctx,ref):return {'life':ctx.get(ref,('runtime','lifecycle_generation'),0),'death':ctx.get(ref,('runtime','death_generation'),0)}
def valid(ctx,ref):
 spec=cfg(ctx,ref)
 if not spec or getattr(ctx,'rebirth',None) is None or not ctx.alive(ref) or ctx.state().get('finished'):return None
 state=ctx.rebirth._state(ref);row=state.get('terminal')
 if state.get('phase')!='terminal_active' or not isinstance(row,Mapping):return None
 if type(state.get('generation')) is not int or state['generation']<=0 or type(state.get('count')) is not int or state['count'] not in spec['counts']:return None
 if ctx.get(ref,('runtime','state'))!='terminal_active' or ctx.resources.current(ref,ctx.rebirth._spec(ref)['resource'])!=0:return None
 if row.get('generation')!=state['generation'] or row.get('incarnation')!=stamp(ctx,ref) or type(row.get('due_at')) is not int:return None
 if type(row.get('generation')) is not int or type(row.get('task')) is not int or row['task']<=0 or not isinstance(row.get('incarnation'),Mapping) or set(row['incarnation'])!={'life','death'} or any(type(x) is not int or x<0 for x in row['incarnation'].values()):return None
 job={'target':ref,'generation':state['generation']}
 pending=any(t['id']==row.get('task') and t['kind']=='domain.rebirth.terminal_end' and t['at']==row['due_at'] and t['payload']==job for t in ctx.session.scheduler.pending)
 task=ctx.session.current_task
 dispatched=task is not None and task['id']==row.get('task') and task['kind']=='domain.rebirth.terminal_end' and task['at']==row['due_at'] and task['payload']==job
 if not pending and not dispatched:return None
 return state,spec

@contextmanager
def entering(system,ref,generation):
 stack=getattr(system,'_terminal_entering',None)
 if stack is None:stack=[];system._terminal_entering=stack
 stack.append((ref,generation))
 try:yield
 finally:stack.pop()

def begin(system,ref,generation,spec,state):
 config=spec.get('zero_restore_lifecycle')
 if config is None or state['count'] not in config['counts']:return False
 validate(config,system.ctx.entity(ref)['components'],system.ctx.program.definitions);ctx=system.ctx
 if state['phase']!='completing' or ctx.resources.current(ref,spec['resource'])!=0 or not ctx.alive(ref):raise ValueError('Terminal requires exact actual zero restoration transition')
 now=ctx.session.time;due=now+ctx.quantize(config['duration_seconds']);job=ctx.session.schedule('domain.rebirth.terminal_end',{'target':ref,'generation':generation},due,phase=ctx.effect_phase)
 state.update(phase='terminal_active',task=None,terminal={'generation':generation,'incarnation':stamp(ctx,ref),'began_at':now,'due_at':due,'task':job});ctx.set(ref,('runtime','rebirth'),state);ctx.set(ref,('runtime','active'),True);ctx.set(ref,('runtime','state'),'terminal_active');ctx.emit('entity.terminal.started',{'target':ref,'generation':generation,'health':0,'due_at':due,'owned_abilities':list(config['owned_abilities'])})
 with entering(system,ref,generation):
  for effect in config['on_enter']:
   if valid(ctx,ref) is None:return True
   ctx.effects.execute(ref,[ref],thaw(effect))
 return True

def authorize(ctx,ref,ability,automatic):
 state=ctx.get(ref,('runtime','rebirth'),{})
 if state.get('phase')!='terminal_active':return None
 check=valid(ctx,ref)
 if check is None:raise ValueError('Invalid terminal lifecycle activity')
 state,spec=check
 if not automatic or ability not in spec['owned_abilities']:raise ValueError('Terminal activity requires finite owned internal action')
 authorized=(ref,state['generation']) in getattr(ctx.rebirth,'_terminal_entering',[]);task=ctx.session.current_task
 if not authorized and task is not None and task['kind']=='domain.buff.periodic':
  payload=task['payload'];inst=next((i for i in ctx.buffs._instances(ref) if i['id']==payload.get('instance')),None)
  authorized=inst is not None and buff_bound(ctx,ref,inst) and payload.get('target')==ref and type(payload.get('generation')) is int and inst['generation']==payload['generation'] and inst['tasks'].get('periodic')==task['id'] and inst['source']==ref and (inst['expires_at'] is None or ctx.session.time<inst['expires_at'])
 if not authorized:raise ValueError('Terminal action needs real internal callback/timer')
 return {'generation':state['generation'],'task':state['terminal']['task'],'incarnation':stamp(ctx,ref)}

def cast_valid(ctx,ref,cast):
 row=cast.get('terminal_lifecycle')
 if row is None:return ctx.get(ref,('runtime','rebirth','phase'))!='terminal_active'
 if not isinstance(row,Mapping) or type(row.get('generation')) is not int or type(row.get('task')) is not int or not isinstance(row.get('incarnation'),Mapping) or any(type(v) is not int for v in row['incarnation'].values()):return False
 check=valid(ctx,ref)
 if check is None:return False
 state,spec=check
 return cast['ability'] in spec['owned_abilities'] and row=={'generation':state['generation'],'task':state['terminal']['task'],'incarnation':stamp(ctx,ref)}

def end(system,session,payload):
 if not isinstance(payload,Mapping) or set(payload)!={'target','generation'} or type(payload['generation']) is not int:raise ValueError('Terminal end strict target/generation')
 with session.atomic():
  ref=session.world.resolve(payload['target']);check=valid(system.ctx,ref)
  if check is None:return
  state,spec=check
  if state['generation']!=payload['generation'] or session.time<state['terminal']['due_at']:return
  # Half-open removal uses the actual bound instance and normal on_remove path.
  # Run at the domain phase so callback events retain their original schedule contract.
  for inst in list(system.ctx.buffs._instances(ref)):
   if inst['definition'] in spec.get('completion_buffs',[]) and buff_bound(system.ctx,ref,inst) and type(inst.get('expires_at')) is int and session.time>=inst['expires_at']:
    system.ctx.buffs.remove(ref,inst['id'])
    if valid(system.ctx,ref) is None:return
  finish(system,ref,'deadline')

def finish(system,ref,reason):
 ctx=system.ctx;check=valid(ctx,ref)
 if check is None:return False
 state,_=check;job=state['terminal']['task']
 if job in {t['id'] for t in ctx.session.scheduler.pending}:ctx.session.cancel(job)
 state['phase']='terminal_complete';ctx.set(ref,('runtime','rebirth'),state);cause=ctx.emit('entity.terminal.completed',{'target':ref,'generation':state['generation'],'health':0,'reason':reason});ctx.lifecycle.retire(ref,'dead');ctx.lifecycle.claim_combat_kill(ref,thaw(state.get('cause',{})),cause)
 return True

def cancel(system,ref,reason):
 ctx=system.ctx;state=ctx.get(ref,('runtime','rebirth'),{})
 if state.get('phase')!='terminal_active':return False
 row=state.get('terminal',{});job=row.get('task')
 if job in {t['id'] for t in ctx.session.scheduler.pending}:ctx.session.cancel(job)
 state['phase']='terminal_cancelled';ctx.set(ref,('runtime','rebirth'),state);ctx.abilities.interrupt(ref,'terminal_cancelled');ctx.emit('entity.terminal.cancelled',{'target':ref,'generation':state.get('generation'),'reason':reason});return True

def issue_buff(ctx,inst):
 ref=inst['target'];check=valid(ctx,ref)
 if check is None or inst['source']!=ref:return
 state,spec=check
 if inst['definition'] not in spec['retained_buffs'] or (ref,state['generation']) not in getattr(ctx.rebirth,'_terminal_entering',[]):return
 state['terminal'].setdefault('buff_leases',{})[inst['id']]={'definition':inst['definition'],'generation':inst['generation'],'source':ref,'target':ref}
 ctx.set(ref,('runtime','rebirth'),state)

def buff_bound(ctx,ref,inst):
 check=valid(ctx,ref)
 if check is None:return False
 state,spec=check;row=state['terminal'].get('buff_leases',{}).get(inst['id'])
 if not isinstance(row,Mapping) or any(type(row.get(k)) is not int for k in ('generation','source','target')):return False
 return inst['definition'] in spec['retained_buffs'] and type(inst['generation']) is int and row=={'definition':inst['definition'],'generation':inst['generation'],'source':ref,'target':ref} and inst['source']==ref and inst['target']==ref

@contextmanager
def removing_buff(ctx,inst):
 if getattr(ctx,'rebirth',None) is None:
  yield
  return
 ref=inst['target'];check=valid(ctx,ref);authorized=check is not None and inst['definition'] in check[1].get('completion_buffs',[]) and buff_bound(ctx,ref,inst) and type(inst.get('expires_at')) is int and ctx.session.time>=inst['expires_at']
 stack=getattr(ctx.rebirth,'_terminal_removing',None)
 if stack is None:stack=[];ctx.rebirth._terminal_removing=stack
 # Every callback shadows the parent, even when this instance has no lease.
 stack.append((ref,check[0]['generation'] if check else None,inst['id'],inst['generation'],authorized))
 try:yield
 finally:stack.pop()

def source_finish_kill(system,source,target,options):
 ctx=system.ctx;check=valid(ctx,target)
 if check is None or source!=target or options.get('skip_rebirth') is not False:return False
 state,_=check
 stack=getattr(system,'_terminal_removing',[])
 if not stack:return False
 row=stack[-1]
 if row[4] is not True or row[0]!=target or type(row[1]) is not int or row[1]!=state['generation'] or type(row[3]) is not int:return False
 lease=state['terminal'].get('buff_leases',{}).get(row[2])
 if not isinstance(lease,Mapping) or type(lease.get('generation')) is not int or lease['generation']!=row[3] or lease.get('source')!=source or lease.get('target')!=target:return False
 return finish(system,target,'owned_buff_finished')
