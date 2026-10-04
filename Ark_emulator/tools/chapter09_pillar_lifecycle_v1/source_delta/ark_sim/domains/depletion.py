"""Opt-in exact-zero health states and finite generation-owned callbacks."""
from contextlib import contextmanager
from collections.abc import Mapping
import math
from ark_sim.contracts import thaw,digest

def number(value):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Depletion values must be finite numbers')
    return value
def validate(spec,components=None):
    if not isinstance(spec,Mapping) or set(spec)-{'resource','rule','initial_stage','stages','actions','parameters','damage_gate_rule'} or not {'resource','rule','initial_stage','stages','actions','parameters'}<=set(spec):raise ValueError('Depletion requires exact resource/rule/stage/actions/parameters')
    if 'damage_gate_rule' in spec and (not isinstance(spec['damage_gate_rule'],str) or not spec['damage_gate_rule']):raise ValueError('Damage gate requires an explicit pure rule')
    if any(not isinstance(spec[k],str) or not spec[k] for k in ('resource','rule','initial_stage')):raise ValueError('Depletion IDs must be nonempty strings')
    stages=spec['stages'];actions=spec['actions']
    if not isinstance(stages,Mapping) or not 1<=len(stages)<=16 or spec['initial_stage'] not in stages:raise ValueError('Finite declared depletion stages required')
    for key,row in stages.items():
        if not isinstance(key,str) or not key or not isinstance(row,Mapping) or set(row)!={'active','selectable'} or any(type(v) is not bool for v in row.values()):raise ValueError('Depletion stage flags must be strict booleans')
    if not isinstance(actions,Mapping) or not 1<=len(actions)<=32:raise ValueError('Finite declared depletion actions required')
    for key,row in actions.items():
        if not isinstance(key,str) or not key or not isinstance(row,Mapping) or set(row)-{'at_seconds','effects','next_stage','owned_ability'} or not {'at_seconds','effects'}<=set(row):raise ValueError('Invalid depletion action declaration')
        if 'owned_ability' in row and (not isinstance(row['owned_ability'],str) or not row['owned_ability'] or (components is not None and row['owned_ability'] not in components.get('abilities',()))):raise ValueError('Depletion owned ability must be explicitly possessed')
        if not 0<=number(row['at_seconds'])<=3600:raise ValueError('Depletion action time outside bounded horizon')
        if row.get('next_stage',spec['initial_stage']) not in stages:raise ValueError('Depletion next stage is undeclared')
        if not isinstance(row['effects'],(list,tuple)) or len(row['effects'])>32:raise ValueError('Finite depletion effect list required')
        from ark_sim.content.schemas import validate_effect,DEFAULT_CAPABILITIES
        def bounded(effect):
            validate_effect(effect,'depletion.action',DEFAULT_CAPABILITIES)
            if effect['op'] in {'schedule','trigger_ability','begin_attachment','heal','regenerate','spawn_on_tiles'}:raise ValueError('Depletion action requires a supported finite synchronous effect; owned-cast bridge separately required')
            for field in ('effects','on_success','on_failure'):
                for child in effect.get(field,()):bounded(child)
        for effect in row['effects']:bounded(effect)
    if not isinstance(spec['parameters'],Mapping):raise ValueError('Depletion parameters must be a record')
    if components is not None:
        if components.get('rebirth') is not None:raise ValueError('Depletion and positive-health rebirth cannot share one owner')
        resource=components.get('resources',{}).get(spec['resource'],{});resource=resource.get('spec',resource)
        if resource.get('role')!='health':raise ValueError('Depletion resource must be declared owner health')
        if number(resource.get('initial',0))<=0:raise ValueError('Depletion owner requires positive initial health')

class DepletionSystem:
    def __init__(self,ctx):self.ctx=ctx;self._attacks=[];self._deliveries=[];self._callbacks=[];self._entries=[]
    def spec(self,ref):return self.ctx.get(ref,('depletion',))
    def state(self,ref):return self.ctx.get(ref,('runtime','depletion'))
    def stamp(self,ref):
        e=self.ctx.entity(ref);r=e['components'].get('runtime',{})
        return {'id':e['id'],'definition':e['definition_id'],'life':r.get('lifecycle_generation',0),'death':r.get('death_generation',0)}
    def snapshot(self,ref):
        if ref is None:return {}
        e=self.ctx.capture_view(ref);e['components'].get('runtime',{}).pop('depletion',None);return e
    def initialize(self,ref):
        spec=self.spec(ref)
        if spec is None:return
        validate(spec,self.ctx.get(ref,()))
        self.ctx.set(ref,('runtime','depletion'),{'generation':0,'stage':spec['initial_stage'],'lease':None})
    def depleted(self,ref):
        state=self.state(ref);return state is not None and state['generation']>0 and self.ctx.alive(ref)
    def _valid_scope(self):
        if not self._callbacks:return None
        scope=self._callbacks[-1];state=self.state(scope['owner'])
        if (state is None or state['generation']!=scope['generation'] or not self.ctx.alive(scope['owner']) or self.stamp(scope['owner'])!=scope['stamp'] or self.ctx.state().get('finished')):return None
        return scope
    def target_allowed(self,ref):
        scope=self._valid_scope();return scope is not None and scope['owner']==self.ctx.session.world.resolve(ref)
    def source_allowed(self,ref,cast=None):
        if ref is None or not self.depleted(ref):return True
        scope=self._valid_scope();return scope is not None and scope['owner']==self.ctx.session.world.resolve(ref) and cast is scope['cast']
    def callback_cast_allowed(self,ref,cast):
        scope=self._valid_scope();return scope is not None and scope['owner']==ref and scope['cast'] is cast
    def damage_gate(self,source,ref,effect,amount,ability=None,cast=None):
        spec=self.spec(ref)
        if spec is None or not spec.get('damage_gate_rule'):return True
        source=self.ctx.session.world.resolve(source) if source is not None else None
        attack=self._attacks[-1] if self._attacks else None
        if attack is None or attack['source']!=source or attack['target']!=ref or attack['resource']!=spec['resource'] or attack['effect'] is not effect or attack['delivered']:raise ValueError('Damage gate requires actual canonical health attack scope')
        inputs={'source':self.snapshot(source),'target':self.snapshot(ref),'request':{'operation':'damage','resource':spec['resource'],'requested_amount':amount,'effect':thaw(effect)},'state':self.state(ref),'clock':{'time':self.ctx.session.time,'quantum':self.ctx.session.quantum},'parameters':spec['parameters']}
        result=self.ctx.calc('resource.depletion',inputs,target=ref,owner=ref,rule_id=spec['damage_gate_rule'],scope_extra={'source':{},'target':{},'owner':{}},extra={'source':inputs['source'],'target':inputs['target'],'owner':inputs['target']});cause=self.ctx.last_calculation_event_id
        if not isinstance(result,Mapping) or set(result)!={'accepted','actions'} or type(result['accepted']) is not bool or not isinstance(result['actions'],(list,tuple)) or len(result['actions'])>32 or len(set(result['actions']))!=len(result['actions']) or any(k not in spec['actions'] for k in result['actions']):raise ValueError('Damage gate requires a finite declared plan')
        token={'depletion_action':{'owner':ref,'generation':self.state(ref)['generation'],'gate':True}};scope={'owner':ref,'generation':self.state(ref)['generation'],'stamp':self.stamp(ref),'cast':token};self._callbacks.append(scope)
        try:
            for key in result['actions']:
                row=spec['actions'][key]
                if row['at_seconds']!=0 or 'next_stage' in row or 'owned_ability' in row:raise ValueError('Damage gate actions must be synchronous effects without lifecycle or cast changes')
                for child in row['effects']:
                    if self._valid_scope() is None:break
                    self.ctx.effects.execute(ref,[ref],thaw(child),cast=token,cause=cause)
        finally:assert self._callbacks.pop() is scope
        return result['accepted']
    def authorize_start(self,ref,ability):
        scope=self._valid_scope()
        if scope is None or scope['owner']!=ref:return None
        state=self.state(ref);lease=state['lease'];slot=scope.get('slot')
        row=lease['actions'].get(slot)
        if row is None or not row['done'] or self.spec(ref)['actions'][row['key']].get('owned_ability')!=ability:return None
        return {'owner':ref,'generation':state['generation'],'stamp':lease['stamp'],'slot':slot,'plan_event':lease['plan_event'],'ability':ability}
    def cast_valid(self,ref,cast):
        permit=cast.get('depletion_owned') if isinstance(cast,Mapping) else None
        if not isinstance(permit,Mapping) or set(permit)!={'owner','generation','stamp','slot','plan_event','ability'}:return False
        state=self.state(ref);lease=state.get('lease') if state else None
        if (not lease or not self.ctx.alive(ref) or permit['owner']!=ref or permit['generation']!=state['generation'] or permit['stamp']!=self.stamp(ref) or permit['plan_event']!=lease['plan_event'] or permit['ability']!=cast.get('ability')):return False
        row=lease['actions'].get(permit['slot'])
        return (row is not None and row['done'] and self.spec(ref)['actions'][row['key']].get('owned_ability')==cast['ability'] and cast['ability'] in self.ctx.get(ref,('abilities',),[]) and cast.get('source')==ref and self.ctx.get(ref,('runtime','casts',cast.get('id')))==thaw(cast))
    @contextmanager
    def cast_scope(self,ref,cast,starting=False):
        if not self.cast_valid(ref,cast):raise ValueError('Depletion owned cast lease is invalid')
        if starting:
            if self.authorize_start(ref,cast['ability'])!=thaw(cast['depletion_owned']):raise ValueError('Depletion cast entry requires actual finite callback')
        else:
            task=self.ctx.session.current_task
            if not (task and task['kind']=='domain.ability.effect' and task['id'] in cast['tasks'] and task['at']==self.ctx.session.time and task['phase']==self.ctx.session.scheduler.rank(self.ctx.effect_phase) and task['payload']['source']==ref and task['payload']['cast']==cast['id']):raise ValueError('Depletion cast effect requires actual owned task')
        scope={'owner':ref,'generation':cast['depletion_owned']['generation'],'stamp':cast['depletion_owned']['stamp'],'cast':cast};self._callbacks.append(scope)
        try:yield
        finally:assert self._callbacks.pop() is scope
    def flags(self,ref):
        state=self.state(ref)
        if state is None or state['generation']==0:return None
        return self.spec(ref)['stages'][state['stage']]
    def health_update(self,ref,resource,candidate):
        if self.depleted(ref) and resource==self.spec(ref)['resource'] and candidate>0:raise ValueError('Owned depletion cannot restore positive health')
    @contextmanager
    def attack(self,source,target,effect,ability=None,cast=None,resource=None):
        source=self.ctx.session.world.resolve(source) if source is not None else None
        target=self.ctx.session.world.resolve(target)
        row={'source':source,'target':target,'resource':resource or effect.get('resource') or self.ctx.health_resource(target),'effect':effect,'ability':ability or {},'cast':cast or {},'delivered':False};self._attacks.append(row)
        try:yield
        finally:assert self._attacks.pop() is row
    @contextmanager
    def delivery(self,ref,event,requested=None):
        spec=self.spec(ref)
        if spec is None:yield;return
        attack=self._attacks[-1] if self._attacks else None
        after=self.ctx.resources.current(ref,spec['resource']);delta=event.get('delta',0)
        source=event.get('source');source=self.ctx.session.world.resolve(source) if source is not None else None
        if (attack is None or attack['delivered'] or event.get('operation')!='damage'
                or attack['source']!=source or attack['target']!=self.ctx.session.world.resolve(ref)
                or attack['resource']!=event.get('resource')):attack=None
        if attack is not None:attack['delivered']=True
        request={'operation':'damage' if attack else 'resource_change','source':source,'target':self.ctx.session.world.resolve(ref),'resource':event['resource'],'health_before':after-delta,'health_after':after,'requested_change':requested if requested is not None else delta,'actual_change':delta,'actual_health_loss':max(-delta,0),'source_snapshot':self.snapshot(source),'source_stamp':self.stamp(source) if source is not None else None,'target_stamp':self.stamp(ref),'attack_type':(attack['effect'].get('attack_type') or attack['effect'].get('damage_flags',{}).get('source_attack_type','NORMAL')) if attack else None,'damage_type':attack['effect'].get('damage_type') if attack else None,'ability':event.get('ability'),'cast':event.get('cast')}
        row={'owner':self.ctx.session.world.resolve(ref),'event':event,'request':request};self._deliveries.append(row)
        try:yield
        finally:assert self._deliveries.pop() is row
    def consume(self,ref,event):
        spec=self.spec(ref)
        if spec is None:return False
        state=self.state(ref);health=self.ctx.resources.current(ref,spec['resource'])
        if health>0:return False
        delivery=self._deliveries[-1] if self._deliveries else None
        if delivery is None or delivery['owner']!=ref or delivery['event'] is not event:return state['generation']>0
        if event.get('resource')!=spec['resource']:return state['generation']>0
        inputs={'source':delivery['request']['source_snapshot'],'target':self.snapshot(ref),'request':delivery['request'],'state':state,'clock':{'time':self.ctx.session.time,'quantum':self.ctx.session.quantum},'parameters':spec['parameters']}
        plan=self.ctx.calc('resource.depletion',inputs,target=ref,owner=ref,rule_id=spec['rule'],scope_extra={'source':{},'target':{},'owner':{}},extra={'source':inputs['source'],'target':inputs['target'],'owner':inputs['target']});event_id=self.ctx.last_calculation_event_id
        if not isinstance(plan,Mapping) or set(plan)!={'action','stage','actions'} or plan['action'] not in {'none','defer','finish'} or plan['stage'] not in spec['stages'] or not isinstance(plan['actions'],list) or len(plan['actions'])>32 or len(set(plan['actions']))!=len(plan['actions']) or any(key not in spec['actions'] for key in plan['actions']):raise ValueError('Invalid finite depletion plan')
        if plan['action']=='none':
            if plan['actions'] or plan['stage']!=state['stage']:raise ValueError('No-op depletion plan must preserve stage and actions')
            return state['generation']>0
        if plan['action']=='finish':
            if plan['actions']:raise ValueError('Finish cannot create new depletion actions')
            self.cancel(ref,'finish');return False
        self.cancel(ref,'replace');state=self.state(ref);state['generation']+=1;state['stage']=plan['stage']
        lease={'generation':state['generation'],'stamp':self.stamp(ref),'spec_digest':digest(spec),'plan_event':event_id,'started_event':None,'plan':plan,'provenance':delivery['request'],'started':self.ctx.session.time,'actions':{}}
        state['lease']=lease;self.ctx.set(ref,('runtime','depletion'),state)
        self.ctx.abilities.interrupt(ref,'depletion')
        for slot,key in enumerate(plan['actions']):
            action=spec['actions'][key]
            ticks=self.ctx.calc('time.quantize',{'seconds':action['at_seconds'],'quantum':self.ctx.session.quantum,'rounding':{'mode':'ceil'}},extra={'depletion_schedule_next_seq':self.ctx.session.scheduler._next_seq,'depletion_effect_phase':self.ctx.effect_phase})
            time_event=self.ctx.last_calculation_event_id;due=self.ctx.session.time+ticks
            if type(ticks) is not int or ticks<0:raise ValueError('Depletion quantized time must be finite logical ticks')
            if ticks==0:lease['actions'][str(slot)]={'key':key,'due':due,'task':None,'seq':None,'phase':self.ctx.effect_phase,'done':False,'time_event':time_event,'issued_event':None,'executed_event':None}
            else:
                seq=self.ctx.session.scheduler._next_seq;tid=self.ctx.session.schedule('domain.depletion.action',{'target':ref,'generation':state['generation'],'slot':slot},due,phase=self.ctx.effect_phase)
                lease['actions'][str(slot)]={'key':key,'due':due,'task':tid,'seq':seq,'phase':self.ctx.effect_phase,'done':False,'time_event':time_event,'issued_event':None,'executed_event':None}
            record=lease['actions'][str(slot)]
            record['issued_event']=self.ctx.emit('depletion.action.issued',{'target':ref,'generation':state['generation'],'slot':str(slot),'key':key,'due':due,'task':record['task'],'seq':record['seq'],'phase':record['phase'],'time_event':time_event},event_id)
        state=self.state(ref);state['lease']=lease;self.ctx.set(ref,('runtime','depletion'),state)
        started=self.ctx.emit('depletion.started',{'target':ref,'generation':state['generation'],'stage':state['stage'],'provenance':lease['provenance']},event_id)
        current=self.state(ref);current['lease']['started_event']=started;self.ctx.set(ref,('runtime','depletion'),current)
        for slot,row in lease['actions'].items():
            if row['task'] is None:
                entry={'owner':ref,'generation':state['generation'],'slot':slot,'delivery':delivery}
                self._entries.append(entry)
                try:self._dispatch(ref,state['generation'],slot)
                finally:assert self._entries.pop() is entry
        return True
    def _dispatch(self,ref,generation,slot):
        state=self.state(ref);lease=state.get('lease') if state else None
        if not lease or lease['generation']!=generation or lease['stamp']!=self.stamp(ref) or not self.ctx.alive(ref):return
        spec=self.spec(ref)
        if digest(spec)!=lease['spec_digest']:raise ValueError('Owned depletion declaration changed')
        row=lease['actions'][slot]
        if row['done']:return
        task=self.ctx.session.current_task
        entry=self._entries[-1] if self._entries else None
        if row['task'] is None:
            if (entry is None or entry['owner']!=ref or entry['generation']!=generation or entry['slot']!=slot
                    or not self._deliveries or self._deliveries[-1] is not entry['delivery']
                    or self.ctx.session.time!=lease['started'] or row['due']!=self.ctx.session.time):return
        elif (task is None or task['id']!=row['task'] or task['seq']!=row['seq']
                or self.ctx.session.time!=row['due'] or task['at']!=row['due']
                or task['phase']!=self.ctx.session.scheduler.rank(row['phase'])
                or task['kind']!='domain.depletion.action'
                or task['payload']!={'target':ref,'generation':generation,'slot':int(slot)}):return
        row['done']=True;action=spec['actions'][row['key']]
        if 'next_stage' in action:state['stage']=action['next_stage']
        self.ctx.set(ref,('runtime','depletion'),state)
        cast={'depletion_action':{'owner':ref,'generation':generation,'slot':slot}};scope={'owner':ref,'generation':generation,'stamp':lease['stamp'],'cast':cast,'slot':slot};self._callbacks.append(scope)
        try:
            for effect in action['effects']:
                if self._valid_scope() is None:break
                child=thaw(effect)
                if child['op']=='no_source_damage':
                    child.setdefault('origin',{})['depletion']=thaw(lease['provenance']);self.ctx.effects.execute(None,[ref],child,cause=lease['plan_event'])
                else:self.ctx.effects.execute(ref,[ref],child,cast=cast,cause=lease['plan_event'])
            if action.get('owned_ability') and self._valid_scope() is not None:
                self.ctx.abilities.start(ref,action['owned_ability'],automatic=True,cause=lease['plan_event'])
        finally:assert self._callbacks.pop() is scope
        executed=self.ctx.emit('depletion.action.executed',{'target':ref,'generation':generation,'slot':slot,'key':row['key'],'stage':state['stage']},lease['plan_event'])
        current=self.state(ref)
        if current is not None and current['generation']==generation and current['lease'] is not None:
            current['lease']['actions'][slot]['executed_event']=executed;self.ctx.set(ref,('runtime','depletion'),current)
    def action(self,session,payload):
        with session.atomic():
            if not isinstance(payload,Mapping) or set(payload)!={'target','generation','slot'} or any(type(payload[k]) is not int for k in payload) or payload['target']<1 or payload['generation']<1 or payload['slot']<0:raise ValueError('Strict depletion action identity required')
            ref=payload['target'];state=self.state(ref);lease=state.get('lease') if state else None;task=session.current_task
            row=lease.get('actions',{}).get(str(payload['slot'])) if lease else None
            if not row or lease['generation']!=payload['generation'] or not task or row['task']!=task['id'] or row['seq']!=task['seq'] or row['due']!=session.time or task['at']!=row['due'] or task['phase']!=session.scheduler.rank(row['phase']) or task['kind']!='domain.depletion.action' or task['payload']!=thaw(payload):return
            self._dispatch(ref,payload['generation'],str(payload['slot']))
    def cancel(self,ref,reason):
        state=self.state(ref)
        if state is None or state['lease'] is None:return
        pending={x['id'] for x in self.ctx.session.scheduler.pending}
        for row in state['lease']['actions'].values():
            if row['task'] in pending:self.ctx.session.cancel(row['task'])
        state['lease']=None;state['generation']+=1;self.ctx.set(ref,('runtime','depletion'),state)
        self.ctx.emit('depletion.cancelled',{'target':ref,'reason':reason,'generation':state['generation']})
    def validate_restored(self):
        for entity in self.ctx.session.world.entities():
            ref=entity['id'];state=self.state(ref)
            if state is None:continue
            spec=self.spec(ref);validate(spec)
            if set(state)!={'generation','stage','lease'} or type(state['generation']) is not int or state['generation']<0 or state['stage'] not in spec['stages']:raise ValueError('Invalid restored depletion state')
            lease=state['lease']
            if lease is None:continue
            if not isinstance(lease,dict) or set(lease)!={'generation','stamp','spec_digest','plan_event','started_event','plan','provenance','started','actions'}:raise ValueError('Invalid restored depletion lease shape')
            if lease['generation']!=state['generation'] or lease['stamp']!=self.stamp(ref) or lease['spec_digest']!=digest(spec) or self.ctx.resources.current(ref,spec['resource'])!=0:raise ValueError('Invalid restored depletion owner')
            event=self.ctx.session._events._records[lease['plan_event']-1]
            if event['id']!=lease['plan_event'] or event['payload'].get('calculation_id')!='resource.depletion' or event['payload'].get('rule_id')!=spec['rule'] or thaw(event['payload']['value'])!=lease['plan'] or event['payload']['trace']['rule_fingerprint']!=self.ctx.rules.rule_fingerprints[spec['rule']]:raise ValueError('Restored depletion lineage differs')
            started=self.ctx.session._events._records[lease['started_event']-1]
            if started['type']!='depletion.started' or started['id']!=lease['started_event'] or started['time']!=lease['started'] or started['cause']!=lease['plan_event'] or started['payload']['target']!=ref or started['payload']['generation']!=state['generation'] or thaw(started['payload']['provenance'])!=lease['provenance']:raise ValueError('Restored depletion provenance differs')
            expected={'request':lease['provenance'],'source':lease['provenance']['source_snapshot']}
            if self.ctx.program.ruleset.get('parameters',{}).get('trace_mode','compact')!='full':
                from .context import compact_trace
                expected=thaw(compact_trace(expected))
            recorded={'request':thaw(event['payload']['trace']['inputs']['request']),'source':thaw(event['payload']['trace']['inputs']['source'])}
            if digest(expected)!=digest(recorded):raise ValueError('Restored depletion calculation request differs')
            from .context import compact_trace
            compact=self.ctx.program.ruleset.get('parameters',{}).get('trace_mode','compact')!='full'
            declared=thaw(compact_trace(spec)) if compact else spec
            if digest(event['payload']['trace']['inputs']['target']['components']['depletion'])!=digest(declared):raise ValueError('Restored declaration differs from historical plan target')
            original_inputs=thaw(event['payload']['trace']['inputs']);original_inputs['source']=lease['provenance']['source_snapshot'];original_inputs['request']=lease['provenance'];original_inputs['target']['components']['depletion']=spec
            plan_scope={'scenario':self.ctx.program.scenario.get('rules',{}),'source':{},'target':{},'owner':{},'component':{},'attribute_or_resource':{},'ability':{},'effect':{}}
            plan_context={'time':lease['started'],'seconds':lease['started']*self.ctx.session.quantum,'quantum':self.ctx.session.quantum,'source':original_inputs['source'],'target':original_inputs['target'],'owner':original_inputs['target']}
            recalculated=self.ctx.rules.evaluate('resource.depletion',original_inputs,scope=plan_scope,rule_id=spec['rule'],context=plan_context)
            trace=thaw(compact_trace(recalculated.trace)) if compact else thaw(recalculated.trace)
            if digest(trace)!=digest(event['payload']['trace']) or digest(recalculated.value)!=digest(lease['plan']):raise ValueError('Restored original pure depletion plan cannot be reproduced')
            pending={x['id']:x for x in self.ctx.session.scheduler.pending}
            if set(lease['actions'])!={str(i) for i in range(len(lease['plan']['actions']))}:raise ValueError('Restored action count or slots differ from plan')
            progressed=[]
            for slot,row in lease['actions'].items():
                if (not isinstance(row,dict) or set(row)!={'key','due','task','seq','phase','done','time_event','issued_event','executed_event'} or row['key']!=lease['plan']['actions'][int(slot)] or row['key'] not in spec['actions'] or type(row['done']) is not bool):raise ValueError('Invalid restored action declaration')
                timing=self.ctx.session._events._records[row['time_event']-1]
                if (timing['type']!='calculation' or timing['time']!=lease['started'] or timing['payload'].get('calculation_id')!='time.quantize' or timing['payload']['trace']['inputs']['seconds']!=spec['actions'][row['key']]['at_seconds'] or timing['payload']['trace']['inputs']['quantum']!=self.ctx.session.quantum or type(timing['payload']['value']) is not int or row['due']!=lease['started']+timing['payload']['value']):raise ValueError('Restored action due differs from declared quantized offset')
                timing_inputs={'seconds':spec['actions'][row['key']]['at_seconds'],'quantum':self.ctx.session.quantum,'rounding':{'mode':'ceil'}}
                timing_context={'time':lease['started'],'seconds':lease['started']*self.ctx.session.quantum,'quantum':self.ctx.session.quantum,'source':{},'target':{},'owner':{}}
                timing_context.update({k:timing['payload']['trace']['context'][k] for k in ('depletion_schedule_next_seq','depletion_effect_phase')})
                time_result=self.ctx.rules.evaluate('time.quantize',timing_inputs,scope=plan_scope,context=timing_context)
                time_trace=thaw(compact_trace(time_result.trace)) if compact else thaw(time_result.trace)
                if digest(time_trace)!=digest(timing['payload']['trace']) or digest(time_result.value)!=digest(timing['payload']['value']) or row['due']!=lease['started']+time_result.value:raise ValueError('Restored pure action clock cannot be reproduced')
                if row['phase']!=self.ctx.effect_phase or row['phase']!=timing_context['depletion_effect_phase'] or (row['task'] is not None and row['seq']!=timing_context['depletion_schedule_next_seq']):raise ValueError('Restored action phase or issued sequence differs from original clock context')
                issued=self.ctx.session._events._records[row['issued_event']-1]
                expected_issue={'target':ref,'generation':state['generation'],'slot':slot,'key':row['key'],'due':row['due'],'task':row['task'],'seq':row['seq'],'phase':row['phase'],'time_event':row['time_event']}
                if issued['type']!='depletion.action.issued' or issued['time']!=lease['started'] or issued['cause']!=lease['plan_event'] or thaw(issued['payload'])!=expected_issue:raise ValueError('Restored action issued ownership differs')
                if not row['done']:
                    if row['executed_event'] is not None:raise ValueError('Unexecuted action has execution claim')
                    task=pending.get(row['task']);expected={'target':ref,'generation':state['generation'],'slot':int(slot)}
                    if task is None or task['seq']!=row['seq'] or task['at']!=row['due'] or task['phase']!=self.ctx.session.scheduler.rank(row['phase']) or task['kind']!='domain.depletion.action' or task['payload']!=expected:raise ValueError('Restored depletion task differs')
                else:
                    if row['task'] in pending or type(row['executed_event']) is not int:raise ValueError('Executed action still pending or lacks event')
                    executed=self.ctx.session._events._records[row['executed_event']-1]
                    next_stage=spec['actions'][row['key']].get('next_stage')
                    if executed['type']!='depletion.action.executed' or executed['time']!=row['due'] or executed['cause']!=lease['plan_event'] or executed['payload']['target']!=ref or executed['payload']['generation']!=state['generation'] or executed['payload']['slot']!=slot or executed['payload']['key']!=row['key']:raise ValueError('Restored execution event differs')
                    progressed.append((row['executed_event'],next_stage,executed['payload']['stage']))
            expected_stage=lease['plan']['stage']
            for _,next_stage,observed in sorted(progressed):
                if next_stage is not None:expected_stage=next_stage
                if observed!=expected_stage:raise ValueError('Restored action stage progression differs')
            if state['stage']!=expected_stage:raise ValueError('Restored stage differs from executed actions')
            for cast in self.ctx.get(ref,('runtime','casts'),{}).values():
                if not cast.get('depletion_owned'):raise ValueError('Depleted owner cannot retain an ordinary cast')
                if not self.cast_valid(ref,cast):raise ValueError('Restored depletion cast ownership differs')
                self.validate_cast_record(ref,cast)
    def validate_cast_record(self,ref,cast):
        from .context import compact_trace
        events=self.ctx.session._events._records
        proof=events[cast['depletion_schedule_event']-1]
        data=proof['payload'];permit=cast['depletion_owned']
        if (proof['type']!='depletion.cast.issued' or proof['cause']!=permit['plan_event'] or proof['time']!=cast['started_at'] or data['source']!=ref or data['cast']!=cast['id'] or thaw(data['permit'])!=thaw(permit) or data['generation']!=cast['generation'] or data['started_at']!=cast['started_at'] or data['finish_at']!=cast['finish_at'] or thaw(data['tile_targets'])!=cast.get('tile_targets',[]) or thaw(data['timing_events'])!=cast['depletion_timing_events']):raise ValueError('Restored issued owned cast differs')
        tasks=thaw(data['tasks'])
        if [t['id'] for t in tasks]!=cast['tasks'] or len(set(cast['tasks']))!=len(cast['tasks']):raise ValueError('Owned cast task identity differs')
        ability=self.ctx.program.definitions[cast['ability']]
        declared=[thaw(e) for row in ability.get('timeline',[]) for e in (row.get('effects',[]) or ([row['effect']] if 'effect' in row else []))]
        pending={t['id']:thaw(t) for t in self.ctx.session.scheduler.pending}
        clock=events[cast['depletion_schedule_clock']-1]['payload']['trace']['context']
        for index,task in enumerate(tasks):
            if task['id']!=clock['depletion_cast_next_task']+index or task['seq']!=clock['depletion_cast_next_seq']+index or task['phase']!=clock['depletion_cast_phase']:raise ValueError('Owned cast task identity differs from original scheduling clock')
            if task['phase']!=self.ctx.session.scheduler.rank(self.ctx.effect_phase) or task['payload']['source']!=ref or task['payload']['cast']!=cast['id']:raise ValueError('Owned cast task scope differs')
            if task['kind']=='domain.ability.effect':
                if task['payload']['effect'] not in declared:raise ValueError('Owned cast task effect is not declared')
            elif task['kind']!='domain.ability.finish':raise ValueError('Owned cast task kind differs')
            if task['id'] in pending and pending[task['id']]!=task:raise ValueError('Owned cast pending task differs from issuance')
            if task['at']>=self.ctx.session.time and task['id'] not in pending:raise ValueError('Owned cast future task missing')
        compact=self.ctx.program.ruleset.get('parameters',{}).get('trace_mode','compact')!='full'
        for event_id in cast['depletion_timing_events']:
            event=events[event_id-1];payload=event['payload'];trace=thaw(payload['trace']);context=trace['context']
            if event['type']!='calculation' or event['time']!=cast['started_at'] or payload['calculation_id'] not in {'ability.windup','ability.repeat','ability.duration','ability.recovery','time.quantize'}:raise ValueError('Owned cast timing event differs')
            if compact:
                for role in ['source','target','owner']:
                    actor=context.pop(role+'_id',None);context[role]=cast['depletion_timing_source'] if actor==ref else {}
            result=self.ctx.rules.evaluate(payload['calculation_id'],trace['inputs'],scope=context['rule_scope'],context=context)
            actual=thaw(compact_trace(result.trace)) if compact else thaw(result.trace)
            if digest(actual)!=digest(payload['trace']) or digest(result.value)!=digest(payload['value']):raise ValueError('Owned cast timing pure rule cannot be reproduced')
        # Reconstruct the declared finite timeline from the original pure timing
        # results, rather than accepting mutually edited queue/issuance times.
        calculations=[events[i-1]['payload'] for i in cast['depletion_timing_events'] if i!=cast['depletion_schedule_clock']]
        cursor=0;expected=[];last_delay=0
        params={**thaw(ability.get('parameters',{})),**thaw(ability.get('activation',{}).get('parameters',{}))}
        pre=ability.get('activation',{}).get('parameters',{}).get('windup_seconds',params.get('pre_delay_seconds',0))
        for entry in ability.get('timeline',[]):
            wind,repeat,delay,interval=calculations[cursor:cursor+4];cursor+=4
            seconds=entry['at']*self.ctx.session.quantum if 'at' in entry else entry.get('at_seconds',0)
            if [x['calculation_id'] for x in (wind,repeat,delay,interval)]!=['ability.windup','ability.repeat','time.quantize','time.quantize'] or wind['trace']['inputs']['timing_parameters']['seconds']!=pre+seconds or delay['trace']['inputs']['seconds']!=wind['value'] or interval['trace']['inputs']['seconds']!=repeat['value']['interval']:raise ValueError('Owned cast declared timing inputs differ')
            for n in range(repeat['value']['count']):
                offset=delay['value']+n*interval['value'];last_delay=max(last_delay,offset)
                for effect in entry.get('effects',[]) or ([entry['effect']] if 'effect' in entry else []):expected.append({'kind':'domain.ability.effect','at':cast['started_at']+offset,'payload':{'source':ref,'cast':cast['id'],'effect':thaw(effect),'condition':entry.get('condition')}})
        duration,finish=calculations[cursor:cursor+2]
        if duration['calculation_id']!='ability.duration' or finish['calculation_id']!='time.quantize' or duration['trace']['inputs']['duration_parameters']['seconds']!=ability.get('duration_seconds',ability.get('activation',{}).get('duration_seconds',0)) or finish['trace']['inputs']['seconds']!=duration['value']:raise ValueError('Owned cast declared duration differs')
        due=cast['started_at']+max(last_delay,finish['value']);expected.append({'kind':'domain.ability.finish','at':due,'payload':{'source':ref,'cast':cast['id']}})
        if due!=cast['finish_at'] or [{'kind':t['kind'],'at':t['at'],'payload':t['payload']} for t in tasks]!=expected:raise ValueError('Owned cast queue differs from pure declared timeline')
