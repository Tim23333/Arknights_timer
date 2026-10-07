"""Pure configurable accounting at an actual route exit, without fake death."""
from collections.abc import Mapping
import math
from ark_sim.contracts import thaw


def validate(plan):
    if not isinstance(plan, Mapping) or set(plan)!={'base_life_loss','kills_delta','leaks_delta'}:
        raise ValueError('Exit plan requires exact loss/kills/leaks fields')
    loss=plan['base_life_loss']
    if type(loss) not in (int,float) or not math.isfinite(loss) or loss<0:
        raise ValueError('Exit base life loss must be finite and nonnegative')
    if any(type(plan[k]) is not int or plan[k] not in (0,1) for k in ('kills_delta','leaks_delta')):
        raise ValueError('Exit counts must be strict zero/one integers')
    if plan['kills_delta']+plan['leaks_delta']>1:
        raise ValueError('One actor exit cannot count twice')


def execute(system, ref):
    ctx=system.ctx
    with ctx.session.atomic():
        ref=ctx.session.world.resolve(ref)
        if not ctx.alive(ref) or ctx.get(ref,('runtime','exit_accounting_claim')) is not None:
            return False
        specification=ctx.get(ref,('lifecycle',),{})
        rule=specification['exit_rule']
        parameters=thaw(specification.get('exit_parameters',{}))
        if not isinstance(parameters,dict):raise ValueError('Exit parameters must be a record')
        generation=ctx.get(ref,('runtime','death_generation'),0)
        plan=ctx.calc('lifecycle.exit', {'entity':ctx.entity(ref),'exit':{'reason':'route_exit'},'exit_parameters':parameters},
                      target=ref,rule_id=rule)
        validate(plan)
        if not ctx.alive(ref) or ctx.get(ref,('runtime','death_generation'),0)!=generation:
            return False
        if (plan['kills_delta'] or plan['leaks_delta']) and 'enemy' not in ctx.entity(ref)['tags']:
            raise ValueError('Scenario enemy credit requires an enemy actor')
        ctx.set(ref,('runtime','exit_accounting_claim'),{'at':ctx.session.time,'generation':generation,'plan':thaw(plan),'rule':rule})
        resource=ctx.program.scenario.get('objectives',{}).get('life_resource')
        if resource and plan['base_life_loss']:
            ctx.resources.adjust('system/battle',resource,-plan['base_life_loss'])
        state=ctx.state()
        ctx.state_update(kills=state['kills']+plan['kills_delta'],leaks=state['leaks']+plan['leaks_delta'])
        ctx.emit('lifecycle.exit_accounted',{'source':None,'target':ref,'rule':rule,'reason':'route_exit',**thaw(plan)})
        system.retire(ref,'exited')
        return True
