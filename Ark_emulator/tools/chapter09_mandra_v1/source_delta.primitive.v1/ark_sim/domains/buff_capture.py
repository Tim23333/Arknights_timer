"""Optional pure Buff blackboard sampling with event-bound historical values."""
from collections.abc import Mapping
import math
from ark_sim.contracts import thaw,digest

def validate(spec):
    if not isinstance(spec,Mapping) or set(spec)!={'rule','refresh','parameters'} or not isinstance(spec['rule'],str) or not spec['rule'] or spec['refresh'] not in {'retain','resample'} or not isinstance(spec['parameters'],Mapping):raise ValueError('Buff capture requires explicit rule/refresh/parameters')
def finite(value,depth=0):
    if depth>8:raise ValueError('Buff capture record nesting exceeds limit')
    if value is None or isinstance(value,(bool,str)):
        if isinstance(value,str) and len(value)>4096:raise ValueError('Buff capture string exceeds limit')
        return
    if type(value) in (int,float):
        if not math.isfinite(value):raise ValueError('Buff capture numbers must be finite')
        return
    if isinstance(value,Mapping):
        if len(value)>32 or any(not isinstance(k,str) or not k or len(k)>128 for k in value):raise ValueError('Buff capture requires bounded named records')
        for child in value.values():finite(child,depth+1)
        return
    raise ValueError('Buff capture values must be scalars or finite records')
def stamp(ctx,ref):
    actor=ctx.entity(ref);runtime=actor['components'].get('runtime',{})
    return {'id':actor['id'],'definition':actor['definition_id'],'life':runtime.get('lifecycle_generation',0),'death':runtime.get('death_generation',0)}
def prepare(system,instance,existing):
    ctx=system.ctx;definition=ctx.program.definitions[instance['definition']];spec=definition.get('capture')
    if spec is None:return
    validate(spec);source=instance['source'];target=instance['target']
    if existing and spec['refresh']=='retain':
        old=existing.get('capture')
        if old is None:raise ValueError('Retained Buff capture is missing')
        record=thaw(old);record['binding_event']=ctx.emit('buff.capture.retained',{'source':source,'target':target,'instance':instance['id'],'from_generation':existing['generation'],'generation':instance['generation'],'sample_event':record['sample_event'],'source_stamp':stamp(ctx,source),'target_stamp':stamp(ctx,target)},record['sample_event']);record['generation']=instance['generation'];instance['capture']=record;return
    inputs={'source':ctx.capture_view(source),'target':ctx.capture_view(target),'instance':{'id':instance['id'],'definition':instance['definition'],'source':source,'target':target,'generation':instance['generation']},'clock':{'time':ctx.session.time,'quantum':ctx.session.quantum},'parameters':thaw(spec['parameters'])}
    scope={'scenario':ctx.program.scenario.get('rules',{}),'source':ctx.definition_bindings(source),'target':ctx.definition_bindings(target),'owner':ctx.definition_bindings(target),'component':{},'attribute_or_resource':{},'ability':{},'effect':{}}
    context={'time':ctx.session.time,'seconds':ctx.session.time*ctx.session.quantum,'quantum':ctx.session.quantum,'source':inputs['source'],'target':inputs['target'],'owner':inputs['target']}
    previous=ctx.session._capturing_atomic;ctx.session._capturing_atomic=True
    try:result=ctx.rules.evaluate('buff.capture',inputs,scope=scope,rule_id=spec['rule'],context=context)
    finally:ctx.session._capturing_atomic=previous
    from .context import compact_trace
    trace=result.trace if ctx.program.ruleset.get('parameters',{}).get('trace_mode','compact')=='full' else compact_trace(result.trace)
    value=result.value;event=ctx.emit('calculation',{'calculation_id':'buff.capture','rule_id':result.rule_id,'source':source,'target':target,'value':value,'trace':trace});ctx.last_calculation_event_id=event
    if not isinstance(value,Mapping):raise ValueError('Buff capture output must be a record')
    finite(value);instance['blackboard']=thaw(value)
    instance['capture']={'sample_event':event,'binding_event':event,'sample_generation':instance['generation'],'generation':instance['generation'],'sample_time':ctx.session.time,'source_stamp':stamp(ctx,source),'target_stamp':stamp(ctx,target),'spec_digest':digest(spec),'value_digest':digest(value)}
def validate_restored(system):
    ctx=system.ctx;events=ctx.session._events._records
    from .context import compact_trace
    compact=ctx.program.ruleset.get('parameters',{}).get('trace_mode','compact')!='full'
    for actor in ctx.session.world.entities():
        for instance in actor['components'].get('buffs',{}).get('instances',[]):
            spec=ctx.program.definitions[instance['definition']].get('capture')
            if spec is None:
                if instance.get('capture') is not None:raise ValueError('Unowned Buff capture data')
                continue
            validate(spec);record=instance.get('capture')
            if not isinstance(record,Mapping) or set(record)!={'sample_event','binding_event','sample_generation','generation','sample_time','source_stamp','target_stamp','spec_digest','value_digest'}:raise ValueError('Required Buff capture is missing or malformed')
            if record['source_stamp']!=stamp(ctx,instance['source']) or record['target_stamp']!=stamp(ctx,instance['target']) or record['generation']!=instance['generation'] or record['spec_digest']!=digest(spec) or record['value_digest']!=digest(instance['blackboard']):raise ValueError('Buff capture actor/generation/value differs')
            history=[e for e in events if e['type'] in {'buff.applied','buff.removed'} and e['payload'].get('instance')==instance['id'] and e['payload'].get('target')==instance['target']]
            if not history or history[-1]['type']!='buff.applied' or history[-1]['time']!=instance['started_at']:raise ValueError('Buff capture handle was removed or not actually applied')
            for key in ['sample_event','binding_event','sample_generation','generation']:
                if type(record[key]) is not int or record[key]<1:raise ValueError('Buff capture identity must be positive integers')
            if type(record['sample_time']) is not int or record['sample_time']<0 or record['sample_event']>len(events) or record['binding_event']>len(events):raise ValueError('Buff capture time/event must be valid logical identities')
            finite(instance['blackboard'])
            event=events[record['sample_event']-1];payload=event['payload'];trace=thaw(payload['trace']);inputs=trace['inputs']
            expected={'id':instance['id'],'definition':instance['definition'],'source':instance['source'],'target':instance['target'],'generation':record['sample_generation']}
            if event['id']!=record['sample_event'] or event['type']!='calculation' or payload['calculation_id']!='buff.capture' or payload['rule_id']!=spec['rule'] or payload['source']!=instance['source'] or payload['target']!=instance['target'] or event['time']!=record['sample_time'] or inputs['clock']['time']!=record['sample_time'] or inputs['clock']['quantum']!=ctx.session.quantum or inputs['instance']!=expected or inputs['parameters']!=thaw(spec['parameters']) or digest(payload['value'])!=digest(instance['blackboard']):raise ValueError('Buff capture lost original calculation binding')
            scope={'scenario':ctx.program.scenario.get('rules',{}),'source':{**thaw(ctx.program.definitions[inputs['source']['definition_id']].get('rules',{})),**inputs['source']['components'].get('runtime',{}).get('rule_bindings',{})},'target':{**thaw(ctx.program.definitions[inputs['target']['definition_id']].get('rules',{})),**inputs['target']['components'].get('runtime',{}).get('rule_bindings',{})},'owner':{**thaw(ctx.program.definitions[inputs['target']['definition_id']].get('rules',{})),**inputs['target']['components'].get('runtime',{}).get('rule_bindings',{})},'component':{},'attribute_or_resource':{},'ability':{},'effect':{}}
            context={'time':record['sample_time'],'seconds':record['sample_time']*ctx.session.quantum,'quantum':ctx.session.quantum,'source':inputs['source'],'target':inputs['target'],'owner':inputs['target']}
            previous=ctx.session._capturing_atomic;ctx.session._capturing_atomic=True
            try:result=ctx.rules.evaluate('buff.capture',inputs,scope=scope,rule_id=spec['rule'],context=context)
            finally:ctx.session._capturing_atomic=previous
            actual=thaw(compact_trace(result.trace)) if compact else thaw(result.trace)
            if digest(actual)!=digest(payload['trace']) or digest(result.value)!=record['value_digest']:raise ValueError('Buff capture pure historical calculation differs')
            if record['binding_event']==record['sample_event']:
                if record['generation']!=record['sample_generation'] or instance['started_at']!=record['sample_time']:raise ValueError('Buff capture original generation/time differs')
            else:
                retained=events[record['binding_event']-1]
                expected_retained={'source':instance['source'],'target':instance['target'],'instance':instance['id'],'from_generation':record['generation']-1,'generation':record['generation'],'sample_event':record['sample_event'],'source_stamp':record['source_stamp'],'target_stamp':record['target_stamp']}
                if spec['refresh']!='retain' or retained['id']!=record['binding_event'] or retained['type']!='buff.capture.retained' or retained['time']!=instance['started_at'] or retained['cause']!=record['sample_event'] or thaw(retained['payload'])!=expected_retained:raise ValueError('Retained Buff capture refresh binding differs')
