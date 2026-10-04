"""Opt-in dynamic nominal-duration clock; old fixed Buff timers unchanged."""
import math
from collections.abc import Mapping
from ark_sim.contracts import Intent,thaw


def validate(spec):
    if not isinstance(spec,Mapping) or set(spec)!={'rule','parameters','count_when_inactive'}:
        raise ValueError('Buff lifetime requires explicit rule/parameters/inactive policy')
    if type(spec['rule']) is not str or not spec['rule'] or not isinstance(spec['parameters'],Mapping) or type(spec['count_when_inactive']) is not bool:
        raise ValueError('Buff lifetime requires rule ID, parameter record and strict bool')


def rate(system,instance,sample_time=None):
    ctx=system.ctx;spec=ctx.program.definitions[instance['definition']]['lifetime'];owner=instance['target'];source=instance['source']
    from .buff_application import pure_attributes
    when=ctx.session.time if sample_time is None else sample_time
    value=ctx.calc('buff.lifetime_rate',{'owner':ctx.entity(owner),'source':ctx.entity(source),'instance':instance,
        'clock':{'time':when,'quantum':ctx.session.quantum},'attributes':pure_attributes(ctx,owner,when),'parameters':thaw(spec['parameters'])},
        source=source,target=owner,owner=owner,rule_id=spec['rule'],extra={'time':when,'seconds':when*ctx.session.quantum,'lifetime_sample_time':when})
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:
        raise ValueError('Buff lifetime rate must be finite nonnegative numeric')
    return value


def prepare(system,instance,duration,existing):
    ctx=system.ctx;definition=ctx.program.definitions[instance['definition']];spec=definition.get('lifetime')
    if spec is None:return None
    validate(spec)
    if duration<=0:raise ValueError('Dynamic Buff lifetime requires finite positive resolved duration')
    mode=definition.get('stacking',{}).get('mode')
    if existing and 'lifetime_clock' in existing and mode in ('extend','max'):
        previous=existing['lifetime_clock']
        counting=previous['counting']
        consumed=(ctx.session.time-previous['last_time'])*ctx.session.quantum*previous['rate'] if counting else 0
        old_remaining=max(0,previous['remaining_seconds']-consumed)
        remaining=old_remaining+duration if mode=='extend' else max(old_remaining,duration)
    else:remaining=duration
    instance['expires_at']=None
    value=rate(system,instance)
    counting=spec['count_when_inactive'] or (ctx.active(instance['target']) and system.applicability.active(instance))
    instance['lifetime_clock']={'remaining_seconds':remaining,'last_time':ctx.session.time,'rate':value,'counting':counting,
        'task_seq':None,'due':None}
    # Current projection becomes at least one futuretick until owned callback
    # settles remaining nominal time. Zero rate explicitly pauses expiration.
    # Keep public availability alive until the owned callback decides expiry;
    # a future rate change can legitimately extend this clock beyond an old
    # prediction. The callback always runs before same-phase packet dispatch.
    instance['expires_at']=ctx.session.time+(1 if counting and remaining-value*ctx.session.quantum<=1e-9 else 2)
    due=ctx.session.time+1;seq=ctx.session.scheduler._next_seq
    instance['lifetime_clock'].update(task_seq=seq,due=due,phase=ctx.effect_phase)
    return Intent('schedule',data={'kind':'domain.buff.lifetime','at':due,'phase':ctx.effect_phase,
        'payload':{'target':instance['target'],'instance':instance['id'],'generation':instance['generation']}})


def pulse(system,session,payload):
    with session.atomic():
        instance=system._active(payload)
        if instance is None or 'lifetime_clock' not in instance:return
        clock=instance['lifetime_clock'];key=session._active_key
        if (key is None or session.time!=clock['due'] or key[1]!=session.scheduler.rank(clock['phase']) or key[3]!=clock['task_seq']):return
        ctx=system.ctx;definition=ctx.program.definitions[instance['definition']];spec=definition['lifetime']
        from .rebirth_self_buffs import retained as retained_self
        if not ctx.active(instance['target']) and definition.get('removal',{}).get('on_target_death','remove')=='remove' and not retained_self(ctx,instance):
            system.remove(instance['target'],instance['id']);return
        elapsed=(session.time-clock['last_time'])*session.quantum
        remaining=max(0,clock['remaining_seconds']-elapsed*clock['rate']) if clock['counting'] else clock['remaining_seconds']
        if remaining<=1e-9:
            system.remove(instance['target'],instance['id']);return
        value=rate(system,instance)
        counting=spec['count_when_inactive'] or (ctx.active(instance['target']) and system.applicability.active(instance))
        rows=system._instances(instance['target']);current=next((i for i in rows if i['id']==instance['id'] and i['generation']==instance['generation']),None)
        if current is None:return
        due=session.time+1;seq=session.scheduler._next_seq;task=session.scheduler.next_task_id
        current['lifetime_clock']={'remaining_seconds':remaining,'last_time':session.time,'rate':value,'counting':counting,'task_seq':seq,'due':due,'phase':ctx.effect_phase}
        current['expires_at']=session.time+(1 if counting and remaining-value*session.quantum<=1e-9 else 2)
        current['tasks']['lifetime']=task
        session.commit([Intent('set',instance['target'],('buffs','instances'),rows),Intent('schedule',data={'kind':'domain.buff.lifetime','at':due,'phase':ctx.effect_phase,'payload':payload})])


def expired_now(system,instance):
    clock=instance.get('lifetime_clock')
    if clock is None:return False
    if not clock['counting']:return False
    elapsed=(system.ctx.session.time-clock['last_time'])*system.ctx.session.quantum
    return clock['remaining_seconds']-elapsed*clock['rate']<=1e-9


def boundary(system,session):
    # Observer runs at t+1 after every action of t has settled. It samples the
    # final effective state of t, consumes t→t+1 with that state, and marks the
    # interval settled so the owned callback at t+1 never consumes it twice.
    with session.atomic():
        ctx=system.ctx
        for actor in session.world.entities():
            for captured in system._instances(actor['id']):
                clock=captured.get('lifetime_clock')
                if clock is None or clock['last_time']>=session.time:continue
                spec=ctx.program.definitions[captured['definition']]['lifetime']
                counting=spec['count_when_inactive'] or (ctx.active(captured['target']) and system.applicability.active(captured))
                value=rate(system,captured,session.time-1)
                remaining=max(0,clock['remaining_seconds']-(session.time-clock['last_time'])*session.quantum*value) if counting else clock['remaining_seconds']
                rows=system._instances(captured['target']);current=next((i for i in rows if i['id']==captured['id'] and i['generation']==captured['generation']),None)
                if current is None:continue
                current['lifetime_clock'].update(remaining_seconds=remaining,last_time=session.time,rate=value,counting=counting)
                current['expires_at']=session.time if remaining<=1e-9 else session.time+(1 if counting and remaining-value*session.quantum<=1e-9 else 2)
                ctx.set(captured['target'],('buffs','instances'),rows)
