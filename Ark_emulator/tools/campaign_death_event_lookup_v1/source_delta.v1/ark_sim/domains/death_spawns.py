"""Finite post-retirement births owned by a real death and scheduler task.

Only authored definitions/placement can execute. Corpse dictionaries, ordinary
effects and copied task payloads never constitute a spawn capability.
"""
import math
from collections.abc import Mapping
from ark_sim.contracts import thaw,digest

def validate(spec):
    if not isinstance(spec,Mapping) or set(spec)!={'actions'} or not isinstance(spec['actions'],(list,tuple)) or not 1<=len(spec['actions'])<=16:raise ValueError('Death spawns require finite declared actions')
    keys=set()
    for row in spec['actions']:
        if not isinstance(row,Mapping) or set(row)!={'key','definition','count','delay_seconds','inherit_route','managed','rule','parameters','placement'}:raise ValueError('Death spawn action has exact definition/count/timing/inheritance/placement fields')
        if any(not isinstance(row[k],str) or not row[k] for k in ('key','definition','rule')) or row['key'] in keys:raise ValueError('Death spawn unique named action/definition/rule required')
        keys.add(row['key'])
        if type(row['count'])is not int or not 1<=row['count']<=32 or type(row['inherit_route'])is not bool or row['managed'] not in ('inherit_source','unmanaged'):raise ValueError('Death spawn count/inheritance policy invalid')
        if type(row['delay_seconds'])not in (int,float) or not math.isfinite(row['delay_seconds']) or not 0<=row['delay_seconds']<=3600 or not isinstance(row['parameters'],Mapping):raise ValueError('Death spawn finite timing/parameters required')
        p=row['placement']
        if not isinstance(p,Mapping) or set(p)!={'rule','stream','sample_axes','offset','random_range'} or any(not isinstance(p[k],str) or not p[k] for k in ('rule','stream')) or p['sample_axes']!=['row','col']:raise ValueError('Death spawn named RNG/placement policy required')
        for key in ('offset','random_range'):
            if not isinstance(p[key],Mapping) or set(p[key])!={'row','col'} or any(type(v)not in (int,float) or not math.isfinite(v) or key=='random_range' and v<0 for v in p[key].values()):raise ValueError('Death spawn finite placement vectors required')

def stamp(ctx,ref):return {'id':ref,'definition':ctx.entity(ref)['definition_id'],'life':ctx.get(ref,('runtime','lifecycle_generation'),0),'death':ctx.get(ref,('runtime','death_generation'),0)}

class DeathSpawnSystem:
    def __init__(self,ctx):self.ctx=ctx;self._issuing=[]
    def state(self):return self.ctx.state().get('death_spawns',{})
    def save(self,rows):self.ctx.state_update(death_spawns=rows)
    def event(self,event_id):
        if type(event_id) is not int or event_id < 1:
            raise ValueError('Death spawn event requires a strict positive integer ID')
        records = self.ctx.session._events._records
        if event_id > len(records):
            raise ValueError('Death spawn causal event unavailable')
        record = records[event_id - 1]
        if (not isinstance(record, Mapping) or type(record.get('id')) is not int or
                record['id'] != event_id or type(record.get('type')) is not str or not record['type']):
            raise ValueError('Death spawn causal event identity/type invalid')
        return record
    def calculation(self,contract,inputs,rule_id=None,ref=None):
        scope={"scenario":self.ctx.program.scenario.get('rules',{}),'source':self.ctx.definition_bindings(ref),'target':{},'owner':self.ctx.definition_bindings(ref),'component':{},'attribute_or_resource':{},'ability':{},'effect':{}}
        context={'time':self.ctx.session.time,'seconds':self.ctx.session.time*self.ctx.session.quantum,'quantum':self.ctx.session.quantum,'source':thaw(self.ctx.entity(ref)) if ref is not None else {},'target':{},'owner':thaw(self.ctx.entity(ref)) if ref is not None else {}}
        old=self.ctx.session._capturing_atomic;self.ctx.session._capturing_atomic=True
        try:result=self.ctx.rules.evaluate(contract,inputs,scope=scope,rule_id=rule_id,context=context)
        finally:self.ctx.session._capturing_atomic=old
        from .context import compact_trace
        trace=thaw(result.trace) if self.ctx.program.ruleset.get('parameters',{}).get('trace_mode','compact')=='full' else thaw(compact_trace(result.trace))
        event=self.ctx.session.emit('calculation',{'calculation_id':contract,'rule_id':result.rule_id,'source':ref,'target':None,'value':result.value,'trace':trace})
        self.ctx.last_calculation_event_id=event
        return thaw(result.value),{'event':event,'contract':contract,'inputs':thaw(inputs),'scope':thaw(scope),'context':context,'rule_id':result.rule_id,'requested_rule_id':rule_id,'value':thaw(result.value),'trace':trace,'runtime_fingerprint':self.ctx.rules.fingerprint}
    def issue(self,ref,death_event):
        if (ref,death_event) not in self._issuing:raise ValueError('Death spawn issuance requires actual retirement scope')
        cfg=self.ctx.get(ref,('lifecycle','death_spawns'))
        if not cfg:return
        validate(cfg);snapshot=self.ctx.capture_view(ref);signature=stamp(self.ctx,ref)
        event=self.event(death_event)
        if event['type']!='entity.died' or event['payload'].get('target')!=ref or self.ctx.alive(ref):raise ValueError('Death spawn requires actual completed death event')
        timeline=getattr(self.ctx,'timeline',None);member=thaw(timeline._state()['members'].get(str(ref))) if timeline is not None else None
        ledger=self.state();key=str(ref)+'/'+str(signature['death'])
        if key in ledger:raise ValueError('Death spawn epoch already issued')
        rows=[]
        for action in cfg['actions']:
            accepted,decision_proof=self.calculation('lifecycle.death_emission',{'entity':snapshot,'selection_state':{},'parameters':thaw(action['parameters']),'clock':{'time':self.ctx.session.time,'quantum':self.ctx.session.quantum}},action['rule'],ref)
            if type(accepted)is not bool:raise ValueError('Death spawn decision must return strict bool')
            if not accepted:continue
            decision=self.ctx.last_calculation_event_id
            ticks,timing_proof=self.calculation('time.quantize',{'seconds':action['delay_seconds'],'quantum':self.ctx.session.quantum,'rounding':{'mode':'ceil'}});timing=self.ctx.last_calculation_event_id
            for index in range(action['count']):
                slot=action['key']+'/'+str(index);due=self.ctx.session.time+ticks
                payload={'ledger':key,'slot':slot};task=self.ctx.session.schedule('domain.death_spawn',payload,due,phase=self.ctx.effect_phase)
                queued=next(t for t in self.ctx.session.scheduler.pending if t['id']==task)
                rows.append({'slot':slot,'action':action['key'],'index':index,'due':due,'task':task,'phase':queued['phase'],'seq':queued['seq'],'decision_event':decision,'timing_event':timing,'status':'pending','child':None,'decision':decision_proof,'timing':timing_proof})
        if not rows:return
        issued=self.ctx.emit('descendant.issued',{'source':ref,'stamp':signature,'death_event':death_event,'snapshot':snapshot,'spec':thaw(cfg),'spec_digest':digest(cfg),'membership':member,'rows':rows},death_event)
        entry={'source':ref,'stamp':signature,'death_event':death_event,'issued_event':issued,'rows':rows};ledger[key]=entry;self.save(ledger)
        if timeline is not None and member is not None:
            state=timeline._state();pending=state.setdefault('descendant_pending',{})
            for row in rows:
                action=next(a for a in cfg['actions'] if a['key']==row['action'])
                if action['managed']=='inherit_source':pending[key+'/'+row['slot']]={**member,'ledger':key,'slot':row['slot']}
            timeline._save(state)
        self.ctx.state_update(pending_waves=self.ctx.state()['pending_waves']+len(rows))
    def _dispatch(self,session,payload):
        if not isinstance(payload,Mapping) or set(payload)!={'ledger','slot'}:raise ValueError('Death spawn exact task payload required')
        ledger=self.state();entry=ledger.get(payload['ledger']);row=next((r for r in entry['rows'] if r['slot']==payload['slot']),None) if entry else None
        task=session.current_task
        if row is None or row['status']!='pending' or task is None or task['kind']!='domain.death_spawn' or task['payload']!=payload or any(task[k]!=row[k] for k in ('task','phase','seq') if k!='task') or task['id']!=row['task'] or task['at']!=row['due'] or session.time!=row['due']:raise ValueError('Death spawn requires actual owned scheduled task')
        ref=entry['source'];issued=self.event(entry['issued_event']);cfg=self.ctx.get(ref,('lifecycle','death_spawns'))
        if digest(issued['payload']['stamp'])!=digest(entry['stamp']):raise ValueError('Death spawn issuance stamp differs')
        if stamp(self.ctx,ref)!=entry['stamp'] or self.ctx.alive(ref) or digest(cfg)!=issued['payload']['spec_digest']:self.cancel(entry,row,'source_invalidated');return
        if self.ctx.state().get('finished'):self.cancel(entry,row,'terminal');return
        action=next(a for a in cfg['actions'] if a['key']==row['action']);p=action['placement'];snapshot=issued['payload']['snapshot'];spatial=snapshot['components']['spatial']
        samples=[{'axis':axis,'value':session.random.sample(p['stream'])} for axis in p['sample_axes']]
        position=self.ctx.calc('spawn.position',{'anchor':spatial['position'],'offset':p['offset'],'random_range':p['random_range'],'samples':samples},source=ref,rule_id=p['rule'],extra={'death_spawn':{'source_stamp':entry['stamp'],'issued_event':entry['issued_event'],'slot':row['slot']}})
        if not isinstance(position,Mapping) or set(position)!={'row','col'} or any(type(v)not in (int,float) or not math.isfinite(v) for v in position.values()):raise ValueError('Death spawn position must be finite row/col')
        route=thaw(spatial.get('route')) if action['inherit_route'] else None
        if route is not None:route['startPosition']=dict(position)
        old_move=spatial.get('movement',{});movement={'checkpoint':old_move.get('checkpoint',0),'path_index':0}
        if 'wait_until' in old_move:movement['wait_until']=old_move['wait_until']
        overrides={'spatial':{'movement':movement,'timing_origins':thaw(spatial.get('timing_origins',{}))}} if route is not None else None
        child=self.ctx.lifecycle.create(action['definition'],position,route=route,component_overrides=overrides)
        self.ctx.set(child,('runtime','spawn_lineage'),{'source_stamp':entry['stamp'],'issued_event':entry['issued_event'],'death_event':entry['death_event'],'slot':row['slot'],'parent':ref})
        row.update(status='born',child=child,born_at=session.time);self.save(ledger)
        timeline=getattr(self.ctx,'timeline',None);member=issued['payload']['membership']
        if timeline is not None:
            state=timeline._state();state.get('descendant_pending',{}).pop(payload['ledger']+'/'+row['slot'],None)
            if action['managed']=='inherit_source' and member is not None and self.ctx.alive(child):state['members'][str(child)]={**thaw(member),'descendant_origin':entry['issued_event'],'descendant_slot':row['slot']}
            timeline._schedule(state,session.time);timeline._save(state)
        self.ctx.state_update(pending_waves=self.ctx.state()['pending_waves']-1)
        self.ctx.emit('descendant.born',{'source':ref,'source_stamp':entry['stamp'],'child':child,'definition':action['definition'],'issued_event':entry['issued_event'],'death_event':entry['death_event'],'slot':row['slot'],'managed_membership':thaw(member) if action['managed']=='inherit_source' else None,'route_inherited':route is not None,'position':dict(position)},entry['issued_event'])
    def handle(self,session,payload):
        with session.atomic():return self._dispatch(session,payload)
    def cancel(self,entry,row,reason):
        row.update(status='cancelled',reason=reason);ledger=self.state();ledger[str(entry['source'])+'/'+str(entry['stamp']['death'])]=entry;self.save(ledger)
        self.ctx.state_update(pending_waves=self.ctx.state()['pending_waves']-1)
        self.ctx.emit('descendant.cancelled',{'source':entry['source'],'source_stamp':entry['stamp'],'issued_event':entry['issued_event'],'slot':row['slot'],'reason':reason},entry['issued_event'])
        timeline=getattr(self.ctx,'timeline',None)
        if timeline is not None:
            state=timeline._state();state.get('descendant_pending',{}).pop(str(entry['source'])+'/'+str(entry['stamp']['death'])+'/'+row['slot'],None);timeline._schedule(state,self.ctx.session.time);timeline._save(state)
    def validate_restored(self):
        pending={t['id']:t for t in self.ctx.session.scheduler.pending};owned=set()
        for event in self.ctx.session.events:
            if event['type']=='descendant.issued':
                signature=event['payload']['stamp'];key=str(signature['id'])+'/'+str(signature['death'])
                if key not in self.state() or self.state()[key]['issued_event']!=event['id']:raise ValueError('Missing restored death spawn issuance ledger')
        for key,entry in self.state().items():
            ref=entry['source'];issued=self.event(entry['issued_event']);body=issued['payload'];death=self.event(entry['death_event']);cfg=self.ctx.get(ref,('lifecycle','death_spawns'))
            validate(cfg)
            if issued['type']!='descendant.issued' or death['type']!='entity.died' or death['payload'].get('target')!=ref or issued.get('cause')!=entry['death_event'] or body['spec_digest']!=digest(cfg) or digest(body['spec'])!=digest(cfg) or digest(body['stamp'])!=digest(entry['stamp']):raise ValueError('Invalid restored death spawn provenance')
            if key!=str(ref)+'/'+str(entry['stamp']['death']) or len(entry['rows'])!=len(body['rows']):raise ValueError('Restored death spawn row count/epoch differs')
            for row,original in zip(entry['rows'],body['rows']):
                if any(digest(row[k])!=digest(original[k]) for k in ('slot','action','index','due','task','phase','seq','decision_event','timing_event','decision','timing')):raise ValueError('Restored death spawn immutable issuance differs')
                action=next((a for a in cfg['actions'] if a['key']==row['action']),None)
                if action is None or row['index']>=action['count'] or row['slot']!=action['key']+'/'+str(row['index']):raise ValueError('Restored death spawn declared slot differs')
                from .context import compact_trace
                expected_entity=thaw(body['snapshot']);expected_context_entity=thaw(expected_entity);expected_context_entity.pop('sampled_at',None)
                expected_inputs={'entity':expected_entity,'selection_state':{},'parameters':thaw(action['parameters']),'clock':{'time':issued['time'],'quantum':self.ctx.session.quantum}}
                if digest(row['decision']['inputs'])!=digest(expected_inputs) or row['decision']['context']['time']!=issued['time'] or digest(row['decision']['context']['source'])!=digest(expected_context_entity) or digest(row['decision']['context']['owner'])!=digest(expected_context_entity):raise ValueError('Restored death decision historical actor/context differs')
                if expected_entity['id']!=ref or expected_entity['definition_id']!=entry['stamp']['definition'] or expected_entity['components']['runtime'].get('death_generation',0)!=entry['stamp']['death'] or expected_entity['components']['runtime'].get('lifecycle_generation',0)!=entry['stamp']['life'] or expected_entity['components']['runtime']['alive'] or expected_entity['components']['runtime']['state']!='dead':raise ValueError('Restored death actor snapshot stamp differs')
                for proof in [row['timing'],row['decision']]:
                    event=self.event(proof['event'])
                    if event['type']!='calculation' or event['time']!=issued['time'] or event['payload']['calculation_id']!=proof['contract'] or event['payload']['rule_id']!=proof['rule_id'] or digest(event['payload']['value'])!=digest(proof['value']) or proof['runtime_fingerprint']!=self.ctx.rules.fingerprint:raise ValueError('Restored death spawn calculation binding differs')
                    old=self.ctx.session._capturing_atomic;self.ctx.session._capturing_atomic=True
                    try:result=self.ctx.rules.evaluate(proof['contract'],proof['inputs'],scope=proof['scope'],rule_id=proof['requested_rule_id'],context=proof['context'])
                    finally:self.ctx.session._capturing_atomic=old
                    trace=thaw(result.trace) if self.ctx.program.ruleset.get('parameters',{}).get('trace_mode','compact')=='full' else thaw(compact_trace(result.trace))
                    if result.rule_id!=proof['rule_id'] or digest(trace)!=digest(event['payload']['trace']) or digest(result.value)!=digest(proof['value']):raise ValueError('Restored death spawn pure calculation cannot reproduce')
                request=row['timing']['inputs'];expected=row['timing']['value']
                if row['due']!=issued['time']+expected or request['seconds']!=action['delay_seconds'] or request['quantum']!=self.ctx.session.quantum or row['decision']['value'] is not True or row['decision']['rule_id']!=action['rule']:raise ValueError('Restored death spawn due/decision differs from declaration')
                if row['status']=='pending':
                    if stamp(self.ctx,ref)!=entry['stamp'] or self.ctx.alive(ref):raise ValueError('Restored pending death source stamp/activity differs')
                    task=pending.get(row['task']);owned.add(row['task'])
                    if task is None or task['kind']!='domain.death_spawn' or task['payload']!={'ledger':key,'slot':row['slot']} or task['at']!=row['due'] or task['phase']!=row['phase'] or task['seq']!=row['seq']:raise ValueError('Restored death spawn pending task differs')
                elif row['status']=='born':
                    child=self.ctx.entity(row['child']);lineage=child['components']['runtime'].get('spawn_lineage')
                    if lineage!={'source_stamp':entry['stamp'],'issued_event':entry['issued_event'],'death_event':entry['death_event'],'slot':row['slot'],'parent':ref}:raise ValueError('Restored child lineage differs')
                elif row['status']!='cancelled':raise ValueError('Restored death spawn status invalid')
        for actor in self.ctx.session.world.entities():
            lineage=actor['components'].get('runtime',{}).get('spawn_lineage')
            if lineage is None:continue
            if not isinstance(lineage,Mapping) or set(lineage)!={'source_stamp','issued_event','death_event','slot','parent'}:raise ValueError('Restored child exact lineage record required')
            signature=lineage['source_stamp'];key=str(lineage['parent'])+'/'+str(signature['death']);entry=self.state().get(key)
            row=next((r for r in entry['rows'] if r['slot']==lineage['slot']),None) if entry else None
            if entry is None or row is None or row['status']!='born' or row['child']!=actor['id'] or digest(signature)!=digest(entry['stamp']) or lineage['issued_event']!=entry['issued_event'] or lineage['death_event']!=entry['death_event']:raise ValueError('Restored child reverse issuance link differs')
            spec=self.event(entry['issued_event'])['payload']['spec'];action=next(a for a in spec['actions'] if a['key']==row['action'])
            if actor['definition_id']!=action['definition']:raise ValueError('Restored descendant definition differs from declaration')
        if {t['id'] for t in pending.values() if t['kind']=='domain.death_spawn'}!=owned:raise ValueError('Orphan restored death spawn task')
