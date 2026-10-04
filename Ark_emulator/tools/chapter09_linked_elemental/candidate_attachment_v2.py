"""Generic cast-owned traveling/held attachments; every record lives in World."""
import math
from collections.abc import Mapping
from ark_sim.contracts import thaw
from .selection import DEFAULT_STATE

FIELDS={'id','kind','version','metadata','dependencies','duration_seconds','flight_lifetime_seconds',
    'step_interval_seconds','refresh_interval_seconds','motion','target_buff','effect','damage_integral',
    'source_cancel_flags','ignored_owned_source_flags','force_reach_on_timeout','lifecycle','max_packets','completion_blocking','source_recovery_buff','recovery_on','hit_interval_seconds'}
REASONS={'complete','target_invalid','source_invalid','source_hidden','target_hidden','source_flags',
         'cast_interrupted','battle_terminal','flight_timeout','max_packets'}

def positive(value,label):
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
        raise ValueError(label+' requires a finite positive value')

def validate_profile(d):
    if not isinstance(d,Mapping) or set(d)-FIELDS or d.get('kind')!='attachment':
        raise ValueError('Owned attachment profile fields invalid')
    for key in ['duration_seconds','flight_lifetime_seconds','step_interval_seconds','refresh_interval_seconds']:
        positive(d.get(key),key)
    for key in ['damage_integral','completion_blocking','force_reach_on_timeout']:
        if type(d.get(key)) is not bool:raise ValueError(key+' requires explicit boolean')
    if not isinstance(d.get('motion'),Mapping) or set(d['motion'])!={'rule','parameters'}:
        raise ValueError('Attachment motion requires explicit rule/parameters')
    if not isinstance(d['motion']['rule'],str) or not isinstance(d['motion']['parameters'],Mapping):
        raise ValueError('Attachment motion values invalid')
    if 'hit_interval_seconds' in d:
        positive(d['hit_interval_seconds'], 'hit_interval_seconds')
        if d['damage_integral']:
            raise ValueError('Separate packet clock requires damage_integral false')
    effect = d.get('effect')
    if not isinstance(effect, Mapping) or effect.get('op') not in {'damage', 'elemental_attack'}:
        raise ValueError('Owned attachment requires actor damage or an atomic health/element packet')
    if effect.get('op') == 'elemental_attack':
        from .elemental import validate_effect
        validate_effect(effect)
        # A compound packet has independently authored health and EP amounts.
        # Integral scaling needs a separate explicit contract for both parts.
        if d['damage_integral']:
            raise ValueError('Compound attachment packets require damage_integral false')
    if not isinstance(d.get('target_buff'),str) or not d['target_buff']:
        raise ValueError('Attachment target_buff reference required')
    flags=d.get('source_cancel_flags')
    if not isinstance(flags,(list,tuple)) or any(type(flag) is not int or not 0<=flag<46 for flag in flags):
        raise ValueError('Attachment cancellation requires typed flags')
    ignored=d.get('ignored_owned_source_flags')
    if not isinstance(ignored,(list,tuple)) or any(type(flag) is not int or not 0<=flag<46 for flag in ignored):
        raise ValueError('Attachment owned-source exception requires typed explicit flags')
    lifecycle=d.get('lifecycle')
    if (not isinstance(lifecycle,Mapping) or set(lifecycle)!={'source_invalid','target_invalid','source_hidden','target_hidden'}
        or lifecycle['source_invalid']!='cancel' or lifecycle['target_invalid']!='cancel'
        or lifecycle['source_hidden'] not in {'cancel','retain'} or lifecycle['target_hidden'] not in {'cancel','retain'}):
        raise ValueError('Owned attachment lifecycle requires cancel for invalid owners/targets')
    if d.get('max_packets') is not None and (type(d['max_packets']) is not int or d['max_packets']<1):
        raise ValueError('Attachment max_packets is null(unlimited) or positive integer')
    if d.get('source_recovery_buff') is not None and not isinstance(d['source_recovery_buff'],str):
        raise ValueError('source_recovery_buff must be a reference or null')
    if not isinstance(d.get('recovery_on'),(list,tuple)) or set(d['recovery_on'])-REASONS:
        raise ValueError('Attachment recovery_on requires explicit supported reasons')


class AttachmentSystem:
    def __init__(self,ctx):
        self.ctx=ctx
        self.handlers={'domain.attachment.step':self.step}

    def state(self):return self.ctx.get('system/battle',('attachments',),{'next_id':1,'instances':{}})
    def save(self,data):self.ctx.set('system/battle',('attachments',),data)
    def current(self,uid):return self.state()['instances'].get(uid)
    def put(self,x):
        data=self.state();data['instances'][x['id']]=x;self.save(data)
    def profile(self,x):return self.ctx.program.definitions[x['definition']]
    def completion_pending(self):
        return any(x['active'] and self.profile(x)['completion_blocking'] for x in self.state()['instances'].values())

    def _schedule(self,x):
        units=self.ctx.quantize(self.profile(x)['step_interval_seconds'])
        if units<1:raise ValueError('Attachment step must advance time')
        due=self.ctx.session.time+units;seq=self.ctx.session.scheduler._next_seq
        task=self.ctx.session.schedule('domain.attachment.step',{'attachment':x['id'],'generation':x['generation']},due,
            phase=self.ctx.effect_phase)
        x.update(task=task,task_seq=seq,due=due,phase=self.ctx.effect_phase);self.put(x)

    def begin(self,source,target,definition,ability,cast,cause=None):
        with self.ctx.session.atomic():
            source=self.ctx.session.world.resolve(source);target=self.ctx.session.world.resolve(target)
            current=self.ctx.abilities._active(source,cast.get('id'))
            if current is None or current['ability']!=ability.get('id') or not ability.get('wait_for_channels'):
                raise ValueError('Attachment requires its explicit active waiting cast')
            if not self.ctx.active(source) or not self.ctx.active(target):return None
            d=self.ctx.program.definitions[definition];validate_profile(d)
            if any(x['active'] and (x['source'],x['target'],x['cast'],x['definition'])==(source,target,current['id'],definition)
                   for x in self.state()['instances'].values()):raise ValueError('Duplicate owned attachment')
            data=self.state();uid='attachment/'+str(data['next_id']);data['next_id']+=1
            now=self.ctx.session.time;position=self.ctx.get(source,('spatial','position'))
            x={'id':uid,'definition':definition,'source':source,'target':target,'cast':current['id'],
                'ability':ability['id'],'active':True,'state':'flight','generation':1,'born':now,
                'position':position,'start':position,'last_target':self.ctx.get(target,('spatial','position')),
                'motion_state':{},'last_tick':now,'flight_expires':now+self.ctx.quantize(d['flight_lifetime_seconds']),
                'held_until':None,'next_refresh':None,'packets':0,'owned_buffs':[],
                'cause':cause if cause is not None else current.get('started_event'),
                'task':None,'task_seq':None,'due':None,'phase':self.ctx.effect_phase}
            data['instances'][uid]=x;self.save(data);self.ctx.abilities.channel_started(source,current['id'])
            self._schedule(x)
            self.ctx.emit('attachment.started',{'attachment':uid,'source':source,'target':target,'cast':current['id'],
                'definition':definition,'state':'flight'},x['cause'])
            return uid

    def _source_flags(self,x):
        cast=self.ctx.abilities._active(x['source'],x['cast']) or {}
        own={row['instance'] for row in cast.get('owned_buffs',[]) if row['target']==x['source']}
        state=self.ctx.get(x['source'],('selection_state',),{})
        flags=set(state.get('abnormal_flags',[]));immunes=set(state.get('abnormal_immunes',[]))
        for buff in self.ctx.get(x['source'],('buffs','instances'),[]):
            if buff['expires_at'] is not None and self.ctx.session.time>=buff['expires_at']:continue
            f=self.ctx.program.definitions[buff['definition']].get('selection_flags',{})
            immunes.update(f.get('abnormal_immunes',[]))
            contributed=set(f.get('abnormal_flags',[]))
            if buff['id'] in own:contributed-=set(self.profile(x)['ignored_owned_source_flags'])
            flags.update(contributed)
        return flags-immunes

    def invalid(self,x):
        d=self.profile(x);life=d['lifecycle']
        if self.ctx.state().get('finished'):return 'battle_terminal'
        if not self.ctx.active(x['source']):return 'source_invalid'
        if not self.ctx.active(x['target']):return 'target_invalid'
        if self.ctx.abilities._active(x['source'],x['cast']) is None:return 'cast_interrupted'
        if life['source_hidden']=='cancel' and self.ctx.route_hidden(x['source']):return 'source_hidden'
        if life['target_hidden']=='cancel' and self.ctx.route_hidden(x['target']):return 'target_hidden'
        if set(d['source_cancel_flags']) & self._source_flags(x):return 'source_flags'
        return None

    def _refresh(self,x):
        d=self.profile(x);uid=self.ctx.abilities.apply_cast_buff(x['source'],x['cast'],x['target'],d['target_buff'])
        if uid is not None:
            if uid not in x['owned_buffs']:x['owned_buffs'].append(uid)
        interval=self.ctx.quantize(d['refresh_interval_seconds'])
        if interval<1:raise ValueError('Attachment refresh must advance time')
        x['next_refresh']=self.ctx.session.time+interval;self.put(x)
        self.ctx.emit('attachment.refreshed',{'attachment':x['id'],'source':x['source'],'target':x['target'],
            'instance':uid,'next_refresh':x['next_refresh']},x['cause'])

    def step(self,session,payload):
        with session.atomic():
            x=self.current(payload['attachment']);key=session._active_key
            if (x is None or not x['active'] or x['generation']!=payload['generation'] or key is None
                    or key[3]!=x['task_seq'] or session.time!=x['due']):return
            x.update(task=None,task_seq=None,due=None);self.put(x)
            reason=self.invalid(x)
            if reason:self.stop(x['id'],reason);return
            d=self.profile(x);now=session.time
            if x['state']=='flight':
                position=self.ctx.get(x['target'],('spatial','position'))
                motion=d['motion']
                plan=self.ctx.calc('projectile.trajectory',{'source':self.ctx.entity(x['source']),
                    'target':self.ctx.entity(x['target']),'positions':[{'position':x['position'],'start':x['start'],
                    'last_target':position,'motion_state':x['motion_state']}],
                    'trajectory_parameters':{**thaw(motion['parameters']),
                        'age_seconds':(now-x['born'])*session.quantum,'delta_seconds':(now-x['last_tick'])*session.quantum,
                        'lifetime_seconds':d['flight_lifetime_seconds']}},source=x['source'],target=x['target'],rule_id=motion['rule'])
                point=plan.get('position')
                if (not isinstance(point,Mapping) or any(type(point.get(k)) not in (int,float) or not math.isfinite(point[k]) for k in ('row','col'))
                        or type(plan.get('reached')) is not bool):raise ValueError('Attachment trajectory plan invalid')
                x.update(position=thaw(point),motion_state=thaw(plan.get('motion_state',{})),last_target=position,last_tick=now)
                if not plan['reached']:
                    if now>=x['flight_expires']:
                        if not d['force_reach_on_timeout']:self.put(x);self.stop(x['id'],'flight_timeout');return
                        x['position']=position
                    else:self.put(x);self._schedule(x);return
                x.update(state='held',held_until=now+self.ctx.quantize(d['duration_seconds']),next_refresh=now)
                if 'hit_interval_seconds' in d:
                    x['next_packet'] = now
                self.put(x)
                self.ctx.emit('attachment.reached',{'attachment':x['id'],'source':x['source'],'target':x['target'],
                    'held_until':x['held_until'],'position':x['position']},x['cause'])
                current=self.current(x['id'])
                if current is None or not current['active']:return
                x=current
                reason=self.invalid(x)
                if reason:self.stop(x['id'],reason);return
            if now>=x['held_until']:self.stop(x['id'],'complete');return
            if now>=x['next_refresh']:self._refresh(x)
            current=self.current(x['id'])
            if current is None or not current['active']:return
            x=current;reason=self.invalid(x)
            if reason:self.stop(x['id'],reason);return
            if 'hit_interval_seconds' in d:
                if now < x['next_packet']:
                    self._schedule(x)
                    return
                interval = self.ctx.quantize(d['hit_interval_seconds'])
                if interval < 1:
                    raise ValueError('Attachment packet clock must advance time')
                x['next_packet'] = now + interval
                self.put(x)
            effect=thaw(d['effect']);units=min(self.ctx.quantize(d['step_interval_seconds']),x['held_until']-now)
            if d['damage_integral']:effect['scale']=effect.get('scale',1)*units*session.quantum
            cast=self.ctx.abilities._active(x['source'],x['cast']);ability=thaw(self.ctx.program.definitions[x['ability']])
            x['packets']+=1;self.put(x)
            self.ctx.effects.execute(x['source'],[x['target']],effect,ability=ability,cast=cast,cause=x['cause'])
            current=self.current(x['id'])
            if current is None or not current['active']:return
            x=current
            reason=self.invalid(x)
            if reason:self.stop(x['id'],reason);return
            if d['max_packets'] is not None and x['packets']>=d['max_packets']:self.stop(x['id'],'max_packets');return
            self._schedule(x)

    def stop(self,uid,reason):
        with self.ctx.session.atomic():
            x=self.current(uid)
            if x is None or not x['active']:return
            if reason not in REASONS:raise ValueError('Unknown attachment stop reason')
            d=self.profile(x);task=x['task'];x.update(active=False,state='ended',reason=reason,
                generation=x['generation']+1,task=None,task_seq=None,due=None);self.put(x)
            if task is not None and task in self.ctx.session.scheduler._tasks:self.ctx.session.cancel(task)
            for buff in x['owned_buffs']:self.ctx.buffs.remove(x['target'],buff)
            if reason in d['recovery_on'] and d.get('source_recovery_buff') and self.ctx.active(x['source']) and not self.ctx.state().get('finished'):
                self.ctx.buffs.apply(x['source'],x['source'],d['source_recovery_buff'])
            self.ctx.emit('attachment.finished',{'attachment':uid,'source':x['source'],'target':x['target'],
                'cast':x['cast'],'reason':reason,'packets':x['packets']},x['cause'])
            self.ctx.abilities.channel_finished(x['source'],x['cast'])

    def cancel_cast(self,source,cast):
        for x in self.state()['instances'].values():
            if x['active'] and x['source']==source and x['cast']==cast:self.stop(x['id'],'cast_interrupted')

    def target_invalid(self,target):
        for x in self.state()['instances'].values():
            if x['active'] and x['target']==target:self.stop(x['id'],'target_invalid')

    def terminate_all(self):
        for x in self.state()['instances'].values():
            if x['active']:self.stop(x['id'],'battle_terminal')

    def tick(self,session):
        with session.atomic():return self._tick(session)

    def _tick(self,session):
        for x in self.state()['instances'].values():
            if not x['active']:continue
            reason=self.invalid(x)
            if reason:self.stop(x['id'],reason)
            elif x['state']=='held' and session.time>=x['held_until']:self.stop(x['id'],'complete')
