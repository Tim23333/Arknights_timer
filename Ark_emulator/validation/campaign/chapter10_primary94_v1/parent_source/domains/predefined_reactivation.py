"""Bounded explicit registration reuse creates fresh actor incarnations."""
from collections.abc import Mapping
from ark_sim.contracts import thaw

def validate(spec):
    if not isinstance(spec,Mapping) or set(spec)!={'max_activations','after_reasons'}:
        raise ValueError('Reactivation requires exact count and retirement reasons')
    if type(spec['max_activations']) is not int or not 1<=spec['max_activations']<=10000:
        raise ValueError('Reactivation count requires boundedpositive integer')
    reasons=spec['after_reasons']
    if not isinstance(reasons,(list,tuple)) or not reasons or len(set(reasons))!=len(reasons) or any(r not in ('withdrawn','dead','expired') for r in reasons):
        raise ValueError('Reactivation requires explicit unique retirement reasons')

def register(ctx,key,item,ref):
    spec=item.get('reactivation')
    if spec is None:return
    validate(spec)
    if item.get('active',True) is not False or item.get('instanceAlias') is not None:
        raise ValueError('Reusablepredefine requires dormant registration and no mutable instancealias')
    template=thaw(item);template.pop('reactivation')
    data=ctx.state().get('predefined_reactivation',{})
    data[key]={'template':template,'profile':thaw(spec),'activations':0,'current':ref}
    ctx.state_update(predefined_reactivation=data)

def activate(system,key):
    ctx=system.ctx;row=ctx.state().get('predefined_reactivation',{}).get(key)
    if row is None:return None
    with ctx.session.atomic():
        if not isinstance(row,Mapping) or set(row)!={'template','profile','activations','current'} or type(row['activations']) is not int or row['activations']<0 or type(row['current']) is not int:
            raise ValueError('Predefinedreactivation state requires exact typed registry counter')
        validate(row['profile'])
        if row['activations']>=row['profile']['max_activations']:raise ValueError('Predefinedactivation budget exhausted')
        ref=ctx.state().get('predefined_registry',{}).get(key)
        if ref!=row['current']:raise ValueError('Predefinedcurrent incarnation registry differs')
        if row['template'].get('registration_key')!=key or row['template'].get('active') is not False or row['template'].get('instanceAlias') is not None:
            raise ValueError('Predefinedreactivation template identity differs')
        if ctx.active(ref):raise ValueError('Predefinedcurrent incarnation alreadyactive')
        if ctx.alive(ref):
            result=system._activate_predefined_once(key)
        else:
            if ctx.get(ref,('runtime','state')) not in row['profile']['after_reasons']:raise ValueError('Predefinedretirement reason doesnot permit reuse')
            t=row['template']
            # Preserve old actor identity so already-launched retained packets
            # read its actual old source. Fresh actor has source-definedHP/SP.
            result=system.create(t['definition'],t.get('position'),t.get('facing','right'),t.get('route'),
                parameters=t.get('parameters'),deployed=t.get('deployed',False),component_overrides=t.get('components'),rule_overrides=t.get('rules'),tags=t.get('tags'),active=True)
            registry=ctx.state().get('predefined_registry',{});registry[key]=result;ctx.state_update(predefined_registry=registry)
            ctx.emit('entity.activated',{'source':result,'target':result,'registration_key':key,'previous_incarnation':ref})
        data=ctx.state().get('predefined_reactivation',{});current=data.get(key)
        if current is None or current!=row:raise ValueError('Predefinedactivation callback changed its source registration')
        current.update(activations=row['activations']+1,current=result);ctx.state_update(predefined_reactivation=data)
        return result
