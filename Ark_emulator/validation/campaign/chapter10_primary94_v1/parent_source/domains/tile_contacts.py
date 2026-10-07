"""Declared point-contact lifecycle policy; tile names never select behavior."""
import math
from collections.abc import Mapping
from ark_sim.contracts import thaw
from .spatial import project_cell,route_motion_mode

def validate_profile(p):
    required={'type','rule','parameters','normal_path_passable','forced_contact_passable','appearance_contact_passable','health_policy','death_reason','reevaluate_each_tick'}
    if not isinstance(p,Mapping) or set(p)!=required:raise ValueError('contact profile requires explicit rule, collision and lifecycle policies')
    if not isinstance(p['rule'],str) or not p['rule']:raise ValueError('contact rule reference required')
    if not isinstance(p['parameters'],Mapping):raise ValueError('contact parameters must be data mapping')
    for k in ('normal_path_passable','forced_contact_passable','appearance_contact_passable','reevaluate_each_tick'):
        if type(p[k]) is not bool:raise ValueError('contact '+k+' must be boolean')
    if p['health_policy'] not in ('zero','preserve'):raise ValueError('contact health_policy requires zero/preserve')
    if p['death_reason']!='dead':raise ValueError('contact lifecycle uses explicit dead reason; exit is not a fall')

class TileContactSystem:
    def __init__(self,ctx):self.ctx=ctx;self._settling=set()
    def mode(self,ref):
        spatial=self.ctx.get(ref,('spatial',),{})
        value=spatial.get('motion_mode')
        if value is None:return route_motion_mode(spatial.get('route'))
        if type(value) is not int or value not in (0,1):raise ValueError('contact motion mode requires WALK0/FLY1')
        return value
    def ready(self,ref):
        now=self.ctx.session.time
        for instance in self.ctx.get(ref,('buffs','instances'),[]):
            if instance.get('expires_at') is not None and instance['expires_at']<=now:continue
            definition=self.ctx.program.definitions[instance['definition']]
            if definition.get('contact_flags',{}).get('defer_fall'):return False
        return True
    def _profile(self,position):
        grid=self.ctx.spatial.grid;row,col=grid._cell(position);tile=grid.tile(row,col)
        p=grid.tile_mechanics.get(tile.get('tileKey'),{})
        return (tile,p,{'row':row,'col':col}) if p.get('type')=='contact_lifecycle' else None
    def decision(self,ref,position,kind,source=None):
        if not self.ctx.active(ref) or self.ctx.route_hidden(ref) or 'tile_field_owner' in self.ctx.entity(ref)['tags']:return None
        row=self._profile(position)
        if row is None:return None
        tile,p,cell=row
        cause={'kind':kind,'source':self.ctx.session.world.resolve(source) if source is not None else None,'environment':True}
        accepted=self.ctx.calc('tile.contact',{'entity':self.ctx.entity(ref),'tile':tile,'cause':cause,
            'motion_mode':self.mode(ref),'ready':self.ready(ref),'parameters':thaw(p['parameters'])},source=ref,rule_id=p['rule'])
        if type(accepted) is not bool:raise ValueError('tile.contact must return strict boolean')
        return {'position':dict(position),'cell':cell,'tile_key':tile['tileKey'],'profile':thaw(p),'cause':cause} if accepted else None
    def inspect(self,ref,kind,source=None):
        if not self.ctx.active(ref) or ref in self._settling:return
        spatial=self.ctx.get(ref,('spatial',),{})
        if 'position' not in spatial:return
        row=self._profile(spatial['position'])
        if row is None:return
        _,p,cell=row
        signature={'cell':cell,'motion_mode':self.mode(ref),'ready':self.ready(ref),'hidden':self.ctx.route_hidden(ref)}
        if kind in ('tick','movement_check') and not p['reevaluate_each_tick'] and signature==spatial.get('contact_signature'):return
        with self.ctx.session.atomic():
            self.ctx.set(ref,('spatial','contact_signature'),signature)
            hit=self.decision(ref,spatial['position'],kind,source)
            if hit is not None:self.settle(ref,hit,kind)
    def segment(self,ref,origin,destination,kind,source=None):
        # Enumerate all crossed cells rather than only the end cell (no tunneling).
        if not self.ctx.active(ref):return None
        dr=destination['row']-origin['row'];dc=destination['col']-origin['col'];times={0.,1.}
        for axis,delta in [('row',dr),('col',dc)]:
            if delta:
                low,high=sorted((origin[axis],destination[axis]))
                for n in range(math.floor(low+.5),math.floor(high+.5)+1):
                    t=(n+.5-origin[axis])/delta
                    if 0<=t<1:times.add(min(1.,t+1e-9/max(abs(dr),abs(dc),1.)))
        seen=set()
        for t in sorted(times):
            point={'row':origin['row']+dr*t,'col':origin['col']+dc*t};cell=project_cell(point)
            if cell in seen:continue
            seen.add(cell)
            if not self.ctx.spatial.grid.inside(*cell):break
            hit=self.decision(ref,point,kind,source)
            if hit is not None:return hit
        return None
    def settle(self,ref,hit,kind):
        if ref in self._settling or not self.ctx.active(ref):return
        with self.ctx.session.atomic():
            self._settling.add(ref)
            try:
                owner=self.ctx.get(ref,('ownership','owner'))
                self.ctx.set(ref,('runtime','death_cause'),{'type':'environment_contact','tile_key':hit['tile_key'],
                    'cell':hit['cell'],'source':hit['cause']['source'],'owner':owner,'kind':kind})
                if hit['profile']['health_policy']=='zero':
                    health=self.ctx.health_resource(ref)
                    if health is not None:self.ctx.resources.adjust(ref,health,value=0)
                self.ctx.emit('tile.contact_death',{'source':hit['cause']['source'],'target':ref,'owner':owner,
                    'cell':hit['cell'],'tile_key':hit['tile_key'],'cause':kind,'health_policy':hit['profile']['health_policy'],
                    'combat_damage':False,'caster_kill_credit':False})
                self.ctx.lifecycle.retire(ref,'dead')
                spatial=self.ctx.get(ref,('spatial',),{})
                motion=spatial.pop('forced_motion',None)
                if motion and motion.get('task') in {t['id'] for t in self.ctx.session.scheduler.pending}:self.ctx.session.cancel(motion['task'])
                self.ctx.set(ref,('spatial',),spatial)
            finally:self._settling.remove(ref)
    def tick(self,session):
        if self.ctx.state().get('finished'):return
        for entity in session.world.entities():
            if entity['id']!=session.world.resolve('system/battle'):self.inspect(entity['id'],'tick')
