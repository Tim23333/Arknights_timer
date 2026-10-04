"""Owned conditional Buff children and logical restore deadlines."""
from collections.abc import Mapping
from ark_sim.contracts import thaw
from ark_sim.rules.expressions import evaluate_expression

def validate(spec,path='toggle'):
    if not isinstance(spec,Mapping) or set(spec)-{'rule','buff','initial_enabled','restore_delay_seconds','events','parameters'}:
        raise ValueError(path+': unknown toggle fields')
    if not all(isinstance(spec.get(k),str) and spec[k] for k in ('rule','buff')) or type(spec.get('initial_enabled')) is not bool:
        raise ValueError(path+': rule/buff and initial bool required')
    import math
    delay=spec.get('restore_delay_seconds')
    if type(delay) not in (int,float) or not math.isfinite(delay) or delay<0:raise ValueError(path+': finite nonnegative restore delay required')
    if not isinstance(spec.get('parameters',{}),Mapping):raise ValueError(path+': parameters record required')
    events=spec.get('events',[])
    if not isinstance(events,(list,tuple)):raise ValueError(path+': events list required')
    for event in events:
        if not isinstance(event,Mapping) or set(event)-{'event','owner_role','condition'} or not isinstance(event.get('event'),str) or not event['event'] or event.get('owner_role') not in {'source','target'}:
            raise ValueError(path+': explicit event/owner_role required')
        if 'condition' in event:
            from ark_sim.rules.expressions import Expression
            Expression(event['condition'])

class ToggleSystem:
    def __init__(self,ctx,buffs):
        self.ctx,self.buffs=ctx,buffs
        self.enabled=any(d.get('kind')=='buff' and d.get('toggle') for d in ctx.program.definitions.values())
        self._busy=False;self._requested=False;self._removing=set()
    def _current(self,owner,uid):return next((i for i in self.buffs._instances(owner) if i['id']==uid),None)
    def _write(self,owner,instance,state):
        current=self._current(owner,instance['id'])
        if current is None:return False
        if current.get('toggle_state')==state:return False
        values=self.buffs._instances(owner)
        for item in values:
            if item['id']==instance['id']:item['toggle_state']=state
        self.ctx.set(owner,('buffs','instances'),values);return True
    def _children(self,owner,uid):return [i for i in self.buffs._instances(owner) if i.get('toggle_parent')==uid]
    def remove(self,owner,parent):
        if not self.enabled:return
        self._removing.add(parent['id'])
        try:
            for child in self._children(owner,parent['id']):self.buffs.remove(owner,child['id'])
        finally:self._removing.discard(parent['id'])
    def pulse(self,event,payload):
        if not self.enabled:return
        changed=False
        for entity in self.ctx.session.world.entities():
            owner=entity['id']
            for instance in self.buffs._instances(owner):
                spec=self.ctx.program.definitions[instance['definition']].get('toggle')
                if not spec or instance['id'] in self._removing:continue
                for subscription in spec.get('events',[]):
                    if subscription['event']!=event:continue
                    try:ref=self.ctx.session.world.resolve(payload.get(subscription['owner_role']))
                    except (KeyError,ValueError,TypeError):continue
                    if ref!=owner:continue
                    condition=subscription.get('condition')
                    if condition and not evaluate_expression(condition,{'owner':self.ctx.entity(owner),'source':self.ctx.entity(instance['source']),'payload':payload,'time':self.ctx.session.time},spec.get('parameters',{})):continue
                    state=instance.get('toggle_state',{'enabled':spec['initial_enabled'],'held':False,'restore_at':None,'last_pulse':None})
                    new={**state,'enabled':False,'last_pulse':self.ctx.session.time,'restore_at':self.ctx.session.time+self.ctx.quantize(spec['restore_delay_seconds'])}
                    changed=self._write(owner,instance,new) or changed
        if changed:self.reconcile()
    def reconcile(self):
        if not self.enabled:return
        if self._busy:self._requested=True;return
        self._busy=True
        try:
            with self.ctx.session.atomic():
                budget=self.ctx.session.reaction_budget
                while True:
                    self._requested=False;changed=False
                    for entity in self.ctx.session.world.entities():
                        owner=entity['id']
                        for captured in self.buffs._instances(owner):
                            instance=self._current(owner,captured['id'])
                            if instance is None or instance['id'] in self._removing:continue
                            spec=self.ctx.program.definitions[instance['definition']].get('toggle')
                            if not spec:continue
                            state=instance.get('toggle_state',{'enabled':spec['initial_enabled'],'held':False,'restore_at':None,'last_pulse':None})
                            active=self.ctx.active(owner) and self.ctx.active(instance['source']) and (instance['expires_at'] is None or self.ctx.session.time<instance['expires_at'])
                            blocker=self.ctx.spatial.blocked_by(owner) if self.ctx.spatial is not None else None
                            blocker_active=blocker is not None and self.ctx.active(blocker)
                            held=self.ctx.calc('passive.toggle',{'owner':self.ctx.entity(owner),'source':self.ctx.entity(instance['source']),'blocked_by':blocker,'blocker_active':blocker_active,'clock':{'time':self.ctx.session.time,'quantum':self.ctx.session.quantum},'state':state,'parameters':thaw(spec.get('parameters',{}))},source=instance['source'],target=owner,owner=owner,rule_id=spec['rule']) if active else True
                            if type(held) is not bool:raise ValueError('passive.toggle must return bool held-disabled')
                            now=self.ctx.session.time;new=dict(state)
                            if held:new.update(held=True,enabled=False,restore_at=None)
                            elif state['held']:new.update(held=False,enabled=False,restore_at=now+self.ctx.quantize(spec['restore_delay_seconds']))
                            elif state['restore_at'] is not None and now>=state['restore_at']:new.update(enabled=True,restore_at=None)
                            children=self._children(owner,instance['id'])
                            changed=self._write(owner,instance,new) or changed
                            if not active or not new['enabled']:
                                for child in children:self.buffs.remove(owner,child['id']);changed=True
                            elif not children:
                                self.buffs.apply(instance['source'],owner,spec['buff'],toggle_parent=instance['id']);changed=True
                            current=self._current(owner,instance['id'])
                            if current is None or not self.ctx.active(owner) or not self.ctx.active(instance['source']):
                                for child in self._children(owner,instance['id']):self.buffs.remove(owner,child['id']);changed=True
                    if not changed and not self._requested:break
                    budget-=1
                    if budget<=0:raise ValueError('toggle callbacks exceed stabilization budget')
        finally:self._busy=False;self._requested=False
