"""Typed activation-relative initial clocks; only explicitly declared abilities."""
import math
from collections.abc import Mapping
def delay(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:
        raise ValueError('Initial cooldown requires finite nonnegative seconds')
    return value
def validate_overrides(profile,abilities):
    if not isinstance(profile,Mapping) or set(profile)!={'initial_cooldowns'} or not isinstance(profile['initial_cooldowns'],Mapping):
        raise ValueError('ability_timing requires explicit initial_cooldowns mapping')
    result={}
    for aid,value in profile['initial_cooldowns'].items():
        if not isinstance(aid,str) or aid not in abilities:raise ValueError('Initial cooldown override requires a possessed ability')
        result[aid]=delay(value)
    return result
def initialize(ctx,ref,components):
    abilities=ctx.get(ref,('abilities',),[]);seconds={}
    for aid in abilities:
        ability=ctx.program.definitions[aid]
        if 'initial_cooldown_seconds' in ability:seconds[aid]=delay(ability['initial_cooldown_seconds'])
    if 'ability_timing' in components:seconds.update(validate_overrides(components['ability_timing'],abilities))
    if not seconds:return
    clocks=ctx.get(ref,('runtime','cooldowns'),{})
    for aid,value in seconds.items():clocks[aid]=ctx.session.time+ctx.quantize(value)
    ctx.set(ref,('runtime','cooldowns'),clocks)
def requires_atomic(ctx,definition,overrides):
    components=definition.get('components',{})
    if 'ability_timing' in components or 'ability_timing' in overrides:return True
    abilities=overrides.get('abilities',components.get('abilities',[]))
    if not isinstance(abilities,(list,tuple)):return True
    return any('initial_cooldown_seconds' in ctx.program.definitions.get(aid,{}) for aid in abilities)
