"""Finite actor-owned action leases while the same actor awaits restoration."""
from contextlib import contextmanager
from collections.abc import Mapping
from ark_sim.contracts import thaw


class WaitingActions:
    def __init__(self,ctx):self.ctx=ctx;self._scopes=[];self._timers=[]
    def valid(self,lease):
        fields={'owner','ability','buff_definition','buff_instance','buff_generation','rebirth_generation','lifecycle_generation'}
        if (not isinstance(lease,Mapping) or set(lease)!=fields or self.ctx.state().get('finished')
            or any(type(lease[k]) is not int or lease[k]<0 for k in ('owner','buff_generation','rebirth_generation','lifecycle_generation'))
            or any(type(lease[k]) is not str or not lease[k] for k in ('ability','buff_definition','buff_instance'))):return False
        ref=lease['owner']
        try:
            state=self.ctx.get(ref,('runtime','rebirth'),{})
            if (not self.ctx.alive(ref) or self.ctx.active(ref) or state.get('phase')!='waiting'
                or state.get('generation')!=lease['rebirth_generation']
                or self.ctx.get(ref,('runtime','lifecycle_generation'),0)!=lease['lifecycle_generation']):return False
            task=next((t for t in self.ctx.session.scheduler.pending if t['id']==state.get('task')),None)
            if (task is None or task['kind']!='domain.rebirth.finish' or task['payload']!={'target':ref,'generation':lease['rebirth_generation']}
                or task['at']!=state.get('due_at')):return False
            allowed=self.ctx.get(ref,('rebirth','waiting_actions'),{})
            if lease['ability'] not in allowed.get('abilities',[]) or lease['buff_definition'] not in allowed.get('buffs',[]):return False
            actual=next((b for b in self.ctx.get(ref,('buffs','instances'),[]) if b['id']==lease['buff_instance']),None)
            return bool(actual and actual['source']==ref and actual['target']==ref and actual['generation']==lease['buff_generation']
                and actual['definition']==lease['buff_definition'] and actual.get('applicability',{}).get('active',True)
                and (actual['expires_at'] is None or self.ctx.session.time<actual['expires_at']))
        except KeyError:return False
    def acquire(self,instance,ability):
        ref=instance['target']
        if instance['source']!=ref:return None
        lease={'owner':ref,'ability':ability,'buff_definition':instance['definition'],'buff_instance':instance['id'],
            'buff_generation':instance['generation'],'rebirth_generation':self.ctx.get(ref,('runtime','rebirth','generation')),
            'lifecycle_generation':self.ctx.get(ref,('runtime','lifecycle_generation'),0)}
        return lease if self.valid(lease) else None
    @contextmanager
    def scope(self,lease):
        self._scopes.append(thaw(lease))
        try:yield
        finally:self._scopes.pop()
    def current(self,source,ability=None):
        lease=self._scopes[-1] if self._scopes else None
        return lease if lease and lease['owner']==source and (ability is None or ability==lease['ability']) and self.valid(lease) else None
    def source_allowed(self,source):return self.current(source) is not None
    def cast_allowed(self,source,cast):
        lease=cast.get('waiting_action')
        actual=self.ctx.get(source,('runtime','casts',cast.get('id')),None)
        return bool(lease and actual and actual.get('waiting_action')==lease and cast.get('source')==source
            and cast.get('ability')==lease['ability'] and actual.get('ability')==lease['ability']
            and type(cast.get('generation')) is int and actual.get('generation')==cast['generation']
            and self.valid(lease))
    def cancel_casts(self,source,reason):
        casts=self.ctx.get(source,('runtime','casts'),{})
        for cast in list(casts.values()):
            if not cast.get('waiting_action'):continue
            pending={t['id'] for t in self.ctx.session.scheduler.pending}
            for task in cast.get('tasks',[]):
                if task in pending:self.ctx.session.cancel(task)
            current=self.ctx.get(source,('runtime','casts'),{})
            current.pop(cast['id'],None);self.ctx.set(source,('runtime','casts'),current)
            self.ctx.abilities._release_cast_buffs(source,cast)
            self.ctx.emit('ability.interrupted',{'source':source,'ability':cast['ability'],'cast':cast['id'],'reason':reason})
    def timer_matches(self,instance):
        task=self.ctx.session.current_task
        return bool(task and type(task['id']) is int and type(instance.get('tasks',{}).get('periodic')) is int
            and task['id']==instance['tasks']['periodic'] and task['kind']=='domain.buff.periodic'
            and task['at']==self.ctx.session.time and task['phase']==self.ctx.effect_phase
            and task['payload']=={'target':instance['target'],'instance':instance['id'],'generation':instance['generation']}
            and all(type(task['payload'].get(k)) is int for k in ('target','generation'))
            and type(task['payload'].get('instance')) is str)
    @contextmanager
    def periodic_scope(self,instance):
        if not self.timer_matches(instance):raise ValueError('Waiting action requires actual owned periodic dispatch')
        self._timers.append({k:instance[k] for k in ('id','definition','target','source','generation')})
        try:yield
        finally:self._timers.pop()
    def trigger(self,instance,ability,cause):
        identity={k:instance[k] for k in ('id','definition','target','source','generation')}
        if not self._timers or self._timers[-1]!=identity or not self.timer_matches(instance):return False
        lease=self.acquire(instance,ability)
        if lease is None:return False
        with self.scope(lease):self.ctx.abilities.start(instance['target'],ability,automatic=True,cause=cause)
        return True
