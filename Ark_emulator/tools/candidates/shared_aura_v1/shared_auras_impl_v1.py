"""Opt-in real shared Aura child lease rows. No game IDs, no inactive permission."""
from ark_sim.domains.selection import DEFAULT_STATE
def stamp(ctx,ref):return {'life':ctx.get(ref,('runtime','lifecycle_generation'),0),'death':ctx.get(ref,('runtime','death_generation'),0)}
def eligible(buffs,center,parent):
 ctx=buffs.ctx
 if not buffs._parent_active(center,parent):return False
 definition=ctx.program.definitions[parent['definition']]
 if definition.get('active_rule'):
  if not buffs.applicability._decision(center,parent,'active_rule',ctx.spatial.selection_state(center,DEFAULT_STATE)):return False
 return ctx.aura_available(center) and ctx.aura_available(parent['source'])
def lease(buffs,center,parent,target,order):
 ctx=buffs.ctx
 return {'parent':parent['id'],'center':center,'parent_generation':parent['generation'],'source':parent['source'],'center_incarnation':stamp(ctx,center),'source_incarnation':stamp(ctx,parent['source']),'target_incarnation':stamp(ctx,target),'order':order}
def validate_acquisition(buffs,source,target,buff_id,row):
 ctx=buffs.ctx;parent=buffs._live_parent(row['center'],row['parent'])
 if parent is None or not eligible(buffs,row['center'],parent):raise ValueError('Shared Aura acquisition requires an actual live parent')
 aura=ctx.program.definitions[parent['definition']].get('aura',{})
 if not aura.get('lease_policy') or aura.get('buff')!=buff_id or parent['source']!=source or row!=lease(buffs,row['center'],parent,target,row['order']):raise ValueError('Shared Aura lease identity differs from actual parent/incarnation')
 if target not in ctx.spatial.select(row['center'],aura['selector']):raise ValueError('Shared Aura target is not currently source eligible')
 if any(i['definition']==buff_id for i in buffs._instances(target)):raise ValueError('Shared Aura first application collides with existing child')
def write(buffs,target,child,leases):
 ctx=buffs.ctx;rows=buffs._instances(target);current=next((i for i in rows if i['id']==child),None)
 if current is None:return
 current['aura_leases']=leases
 if leases:current['source']=min(leases.values(),key=lambda r:r['order'])['source']
 before=ctx.resources.capacity_snapshot(target);ctx.set(target,('buffs','instances'),rows);ctx.set(target,('attributes','modifiers'),buffs._modifiers(target,rows));ctx.resources.sync_capacities(target,before,'shared_aura_source_rebound');buffs._sync_blocking([ctx.program.definitions[current['definition']]])
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
      if parent is None or not eligible(buffs,row['center'],parent) or not buffs.ctx.active(target):continue
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
 return buffs.apply(parent['source'],target,aura['buff'],shared_aura_lease=lease(buffs,center,parent,target,1))
def reconcile_parent(buffs,center,parent,desired):
 members=dict(parent.get('aura_members',{}))
 for member,child in list(members.items()):
  if int(member) not in desired:release(buffs,int(member),child,parent['id'])
 for member in sorted(desired):
  current=buffs._live_parent(center,parent['id'])
  if current is None or not eligible(buffs,center,current):buffs._clear_orphan_children(parent['id']);return
  if not buffs.ctx.active(member):continue
  acquire(buffs,center,current,member)
  fresh=buffs._live_parent(center,parent['id'])
  if fresh is None or not eligible(buffs,center,fresh):buffs._clear_orphan_children(parent['id']);return
  if buffs._reconcile_requested:buffs._publish_owned_members(center,parent['id']);return
 buffs._publish_owned_members(center,parent['id'])
