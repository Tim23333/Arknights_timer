"""Opt-in real shared Aura child lease rows. No game IDs, no inactive permission."""
from ark_sim.domains.selection import DEFAULT_STATE
def stamp(ctx,ref):return {'life':ctx.get(ref,('runtime','lifecycle_generation'),0),'death':ctx.get(ref,('runtime','death_generation'),0)}
def eligible(buffs,center,parent):
 ctx=buffs.ctx
 definition=ctx.program.definitions[parent['definition']]
 policy=definition.get('aura',{}).get('lease_policy',{})
 def available(ref):
  if ctx.active(ref):return True
  if policy.get('owner_activity','active_only')!='active_or_rebirth_waiting' or not ctx.alive(ref) or ctx.get(ref,('runtime','state'))!='rebirth':return False
  state=ctx.get(ref,('runtime','rebirth'),{})
  if state.get('phase')!='waiting' or ctx.rebirth is None:return False
  health=ctx.health_resource(ref)
  if ctx.resources.current(ref,health)!=0:return False
  # Actual retained parent identity is authenticated by the real consume
  # transition or already-installed finish job. World flags alone never grant it.
  return ctx.rebirth.aura_waiting_parent_available(ref,parent)
 if not available(center) or not available(parent['source']) or (parent['expires_at'] is not None and ctx.session.time>=parent['expires_at']):return False
 definition=ctx.program.definitions[parent['definition']]
 if definition.get('active_rule'):
  if not buffs.applicability._decision(center,parent,'active_rule',ctx.spatial.selection_state(center,DEFAULT_STATE)):return False
 return all(not ctx.route_hidden(ref) or ctx.visibility_policy(ref).get('hidden_auras','suspend')=='retain' for ref in (center,parent['source']))
def lease(buffs,center,parent,target,order):
 ctx=buffs.ctx
 return {'parent':parent['id'],'center':center,'parent_generation':parent['generation'],'source':parent['source'],'center_incarnation':stamp(ctx,center),'source_incarnation':stamp(ctx,parent['source']),'target_incarnation':stamp(ctx,target),'order':order}
def validate_acquisition(buffs,source,target,buff_id,row):
 ctx=buffs.ctx;parent=buffs._live_parent(row['center'],row['parent'])
 if parent is None or not eligible(buffs,row['center'],parent):raise ValueError('Shared Aura acquisition requires an actual live parent')
 aura=ctx.program.definitions[parent['definition']].get('aura',{})
 if not aura.get('lease_policy') or aura.get('buff')!=buff_id or parent['source']!=source or row!=lease(buffs,row['center'],parent,target,row['order']):raise ValueError('Shared Aura lease identity differs from actual parent/incarnation')
 if target not in ctx.spatial.select(row['center'],aura['selector'],aura_parent=parent['id']):raise ValueError('Shared Aura target is not currently source eligible')
 if any(i['definition']==buff_id for i in buffs._instances(target)):raise ValueError('Shared Aura first application collides with existing child')
def write(buffs,target,child,leases):
 ctx=buffs.ctx;rows=buffs._instances(target);current=next((i for i in rows if i['id']==child),None)
 if current is None:return
 current['aura_leases']=leases
 if leases:
  first=next(iter(leases.values()));parent=buffs._live_parent(first['center'],first['parent']);spec=ctx.program.definitions[parent['definition']]['aura']['lease_policy'].get('modifier_stacks') if parent else None
  if spec:
   count=ctx.calc('buff.stack_amount',{'current_stacks':0,'incoming':{'count':len(leases),'mode':'add'},'stack_parameters':{'max_stacks':spec['maximum'],'mode':'add'}},source=first['source'],target=target,owner=target,rule_id=spec['rule'])
   if type(count) not in (int,float) or int(count)!=count or not 1<=count<=spec['maximum']:raise ValueError('Shared lease modifier stack count invalid')
   current['stacks']=int(count)
 if leases:current['source']=min(leases.values(),key=lambda r:r['order'])['source']
 before=ctx.resources.capacity_snapshot(target);ctx.set(target,('buffs','instances'),rows);ctx.set(target,('attributes','modifiers'),buffs._modifiers(target,rows));ctx.resources.sync_capacities(target,before,'shared_aura_source_rebound');buffs._sync_blocking([ctx.program.definitions[current['definition']]])

def validate_modifier_stacks(buffs):
 """Only the optional lease-count policy adds restored stack qualification."""
 ctx=buffs.ctx
 for actor in ctx.session.world.entities():
  for child in buffs._instances(actor['id']):
   leases=child.get('aura_leases')
   if not leases:continue
   first=next(iter(leases.values()));parent=buffs._live_parent(first['center'],first['parent'])
   if parent is None:continue
   spec=ctx.program.definitions[parent['definition']].get('aura',{}).get('lease_policy',{}).get('modifier_stacks')
   if not spec:continue
   for uid,row in leases.items():
    current=buffs._live_parent(row['center'],uid)
    if current is None or not eligible(buffs,row['center'],current) or row!=lease(buffs,row['center'],current,actor['id'],row['order']):raise ValueError('Restored lease-count modifier parent stamp differs')
   inputs={'current_stacks':0,'incoming':{'count':len(leases),'mode':'add'},'stack_parameters':{'max_stacks':spec['maximum'],'mode':'add'}}
   scope={'scenario':ctx.program.scenario.get('rules',{}),'source':ctx.definition_bindings(first['source']),'target':ctx.definition_bindings(actor['id']),'owner':ctx.definition_bindings(actor['id']),'component':{},'attribute_or_resource':{},'ability':{},'effect':{}}
   context={'time':ctx.session.time,'seconds':ctx.session.time*ctx.session.quantum,'quantum':ctx.session.quantum,'source':ctx.entity(first['source']),'target':actor,'owner':actor}
   old=ctx.session._capturing_atomic;ctx.session._capturing_atomic=True
   try:value=ctx.rules.evaluate('buff.stack_amount',inputs,scope=scope,rule_id=spec['rule'],context=context).value
   finally:ctx.session._capturing_atomic=old
   if type(child['stacks'])is not int or child['stacks']!=value:raise ValueError('Restored shared lease modifier stacks differ from pure count')
def release(buffs,target,child,parent):
 current=next((i for i in buffs._instances(target) if i['id']==child),None)
 if current is None:return
 leases=dict(current.get('aura_leases',{}));leases.pop(parent,None)
 if not leases:buffs.remove(target,child,_from_aura=True)
 else:write(buffs,target,child,leases)
def prune(buffs):
 if getattr(buffs,'_shared_pruning',False):return
 buffs._shared_pruning=True
 try:
  with buffs.ctx.session.atomic():
   for entity in buffs.ctx.session.world.entities():
    target=entity['id']
    for child in buffs._instances(target):
     if not child.get('aura_leases'):continue
     leases={}
     for uid,row in child['aura_leases'].items():
      parent=buffs._live_parent(row['center'],uid)
      if parent is None or not eligible(buffs,row['center'],parent) or not target_allowed(buffs,row['center'],parent,target):continue
      if row['target_incarnation']!=stamp(buffs.ctx,target):continue
      # A real refreshed parent can rebind its source; no new child/refreshed
      # modifier is installed. Retired/absent parents never gain a new lease.
      fresh=lease(buffs,row['center'],parent,target,row['order']);leases[uid]=fresh
     if not leases:buffs.remove(target,child['id'],_from_aura=True)
     elif leases!=child['aura_leases'] or child['source']!=min(leases.values(),key=lambda r:r['order'])['source']:write(buffs,target,child['id'],leases)
 finally:buffs._shared_pruning=False
def acquire(buffs,center,parent,target):
 ctx=buffs.ctx;aura=ctx.program.definitions[parent['definition']]['aura'];children=[i for i in buffs._instances(target) if i['definition']==aura['buff']]
 if len(children)>1:raise ValueError('Multiple shared Aura child instances collide')
 if children:
  child=children[0]
  if not child.get('aura_leases'):raise ValueError('External same-ID child collides with shared Aura acquisition')
  leases=dict(child['aura_leases']);old=leases.get(parent['id']);order=old['order'] if old else child.get('aura_next_lease_order',2);leases[parent['id']]=lease(buffs,center,parent,target,order);write(buffs,target,child['id'],leases)
  if old is None:
   rows=buffs._instances(target);current=next((i for i in rows if i['id']==child['id']),None)
   if current is not None:current['aura_next_lease_order']=order+1;ctx.set(target,('buffs','instances'),rows)
  return child['id']
 uid=buffs.apply(parent['source'],target,aura['buff'],shared_aura_lease=lease(buffs,center,parent,target,1))
 current=next((i for i in buffs._instances(target) if i['id']==uid),None)
 if current is not None and (current['stacks']!=1 or current['expires_at'] is not None):raise ValueError('Shared Aura child actual instance must remain permanent max1')
 return uid
def reconcile_parent(buffs,center,parent,desired):
 members=dict(parent.get('aura_members',{}))
 for member,child in list(members.items()):
  if int(member) not in desired:release(buffs,int(member),child,parent['id'])
 for member in sorted(desired):
  current=buffs._live_parent(center,parent['id'])
  if current is None or not eligible(buffs,center,current):buffs._clear_orphan_children(parent['id']);return
  if not target_allowed(buffs,center,current,member):continue
  acquire(buffs,center,current,member)
  fresh=buffs._live_parent(center,parent['id'])
  if fresh is None or not eligible(buffs,center,fresh):buffs._clear_orphan_children(parent['id']);return
  if buffs._reconcile_requested:buffs._publish_owned_members(center,parent['id']);return
 buffs._publish_owned_members(center,parent['id'])

def selection_source_allowed(ctx,source,selector,parent_uid):
 if type(parent_uid) is not str or not parent_uid:raise ValueError('Aura source selection parent requires actual UID string')
 source=ctx.session.world.resolve(source)
 parent=ctx.buffs._live_parent(source,parent_uid)
 if parent is None:return False
 definition=ctx.program.definitions[parent['definition']]
 aura=definition.get('aura',{})
 if not aura.get('lease_policy') or aura.get('selector')!=selector.get('id'):return False
 return eligible(ctx.buffs,source,parent)

def target_allowed(buffs,center,parent,target):
 ctx=buffs.ctx
 if ctx.active(target):return True
 return (target==center and ctx.alive(target) and eligible(buffs,center,parent)
     and ctx.program.definitions[parent['definition']].get('aura',{}).get('lease_policy',{}).get('owner_activity')=='active_or_rebirth_waiting'
     and ctx.rebirth is not None and ctx.rebirth.aura_waiting_parent_available(target,parent))
def selection_target_allowed(ctx,source,candidate,selector,parent_uid):
 if ctx.active(candidate):return True
 source=ctx.session.world.resolve(source);candidate=ctx.session.world.resolve(candidate)
 if candidate!=source or not selection_source_allowed(ctx,source,selector,parent_uid):return False
 parent=ctx.buffs._live_parent(source,parent_uid)
 return parent is not None and target_allowed(ctx.buffs,source,parent,candidate)
def retained_waiting_self_child(buffs,target,child):
 current=next((i for i in buffs._instances(target) if i['id']==child['id'] and i['generation']==child['generation']),None)
 if current is None:return False
 for uid,row in current.get('aura_leases',{}).items():
  if row['center']!=target:continue
  parent=buffs._live_parent(target,uid)
  if parent is not None and target_allowed(buffs,target,parent,target):return True
 return False
