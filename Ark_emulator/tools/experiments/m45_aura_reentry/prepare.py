from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m42_aura_remove_candidate/ark_sim';DEST=ROOT.parent/'unpack_work/campaign_m45_aura_reentry_candidate/ark_sim'
def main():
    p=DEST/'domains/buffs.py';s=(BASE/'domains/buffs.py').read_text(encoding='utf8')
    s=s.replace('        self._removal_depth = 0','        self._removal_depth = 0\n        self._reconcile_requested = False',1)
    old='''            self.reconcile()
            return uid

    def remove(self, target, buff_or_instance):'''
    new='''            # Normal owned-child installation is already part of this pass.
            # Its real effects can separately request another reconciliation.
            if not (self._reconciling and aura_parent is not None):self.reconcile()
            return uid

    def remove(self, target, buff_or_instance, *, _from_aura=False):'''
    assert old in s;s=s.replace(old,new)
    old='''            if removed and self._removal_depth == 0:
                self.reconcile()
            return removed'''
    new='''            if removed:
                if self._reconciling and not _from_aura:self._reconcile_requested = True
                if self._removal_depth == 0 and not (self._reconciling and _from_aura):self.reconcile()
            return removed'''
    assert old in s;s=s.replace(old,new)
    s=s.replace('self.remove(int(member), child)','self.remove(int(member), child, _from_aura=True)')
    start=s.index('    def reconcile(self, session=None):');end=s.index('\n    def ',start+8)
    s=s[:start]+METHOD+s[end:];p.write_text(s,encoding='utf8',newline='')
METHOD='''    def _live_parent(self, center, uid):
        return next((p for p in self._instances(center) if p["id"] == uid), None)

    def _parent_active(self, center, parent):
        return (getattr(self.ctx, 'active', self.ctx.alive)(center)
                and getattr(self.ctx, 'active', self.ctx.alive)(parent["source"])
                and (parent["expires_at"] is None or self.ctx.session.time < parent["expires_at"]))

    def _clear_orphan_children(self, parent_id):
        # Instance identity includes the center, so this does not touch other
        # parents with the same definition or sources sharing a target.
        for entity in self.ctx.session.world.entities():
            for child in self._instances(entity["id"]):
                if child.get("aura_parent") == parent_id:
                    self.remove(entity["id"], child["id"], _from_aura=True)

    def _publish_owned_members(self, center, parent_id):
        parent = self._live_parent(center, parent_id)
        if parent is None:
            self._clear_orphan_children(parent_id)
            return
        members = {}
        for entity in self.ctx.session.world.entities():
            for child in self._instances(entity["id"]):
                if child.get("aura_parent") == parent_id:
                    key = str(entity["id"])
                    if key in members:raise ValueError("aura parent owns duplicate children on one target")
                    members[key] = child["id"]
        if members != parent.get("aura_members", {}):
            parents = self._instances(center)
            for item in parents:
                if item["id"] == parent_id:item["aura_members"] = members
            self.ctx.set(center, ("buffs", "instances"), parents)

    def _reconcile_pass(self):
        for entity in self.ctx.session.world.entities():
            center = entity["id"]
            for captured in self._instances(center):
                parent = self._live_parent(center, captured["id"])
                if parent is None:continue
                definition = self.ctx.program.definitions[parent["definition"]]
                aura = definition.get("aura")
                if not aura:continue
                if not self._parent_active(center, parent):
                    self.remove(center, parent["id"], _from_aura=True)
                    self._clear_orphan_children(parent["id"])
                    continue
                available = self.ctx.aura_available(center) and self.ctx.aura_available(parent["source"])
                desired = set(self.ctx.spatial.select(center, aura["selector"])) if available else set()
                desired = {ref for ref in desired if getattr(self.ctx, 'active', self.ctx.alive)(ref)}
                members = dict(parent.get("aura_members", {}))
                invalid = False
                for member, child in list(members.items()):
                    if int(member) not in desired:
                        self.remove(int(member), child, _from_aura=True)
                        members.pop(member, None)
                        current = self._live_parent(center, parent["id"])
                        if current is None or not self._parent_active(center, current):
                            if current is not None:self.remove(center, current["id"], _from_aura=True)
                            self._clear_orphan_children(parent["id"])
                            invalid = True
                            break
                        if current["source"] != parent["source"]:
                            self._reconcile_requested = True
                            invalid = True
                            break
                        if self._reconcile_requested:
                            self._publish_owned_members(center, parent["id"])
                            return
                if invalid:continue
                for member in sorted(desired):
                    current = self._live_parent(center, parent["id"])
                    if current is None or not self._parent_active(center, current):
                        if current is not None:self.remove(center, current["id"], _from_aura=True)
                        self._clear_orphan_children(parent["id"])
                        invalid = True
                        break
                    if not getattr(self.ctx, 'active', self.ctx.alive)(member):continue
                    key = str(member)
                    if key not in members or not any(i["id"] == members[key] for i in self._instances(member)):
                        members[key] = self.apply(current["source"], member, aura["buff"], aura_parent=parent["id"])
                        fresh = self._live_parent(center, parent["id"])
                        if fresh is None or not self._parent_active(center, fresh):
                            if fresh is not None:self.remove(center, fresh["id"], _from_aura=True)
                            self._clear_orphan_children(parent["id"])
                            invalid = True
                            break
                        if self._reconcile_requested:
                            self._publish_owned_members(center, parent["id"])
                            return
                current = self._live_parent(center, parent["id"])
                if invalid or current is None:continue
                if not self._parent_active(center, current):
                    self.remove(center, current["id"], _from_aura=True)
                    self._clear_orphan_children(parent["id"])
                    continue
                if members != current.get("aura_members", {}):
                    parents = self._instances(center)
                    for item in parents:
                        if item["id"] == current["id"]:item["aura_members"] = members
                    self.ctx.set(center, ("buffs", "instances"), parents)

    def reconcile(self, session=None):
        if not self.has_auras:return
        if self._reconciling:
            self._reconcile_requested = True
            return
        if self._removal_depth:return
        self._reconciling = True
        try:
            with self.ctx.session.atomic():
                budget = self.ctx.session.reaction_budget
                while True:
                    self._reconcile_requested = False
                    self._reconcile_pass()
                    if not self._reconcile_requested:break
                    budget -= 1
                    if budget <= 0:raise ValueError("aura callbacks exceed reconciliation budget")
        finally:
            self._reconciling = False
            self._reconcile_requested = False
'''
if __name__=='__main__':main()
