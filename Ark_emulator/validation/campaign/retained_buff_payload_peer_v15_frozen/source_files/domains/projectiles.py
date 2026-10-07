"""Generic persistent projectiles/attachments, opt-in content only."""
import math
from ark_sim.contracts import thaw

class ProjectileSystem:
 def __init__(self,context):
  self.ctx=context
  self._inflight_hits={}
  self._impact_payload_scopes=[]
  self.handlers={'domain.projectile.step':self.step,'domain.projectile.expire':self.expire}
 def _state(self):return self.ctx.get('system/battle',('projectiles',),{'next_id':1,'instances':{}})
 def _save(self,state):self.ctx.set('system/battle',('projectiles',),state)
 def _put(self,instance):
  state=self._state();state['instances'][instance['id']]=instance;self._save(state)
 def _get(self,key):return self._state()['instances'].get(key)
 def completion_pending(self):
  return any(x['state']=='active' and self._definition(x).get('completion_blocking',False) for x in self._state()['instances'].values())
 def active_casts(self,source):
  return {x['cast'].get('id') for x in self._state()['instances'].values() if x['state']=='active' and x['source']==source and x['cast'].get('id')}
 def _trajectory_context(self,definition):
  if definition['motion'].get('parameters',{}).get('extent_policy')!='map_bounds':return {}
  grid=self.ctx.spatial.grid
  return {'projectile_map_bounds':{'min_row':-.5,'max_row':grid.rows-.5,'min_col':-.5,'max_col':grid.cols-.5}}
 def _collision_context(self,x,definition,candidates):
  params=thaw(definition['collision'].get('parameters',{}))
  if params.get('qualified_ray') is not True:return params
  from .selection import validate_eligibility
  validate_eligibility(params.get('eligibility'),'qualified projectile eligibility')
  defaults=params['eligibility']['parameters']['defaults']
  params['projectile_selection_states']={'source':self.ctx.spatial.selection_state(x['source'],defaults),'candidates':{str(e['id']):self.ctx.spatial.selection_state(e['id'],defaults) for e in candidates}}
  params['projectile_candidate_previous_positions']=thaw(x.get('candidate_previous_positions',{}))
  return params
 def _definition(self,instance):return self.ctx.program.definitions[instance['definition']]
 def _position(self,ref):return self.ctx.get(ref,('spatial','position'))
 def _valid_position(self,value):
  if not isinstance(value,dict) or not {'row','col'}<=set(value) or any(type(value[k]) not in (int,float) or not math.isfinite(value[k]) for k in ('row','col')):raise ValueError('projectile trajectory requires finite row/col')
  if 'height' in value and (type(value['height']) not in (int,float) or not math.isfinite(value['height'])):raise ValueError('invalid projectile height')
 def _schedule_step(self,x,when):
  job=self.ctx.session.schedule('domain.projectile.step',{'projectile':x['id']},when,phase=self.ctx.effect_phase);x['jobs'].append(job)
 def launch(self,source,target,effect,ability,cast,cause):
  with self.ctx.session.atomic():
   source=self.ctx.session.world.resolve(source);target=self.ctx.session.world.resolve(target);d=self.ctx.program.definitions[effect['projectile_definition']];a=self._position(source);b=self._position(target)
   self._valid_position(a);self._valid_position(b)
   state=self._state();key='projectile/'+str(state['next_id']);state['next_id']+=1
   packet=thaw(effect);packet.pop('projectile_definition');c=thaw(cast);c['projectile_impact']=True;c['launch_snapshot']=self.ctx.capture_view(source);c['launch_target_snapshots']={str(target):self.ctx.capture_view(target)}
   now=self.ctx.session.time;life=self.ctx.quantize(d['lifetime_seconds']);wait=ability.get('parameters',{}).get('wait_for_projectiles',False)
   if wait:self.ctx.abilities.projectile_started(source,c.get('id'))
   x={'id':key,'definition':d['id'],'source':source,'trace_target':target,'attachment_target':target,'position':b if d.get('attach_at_launch') else a,'start':a,'last_target':b,'previous_target':b,'born':now,'expires':now+life,'last_tick':now,'motion_state':{},'state':'active','jobs':[],'hit_targets':[],'hit_count':0,'cast':c,'ability':thaw(ability),'effect':packet,'cause':cause,'waiting_cast':wait}
   if d['collision'].get('parameters',{}).get('qualified_ray') is True:x['candidate_previous_positions']={str(e['id']):thaw(e['components']['spatial']['position']) for e in self.ctx.session.world.entities() if e['components'].get('spatial',{}).get('position') is not None}
   motion=d['motion'];plan=self.ctx.calc('projectile.trajectory',{'source':self.ctx.entity(source),'target':self.ctx.entity(target),'positions':[{'position':x['position'],'start':x['start'],'last_target':x['last_target'],'motion_state':{}}],'trajectory_parameters':{**thaw(motion.get('parameters',{})),'age_seconds':0,'delta_seconds':0,'lifetime_seconds':d['lifetime_seconds']}},source=source,target=target,rule_id=motion['rule'],extra=self._trajectory_context(d));self._valid_position(plan.get('position'));x['position']=plan['position'];x['motion_state']=plan.get('motion_state',{})
   x['jobs'].append(self.ctx.session.schedule('domain.projectile.expire',{'projectile':key},x['expires'],phase=self.ctx.effect_phase));self._schedule_step(x,now+1);state['instances'][key]=x;self._save(state)
   self.ctx.emit('projectile.launched',{'projectile':key,'definition':d['id'],'source':source,'target':target,'attachment_target':target,'ability':ability.get('id'),'position':x['position'],'expires':x['expires']},cause)
   return key
 def _invalid_policy(self,x,d):
  policies=d['lifecycle']
  if not self.ctx.alive(x['source']) and policies['source_invalid']=='cancel':return 'source_invalid'
  if self.ctx.route_hidden(x['source']) and policies['source_hidden']=='cancel':return 'source_hidden'
  if not self.ctx.alive(x['trace_target']) and policies['target_invalid']=='cancel':return 'target_invalid'
  if self.ctx.route_hidden(x['trace_target']) and policies['target_hidden']=='cancel':return 'target_hidden'
  return None
 def _target_available(self,x):return self.ctx.alive(x['trace_target']) and self.ctx.selectable(x['trace_target']) and self.ctx.effect_target_available(x['trace_target'])
 def _quota_exhausted(self,x,d,reserved=0):
  count=x['hit_count']+reserved
  return (d['stop_after_first'] and count>=1) or (d['max_hits'] is not None and count>=d['max_hits'])
 def _hit(self,x,d,target=None,finish_reason='max_hit'):
  target=x['trace_target'] if target is None else target
  target=self.ctx.session.world.resolve(target)
  latest=self._get(x['id'])
  if not latest or latest['state']!='active':return False
  reservations=self._inflight_hits.get(x['id'],[])
  if self._quota_exhausted(latest,d,len(reservations)) or (not d['can_hit_same_target'] and (target in latest['hit_targets'] or target in reservations)):return False
  if (not self.ctx.alive(target) or not self.ctx.selectable(target) or not self.ctx.effect_target_available(target)) and latest['effect']['op']!='area':return False
  # Reserve only call-stack quota. Packet input snapshots and public count retain
  # their former ordering; a failed outer atomic operation rolls back all writes.
  self._inflight_hits.setdefault(x['id'],[]).append(target)
  try:
   effect=thaw(latest['effect'])
   if effect['op']=='area':effect['center_position']={k:latest['position'][k] for k in ('row','col')}
   scope={'projectile':latest['id'],'source':latest['source'],'target':target,'cast':latest['cast'],
          'source_identity':self.payload_incarnation(latest['source']),'target_identity':self.payload_incarnation(target),
          'time':self.ctx.session.time,'active_key':self.ctx.session._active_key}
   self._impact_payload_scopes.append(scope)
   try:self.ctx.effects.execute(latest['source'],[target],effect,latest['ability'],latest['cast'],latest['cause'])
   finally:self._impact_payload_scopes.pop()
   current=self._get(x['id'])
   if current is None:
    # An external lifecycle may remove an instance. Never recreate it from a
    # captured local record, even though this packet already dispatched.
    x['state']='invalid';return True
   current['hit_targets'].append(target);current['hit_count']+=1;self._put(current)
   x.clear();x.update(current)
   self.ctx.emit('projectile.hit',{'projectile':x['id'],'source':x['source'],'target':target,'position':x['position'],'hit_count':x['hit_count']})
   if x['state']=='active' and (d['stop_after_first'] or (d['stop_after_max'] and d['max_hits'] is not None and x['hit_count']>=d['max_hits'])):self._finish(x,finish_reason)
   return True
  finally:
   pending=self._inflight_hits[x['id']];pending.remove(target)
   if not pending:del self._inflight_hits[x['id']]
 def payload_incarnation(self,ref):
  return (self.ctx.alive(ref),self.ctx.active(ref),self.ctx.get(ref,("runtime","state")),self.ctx.get(ref,("runtime","death_generation"),0),self.ctx.get(ref,("runtime","lifecycle_generation"),0))
 def retained_payload_allowed(self,source,target,cast):
  # A public effect cannot acquire this call-stack authority by forging cast JSON.
  for scope in reversed(self._impact_payload_scopes):
   if scope['source']!=source or scope['target']!=target or cast is not scope['cast']:continue
   current=self._get(scope['projectile'])
   if not current or current['state']!='active' or current['source']!=source:continue
   if target not in self._inflight_hits.get(scope['projectile'],[]):continue
   if not self.ctx.active(source) and self._definition(current)['lifecycle']['source_invalid']!='retain':continue
   if self.payload_incarnation(source)!=scope['source_identity'] or self.payload_incarnation(target)!=scope['target_identity']:continue
   if self.ctx.session.time!=scope['time'] or self.ctx.session._active_key!=scope['active_key']:continue
   return True
  if any(cast is scope['cast'] and source==scope['source'] and target==scope['target'] for scope in self._impact_payload_scopes):return False
  return None
 def _finish(self,x,reason,callbacks=True):
  if not x or x['state']!='active':return
  d=self._definition(x);x['state']='invalid';x['reason']=reason;self._put(x)
  pending={t['id'] for t in self.ctx.session.scheduler.pending}
  for job in x['jobs']:
   if job in pending:self.ctx.session.cancel(job)
  x['jobs']=[];self._put(x)
  self.ctx.emit('projectile.invalid',{'projectile':x['id'],'source':x['source'],'target':x['trace_target'],'reason':reason,'position':x['position']})
  if callbacks:
   for e in d.get('on_invalid',[]):self.ctx.effects.execute(x['source'],[x['trace_target']],thaw(e),x['ability'],x['cast'],x['cause'])
  if x['waiting_cast']:self.ctx.abilities.projectile_finished(x['source'],x['cast'].get('id'))
  # Retain compact identity/history, not recursive actor/cast snapshots.
  for field in ('cast','ability','effect'):x.pop(field,None)
  self._put(x)
 def step(self,session,payload):
  with session.atomic():
   x=self._get(payload['projectile'])
   if x and x['state']=='active':x['jobs']=[job for job in x['jobs'] if job in {t['id'] for t in session.scheduler.pending}]
   if not x or x['state']!='active':return
   if self.ctx.state().get('finished'):self._finish(x,'battle_terminal',False);return
   d=self._definition(x);invalid=self._invalid_policy(x,d)
   if invalid:self._finish(x,invalid);return
   if session.time>=x['expires']:return
   previous=thaw(x['position']);previous_target=thaw(x['previous_target']);available=self._target_available(x)
   if available:x['last_target']=self._position(x['trace_target'])
   motion=d['motion'];params={**thaw(motion.get('parameters',{})),'age_seconds':(session.time-x['born'])*session.quantum,'delta_seconds':(session.time-x['last_tick'])*session.quantum,'lifetime_seconds':d['lifetime_seconds']}
   plan=self.ctx.calc('projectile.trajectory',{'source':self.ctx.entity(x['source']),'target':self.ctx.entity(x['trace_target']),'positions':[{'position':x['position'],'start':x['start'],'last_target':x['last_target'],'motion_state':x['motion_state']}],'trajectory_parameters':params},source=x['source'],target=x['trace_target'],rule_id=motion['rule'],extra=self._trajectory_context(d))
   self._valid_position(plan.get('position'));assert type(plan.get('reached')) is bool,'projectile reached must be boolean'
   x['position']=plan['position'];x['motion_state']=plan.get('motion_state',{});x['last_tick']=session.time;x['previous_target']=x['last_target'];self._put(x)
   collision=d['collision'];data={'previous_position':previous,'position':x['position'],'previous_target_position':previous_target,'target_position':x['last_target'],'trace_target':x['trace_target'],'target_available':available}
   candidates=[entity for entity in self.ctx.session.world.entities() if entity['components'].get('spatial',{}).get('position') is not None]
   if collision.get('parameters',{}).get('qualified_ray') is True:candidates=[e for e in candidates if self.ctx.alive(e['id']) and self.ctx.selectable(e['id']) and self.ctx.effect_target_available(e['id'])]
   result=self.ctx.calc('projectile.collision',{'projectile':data,'entities':candidates,'spatial_state':{'map':self.ctx.spatial.map_definition,'parameters':thaw(collision.get('parameters',{}))}},source=x['source'],target=x['trace_target'],rule_id=collision['rule'],extra=self._collision_context(x,d,candidates))
   if not isinstance(result,dict) or type(result.get('stop')) is not bool or type(result.get('terrain_hit')) is not bool or not isinstance(result.get('hits'),list):raise ValueError('invalid projectile collision plan')
   if collision.get('parameters',{}).get('qualified_ray') is True:
    x['candidate_previous_positions']={str(e['id']):thaw(e['components']['spatial']['position']) for e in self.ctx.session.world.entities() if e['components'].get('spatial',{}).get('position') is not None};self._put(x)
   hits=[self.ctx.session.world.resolve(ref) for ref in result['hits']]
   if not collision.get('allow_other_targets',False) and any(ref!=x['trace_target'] for ref in hits):raise ValueError('collision profile hit outside captured trace target')
   for hit in hits:
    self._hit(x,d,hit,finish_reason=('terrain_collision' if result['terrain_hit'] else 'collision_stop') if result['stop'] else 'max_hit')
    if x['state']!='active':return
   if result['stop']:self._finish(x,'terrain_collision' if result['terrain_hit'] else 'collision_stop');return
   if x['hit_count'] and (d['stop_after_first'] or (d['stop_after_max'] and d['max_hits'] is not None and x['hit_count']>=d['max_hits'])):self._finish(x,'max_hit');return
   if plan['reached']:
    self.ctx.emit('projectile.reached',{'projectile':x['id'],'position':x['position']})
    if d['lifecycle']['hit_on_reach']:
     self._hit(x,d)
     if x['state']!='active':return
    if d['lifecycle']['finish_on_reach']:self._finish(x,'reached');return
   self._schedule_step(x,session.time+1);self._put(x)
 def expire(self,session,payload):
  with session.atomic():
   x=self._get(payload['projectile'])
   if x and x['state']=='active':x['jobs']=[job for job in x['jobs'] if job in {t['id'] for t in session.scheduler.pending}]
   if not x or x['state']!='active':return
   if self.ctx.state().get('finished'):self._finish(x,'battle_terminal',False);return
   d=self._definition(x);invalid=self._invalid_policy(x,d)
   if invalid:self._finish(x,invalid);return
   if self._target_available(x):
    x['last_target']=self._position(x['trace_target'])
    # Follow/fixed placement at expiry is evaluated by the same pure motion.
    motion=d['motion'];plan=self.ctx.calc('projectile.trajectory',{'source':self.ctx.entity(x['source']),'target':self.ctx.entity(x['trace_target']),'positions':[{'position':x['position'],'start':x['start'],'last_target':x['last_target'],'motion_state':x['motion_state']}],'trajectory_parameters':{**thaw(motion.get('parameters',{})),'age_seconds':(session.time-x['born'])*session.quantum,'delta_seconds':0,'lifetime_seconds':d['lifetime_seconds']}},source=x['source'],target=x['trace_target'],rule_id=motion['rule'],extra=self._trajectory_context(d));self._valid_position(plan['position']);x['position']=plan['position']
   if d['lifecycle']['force_reach_on_expire']:self.ctx.emit('projectile.reached',{'projectile':x['id'],'position':x['position'],'expiry':True})
   if d['lifecycle']['hit_on_expire']:
    self._hit(x,d,finish_reason='expired')
    if x['state']!='active':return
   self._finish(x,'expired')
 def tick(self,session):
  if not self.ctx.state().get('finished'):return
  with session.atomic():
   for x in list(self._state()['instances'].values()):
    if x['state']=='active':self._finish(x,'battle_terminal',False)
