"""Explicit finite state/cast/clock restart, separate from ordinary transition."""
import math
from collections.abc import Mapping


def validate(effect):
    if not isinstance(effect,Mapping) or effect.get('op')!='restart_behavior':
        raise ValueError('Explicit restart_behavior effect required')
    if not isinstance(effect.get('state'),str) or not effect['state']:
        raise ValueError('Behavior restart requires a nonempty state')
    p=effect.get('parameters')
    if not isinstance(p,Mapping) or set(p)!={'abilities','reset_attack_clock','initial_cooldowns','reason'}:
        raise ValueError('Behavior restart requires exact finite abilities, reset flag, clocks and reason')
    ids=p['abilities']
    if not isinstance(ids,(list,tuple)) or not 1<=len(ids)<=128 or any(type(a) is not str or not a for a in ids) or len(set(ids))!=len(ids):
        raise ValueError('Behavior restart abilities require unique bounded IDs')
    if type(p['reset_attack_clock']) is not bool:
        raise ValueError('Behavior restart reset_attack_clock requires strict bool')
    clocks=p['initial_cooldowns']
    if not isinstance(clocks,Mapping) or set(clocks)-set(ids):
        raise ValueError('Behavior restart clocks must name declared abilities')
    for value in clocks.values():
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:
            raise ValueError('Behavior restart clocks require finite nonnegative seconds')
    if type(p['reason']) is not str or not p['reason'] or len(p['reason'])>256:
        raise ValueError('Behavior restart reason requires bounded nonempty text')
    return p


def validate_target(ctx,target,effect):
    p=validate(effect)
    possessed=ctx.get(target,('abilities',),[])
    if set(p['abilities'])-set(possessed):
        raise ValueError('Behavior restart abilities must be actually possessed by target')
    for aid in p['abilities']:
        if ctx.program.definitions.get(aid,{}).get('kind')!='ability':
            raise ValueError('Behavior restart requires ability definitions')
    machine=ctx.get(target,('behavior','machine'))
    definition=ctx.program.definitions.get(machine,{})
    if definition.get('kind')!='behavior' or effect['state'] not in definition.get('states',{}):
        raise ValueError('Behavior restart state must exist on target machine')
    return p


def validate_content(definitions,scenario):
    def walk(value,owner):
        if isinstance(value,Mapping):
            if value.get('op')=='restart_behavior' and value.get('target','selected') in ('self','source'):
                p=validate(value)
                components=owner.get('components',{})
                if set(p['abilities'])-set(components.get('abilities',[])):
                    raise ValueError('Self behavior restart references an unpossessed ability')
                machine=components.get('behavior',{}).get('machine')
                if value['state'] not in definitions.get(machine,{}).get('states',{}):
                    raise ValueError('Self behavior restart state is absent on actual actor machine')
            for key,child in value.items():
                if key not in ('metadata','parameters'):walk(child,owner)
        elif isinstance(value,(list,tuple)):
            for item in value:walk(item,owner)
    for entity in definitions.values():
        if entity.get('kind')!='entity':continue
        components=entity.get('components',{})
        machine=components.get('behavior',{}).get('machine')
        if machine in definitions:walk(definitions[machine],entity)
        for aid in components.get('abilities',[]):
            if aid in definitions:walk(definitions[aid],entity)


def identity(ctx,target):
    runtime=ctx.get(target,('runtime',),{})
    return (ctx.alive(target),ctx.active(target),runtime.get('state'),
        runtime.get('death_generation',0),runtime.get('lifecycle_generation',0),
        ctx.get(target,('behavior','machine')))


def execute(ctx,source,target,effect,cause=None):
    busy=getattr(ctx.behavior,'_restart_busy',None)
    if busy is None:
        busy=set()
        ctx.behavior._restart_busy=busy
    if target in busy:raise ValueError('Recursive restart of the same behavior actor')
    busy.add(target)
    try:return _execute(ctx,source,target,effect,cause)
    finally:busy.remove(target)


def _execute(ctx,source,target,effect,cause=None):
    p=validate_target(ctx,target,effect)
    if not ctx.active(target) or not ctx.alive(target):
        return False
    with ctx.session.atomic():
        original=identity(ctx,target)
        restart_generation=ctx.get(target,('behavior','restart_generation'),0)
        if type(restart_generation) is not int or restart_generation<0:
            raise ValueError('Behavior restart generation must be nonnegative integer')
        generation=restart_generation+1
        # Own no private Python state: generation lives in transactional World.
        clocks={aid:ctx.session.time+ctx.quantize(seconds) for aid,seconds in p['initial_cooldowns'].items()}
        validate_target(ctx,target,effect)
        if identity(ctx,target)!=original:return False
        ctx.set(target,('behavior','restart_generation'),generation)
        def current():
            return identity(ctx,target)==original and ctx.get(target,('behavior','restart_generation'))==generation
        cancelled=ctx.abilities.interrupt(target,p['reason'],ability_ids=p['abilities'])
        if not current():return False
        if not ctx.behavior.transition(target,effect['state'],cause=cause):return False
        if not current():return False
        runtime=ctx.get(target,('runtime',),{})
        # Owned callbacks can remove abilities synchronously; do not assign stale clocks.
        possessed=ctx.get(target,('abilities',),[])
        if set(p['abilities'])-set(possessed):return False
        runtime.setdefault('cooldowns',{}).update(clocks)
        if p['reset_attack_clock']:runtime['next_attack']=ctx.session.time
        ctx.set(target,('runtime',),runtime)
        ctx.emit('behavior.restarted',{'source':source,'target':target,'state':effect['state'],
            'generation':generation,'cancelled_casts':cancelled,'abilities':list(p['abilities']),
            'initial_cooldowns':clocks,'reset_attack_clock':p['reset_attack_clock'],'reason':p['reason']},cause)
        return True
