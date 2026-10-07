"""Opt-in explicit priority arbitration for multiple automatic actor abilities.

The policy names each ability and its clock/control gates. Array order is only
the declared tie-break, never an accidental choice of the last ready skill.
"""
from collections.abc import Mapping
from ark_sim.contracts import thaw
from ark_sim.rules.expressions import Expression,evaluate_expression
from ark_sim.rules.numeric import validate_data


def validate(spec, abilities, definitions=None):
    if not isinstance(spec,Mapping) or set(spec)!={'priority_order','busy','entries'}:
        raise ValueError('ability arbitration requires explicit priority_order/busy/entries')
    if spec['priority_order'] not in ('higher_first','lower_first') or spec['busy'] not in ('blocking_casts','all_casts'):
        raise ValueError('unsupported arbitration order or busy policy')
    rows=spec['entries']
    if not isinstance(rows,(list,tuple)) or not rows:
        raise ValueError('ability arbitration entries must be nonempty')
    seen=set()
    for row in rows:
        if not isinstance(row,Mapping) or set(row)!={'ability','priority','attack_clock','require_attack_control','condition','parameters'}:
            raise ValueError('arbitration entry requires exact ability/priority/clock/control/condition/parameters')
        if not isinstance(row['ability'],str) or row['ability'] not in abilities or row['ability'] in seen:
            raise ValueError('arbitration ability must be possessed and unique')
        seen.add(row['ability'])
        if type(row['priority']) is not int or type(row['attack_clock']) is not bool or type(row['require_attack_control']) is not bool:
            raise ValueError('arbitration priority integer and gate booleans required')
        Expression(row['condition'])
        if not isinstance(row['parameters'],Mapping):raise ValueError('arbitration parameters require data record')
        validate_data(row['parameters'])
        if definitions is not None:
            definition=definitions.get(row['ability'],{})
            mode=definition.get('activation',{}).get('mode')
            if definition.get('kind')!='ability' or mode not in ('manual','automatic_attack'):
                raise ValueError('arbitration only consumes manual or automatic_attack abilities')
    if set(abilities)!=seen:
        raise ValueError('arbitration must explicitly account for all possessed abilities')


def requires_atomic(definition,overrides):
    return 'ability_arbitration' in definition.get('components',{}) or 'ability_arbitration' in overrides


def initialize(ctx,ref,components):
    spec=components.get('ability_arbitration')
    if spec is not None:validate(spec,ctx.get(ref,('abilities',),[]),ctx.program.definitions)


def tick(system,source):
    ctx=system.ctx
    spec=ctx.get(source,('ability_arbitration',))
    validate(spec,ctx.get(source,('abilities',),[]),ctx.program.definitions)
    runtime=ctx.get(source,('runtime',),{})
    casts=runtime.get('casts',{})
    if casts and (spec['busy']=='all_casts' or any(c.get('blocks_attacks',True) for c in casts.values())):
        return
    if not ctx.buffs.controls(source)['abilities'] or not ctx.active(source) or ctx.route_hidden(source):
        return
    sign=-1 if spec['priority_order']=='higher_first' else 1
    rows=sorted(enumerate(spec['entries']),key=lambda pair:(sign*pair[1]['priority'],pair[0]))
    for index,row in rows:
        runtime=ctx.get(source,('runtime',),{})
        now=ctx.session.time
        if runtime.get('cooldowns',{}).get(row['ability'],0)>now:continue
        if row['attack_clock'] and runtime.get('next_attack',0)>now:continue
        if row['require_attack_control'] and not ctx.buffs.controls(source)['attack']:continue
        accepted=evaluate_expression(row['condition'],{'source':thaw(ctx.entity(source)),
            'runtime':runtime,'controls':ctx.buffs.controls(source),'time':now},row['parameters'],
            {'time':now,'quantum':ctx.session.quantum})
        if type(accepted) is not bool:raise ValueError('arbitration condition must return strict boolean')
        if not accepted:continue
        from .abilities import ActivationRejected
        try:
            # Each attempted ability has its own atomic transaction. A legal
            # temporary rejection rolls back payment/selection/RNG before fallback.
            with ctx.session.atomic():
                cast=system.start(source,row['ability'],automatic=True)
                still_active=ctx.active(source) and bool(system._active(source,cast)) and not ctx.state().get('finished')
                if row['attack_clock'] and still_active:
                    definition=system._definition(row['ability'])
                    params=system._params(definition)
                    mode=definition.get('activation',{}).get('mode')
                    if mode!='automatic_attack' and not params.get('replace_attack'):
                        interval=ctx.calc('time.interval',{'base_interval':ctx.role_value(source,'attack_interval'),
                            'speed':ctx.role_value(source,'attack_speed_ratio'),'adjustments':[]},source=source,
                            ability=definition,rule_id=definition.get('activation',{}).get('interval_rule'))
                        units=ctx.quantize(interval)
                        if type(units) is not int or units<1:raise ValueError('arbitration attack clock must advance')
                        ctx.set(source,('runtime','next_attack'),now+units)
                ctx.emit('ability.arbitrated',{'source':source,'ability':row['ability'],'cast':cast,
                    'priority':row['priority'],'entry_index':index,'attack_clock':row['attack_clock'],
                    'cast_still_active':still_active})
            return
        except ActivationRejected:
            continue
