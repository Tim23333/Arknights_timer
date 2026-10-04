"""Generic pure Buff application plans over existing owned timers and handles."""
from collections.abc import Mapping
import math
from ark_sim.contracts import thaw
from .selection import DEFAULT_STATE


def validate_effect(effect):
    if effect.get('op') != 'buff_application': raise ValueError('Buff application op required')
    allowed = effect.get('allowed')
    if not isinstance(allowed, (list, tuple)) or not allowed or len(allowed) > 32 or not all(isinstance(s, str) and s for s in allowed) or len(set(allowed)) != len(allowed):
        raise ValueError('Buff application requires unique finite allowed Buff IDs')
    if not isinstance(effect.get('application_rule'), str) or not effect['application_rule']:
        raise ValueError('Buff application requires pure rule ID')


def validate_plan(plan, allowed, target, instances, definitions=None):
    if not isinstance(plan, Mapping) or set(plan) != {'accepted', 'operations'} or type(plan['accepted']) is not bool:
        raise ValueError('Buff application plan requires strict Boolean accepted and operations')
    ops = plan['operations']
    if not isinstance(ops, (list, tuple)) or len(ops) > 32 or (not plan['accepted'] and ops):
        raise ValueError('Rejected or oversized Buff application plan')
    owned = {b['id']: b for b in instances}
    for op in ops:
        if not isinstance(op, Mapping) or op.get('kind') not in ('apply', 'remove') or op.get('buff') not in allowed:
            raise ValueError('Undeclared Buff application operation')
        fields = {'kind', 'buff', 'duration_seconds', 'stacks'} if op['kind'] == 'apply' else {'kind', 'buff', 'instance', 'generation'}
        if set(op) - fields: raise ValueError('Foreign source/target or unknown operation fields')
        if op['kind'] == 'apply':
            if 'duration_seconds' not in op:
                raise ValueError('Explicit application duration required')
            n = op['duration_seconds']
            if n is None:
                definition = (definitions or {}).get(op['buff'])
                # None opts into the existing declared permanent Buff lifetime.
                # Validate every item before execution; no partial application.
                if not isinstance(definition, Mapping) or definition.get('kind') != 'buff' or 'duration_seconds' in definition or 'duration_rule' in definition:
                    raise ValueError('Permanent application requires a declared permanent Buff')
                parameter_duration = definition.get('parameters', {}).get('duration_seconds', 0)
                if type(parameter_duration) not in (int, float) or not math.isfinite(parameter_duration) or parameter_duration != 0:
                    raise ValueError('Permanent Buff parameters cannot declare a finite lifetime')
            elif type(n) not in (int, float) or not math.isfinite(n) or n < 0:
                raise ValueError('Finite nonnegative application duration required')
            stacks = op.get('stacks', 1)
            if type(stacks) is not int or not 1 <= stacks <= 10000: raise ValueError('Strict bounded application stacks required')
        else:
            uid, generation = op.get('instance'), op.get('generation')
            if not isinstance(uid, str) or not uid: raise ValueError('Remove handle requires a nonempty instance ID')
            old = owned.get(uid)
            if old is None or old['definition'] != op['buff'] or old['target'] != target or type(generation) is not int or generation != old['generation']:
                raise ValueError('Remove handle must be an actual target-bound Buff instance/generation')


def _generation(ctx, ref): return ctx.get(ref, ('runtime', 'death_generation'), 0)


def pure_attributes(ctx, ref, sample_time=None):
    when=ctx.session.time if sample_time is None else sample_time
    entity = ctx.entity(ref); data = entity['components'].get('attributes', {})
    scope = {'owner': ctx.definition_bindings(ref), 'component': data.get('rules', {})}
    values = {}
    for name, base in data.get('base', {}).items():
        local = {**scope, 'attribute_or_resource': data.get('attribute_rules', {}).get(name, {})}
        values[name] = ctx.rules.evaluate('attributes.effective', {'base': base,
            'modifier_layers': [m for m in data.get('modifiers', []) if m['attribute'] == name],
            'order': [{'layer': layer} for layer in data.get('layers', ctx.program.ruleset.get('attribute_layers', []))]},
            scope=local, context={'time':when,**({'seconds':when*ctx.session.quantum} if sample_time is not None else {}),'quantum':ctx.session.quantum,'source':entity,'owner':entity,
                'attribute':name,'attribute_sample_time':when}).value
    return values



def validate_permanent_duration(ctx, source, target, buff_id):
    # Same public attribute calculations and complete scope as BuffSystem.apply.
    # The enclosing Session.atomic rolls back traces/cache epoch/state on reject.
    definition = ctx.program.definitions[buff_id]
    attrs = ctx.attributes.values(source)
    parameters = {**thaw(definition.get('parameters', {})),
                  'duration_seconds': definition.get('duration_seconds', 0),
                  'interval_seconds': definition.get('interval_seconds', 0)}
    duration = ctx.calc('buff.duration', {'attributes': attrs, 'buff_parameters': parameters},
                        source=source, target=target, local=definition.get('rules', {}),
                        rule_id=definition.get('duration_rule'))
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration != 0:
        raise ValueError('Permanent application requires actual resolved zero duration')

def execute(system, source, target, effect, cause=None, cast=None):
    ctx = system.ctx
    validate_effect(effect)
    # Contract/dependency validation occurs before evaluating any policy.
    allowed = tuple(effect['allowed'])
    for ident in allowed:
        if ctx.program.definitions.get(ident, {}).get('kind') != 'buff': raise ValueError('Allowed application ID is not a Buff')
    rule = ctx.rules.rules.get(effect['application_rule'])
    if rule is None or rule.get('contract') != 'buff.application': raise ValueError('Application rule has incompatible contract')
    def source_allowed():
        projectile=getattr(ctx,'projectiles',None)
        authority=projectile.retained_payload_allowed(source,target,cast) if projectile is not None else None
        return ctx.active(source) if authority is None else authority
    if not source_allowed() or not ctx.active(target): return False
    with ctx.session.atomic():
        sg, tg = _generation(ctx, source), _generation(ctx, target)
        def identity(ref): return (ctx.alive(ref), ctx.active(ref), ctx.get(ref, ('runtime', 'state')), _generation(ctx, ref), ctx.get(ref, ('runtime', 'lifecycle_generation'), 0))
        source_at_entry, target_at_entry = identity(source), identity(target)
        instances = ctx.get(target, ('buffs', 'instances'), [])
        request = thaw(effect.get('parameters', {}))
        inputs = {'source': ctx.entity(source), 'target': ctx.entity(target),
                  'status': ctx.spatial.selection_state(target, DEFAULT_STATE), 'instances': instances,
                  'request': request, 'allowed': list(allowed), 'attributes': pure_attributes(ctx, target)}
        # Pure path: rejected/no-op plans emit nothing, write nothing and draw no RNG.
        result = ctx.rules.evaluate('buff.application', inputs, rule_id=effect['application_rule'],
            context={'time': ctx.session.time, 'quantum': ctx.session.quantum, 'source': ctx.entity(source), 'target': ctx.entity(target)}).value
        plan = thaw(result); validate_plan(plan, allowed, target, instances, ctx.program.definitions)
        if not plan['accepted'] or not plan['operations']: return False
        for op in plan['operations']:
            if op['kind'] == 'apply' and op['duration_seconds'] is None:
                validate_permanent_duration(ctx, source, target, op['buff'])
        mutated = False
        for op in plan['operations']:
            if not source_allowed() or identity(source) != source_at_entry or identity(target) != target_at_entry or not ctx.active(target) or _generation(ctx, source) != sg or _generation(ctx, target) != tg:
                break  # Retire/reborn callbacks cannot make an old plan act on the next incarnation.
            if op['kind'] == 'remove':
                current = next((b for b in ctx.get(target, ('buffs', 'instances'), []) if b['id'] == op['instance']), None)
                if current is None or current['generation'] != op['generation'] or current['definition'] != op['buff']:
                    continue  # Synchronous callback refreshed/removed that precise handle.
                mutated = bool(ctx.buffs.remove(target, op['instance'])) or mutated
            else:
                permanent = op['duration_seconds'] is None
                if permanent:
                    # Earlier entries and their callbacks may change actual inputs.
                    validate_permanent_duration(ctx, source, target, op['buff'])
                uid = ctx.buffs.apply(source, target, op['buff'], op.get('stacks', 1), duration_override=op['duration_seconds'])
                if permanent and identity(target) == target_at_entry:
                    current = next((b for b in ctx.get(target, ('buffs', 'instances'), []) if b['id'] == uid and b['definition'] == op['buff']), None)
                    # A legitimate callback may already remove this handle/owner.
                    if current is not None and current['expires_at'] is not None:
                        raise ValueError('Permanent application produced a finite live Buff')
                mutated = True
        return mutated
