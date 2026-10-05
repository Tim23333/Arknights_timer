"""Opt-in delayed health depletion lifecycle, persistent same-actor recovery."""
from collections.abc import Mapping
import math
from ark_sim.contracts import thaw
from .rebirth_self_buffs import finish_scope

FIELDS={'on_skip','skip_rule','zero_restore_lifecycle','waiting_actions','resource','max_count','delay_seconds','restore_ratio','restore_rule','parameters','retain_buffs','on_begin','on_finish','reset_cooldowns','reset_attack_clock'}
def validate_kill(options):
 if not isinstance(options,Mapping) or set(options) not in ({'cause','skip_rebirth'},{'cause','skip_rebirth','source_policy','origin'}) or not isinstance(options['cause'],str) or not options['cause'] or not options['cause'].replace('_','').replace('-','').isalnum() or type(options['skip_rebirth']) is not bool:raise ValueError('instant kill requires event-safe cause/explicit skip_rebirth bool')
 if 'source_policy' in options and (options['source_policy']!='none' or not isinstance(options['origin'],Mapping) or not options['origin']):raise ValueError('No-source instant kill requires explicit none policy and origin')
def validate(spec,components=None,definitions=None):
 if not isinstance(spec,Mapping) or set(spec)-FIELDS or not {'resource','max_count','delay_seconds','restore_ratio','restore_rule'}<=set(spec):raise ValueError('rebirth requires exact resource/count/delay/ratio/restore_rule')
 for key in ('resource','restore_rule'):
  if not isinstance(spec[key],str) or not spec[key]:raise ValueError('rebirth '+key+' must be nonempty string')
 if type(spec['max_count']) is not int or not 0<=spec['max_count']<=100000:raise ValueError('rebirth max_count must be bounded nonnegative integer')
 for key in ('delay_seconds','restore_ratio'):
  v=spec[key]
  if type(v) not in (int,float) or not math.isfinite(v) or v<0 or (key=='restore_ratio' and v==0):raise ValueError('rebirth finite delay>=0/ratio>0 required')
 if 'skip_rule' in spec and (not isinstance(spec['skip_rule'],str) or not spec['skip_rule']):raise ValueError('rebirth skip_rule must be nonempty reference')
 if not isinstance(spec.get('parameters',{}),Mapping):raise ValueError('rebirth parameters record required')
 retained=spec.get('retain_buffs',[])
 if not isinstance(retained,(list,tuple)) or any(not isinstance(x,str) or not x for x in retained) or len(set(retained))!=len(retained):raise ValueError('rebirth retained Buff IDs must be unique')
 if 'reset_attack_clock' in spec and type(spec['reset_attack_clock']) is not bool:raise ValueError('rebirth attack clock policy must be bool')
 resets=spec.get('reset_cooldowns',[])
 if not isinstance(resets,(list,tuple)):raise ValueError('rebirth cooldown resets list required')
 seen=set()
 for row in resets:
  if not isinstance(row,Mapping) or set(row)!={'ability','initial_delay_seconds'} or not isinstance(row['ability'],str) or not row['ability'] or row['ability'] in seen:raise ValueError('rebirth unique ability cooldown reset required')
  seen.add(row['ability']);delay=row['initial_delay_seconds']
  if type(delay) not in (int,float) or not math.isfinite(delay) or delay<0:raise ValueError('rebirth cooldown delay must be finite nonnegative')
 for key in ('on_begin','on_finish','on_skip'):
  if not isinstance(spec.get(key,[]),(list,tuple)):raise ValueError('rebirth '+key+' effect list required')
  from ..content.schemas import validate_effect,DEFAULT_CAPABILITIES
  for i,effect in enumerate(spec.get(key,[])):validate_effect(effect,'rebirth.'+key+'['+str(i)+']',DEFAULT_CAPABILITIES)
 if components is not None:
  resources=components.get('resources',{});health=resources.get(spec['resource'])
  if not isinstance(health,Mapping) or health.get('role')!='health':raise ValueError('rebirth resource must be own declared health resource')
  if type(health.get('initial')) not in (int,float) or health['initial']<=0:raise ValueError('rebirth requires positive initial health')
  if not components.get('lifecycle',{}).get('policy'):raise ValueError('rebirth requires explicit lifecycle policy')
  if seen-set(components.get('abilities',[])):raise ValueError('rebirth cooldown must reference exact owned ability')
 if 'zero_restore_lifecycle' in spec:
  from .terminal_lifecycle import validate as terminal_validate
  terminal_validate(spec['zero_restore_lifecycle'],components,definitions)
  if any(x>spec['max_count'] for x in spec['zero_restore_lifecycle']['counts']):raise ValueError('Terminal count exceeds max rebirth count')
  if set(spec['zero_restore_lifecycle']['retained_buffs'])-set(retained):raise ValueError('Terminal callbacks require declared rebirth retained Buffs')
 if 'waiting_actions' in spec:
  w=spec['waiting_actions']
  if not isinstance(w,Mapping) or set(w)!={'abilities','buffs'}:raise ValueError('waiting_actions finite abilities/buffs required')
  for key in ('abilities','buffs'):
   if not isinstance(w[key],(list,tuple)) or not w[key] or len(w[key])>32 or len(set(w[key]))!=len(w[key]) or any(not isinstance(x,str) or not x for x in w[key]):raise ValueError('waiting_actions finite unique owned IDs required')
  if components is not None and set(w['abilities'])-set(components.get('abilities',[])):raise ValueError('waiting action must be exact owned ability')
  if set(w['buffs'])-set(spec.get('retain_buffs',[])):raise ValueError('waiting actions require declared retained Buffs')
 if definitions is not None:
  if 'waiting_actions' in spec:
   for ident in spec['waiting_actions']['abilities']:
    a=definitions.get(ident,{})
    if a.get('kind')!='ability' or a.get('activation',{}).get('mode')!='manual' or a.get('activation',{}).get('parameters',{}).get('auto_only') is not True:raise ValueError('waiting action must declare manual auto_only ability')
   if any(definitions.get(ident,{}).get('kind')!='buff' for ident in spec['waiting_actions']['buffs']):raise ValueError('waiting action Buff kind required')
  if 'skip_rule' in spec:
   skip=definitions.get(spec['skip_rule'],{})
   if skip.get('kind') not in ('rule','calculation_rule') or skip.get('contract')!='lifecycle.rebirth_skip':raise ValueError('rebirth skip_rule requires strict lifecycle.rebirth_skip rule')
  rule=definitions.get(spec['restore_rule'])
  if not rule or rule.get('kind') not in ('rule','calculation_rule') or rule.get('contract')!='resource.recovery':raise ValueError('rebirth restore_rule must implement resource.recovery')
  if any(definitions.get(x,{}).get('kind')!='buff' for x in retained):raise ValueError('rebirth retained reference must be Buff')
  if any(definitions.get(x,{}).get('kind')!='ability' for x in seen):raise ValueError('rebirth cooldown reference must be ability')

class RebirthSystem:
 def __init__(self,context):
  self.ctx=context;self._skip_entering=set();self._requests={};self._callbacks=[];self._settling=False;self._aura_waiting_begins=[]
  self.handlers={'domain.rebirth.finish':self.finish,'domain.rebirth.terminal_end':self.terminal_end}
 def _spec(self,ref):return self.ctx.get(ref,('rebirth',))
 def _state(self,ref):return self.ctx.get(ref,('runtime','rebirth'),{})
 def _same(self,ref,generation,phase):
  return self.ctx.alive(ref) and self._state(ref).get('generation')==generation and self._state(ref).get('phase')==phase
 def effect_allowed(self,target):
  return bool(self._callbacks and self._callbacks[-1][0]==target and self._same(target,self._callbacks[-1][1],self._callbacks[-1][2]))
 def callback_allowed(self):
  return not self._callbacks or (not self.ctx.state().get('finished') and self._same(*self._callbacks[-1]))
 def settle_callback(self,operation):
  if self._callbacks and operation!='emit' and not self._settling and not self.ctx.state().get('finished'):
   self._settling=True
   try:self.ctx.lifecycle.tick(self.ctx.session)
   finally:self._settling=False
 def cancel_all(self,reason):
  for entity in self.ctx.session.world.entities():self.cancel(entity['id'],reason)
 def _effects(self,ref,generation,phase,effects):
  self._callbacks.append((ref,generation,phase))
  try:
   for effect in effects:
    if not self._same(ref,generation,phase) or self.ctx.state().get('finished'):return
    self.ctx.effects.execute(ref,[ref],thaw(effect))
    self.settle_callback(effect['op'])
  finally:self._callbacks.pop()
 def aura_waiting_parent_available(self,ref,parent):
  if not self.ctx.alive(ref) or self.ctx.state().get('finished') or self._state(ref).get('phase')!='waiting':return False
  spec=self._spec(ref)
  if not spec or self.ctx.resources.current(ref,spec['resource'])!=0 or parent.get('target')!=ref or parent['definition'] not in spec.get('retain_buffs',[]):return False
  current=next((i for i in self.ctx.buffs._instances(ref) if i['id']==parent['id']),None)
  if current is None or current['generation']!=parent['generation'] or current['source']!=parent['source']:return False
  for frame in reversed(self._aura_waiting_begins):
   row=frame['parents'].get(parent['id'])
   if frame['actor']==ref and frame['generation']==self._state(ref).get('generation') and row and row['definition']==parent['definition'] and row['target']==ref and row['source']==parent['source'] and row['generation']<=parent['generation']:return True
  state=self._state(ref)
  return any(job['id']==state.get('task') and job['kind']=='domain.rebirth.finish' and job['payload'].get('target')==ref and job['payload'].get('generation')==state.get('generation') and job['at']==state.get('due_at') for job in self.ctx.session.scheduler.pending)
 def consume(self,ref,event):
  spec=self._spec(ref) or {};retained=set(spec.get('retain_buffs',[]))
  frame={'actor':ref,'generation':self._state(ref).get('generation',0)+1,'parents':{i['id']:{k:i[k] for k in ('definition','target','source','generation')} for i in self.ctx.buffs._instances(ref) if i['definition'] in retained}}
  self._aura_waiting_begins.append(frame)
  try:return self._consume(ref,event)
  finally:self._aura_waiting_begins.pop()
 def _consume(self,ref,event):
  if ref in self._skip_entering:return True
  request=self._requests.get(ref,[]);request=request[-1] if request else {}
  if request.get('skip_rebirth'):
   self.ctx.lifecycle.retire(ref,'dead');return True
  spec=self._spec(ref)
  if spec is None:return False
  if self._state(ref).get('phase')=='terminal_active':
   from .terminal_lifecycle import valid
   if valid(self.ctx,ref) is not None:return True
  if self._state(ref).get('phase')=='waiting':return True
  if self.ctx.resources.current(ref,spec['resource'])>0:return False
  if request.get('skip_rebirth') or self.ctx.get(ref,('runtime','initializing'),False):return False
  if spec.get('skip_rule'):
   source=event.get('source')
   actor=self.ctx.entity(source) if source is not None else {}
   result=self.ctx.calc('lifecycle.rebirth_skip',{'clock':{'time':self.ctx.session.time},'source':actor,'target':self.ctx.entity(ref),'depletion_event':thaw(event)},source=source,target=ref,owner=ref,rule_id=spec['skip_rule'])
   if type(result) is not bool:raise ValueError('rebirth skip_rule must return strict bool')
   if result:
    self._skip_entering.add(ref)
    try:
     for effect in spec.get('on_skip',[]):
      if not self.ctx.alive(ref):break
      self.ctx.effects.execute(ref,[ref],thaw(effect))
     self.ctx.emit('entity.rebirth.skipped',{'source':source,'target':ref,'rule':spec['skip_rule']})
    finally:self._skip_entering.remove(ref)
    return False
  old=self._state(ref)
  if old.get('count',0)>=spec['max_count'] or not self.ctx.alive(ref) or self.ctx.state().get('finished'):return False
  with self.ctx.session.atomic():
   now=self.ctx.session.time;generation=old.get('generation',0)+1;due=now+self.ctx.quantize(spec['delay_seconds'])
   state={'phase':'waiting','count':old.get('count',0)+1,'generation':generation,'began_at':now,'due_at':due,'task':None,'cause':thaw(request or event)}
   self.ctx.set(ref,('runtime','rebirth'),state);self.ctx.set(ref,('runtime','active'),False);self.ctx.set(ref,('runtime','state'),'rebirth')
   self.ctx.abilities.interrupt(ref,'rebirth');self.ctx.set(ref,('runtime','blocked_by'),None)
   self._callbacks.append((ref,generation,'waiting'))
   try:
    for instance in list(self.ctx.buffs._instances(ref)):
     if not self._same(ref,generation,'waiting'):return True
     if instance['definition'] not in spec.get('retain_buffs',[]):
      from .shared_auras import retained_waiting_self_child
      if not retained_waiting_self_child(self.ctx.buffs,ref,instance):self.ctx.buffs.remove(ref,instance['id'])
   finally:self._callbacks.pop()
   self.ctx.spatial.blocking();self.ctx.buffs.reconcile()
   self.ctx.emit('entity.rebirth.started',{'source':ref,'target':ref,'generation':generation,'count':state['count'],'due_at':due,'health':0,'cause':state['cause']})
   self._effects(ref,generation,'waiting',spec.get('on_begin',[]))
   if not self._same(ref,generation,'waiting'):return True
   if self.ctx.state().get('finished'):self.cancel(ref,'battle_terminal');return True
   if self.ctx.resources.current(ref,spec['resource'])!=0:raise ValueError('rebirth pending phase must retain zero health')
   if due==now:self.finish(self.ctx.session,{'target':ref,'generation':generation})
   else:
    job=self.ctx.session.schedule('domain.rebirth.finish',{'target':ref,'generation':generation},due,phase=0);state=self._state(ref);state['task']=job;self.ctx.set(ref,('runtime','rebirth'),state)
   return True
 def terminal_end(self,session,payload):
  from .terminal_lifecycle import end
  return end(self,session,payload)
 def cancel(self,ref,reason):
  from .terminal_lifecycle import cancel as terminal_cancel
  if terminal_cancel(self,ref,reason):return
  state=self._state(ref)
  if state.get('phase') not in ('waiting','completing'):return
  self.ctx.waiting_actions.cancel_casts(ref,'waiting_cancelled')
  task=state.get('task');pending={t['id'] for t in self.ctx.session.scheduler.pending}
  if task in pending:self.ctx.session.cancel(task)
  state.update(phase='cancelled',task=None,reason=reason);self.ctx.set(ref,('runtime','rebirth'),state)
  self.ctx.emit('entity.rebirth.cancelled',{'source':ref,'target':ref,'generation':state['generation'],'reason':reason})
 @finish_scope
 def finish(self,session,payload):
  if not isinstance(payload,Mapping) or set(payload)!={'target','generation'} or type(payload['generation']) is not int or payload['generation']<=0:raise ValueError('rebirth finish requires exact target/positive integer generation')
  with session.atomic():
   ref=session.world.resolve(payload['target']);generation=payload['generation']
   if not self._same(ref,generation,'waiting'):return
   if session.time<self._state(ref)['due_at']:return
   if self.ctx.state().get('finished'):self.cancel(ref,'battle_terminal');return
   spec=self._spec(ref);state=self._state(ref);task=state.get('task')
   if task in {t['id'] for t in session.scheduler.pending}:session.cancel(task)
   self.ctx.waiting_actions.cancel_casts(ref,'waiting_completed')
   state.update(phase='completing',task=None);self.ctx.set(ref,('runtime','rebirth'),state)
   capacity=self.ctx.resources.capacity(ref,spec['resource']);parameters={**thaw(spec.get('parameters',{})),'capacity':capacity,'ratio':spec['restore_ratio']}
   value=self.ctx.calc('resource.recovery',{'current':0,'delta_seconds':0,'attributes':self.ctx.attributes.values(ref),'parameters':parameters},owner=ref,source=ref,target=ref,rule_id=spec['restore_rule'],extra={'rebirth':state})
   if type(value) in (int,float) and value==0:
    from .terminal_lifecycle import begin
    if begin(self,ref,generation,spec,state):return
   if type(value) not in (int,float) or not math.isfinite(value) or value<=0:raise ValueError('rebirth restoration must be positive finite')
   self.ctx.resources.adjust(ref,spec['resource'],value=value,source=ref)
   if not self._same(ref,generation,'completing'):return
   if self.ctx.resources.current(ref,spec['resource'])<=0:raise ValueError('rebirth bounds prevented positive restoration')
   self.ctx.set(ref,('runtime','active'),True);self.ctx.set(ref,('runtime','state'),'alive')
   if spec.get('reset_cooldowns'):
    clocks=self.ctx.get(ref,('runtime','cooldowns'),{})
    for row in spec['reset_cooldowns']:clocks[row['ability']]=session.time+self.ctx.quantize(row['initial_delay_seconds'])
    self.ctx.set(ref,('runtime','cooldowns'),clocks)
   if spec.get('reset_attack_clock'):self.ctx.set(ref,('runtime','next_attack'),session.time)
   self._effects(ref,generation,'completing',spec.get('on_finish',[]))
   if not self._same(ref,generation,'completing'):return
   if self.ctx.state().get('finished'):self.cancel(ref,'battle_terminal');return
   state=self._state(ref);state['phase']='complete';self.ctx.set(ref,('runtime','rebirth'),state)
   self.ctx.spatial.blocking();self.ctx.buffs.reconcile()
   if not self.ctx.alive(ref):return
   if getattr(self.ctx,'tile_contacts',None) is not None:self.ctx.tile_contacts.inspect(ref,'rebirth')
   if not self.ctx.alive(ref):return
   self.ctx.emit('entity.rebirth.completed',{'source':ref,'target':ref,'generation':generation,'count':state['count'],'health':self.ctx.resources.current(ref,spec['resource'])})
 def tick(self,session):
  for entity in session.world.entities():
   state=self._state(entity['id'])
   if state.get('phase')=='waiting':
    if self.ctx.state().get('finished'):self.cancel(entity['id'],'battle_terminal')
    elif session.time>=state['due_at']:self.finish(session,{'target':entity['id'],'generation':state['generation']})
 def instant_kill(self,source,target,options,ability=None,cast=None,cause=None):
  validate_kill(options)
  source=self.ctx.session.world.resolve(source);target=self.ctx.session.world.resolve(target)
  owner_source=source
  if options.get('source_policy')=='none':source=None
  if getattr(self.ctx,'depletion',None) is not None and self.ctx.depletion.depleted(target) and self.ctx.depletion.callback_cast_allowed(target,cast):
   if owner_source!=target:raise ValueError('Owned depleted finish must target its callback owner')
   self.ctx.depletion.cancel(target,'owned_finish');self.ctx.lifecycle.retire(target,'dead')
   self.ctx.emit('instant_kill.executed',{'source':source,'target':target,'cause':options['cause'],'skip_rebirth':options['skip_rebirth'],'origin':thaw(options.get('origin',{})),'alive':False,'ability':(ability or {}).get('id')},cause);return
  from .terminal_lifecycle import source_finish_kill
  if source_finish_kill(self,source,target,options):return
  if target==self.ctx.session.world.resolve('system/battle'):raise ValueError('instant kill cannot target battle')
  resources=self.ctx.get(target,('resources',),{});health=[k for k,v in resources.items() if v['spec'].get('role')=='health']
  if len(health)!=1:raise ValueError('instant kill requires one declared health resource')
  if not self.ctx.get(target,('lifecycle','policy')):raise ValueError('instant kill requires declared lifecycle policy')
  if not self.ctx.alive(target):return
  death_generation=self.ctx.get(target,('runtime','death_generation'),0)
  pending=self._state(target).get('phase')=='waiting'
  if not self.ctx.active(target) and not pending:raise ValueError('instant kill cannot target dormant actor')
  request={'source':source,'target':target,'cause':options['cause'],'skip_rebirth':options['skip_rebirth']};self._requests.setdefault(target,[]).append(request)
  try:
   if pending:
    if options['skip_rebirth']:self.ctx.lifecycle.retire(target,'dead')
    else:self.ctx.emit('instant_kill.rejected',{**request,'reason':'rebirth_pending'});return
   else:
    self.ctx.resources.adjust(target,health[0],value=0,source=source,ability=ability,effect={'op':'instant_kill','parameters':options})
    if self.ctx.resources.current(target,health[0])!=0:raise ValueError('instant kill bounds prevented zero health')
   self.ctx.emit('instant_kill.executed',{**request,'alive':self.ctx.alive(target),'ability':(ability or {}).get('id')},cause)
   if not self.ctx.alive(target):self.ctx.lifecycle.claim_combat_kill(target,{'source':source,'target':target,'ability':(ability or {}).get('id'),'cast':(cast or {}).get('id'),'target_tags':list(self.ctx.entity(target)['tags'])},cause,generation=death_generation+1)
  finally:
   self._requests[target].pop()
   if not self._requests[target]:del self._requests[target]
