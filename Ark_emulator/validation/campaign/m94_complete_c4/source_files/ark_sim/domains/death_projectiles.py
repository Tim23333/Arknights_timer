"""Opt-in pre-retirement emission preserves an actual postmortem projectile."""
from collections.abc import Mapping
import math
from ark_sim.contracts import thaw
from .selection import DEFAULT_STATE


def validate(spec):
    if not isinstance(spec,Mapping) or set(spec)!={'rule','parameters','projectile_definition','effect'}:
        raise ValueError('death projectile requires exact rule/parameters/projectile_definition/effect')
    if any(not isinstance(spec[k],str) or not spec[k] for k in ('rule','projectile_definition')) or not isinstance(spec['parameters'],Mapping):
        raise ValueError('death projectile references/parameters invalid')
    packet=spec['effect']
    if not isinstance(packet,Mapping) or packet.get('op')!='area' or 'projectile_definition' in packet or packet.get('center')!='source' or 'center_position' in packet:
        raise ValueError('death projectile requires explicit source-centered area impact without forged position/reference')


def emit(ctx,ref):
    # Optional actual death epoch supports future rebirth integration without
    # inventing a generation on legacy actors. Identity is the canonical ref.
    ref=ctx.session.world.resolve(ref)
    generation=ctx.get(ref,('runtime','death_generation'))
    def current():
        return (ctx.active(ref) and not ctx.state().get('finished',False)
            and ctx.get(ref,('runtime','death_generation'))==generation)
    for spec in ctx.get(ref,('lifecycle','death_projectiles'),[]):
        if not current():return
        validate(spec)
        state=ctx.spatial.selection_state(ref,DEFAULT_STATE)
        accepted=ctx.calc('lifecycle.death_emission',{'entity':ctx.entity(ref),'selection_state':state,
            'parameters':spec['parameters'],'clock':{'time':ctx.session.time,'quantum':ctx.session.quantum}},
            source=ref,owner=ref,rule_id=spec['rule'])
        if type(accepted) is not bool:raise ValueError('death emission decision must be strict boolean')
        if not current():return
        if not accepted:
            ctx.emit('death_projectile.rejected',{'source':ref,'projectile_definition':spec['projectile_definition']})
            continue
        packet=thaw(spec['effect']);packet['projectile_definition']=spec['projectile_definition']
        # Source and anchor are still active at this exact death boundary. The
        # independently owned projectile retains its body point after retirement.
        ctx.projectiles.launch(ref,ref,packet,{}, {},None)


def validate_effective(ctx,components):
    specs=components.get('lifecycle',{}).get('death_projectiles',[])
    if not isinstance(specs,(list,tuple)):raise ValueError('death_projectiles must be array')
    if specs and ctx.projectiles is None:raise ValueError('death emission requires compiled projectile support')
    for spec in specs:
        validate(spec)
        rule=ctx.program.definitions.get(spec['rule'],{})
        projectile=ctx.program.definitions.get(spec['projectile_definition'],{})
        if rule.get('contract')!='lifecycle.death_emission' or projectile.get('kind')!='projectile':
            raise ValueError('death emission requires compiled rule and projectile definitions')
        policy=projectile['lifecycle']
        if policy['source_invalid']!='retain' or policy['target_invalid']!='retain_position':
            raise ValueError('postmortem source/anchor must be retained')
        from ark_sim.content.schemas import validate_effect,DEFAULT_CAPABILITIES
        validate_effect(spec['effect'],'effective death effect',DEFAULT_CAPABILITIES)


def qualified_radius(inputs,params,context):
    options={**thaw(params),**thaw(inputs['parameters'])}
    if set(options)!={'radius','eligibility'} or type(options['radius']) not in (int,float) or not math.isfinite(options['radius']) or options['radius']<0:
        raise ValueError('qualified radius requires explicit finite radius and eligibility')
    projection=context['area_selection_states'];center=inputs['center_position'];result=[]
    for actor in inputs['candidates']:
        pos=actor['components']['spatial']['position']
        if math.hypot(pos['row']-center['row'],pos['col']-center['col'])>options['radius']:continue
        decision=context.calculate('targeting.eligibility',{'source':context['source'],'candidate':actor,
            'selector':{'healing':False},'parameters':options['eligibility']['parameters'],
            'selection_states':{'source':projection['source'],'candidate':projection['candidates'][str(actor['id'])]}},rule_id=options['eligibility']['rule']).value
        if not isinstance(decision,Mapping) or set(decision)!={'accepted','reason'} or type(decision['accepted']) is not bool:
            raise ValueError('radius eligibility must return strict decision')
        if decision['accepted']:result.append(actor['id'])
    return result


def radius_projection(ctx,source,candidates,options):
    defaults=options['eligibility']['parameters']['defaults']
    return {'source':ctx.spatial.selection_state(source,defaults),
        'candidates':{str(actor['id']):ctx.spatial.selection_state(actor['id'],defaults) for actor in candidates}}
