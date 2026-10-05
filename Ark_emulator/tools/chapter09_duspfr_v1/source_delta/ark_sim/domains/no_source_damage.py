"""Explicit source-independent damage settlement; ordinary actor paths untouched."""
from collections.abc import Mapping
import math
from ark_sim.contracts import Intent, thaw
from ark_sim.kernel._data import clone

FLAGS = {'ignore_for_sp', 'node_is_env_damage', 'env_blackboard_injected', 'environmental'}
FIELDS = {'op', 'target', 'resource', 'rules', 'fixed_amount', 'damage_type', 'origin',
          'attack_type', 'damage_without_modify', 'metadata'} | FLAGS


def validate_request(effect):
    if not isinstance(effect, Mapping) or set(effect) - FIELDS:
        raise ValueError('no_source_damage request has unknown fields')
    if effect.get('op') != 'no_source_damage':
        raise ValueError('Explicit no_source_damage operation required')
    value = effect.get('fixed_amount')
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('fixed_amount must be finite and nonnegative')
    if type(effect.get('damage_type')) is not str or effect['damage_type'] not in {'true','arts','physical'}:
        raise ValueError('No-source protocol requires an explicit supported damage type')
    if type(effect.get('attack_type')) is not str or effect['attack_type'] not in {'NONE','BUFF','NORMAL'}:
        raise ValueError('No-source protocol requires attack_type NONE, BUFF or NORMAL')
    if type(effect.get('damage_without_modify')) is not bool:
        raise ValueError('damage_without_modify requires an explicit strict boolean')
    for key in FLAGS:
        if type(effect.get(key)) is not bool:
            raise ValueError(key+' requires an explicit boolean')
    origin = effect.get('origin')
    if not isinstance(origin, Mapping) or not origin:
        raise ValueError('No-source damage requires a nonempty origin object')
    clone(origin)
    mode = effect.get('target', 'selected')
    if mode != 'selected' and (type(mode) is not int or mode < 1):
        raise ValueError('No-source targets must be selected or an explicit positive entity ID')
    binding = effect.get('rules', {}).get('damage.pipeline')
    if not isinstance(binding, str) or not binding:
        raise ValueError('No-source damage requires an explicit damage.pipeline binding')


def attribution(effect):
    return {'source': None, 'source_policy': 'none', 'origin': thaw(effect['origin']),
            **{key: effect[key] for key in FLAGS}, 'attack_type': effect['attack_type'],
            'damage_without_modify': effect['damage_without_modify']}


def execute(system, source, targets, effect, ability=None, cast=None, cause=None):
    if source is not None:
        raise ValueError('no_source_damage cannot have an actor source')
    validate_request(effect)
    ctx = system.ctx
    ability, cast = ability or {}, cast or {}
    if ability or cast:
        raise ValueError('No-source damage does not borrow actor ability/cast state')
    selected = list(targets) if effect.get('target', 'selected') == 'selected' else [effect['target']]
    results = []
    for ref in selected:
        if ctx.state().get('finished'):
            break
        target = ctx.session.world.resolve(ref)
        if (not ctx.active(target) or not ctx.effect_target_available(target) or
                not ctx.spatial.available(None, target, effect=effect, observable=True)):
            continue
        result = settle(system, target, effect, cause)
        results.append(result)
        if not ctx.state().get('finished'):
            ctx.lifecycle.tick(ctx.session)
        # Death callbacks can finish the battle or remove/inactivate later actors.
        # Each following packet re-reads actual state; there is no stale cache.
    return {'results': results, 'finished': bool(ctx.state().get('finished')),
            'actual_health_loss': sum(row['actual_health_loss'] for row in results)}


def settle(system, target, effect, cause):
    ctx = system.ctx
    tag = attribution(effect)
    resource = effect.get('resource') or ctx.health_resource(target)
    if resource != ctx.health_resource(target):
        raise ValueError('No-source primary resource must be the target health role')
    request = thaw(effect)
    if effect['damage_without_modify']:
        pipeline_amount=effect['fixed_amount']
        settlement={'accepted':True,'amount':pipeline_amount,'allocations':[],'events':[]}
        accepted=True
        ctx.emit('damage.modification_bypassed',{**tag,'target':target,'fixed_amount':pipeline_amount},cause)
    else:
        rule_id = request['rules']['damage.pipeline']
        rule = ctx.rules.rules[rule_id]
        for name, binding in rule.get('metadata', {}).get('input_bindings', {}).items():
            if binding['entity'] == 'source':
                raise ValueError('No-source pipeline cannot bind source attributes')
            key = binding.get('attribute') or ctx.attribute_role(binding.get('attribute_role'))
            base = ctx.get(target, ('attributes', 'base'), {})
            if key in base:
                request[name] = ctx.attributes.value(target, key, effect=effect)
            else:
                defaults = ctx.program.ruleset.get('parameters', {}).get('attribute_defaults', {})
                if key not in defaults:
                    raise ValueError('Required no-source target pipeline attribute missing: '+str(key))
                request[name] = defaults[key]
        initial = ctx.calc('damage.pipeline', {'source': {}, 'target': ctx.entity(target),
            'effect': request, 'samples': [], 'states': {}}, source=None, target=target, effect=request,
            rule_id=rule_id, extra={'origin': tag['origin'], 'source_policy': 'none'})
        pipeline_amount = initial['amount']
        initial = system._canonical_settlement(initial, None, target)
        post, _, accepted = system._damage_hooks('after', target, None, target,
            {**request, 'settlement': initial}, {}, {}, None)
        settlement = post['settlement']
    if accepted and settlement['accepted'] and getattr(ctx,'depletion',None) is not None:
        with ctx.depletion.attack(None,target,effect,resource=resource,_capability=ctx.depletion._damage_token):
            if not ctx.depletion.damage_gate(None,target,effect,settlement['amount']):accepted=False
    if not accepted or not settlement['accepted']:
        ctx.emit('damage.rejected', {**tag, 'target': target, 'reason': 'pipeline_or_target_hook',
                                   'pipeline_amount': pipeline_amount}, cause)
        return {'target': target, 'accepted': False, 'pipeline_amount': pipeline_amount,
                'actual_health_loss': 0, 'total_health_loss': 0, 'allocations': []}

    totals = {}
    allocations = settlement.get('allocations') or [{'target': target, 'resource': resource,
                                                     'amount': settlement['amount']}]
    for allocation in allocations:
        if (set(allocation) - {'target', 'resource', 'delta', 'amount'} or
                len(set(allocation) & {'delta', 'amount'}) != 1):
            raise ValueError('Damage allocation requires exactly one delta/amount and known fields')
        if 'amount' in allocation:
            amount = allocation['amount']
            if type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0:
                raise ValueError('Damage allocation amount must be finite and nonnegative')
        if 'resource' in allocation and (not isinstance(allocation['resource'], str) or not allocation['resource']):
            raise ValueError('Damage allocation resource requires a nonempty name')
        recipient = allocation.get('target', target)
        recipient = ctx.session.world.resolve(recipient)
        if not ctx.active(recipient) or not ctx.effect_target_available(recipient):
            continue
        key = allocation.get('resource', resource)
        change = allocation.get('delta', -allocation.get('amount', 0))
        if type(change) not in (int, float) or not math.isfinite(change):
            raise ValueError('Damage allocation delta must be finite')
        totals[(recipient, key)] = totals.get((recipient, key), 0) + change
    plans, rows = [], []
    living = {}
    for (recipient, key), change in totals.items():
        plan, delta = ctx.resources.change_plan(recipient, key, change, source=None, effect=effect)
        plans.extend(plan)
        health = key == ctx.health_resource(recipient)
        living[recipient] = ctx.alive(recipient)
        rows.append({'target': recipient, 'resource': key, 'requested_delta': change,
                     'actual_delta': delta, 'health_loss': max(-delta, 0) if health else 0,
                     'is_health': health})
    ctx.session.commit(plans)
    primary = sum(row['health_loss'] for row in rows if row['target'] == target)
    total = sum(row['health_loss'] for row in rows)
    for row in rows:
        recipient, key, delta = row['target'], row['resource'], row['actual_delta']
        resource_event=ctx.emit('resource.changed', {**tag, 'target': recipient, 'resource': key, 'delta': delta,
                                    'value': ctx.resources.current(recipient, key)}, cause)
        if getattr(ctx,'depletion',None) is not None and ctx.depletion.spec(recipient) is not None:row['resource_event']=resource_event
    # Settlement and its accepted event are visible before lethal cleanup;
    # target SP capture uses the original emission-time freeze mechanism.
    ctx.state_update(damage_dealt=ctx.state().get('damage_dealt', 0) + total)
    damage_event = ctx.emit('damage.accepted', {**tag, 'target': target, 'amount': primary,
        'pipeline_amount': pipeline_amount, 'settlement_amount': settlement['amount'],
        'actual_health_loss': primary, 'total_health_loss': total,
        'resource': resource, 'ability': None, 'allocations': rows}, cause)
    lifecycle_rows = {}
    for row in rows:
        if row['target'] not in lifecycle_rows or row['is_health']:
            lifecycle_rows[row['target']] = row
    for row in lifecycle_rows.values():
        event={**tag,'resource':row['resource'],'delta':row['actual_delta'],'cause':damage_event}
        if 'resource_event' in row:event['resource_event']=row['resource_event']
        if getattr(ctx,'depletion',None) is not None and ctx.depletion.spec(row['target']) is not None:
            event['operation']='damage'
            with ctx.depletion.attack(None,row['target'],effect,resource=row['resource'],_capability=ctx.depletion._damage_token):
                with ctx.depletion.delivery(row['target'],event,row['requested_delta']):ctx.lifecycle.check(row['target'],event)
        else:ctx.lifecycle.check(row['target'],event)
    for recipient, was_alive in living.items():
        if was_alive and not ctx.alive(recipient) and ctx.get(recipient, ('runtime', 'state')) == 'dead':
            ctx.lifecycle.claim_combat_kill(recipient, {**tag, 'target': recipient, 'ability': None, 'cast': None,
                'target_tags': list(ctx.entity(recipient)['tags'])}, damage_event,
                generation=ctx.get(recipient, ('runtime', 'death_generation')))
    for event in settlement.get('events', ()):
        ctx.emit(event['type'], {**event.get('payload', {}), **tag, 'target': target}, damage_event)
    return {'target': target, 'accepted': True, 'pipeline_amount': pipeline_amount,
            'actual_health_loss': primary, 'total_health_loss': total, 'allocations': rows}
