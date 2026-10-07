"""Opt-in pure qualification of persisted Buff contributions."""
from ark_sim.contracts import Intent,thaw
from .selection import DEFAULT_STATE,project_state

class ApplicabilitySystem:
 def __init__(self,context,buffs):
  self.ctx,self.buffs=context,buffs;self.enabled=any(d.get('kind')=='buff' and (d.get('active_rule') or d.get('control_rule')) for d in context.program.definitions.values());self._busy=False;self._requested=False
 def active(self,instance):return instance.get('applicability',{}).get('active',True)
 def control(self,instance):return self.active(instance) and instance.get('applicability',{}).get('control',True)
 def _decision(self,owner,instance,key,status):
  definition=self.ctx.program.definitions[instance['definition']];rule=definition.get(key)
  if not rule:return True
  result=self.ctx.calc('buff.applicability',{'owner':self.ctx.entity(owner),'source':self.ctx.entity(instance['source']),'instance':instance,'status':status,'parameters':thaw(definition.get('parameters',{}))},owner=owner,source=instance['source'],target=owner,rule_id=rule,extra={'contribution':'active' if key=='active_rule' else 'control'})
  if type(result) is not bool:raise ValueError('buff applicability must return strict bool')
  return result
 def reconcile(self):
  if not self.enabled:return
  if self._busy:self._requested=True;return
  self._busy=True
  try:
   with self.ctx.session.atomic():
    budget=self.ctx.session.reaction_budget
    while True:
     self._requested=False;changed=False;affected=[];restart=False
     for entity in self.ctx.session.world.entities():
      owner=entity['id'];instances=self.buffs._instances(owner);status=project_state(self.ctx,owner,DEFAULT_STATE);replacement=[];updates=False;interrupt=False
      for captured in instances:
       definition=self.ctx.program.definitions[captured['definition']];current=thaw(captured)
       if definition.get('active_rule') or definition.get('control_rule'):
        active=self._decision(owner,current,'active_rule',status);control=active and self._decision(owner,current,'control_rule',status)
        state={'active':active,'control':control}
        if active!=self.active(current) and definition.get('movement_damage'):
         total=self.ctx.get(owner,('spatial','distance_travelled'),0)
         if total!=current.get('blackboard',{}).get('distance_cursor',total):
          # Settle old active tail or discard inactive travel BEFORE transition.
          # Callback may retire/remove; restart from actual World, never reinsert.
          self.buffs._flush_movement_damage(owner,current);restart=True;changed=True;break
        if state!=current.get('applicability'):
         if current.get('applicability') is not None and not self.control(current) and active and control and definition.get('control',{}).get('interrupt'):interrupt=True
         current['applicability']=state;updates=True
       replacement.append(current)
      if restart:break
      if updates:
       affected.append((owner,self.ctx.resources.capacity_snapshot(owner)))
       self.ctx.set(owner,('buffs','instances'),replacement);self.ctx.set(owner,('attributes','modifiers'),self.buffs._modifiers(owner,replacement));changed=True
       if interrupt:self.ctx.abilities.interrupt(owner,'buff_control_reactivated')
     for owner,before in affected:self.ctx.resources.sync_capacities(owner,before,'buff_applicability')
     if affected:
      self.ctx.spatial.blocking()
      # Actual aura/toggle passes may request further state stabilization.
      if not self.buffs._reconciling:self.buffs.reconcile()
     if not changed and not self._requested:break
     budget-=1
     if budget<=0:raise ValueError('buff applicability exceeds stabilization budget')
  finally:self._busy=False;self._requested=False
