"""Generic independent elemental resources and a generation-bound break lease.

This file is a candidate source template, never imported by the primary runtime.
"""
from collections.abc import Mapping
import math
from ark_sim.contracts import thaw, digest
from . import elemental_proofs as audit
from .elemental_proofs import tracked

ELEMENT_RULES = {'elemental.capacity', 'elemental.loss', 'elemental.recovery', 'elemental.break_duration'}

def numeric(value, minimum=0):
    if type(value) not in (int,float) or not math.isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError('Elemental values must be finite numbers within their declared bounds')
    return value

def validate(spec):
    if not isinstance(spec,Mapping) or set(spec)-{'elements','eligibility_rule','parameters'}:
        raise ValueError('Elemental component has unknown fields')
    if not isinstance(spec.get('eligibility_rule'),str) or not spec['eligibility_rule']:
        raise ValueError('Elemental component requires an explicit eligibility rule')
    elements=spec.get('elements')
    if not isinstance(elements,Mapping) or not elements:
        raise ValueError('Elemental component requires a finite nonempty element mapping')
    for key,item in elements.items():
        if not isinstance(key,str) or not key or not isinstance(item,Mapping):
            raise ValueError('Element keys must be nonempty strings and profiles must be records')
        if set(item)-{'capacity','resistance','recovery_rate','break_duration_seconds','rules','parameters','on_break','on_end'}:
            raise ValueError('Element profile has unknown fields')
        for name in ('capacity','resistance','recovery_rate','break_duration_seconds'):
            numeric(item.get(name), .000000001 if name in ('capacity','break_duration_seconds') else None)
        if not isinstance(item.get('rules'),Mapping) or set(item['rules'])!=ELEMENT_RULES or not all(isinstance(x,str) and x for x in item['rules'].values()):
            raise ValueError('Element profile requires four explicit calculation bindings')
        for name in ('on_break','on_end'):
            if not isinstance(item.get(name,()),(list,tuple)):
                raise ValueError('Element lifecycle callbacks must be finite effect lists')

def validate_effect(effect):
    target=effect.get('target','selected')
    if target not in ('selected','target') and (type(target) is not int or target<1):
        raise ValueError('Elemental requests require selected or a strict positive target ID')
    if effect.get('op')=='elemental_attack':
        if set(effect)-{'op','target','health_effect','element_effect','metadata'}:
            raise ValueError('Elemental attack has unknown fields')
        health,element=effect.get('health_effect'),effect.get('element_effect')
        if not isinstance(health,Mapping) or health.get('op')!='damage' or health.get('target','selected')!='selected':
            raise ValueError('Atomic elemental attack requires a selected actor health damage effect')
        if not isinstance(element,Mapping) or element.get('op')!='elemental_damage' or element.get('target','selected')!='selected':
            raise ValueError('Atomic elemental attack requires a selected elemental damage effect')
        validate_effect(element)
        return
    if set(effect)-{'op','target','element','amount','amount_rule','parameters','metadata'} or effect.get('op')!='elemental_damage':
        raise ValueError('Elemental damage has unknown fields')
    if not isinstance(effect.get('element'),str) or not effect['element']:
        raise ValueError('Elemental damage requires an exact content element key')
    if ('amount' in effect)==('amount_rule' in effect):
        raise ValueError('Elemental damage requires exactly one amount or amount_rule')
    if 'amount' in effect:numeric(effect['amount'])
    elif not isinstance(effect['amount_rule'],str) or not effect['amount_rule']:
        raise ValueError('Elemental packet amount rule must be a nonempty ID')

class ElementalSystem:
    def __init__(self,ctx):
        self.ctx=ctx
        self._proof_stack=[]
        self._callback_token=object()
        self._callback_scopes=[]

    def profile(self,ref):
        return self.ctx.get(ref,('elemental',))

    def stamp(self,ref):
        entity=self.ctx.entity(ref);runtime=entity['components'].get('runtime',{})
        return {'id':entity['id'],'definition':entity['definition_id'],'alive':self.ctx.alive(ref),'state':runtime.get('state'),
                'death_generation':runtime.get('death_generation',0),'lifecycle_generation':runtime.get('lifecycle_generation',0),'active':self.ctx.active(ref),'finished':bool(self.ctx.state().get('finished'))}

    def calculate(self,contract,ref,key,profile,request=None,source=None,current=0,capacity=0,dt=0):
        inputs={'source':self.ctx.capture_view(source) if source is not None else {},
                'target':self.ctx.capture_view(ref),'element':key,'current':current,'capacity':capacity,
                'delta_seconds':dt,'request':request or {},
                'attributes':{'source':self.ctx.attributes.values(source) if source is not None else {},'target':self.ctx.attributes.values(ref)},
                'parameters':{name:thaw(value) for name,value in profile.items() if name not in {'rules','on_break','on_end'}}}
        rule=profile['rules'].get(contract) if contract in ELEMENT_RULES else self.profile(ref)['eligibility_rule']
        return audit.calculate(self,contract,inputs,source=source,target=ref,owner=ref,rule_id=rule)

    @tracked
    def initialize(self,ref):
        spec=self.profile(ref)
        if spec is None:return
        validate(spec)
        remaining={}
        for key,profile in spec['elements'].items():
            remaining[key]=numeric(self.calculate('elemental.capacity',ref,key,profile), .000000001)
        self.ctx.set(ref,('runtime','elemental'),{'remaining':remaining,'break':None,'generation':0,'last_time':self.ctx.session.time})
        audit.seal(self,ref,'initialize')

    def valid(self,ref,stamp):
        return self.ctx.active(ref) and self.stamp(ref)==stamp and not self.ctx.state().get('finished')

    @tracked
    def cancel(self,ref,reason):
        state=self.ctx.get(ref,('runtime','elemental'))
        if state is None:return
        lease=state.get('break')
        if lease is None:
            recorded=audit.event(self,state['audit_event'])['payload']
            if recorded['stamp']!=self.stamp(ref):audit.seal(self,ref,'owner_state',{'before':thaw(state),'reason':reason})
            return
        if lease is not None:
            if lease.get('task') in {x['id'] for x in self.ctx.session.scheduler.pending}:
                self.ctx.session.cancel(lease['task'])
            before=thaw(state)
            state['break']=None;state['generation']+=1
            self.ctx.set(ref,('runtime','elemental'),state)
            self.ctx.emit('elemental.break.cancelled',{'target':ref,'reason':reason,'generation':lease['generation']})
            audit.seal(self,ref,'cancelled',{'before':before,'closed_lease':lease,'reason':reason})

    @tracked
    def sync_capacities(self,ref):
        state=self.ctx.get(ref,('runtime','elemental'));before=thaw(state);planned={};changes=[]
        for key,profile in self.profile(ref)['elements'].items():
            capacity=numeric(self.calculate('elemental.capacity',ref,key,profile),.000000001)
            current=state['remaining'][key];planned[key]=min(current,capacity)
            if planned[key]!=current:changes.append({'element':key,'previous':current,'remaining':planned[key],'capacity':capacity})
        if changes:
            state['remaining']=planned;self.ctx.set(ref,('runtime','elemental'),state)
            for row in changes:self.ctx.emit('elemental.capacity.synced',{'target':ref,**row})
            audit.seal(self,ref,'capacity',{'before':before})
            state=self.ctx.get(ref,('runtime','elemental'))
        return state

    def _owned_callbacks(self,ref,key,lease,name,cause,*,_capability=None):
        if _capability is not self._callback_token:raise ValueError('Elemental callbacks require actual runtime-owned scope')
        self._callback_scopes.append((ref,lease['generation'],key,name,cause))
        try:return self.callbacks(ref,key,lease,name,cause)
        finally:self._callback_scopes.pop()

    def callbacks(self,ref,key,lease,name,cause):
        if not self._callback_scopes or self._callback_scopes[-1]!=(ref,lease['generation'],key,name,cause):raise ValueError('Elemental callbacks data do not grant owned permission')
        # The status/break owner executes its declared callbacks. Original
        # damage attribution remains separate immutable provenance data.
        for effect in self.profile(ref)['elements'][key].get(name,()):
            if not self.valid(ref,lease['target_stamp']):return
            actual=self.ctx.get(ref,('runtime','elemental'))
            if actual['generation']!=lease['generation']:return
            if name=='on_break' and (actual.get('break') or {}).get('generation')!=lease['generation']:return
            child=thaw(effect)
            if child.get('op')=='no_source_damage':
                # Attribution stays None. The real owned break lineage is data
                # in origin, not actor/cast permission or a dummy zero-ATK unit.
                child.setdefault('origin',{})['elemental_break']={
                    'owner':ref,'generation':lease['generation'],
                    'provenance':thaw(lease['provenance'])}
                self.ctx.effects.execute(None,[ref],child,cause=cause)
            else:
                child.setdefault('parameters',{})['elemental_break']=thaw(lease['provenance'])
                self.ctx.effects.execute(ref,[ref],child,cause=cause)

    @tracked
    def apply(self,source,ref,effect,cause=None,cast=None):
        validate_effect(effect)
        with self.ctx.session.atomic():
            spec=self.profile(ref)
            if spec is None:return {'accepted':False,'reason':'component_absent'}
            key=effect['element']
            if key not in spec['elements']:raise ValueError('Elemental request key is outside the declared finite set')
            if not self.ctx.active(ref) or not self.ctx.effect_target_available(ref) or self.ctx.state().get('finished'):
                return {'accepted':False,'reason':'target_invalid'}
            retained=(source is not None and cast is not None and self.ctx.projectiles is not None
                      and self.ctx.projectiles.retained_payload_allowed(source,ref,cast) is True)
            if source is not None and not self.ctx.active(source) and not retained:return {'accepted':False,'reason':'source_invalid'}
            state=self.ctx.get(ref,('runtime','elemental'));profile=spec['elements'][key]
            if state is None:raise ValueError('Elemental owner was not initialized')
            # Locked and zero direct requests are genuine no-ops: no rule calls,
            # event records, RNG consumption or world writes.
            if state['break'] is not None:return {'accepted':False,'reason':'break_locked'}
            if effect.get('amount')==0:return {'accepted':True,'loss':0,'break':False}
            accepted=self.calculate('elemental.eligibility',ref,key,profile,effect,source=source,current=state['remaining'][key])
            if type(accepted) is not bool:raise ValueError('Elemental eligibility must return a strict bool')
            if not accepted:return {'accepted':False,'reason':'eligibility'}
            request=thaw(effect)
            if 'amount_rule' in effect:
                request['raw_amount']=numeric(audit.calculate(self,'elemental.packet',{
                    'source':self.ctx.capture_view(source) if source is not None else {},'target':self.ctx.capture_view(ref),
                    'source_attributes':self.ctx.attributes.values(source) if source is not None else {},
                    'target_attributes':self.ctx.attributes.values(ref),'request':request},
                    source=source,target=ref,owner=ref,rule_id=effect['amount_rule']))
            else:request['raw_amount']=effect['amount']
            if request['raw_amount']==0:return {'accepted':True,'loss':0,'break':False}
            state=self.sync_capacities(ref)
            capacity=numeric(self.calculate('elemental.capacity',ref,key,profile,request,source),.000000001)
            current=state['remaining'][key]
            before=thaw(state)
            loss=numeric(self.calculate('elemental.loss',ref,key,profile,request,source,current,capacity))
            if loss==0:return {'accepted':True,'loss':0,'break':False}
            state['remaining'][key]=max(0,current-loss)
            crossing=state['remaining'][key]<=0
            lease=None
            if crossing:
                seconds=numeric(self.calculate('elemental.break_duration',ref,key,profile,request,source,current,capacity),.000000001)
                ticks=audit.calculate(self,'time.quantize',{'seconds':seconds,'quantum':self.ctx.session.quantum,'rounding':{'mode':'ceil'}},target=ref,owner=ref)
                if type(ticks) is not int or ticks<1:raise ValueError('Elemental break duration must advance logical time')
                state['generation']+=1
                session=self.ctx.session;due=session.time+ticks
                provenance={'element':key,'source':source,'source_stamp':self.stamp(source) if source is not None else None,
                            'source_snapshot':self.ctx.capture_view(source) if source is not None else {},'request':request}
                lease={'generation':state['generation'],'target_stamp':self.stamp(ref),'element':key,
                       'due':due,'phase':self.ctx.effect_phase,'seq':session.scheduler._next_seq,'provenance':provenance}
                lease['task']=session.schedule('domain.elemental.expire',{'target':ref,'generation':lease['generation']},due,phase=lease['phase'])
                state['break']=lease
            self.ctx.set(ref,('runtime','elemental'),state)
            event=self.ctx.emit('elemental.loss.accepted',{'source':source,'target':ref,'element':key,'loss':loss,
                'actual_loss':current-state['remaining'][key],'remaining':state['remaining'][key],'break':crossing},cause)
            if crossing:
                event=self.ctx.emit('elemental.break.started',{'source':source,'target':ref,'element':key,'generation':lease['generation'],'due':lease['due'],'lease':thaw(lease),'profile_digest':digest(spec)},event)
                lease['break_event']=event
                state['break']=lease
                self.ctx.set(ref,('runtime','elemental'),state)
                audit.seal(self,ref,'loss',{'before':before,'request':request,'source':source,'element':key})
                self._owned_callbacks(ref,key,lease,'on_break',event,_capability=self._callback_token)
            if not crossing:audit.seal(self,ref,'loss',{'before':before,'request':request,'source':source,'element':key})
            return {'accepted':True,'loss':loss,'break':crossing}

    @tracked
    def expire(self,session,payload):
        with session.atomic():
            if (not isinstance(payload,Mapping) or set(payload)!={'target','generation'} or
                type(payload['target']) is not int or payload['target']<1 or
                type(payload['generation']) is not int or payload['generation']<1):
                raise ValueError('Elemental expiry requires strict owned identity and generation')
            ref=payload['target'];state=self.ctx.get(ref,('runtime','elemental'))
            lease=state.get('break') if state else None
            task=session.current_task
            if (not lease or payload.get('generation')!=lease['generation'] or not task or
                task['id']!=lease['task'] or task['seq']!=lease['seq'] or session.time!=lease['due'] or
                task['phase']!=session.scheduler.rank(lease['phase']) or task['kind']!='domain.elemental.expire'):
                return
            if not self.valid(ref,lease['target_stamp']):self.cancel(ref,'owner_invalid');return
            before=thaw(state)
            spec=self.profile(ref);remaining={}
            for key,profile in spec['elements'].items():
                remaining[key]=numeric(self.calculate('elemental.capacity',ref,key,profile),.000000001)
            state.update(remaining=remaining,**{'break':None,'last_time':session.time})
            self.ctx.set(ref,('runtime','elemental'),state)
            event=self.ctx.emit('elemental.break.ended',{'target':ref,'element':lease['element'],'generation':lease['generation']},lease['break_event'])
            audit.seal(self,ref,'ended',{'before':before,'closed_lease':lease,'actual_task':thaw(task),'end_event':event})
            self._owned_callbacks(ref,lease['element'],lease,'on_end',event,_capability=self._callback_token)

    @tracked
    def tick(self,session):
        with session.atomic():
            updated=[]
            for actor in session.world.entities():
                ref=actor['id'];state=self.ctx.get(ref,('runtime','elemental'))
                if state is None:continue
                if not self.ctx.active(ref) or self.ctx.state().get('finished'):
                    self.cancel(ref,'owner_invalid');continue
                if state['break'] is not None and self.stamp(ref)!=state['break']['target_stamp']:
                    self.cancel(ref,'owner_generation_changed')
                    state=self.ctx.get(ref,('runtime','elemental'))
                if state['last_time']>=session.time:continue
                before=thaw(state)
                dt=(session.time-state['last_time'])*session.quantum
                state['last_time']=session.time
                updated.append({'target':ref,'before':before['last_time'],'last_time':session.time,'generation':state['generation']})
                if state['break'] is None:
                    for key,profile in self.profile(ref)['elements'].items():
                        capacity=numeric(self.calculate('elemental.capacity',ref,key,profile),.000000001)
                        value=numeric(self.calculate('elemental.recovery',ref,key,profile,
                            current=min(state['remaining'][key],capacity),capacity=capacity,dt=dt))
                        if value>capacity:raise ValueError('Elemental recovery must return a value within capacity')
                        state['remaining'][key]=value
                self.ctx.set(ref,('runtime','elemental'),state)
                if state['remaining']!=before['remaining']:audit.seal(self,ref,'recovery',{'before':before,'delta_seconds':dt})
            if updated:session.emit('elemental.tick.record',{'time':session.time,'updated':updated})

    def validate_restored(self):
        return audit.validate_restored(self)
