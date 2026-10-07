"""Elemental state/lease proofs, anchored to runtime events and pure contracts."""
from contextlib import contextmanager
from functools import wraps
from collections.abc import Mapping
from ark_sim.contracts import thaw,digest
from .context import compact_trace

def tracked(fn):
 @wraps(fn)
 def call(self,*args,**kwargs):
  self._proof_stack.append([])
  try:return fn(self,*args,**kwargs)
  finally:self._proof_stack.pop()
 return call

def calculate(system,contract,inputs,source=None,target=None,owner=None,rule_id=None):
 ctx=system.ctx;scope={'scenario':ctx.program.scenario.get('rules',{}),'source':ctx.definition_bindings(source),'target':ctx.definition_bindings(target),'owner':ctx.definition_bindings(owner),'component':{},'attribute_or_resource':{},'ability':{},'effect':{}}
 context={'time':ctx.session.time,'seconds':ctx.session.time*ctx.session.quantum,'quantum':ctx.session.quantum,'source':thaw(ctx.entity(source)) if source is not None else {},'target':thaw(ctx.entity(target)) if target is not None else {},'owner':thaw(ctx.entity(owner)) if owner is not None else {}}
 value=ctx.calc(contract,inputs,source=source,target=target,owner=owner,rule_id=rule_id);event=ctx.last_calculation_event_id
 row={'event':event,'cause':self_event_cause(ctx,event),'contract':contract,'inputs':thaw(inputs),'scope':thaw(scope),'context':context,'requested_rule':rule_id,'source':source,'target':target,'owner':owner,'value':thaw(value),'runtime':ctx.rules.fingerprint}
 if system._proof_stack:system._proof_stack[-1].append(row)
 return value

def self_event_cause(ctx,ref):
 # DomainContext.calc appends this exact calculation last. Read the trusted
 # in-memory record directly; never materialize or scan the whole journal.
 if not ctx.session._events._records:raise ValueError('Actual elemental calculation event unavailable')
 actual=ctx.session._events._records[-1]
 if actual['id']!=ref or actual['type']!='calculation':raise ValueError('Elemental calculation event is not actual latest record')
 return actual.get('cause')

def event(system,ref,index=None):
 if type(ref)is not int or ref<1:raise ValueError('Elemental proof event ID must be strict positive integer')
 if index is not None:
  if ref not in index:raise ValueError('Elemental proof event missing')
  return index[ref]
 records=system.ctx.session._events._records
 if ref>len(records):raise ValueError('Elemental proof event outside actual journal')
 actual=records[ref-1]
 if actual['id']!=ref:raise ValueError('Elemental proof event actual ID index differs')
 return actual

def seal(system,ref,operation,detail=None):
 ctx=system.ctx;state=ctx.get(ref,('runtime','elemental'));previous=state.get('audit_event');snapshot=thaw(state);snapshot.pop('audit_event',None)
 proof=[p for p in (system._proof_stack[-1] if system._proof_stack else []) if p['target']==ref or p['owner']==ref]
 ident=ctx.session.emit('elemental.state.record',{'target':ref,'operation':operation,'previous':previous,'stamp':system.stamp(ref),'profile':thaw(system.profile(ref)),'profile_digest':digest(system.profile(ref)),'state':snapshot,'proofs':proof,'detail':thaw(detail or {})})
 state['audit_event']=ident;ctx.set(ref,('runtime','elemental'),state)

def validate_proof(system,proof,index):
 ctx=system.ctx;e=event(system,proof['event'],index);contract=proof['contract'];view=proof['context'];inputs=proof['inputs']
 if e.get('cause')!=proof['cause'] or e['payload'].get('source')!=proof['source'] or e['payload'].get('target')!=proof['target'] or e['type']!='calculation' or e['time']!=view['time'] or view['quantum']!=ctx.session.quantum or view['seconds']!=view['time']*view['quantum'] or proof['runtime']!=ctx.rules.fingerprint or e['payload']['calculation_id']!=contract or digest(e['payload']['value'])!=digest(proof['value']):raise ValueError('Elemental calculation event/context binding invalid')
 def bindings(entity):return {**ctx.program.definitions.get(entity.get('definition_id'),{}).get('rules',{}),**entity.get('components',{}).get('runtime',{}).get('rule_bindings',{})} if entity else {}
 expected={'scenario':ctx.program.scenario.get('rules',{}),'source':bindings(view['source']),'target':bindings(view['target']),'owner':bindings(view['owner']),'component':{},'attribute_or_resource':{},'ability':{},'effect':{}}
 if digest(expected)!=digest(proof['scope']):raise ValueError('Elemental historical rule scope invalid')
 for name in ['source','target']:
  if name in inputs:
   # Same sampling API representation, not a checkpoint comparison exclusion.
   # All original inputs/context/trace/cause stay stored and validated.
   raw=thaw(inputs[name]);raw.pop('sampled_at',None)
   normalized=thaw(view[name])
   for cast in normalized.get('components',{}).get('runtime',{}).get('casts',{}).values():
    for key in ['source_snapshot','target_snapshots','launch_snapshot','launch_target_snapshots']:cast.pop(key,None)
   if digest(raw)!=digest(normalized):raise ValueError('Elemental historical source/target view differs')
 old=ctx.session._capturing_atomic;ctx.session._capturing_atomic=True
 try:result=ctx.rules.evaluate(contract,inputs,scope=proof['scope'],rule_id=proof['requested_rule'],context=view)
 finally:ctx.session._capturing_atomic=old
 trace=result.trace if ctx.program.ruleset.get('parameters',{}).get('trace_mode','compact')=='full' else compact_trace(result.trace)
 if result.rule_id!=e['payload']['rule_id'] or digest(result.value)!=digest(proof['value']) or digest(trace)!=digest(e['payload']['trace']):raise ValueError('Elemental pure calculation proof cannot reproduce')

def transition(system,e,previous,index):
 b=e['payload'];state=b['state'];operation=b['operation'];proofs=b['proofs'];before=b['detail'].get('before');old=previous['payload']['state'] if previous is not None else None
 cap={p['inputs']['element']:p['value'] for p in proofs if p['contract']=='elemental.capacity'}
 if operation=='initialize':
  if state['break'] is not None or state['generation']!=0 or state['remaining']!=cap or state['last_time']!=e['time']:raise ValueError('Elemental initial state differs from declared capacities')
  return
 if old is None or before is None:raise ValueError('Elemental transition lacks actual predecessor')
 if any(digest(before[k])!=digest(old[k]) for k in ['remaining','break','generation']):raise ValueError('Elemental transition before state differs from predecessor')
 if type(before['last_time'])is not int or not old['last_time']<=before['last_time']<=e['time']:raise ValueError('Elemental transition historical clock invalid')
 if operation=='loss':
  key=b['detail']['element'];request=b['detail']['request'];loss=next((p for p in proofs if p['contract']=='elemental.loss'),None);eligible=next((p for p in proofs if p['contract']=='elemental.eligibility'),None)
  if loss is None or eligible is None or eligible['value'] is not True or loss['value']<=0 or digest(request)!=digest(loss['inputs']['request']) or loss['inputs']['current']!=before['remaining'][key]:raise ValueError('Elemental accepted loss declaration/proof invalid')
  packet=next((p for p in proofs if p['contract']=='elemental.packet'),None)
  if 'amount_rule' in request:
   if packet is None or packet['requested_rule']!=request['amount_rule'] or packet['value']!=request['raw_amount']:raise ValueError('Elemental packet rule provenance invalid')
  elif request.get('amount')!=request['raw_amount']:raise ValueError('Elemental fixed packet amount provenance invalid')
  expected=thaw(before['remaining']);expected[key]=max(0,expected[key]-loss['value'])
  crossing=expected[key]==0
  if state['remaining']!=expected or state['generation']!=before['generation']+int(crossing) or bool(state['break'])!=crossing or before['break'] is not None:raise ValueError('Elemental loss state cannot reproduce')
  if crossing:
   provenance=state['break']['provenance'];src=loss['inputs']['source'];source=b['detail']['source']
   if provenance['source']!=source or digest(provenance['request'])!=digest(request) or digest(provenance['source_snapshot'])!=digest(src):raise ValueError('Elemental break actual source/provenance differs')
 elif operation in ('capacity','recovery','ended'):
  expected=thaw(before['remaining'])
  if operation=='recovery':
   for proof in [p for p in proofs if p['contract']=='elemental.recovery']:
    key=proof['inputs']['element'];inputs=proof['inputs']
    if inputs['current']!=min(before['remaining'][key],inputs['capacity']) or inputs['delta_seconds']!=(e['time']-before['last_time'])*system.ctx.session.quantum:raise ValueError('Elemental actual recovery interval/input differs')
    expected[key]=proof['value']
  else:
   for key,value in cap.items():expected[key]=value if operation=='ended' else min(expected[key],value)
  if state['remaining']!=expected or state['generation']!=before['generation']:raise ValueError('Elemental reset/recovery cannot reproduce')
  if operation=='ended':
   lease=before['break'];task=b['detail'].get('actual_task')
   if lease is None or state['break'] is not None or task is None or task['id']!=lease['task'] or task['at']!=e['time'] or task['payload']!={'target':b['target'],'generation':lease['generation']} or task['phase']!=lease['phase'] or task['seq']!=lease['seq'] or task['kind']!='domain.elemental.expire':raise ValueError('Elemental ended state lacks real owned expiry')
   ended=event(system,b['detail']['end_event'],index)
   if ended['type']!='elemental.break.ended' or ended['time']!=e['time'] or ended.get('cause')!=lease['break_event'] or ended['payload']!={'target':b['target'],'element':lease['element'],'generation':lease['generation']}:raise ValueError('Elemental ended event/cause differs from owned lease')
  elif state['break']!=before['break']:raise ValueError('Elemental nonexpiry transition changed break')
 elif operation=='owner_state':
  if any(digest(state[k])!=digest(before[k]) for k in ['remaining','break','generation','last_time']):raise ValueError('Elemental owner-state transition changed resource/lease')
 elif operation=='cancelled':
  if before['break'] is None or state['break'] is not None or state['generation']!=before['generation']+1 or state['remaining']!=before['remaining']:raise ValueError('Elemental cancellation epoch invalid')
 else:raise ValueError('Unknown elemental state transition')

def validate_restored(system):
 ctx=system.ctx;records={};all_records={};last_ticks={};events=list(ctx.session.events);index={e['id']:e for e in events}
 if len(index)!=len(events):raise ValueError('Elemental journal event IDs duplicated')
 for e in events:
  if e['type']=='elemental.tick.record':
   if e['payload']['time']!=e['time']:raise ValueError('Elemental tick actual time differs')
   for row in e['payload']['updated']:
    if row['last_time']!=e['time'] or row['before']>row['last_time']:raise ValueError('Elemental tick clock transition invalid')
    last_ticks[row['target']]={**row,'time':e['time']}
  if e['type']=='elemental.state.record':records[e['payload']['target']]=e;all_records[e['id']]=e
 for started in events:
  if started['type']=='elemental.break.started':
   matches=[r for r in all_records.values() if r['payload']['target']==started['payload']['target'] and r['payload']['operation']=='loss' and (r['payload']['state'].get('break') or {}).get('break_event')==started['id']]
   if len(matches)!=1:raise ValueError('Elemental actual break event lost state issuance record')
 owned=set();tasks={t['id']:t for t in ctx.session.scheduler.pending}
 for actor in ctx.session.world.entities():
  ref=actor['id'];spec=system.profile(ref);state=ctx.get(ref,('runtime','elemental'))
  if spec is None and state is None:
   if ref in records:raise ValueError('Elemental initialized owner lost profile/state')
   continue
  if spec is None or state is None or ref not in records:raise ValueError('Elemental declared owner requires initialized proof/state')
  latest=records[ref];body=latest['payload'];snapshot=body['state']
  if set(state)!={'remaining','break','generation','last_time','audit_event'} or state['audit_event']!=latest['id'] or digest(spec)!=body['profile_digest'] or digest(body['profile'])!=body['profile_digest']:raise ValueError('Elemental state/profile latest event binding invalid')
  if set(state['remaining'])!=set(spec['elements']) or type(state['generation'])is not int or state['generation']<0 or type(state['last_time'])is not int or not 0<=state['last_time']<=ctx.session.time:raise ValueError('Elemental state keyset/generation/time invalid')
  if any(digest(state[k])!=digest(snapshot[k]) for k in ['remaining','break','generation']):raise ValueError('Elemental runtime state differs from actual state event')
  last_tick=last_ticks.get(ref)
  expected_time=max(snapshot['last_time'],last_tick['last_time']) if last_tick is not None and last_tick['time']>=latest['time'] else snapshot['last_time']
  if state['last_time']!=expected_time:raise ValueError('Elemental last logical recovery time invalid')
  seen=set();cursor=latest;capacities={}
  while cursor is not None:
   if cursor['id'] in seen:raise ValueError('Elemental proof predecessor cycle')
   seen.add(cursor['id']);b=cursor['payload']
   if b['target']!=ref or b['profile_digest']!=digest(spec) or b['stamp']['id']!=ref:raise ValueError('Elemental record owner/profile differs')
   for proof in b['proofs']:
    validate_proof(system,proof,index)
    if proof['contract'].startswith('elemental.') and proof['contract']!='elemental.packet':
     key=proof['inputs']['element'];profile=spec['elements'].get(key)
     if profile is None:raise ValueError('Elemental proof unknown declared key')
     expected=profile['rules'].get(proof['contract']) if proof['contract'] in profile['rules'] else spec['eligibility_rule']
     if profile is None or proof['requested_rule']!=expected or digest(proof['inputs']['parameters'])!=digest({k:v for k,v in profile.items() if k not in ['rules','on_break','on_end']}):raise ValueError('Elemental calculation differs from declared profile')
    if proof['contract']=='elemental.capacity':capacities.setdefault(proof['inputs']['element'],proof['value'])
   previous=b['previous'];prior=all_records.get(previous) if previous is not None else None
   transition(system,cursor,prior,index)
   cursor=prior
   if previous is not None and cursor is None:raise ValueError('Elemental predecessor event unavailable')
  for key,value in state['remaining'].items():
   if type(value)not in (int,float) or not __import__('math').isfinite(value) or key not in capacities or not 0<=value<=capacities[key]:raise ValueError('Elemental remaining outside actual capacity')
  lease=state['break']
  if lease is None:continue
  required={'generation','target_stamp','element','due','phase','seq','provenance','task','break_event'}
  if set(lease)!=required or any(type(lease[k])is not int or lease[k]< (0 if k=='due' else 1) for k in ['generation','due','task','seq']) or lease['generation']!=state['generation'] or lease['generation']<1 or lease['target_stamp']!=system.stamp(ref) or not ctx.active(ref) or lease['element']not in spec['elements'] or state['remaining'][lease['element']]!=0:raise ValueError('Elemental active break incarnation/key/generation invalid')
  started=event(system,lease['break_event'],index);payload=started['payload'];baseline=thaw(lease);baseline.pop('break_event')
  if started['type']!='elemental.break.started' or payload['target']!=ref or digest(payload['lease'])!=digest(baseline) or payload['profile_digest']!=digest(spec):raise ValueError('Elemental immutable break/source/provenance binding invalid')
  startrecord=next((e for e in all_records.values() if e['payload']['target']==ref and e['payload']['operation']=='loss' and (e['payload']['state'].get('break') or {}).get('break_event')==lease['break_event']),None)
  if startrecord is None:raise ValueError('Elemental break state issuance record missing')
  proofs=startrecord['payload']['proofs'];d=next((p for p in proofs if p['contract']=='elemental.break_duration'),None);q=next((p for p in proofs if p['contract']=='time.quantize'),None)
  if d is None or q is None or q['inputs']!={'seconds':d['value'],'quantum':ctx.session.quantum,'rounding':{'mode':'ceil'}} or lease['due']!=started['time']+q['value'] or lease['due']<ctx.session.time:raise ValueError('Elemental owned due differs from actual declared duration')
  task=tasks.get(lease['task']);owned.add(lease['task'])
  if task is None or task['kind']!='domain.elemental.expire' or task['payload']!={'target':ref,'generation':lease['generation']} or task['at']!=lease['due'] or task['phase']!=lease['phase'] or task['seq']!=lease['seq']:raise ValueError('Elemental current owned expiry task invalid')
 if {t['id'] for t in tasks.values() if t['kind']=='domain.elemental.expire'}!=owned:raise ValueError('Orphan elemental expiry task')
