from pathlib import Path
import shutil,hashlib,json
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m55_route_obstacle_candidate';OUT=ROOT.parent/'unpack_work/campaign_m57_obstacle_reentry_candidate';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
assert core(BASE)=='5c33c17ec6c7d7d1a1677e0df88176e594237e9d6485262e430c94dba86912ea'
if not OUT.exists():shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
p=OUT/'ark_sim/domains/movement.py';b=(BASE/'ark_sim/domains/movement.py').read_bytes()
def edit(old,new):
 global b
 a=old.encode();c=new.encode()
 if b'\r\n' in b:a=a.replace(b'\n',b'\r\n');c=c.replace(b'\n',b'\r\n')
 if c in b:return
 assert b.count(a)==1,old;b=b.replace(a,c)
edit('    def _blocking(self):\n','''    def _obstacle_facts(self, mover_id, obstacle_id):
        if not self.ctx.active(mover_id) or self.ctx.route_hidden(mover_id) or not self.ctx.active(obstacle_id) or self.ctx.route_hidden(obstacle_id):return None
        mover=thaw(self.ctx.entity(mover_id));obstacle=thaw(self.ctx.entity(obstacle_id))
        spatial=mover['components'].get('spatial',{});other=obstacle['components'].get('spatial',{}).get('position');spec=obstacle['components'].get('route_obstacle')
        if not spatial.get('route') or route_motion_mode(spatial['route']) != 0 or spatial.get('forced_motion') or not spec or other is None:return None
        position=spatial.get('position')
        if position is None:return None
        cursor=spatial.get('movement',{}).get('path_index',0)
        if type(cursor) is not int or cursor<0:raise ValueError('route obstacle path index invalid')
        remaining=list(spatial.get('movement_path',()))[cursor:];cell=project_cell(other)
        if not any(project_cell(point)==cell for point in remaining) and project_cell(position)!=cell:return None
        distance=math.hypot(other['row']-position['row'],other['col']-position['col'])
        if distance>spec['contact_radius']:return None
        return mover,obstacle,remaining,distance,spec

    def _blocking(self):
''')
edit('''        for entity in movers:
            ref = entity["id"]
            spatial = entity["components"].get("spatial", {})''','''        for entity in movers:
            ref = entity["id"]
            if not self.ctx.active(ref):continue
            entity=thaw(self.ctx.entity(ref))
            spatial = entity["components"].get("spatial", {})''')
old='''                remaining=list(spatial.get("movement_path",()))
                cursor=spatial.get("movement",{}).get("path_index",0)
                if type(cursor) is not int or cursor<0:raise ValueError("route obstacle path index invalid")
                remaining=remaining[cursor:]
                for obstacle in sorted(obstacles,key=lambda e:(e["id"]!=previous,e["id"])):
                    spec=obstacle["components"]["route_obstacle"];other=obstacle["components"]["spatial"]["position"]
                    cell=project_cell(other)
                    if not any(project_cell(p)==cell for p in remaining) and project_cell(position)!=cell:continue
                    distance=math.hypot(other["row"]-position["row"],other["col"]-position["col"])
                    if distance>spec["contact_radius"]:continue
                    accepted=self.ctx.calc("blocking.obstacle",{"source":entity,"obstacle":obstacle,"path":remaining,
                        "distance":distance,"parameters":thaw(spec["parameters"])},source=ref,target=obstacle["id"],owner=obstacle["id"],rule_id=spec["rule"])
                    if type(accepted) is not bool:raise ValueError("blocking.obstacle must return strict boolean")
                    if accepted:
                        current=obstacle["id"];break'''
new='''                for captured_obstacle in sorted(obstacles,key=lambda e:(e["id"]!=previous,e["id"])):
                    facts=self._obstacle_facts(ref,captured_obstacle['id'])
                    if facts is None:continue
                    live_mover,obstacle,remaining,distance,spec=facts
                    accepted=self.ctx.calc("blocking.obstacle",{"source":live_mover,"obstacle":obstacle,"path":remaining,
                        "distance":distance,"parameters":thaw(spec["parameters"])},source=ref,target=obstacle["id"],owner=obstacle["id"],rule_id=spec["rule"])
                    if type(accepted) is not bool:raise ValueError("blocking.obstacle must return strict boolean")
                    if accepted and self._obstacle_facts(ref,obstacle['id']) is not None:
                        current=obstacle["id"];break'''
edit(old,new)
edit('''            if current != self.blocked_by(ref):
                self.ctx.set(ref, ("runtime", "blocked_by"), current)
                self.ctx.emit("blocking.changed", {"source": current, "target": ref})''','''            obstacle_relation=current is not None and any(o['id']==current for o in obstacles)
            if obstacle_relation and self._obstacle_facts(ref,current) is None:current=None
            if not self.ctx.active(ref):continue
            if current != self.blocked_by(ref):
                self.ctx.set(ref, ("runtime", "blocked_by"), current)
                self.ctx.emit("blocking.changed", {"source": current, "target": ref})
                # Domain event callbacks may legally retire/move a participant.
                # Do not leave its relation for the next maintenance tick.
                if obstacle_relation and current is not None and self.blocked_by(ref)==current and self._obstacle_facts(ref,current) is None:
                    self.ctx.set(ref, ('runtime','blocked_by'), None)
                    self.ctx.emit('blocking.changed', {'source':None,'target':ref,'reason':'obstacle_callback_invalidated'})''')
edit('''    def blocking(self):
        if self._blocking_reconciling:
            return
        self._blocking_reconciling = True
        try:
            with self.ctx.session.atomic():
                self._blocking()
                self._blocking_reconciling = False
                self.ctx.buffs.toggles.reconcile()
        finally:
            self._blocking_reconciling = False
''','''    def blocking(self):
        if self._blocking_reconciling:
            self._blocking_requested = True
            return
        self._blocking_reconciling = True
        try:
            with self.ctx.session.atomic():
                budget = self.ctx.session.reaction_budget
                while True:
                    self._blocking_requested = False
                    self._blocking()
                    before = tuple(self.ctx.session.world.entities())
                    self.ctx.buffs.toggles.reconcile()
                    if before != tuple(self.ctx.session.world.entities()):self._blocking_requested = True
                    if not self._blocking_requested:break
                    budget -= 1
                    if budget <= 0:raise ValueError('blocking callbacks exceed stabilization budget')
        finally:
            self._blocking_reconciling = False
            self._blocking_requested = False

    def _emit_blocking(self, payload):
        # Immutable snapshots detect synchronous actor/control/path callbacks;
        # pure queries and unchanged events do not request another pass.
        before = tuple(self.ctx.session.world.entities())
        self.ctx.emit('blocking.changed', payload)
        if before != tuple(self.ctx.session.world.entities()):self._blocking_requested = True
''')
edit('self.ctx.emit("blocking.changed",', 'self.ctx.emit("blocking.changed",') if False else None
# Replace all relation emissions, including the invalidation callback emission.
b=b.replace(b'self.ctx.emit("blocking.changed",',b'self._emit_blocking(').replace(b"self.ctx.emit('blocking.changed', {'source':None",b"self._emit_blocking({'source':None")
edit('''            for blocker, capacity in ordered:
                other = self.ctx.get(blocker, ("spatial", "position"))''','''            for blocker, capacity in ordered:
                if not self.ctx.active(blocker) or self.ctx.route_hidden(blocker) or not self.ctx.buffs.controls(blocker)['block']:continue
                captured = next(e for e in entities if e['id']==blocker)
                if captured != thaw(self.ctx.entity(blocker)):
                    capacity = self.ctx.calc('blocking.capacity', {'attributes':self.ctx.attributes.values(blocker),'states':{},'capacity_parameters':{'capacity':self.ctx.role_value(blocker,'block_capacity')}},source=blocker)
                other = self.ctx.get(blocker, ("spatial", "position"))''')
edit('''                    if accepted and self._obstacle_facts(ref,obstacle['id']) is not None:
                        current=obstacle["id"];break''','''                    after=self._obstacle_facts(ref,obstacle['id'])
                    if after != facts:
                        self._blocking_requested=True
                        continue
                    if accepted and after is not None:
                        current=obstacle["id"];break''')
edit('''                plan = self.ctx.calc("blocking.eligibility", {"blocker": self.ctx.entity(blocker),''','''                blocker_before=self.ctx.entity(blocker)
                mover_before=self.ctx.entity(ref)
                plan = self.ctx.calc("blocking.eligibility", {"blocker": blocker_before,''')
edit('''                path = spatial.get("movement_path", ())
                blocker_cell = project_cell(other)''','''                if not self.ctx.active(ref) or not self.ctx.active(blocker) or mover_before != self.ctx.entity(ref) or blocker_before != self.ctx.entity(blocker):
                    self._blocking_requested=True
                    continue
                path = spatial.get("movement_path", ())
                blocker_cell = project_cell(other)''')
p.write_bytes(b);print(json.dumps({'candidate':str(OUT),'core':core(OUT),'changed':['domains/movement.py']}))

