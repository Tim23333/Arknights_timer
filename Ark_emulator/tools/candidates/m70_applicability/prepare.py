from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate/ark_sim';DEST=ROOT.parent/'unpack_work/campaign_m70_buff_applicability_v2_candidate/ark_sim'
def edit(name,changes):
 s=(BASE/name).read_text(encoding='utf8')
 for old,new in changes:
  if old not in s:raise ValueError('M70 patch context '+name)
  s=s.replace(old,new,1)
 (DEST/name).write_text(s,encoding='utf8',newline='')
def main():
 catalog=json.loads((BASE/'rules/contracts.json').read_bytes());catalog['contracts'].append({'id':'buff.applicability','kind':'calculation','owner':'owner','inputs':[{'name':n,'type':t,'required':True} for n,t in [('owner','entity_snapshot'),('source','entity_snapshot'),('instance','record'),('status','record'),('parameters','record')]],'outputType':'boolean','implementations':['expression','graph','provider'],'pureEvaluation':True,'writesStateDirectly':False});(DEST/'rules/contracts.json').write_text(json.dumps(catalog,indent=2)+'\n',encoding='utf8',newline='')
 edit('content/schemas.py', [('"buff": {"toggle",','"buff": {"active_rule", "control_rule", "toggle",')])
 edit('content/compiler.py',[( 'expected_contracts = {"recovery_freeze_rule":', 'expected_contracts = {"active_rule": "buff.applicability", "control_rule": "buff.applicability", "recovery_freeze_rule":')])
 edit('content/capabilities.py',[( '    entity_binding_ids = {', '''    for ident,definition in definitions.items():
        if definition.get("kind")=="buff":
            for key in ("active_rule","control_rule"):
                if key in definition:
                    rule=rules.get(definition[key])
                    if rule is None or rule.get("contract")!="buff.applicability":raise ContentError(ident+": applicability rule must implement buff.applicability")
                    requirements.append({"calculation":"buff.applicability","rule":definition[key],"required_by":ident+"."+key})
    entity_binding_ids = {''')])
 edit('domains/selection.py',[
 ('SETS["abnormal_immunes"] = 46','SETS["abnormal_immunes"] = 46\nSETS["abnormal_combo_immunes"] = 2'),
 ('FIELDS = MANDATORY_FIELDS | {"abnormal_immunes"}','FIELDS = MANDATORY_FIELDS | {"abnormal_immunes","abnormal_combo_immunes"}'),
 ('{x:[] for x in SETS}','{x:[] for x in SETS if x!="abnormal_combo_immunes"}'),
 ('    immunity_declared = "abnormal_immunes" in defaults','    combo_declared = "abnormal_combo_immunes" in defaults\n    result.setdefault("abnormal_combo_immunes", [])\n    immunity_declared = "abnormal_immunes" in defaults'),
 ('    result.update(thaw(base))','    combo_declared = combo_declared or "abnormal_combo_immunes" in base\n    result.update(thaw(base))'),
 ('        flags=ctx.program.definitions[instance["definition"]].get("selection_flags",{})','        if not instance.get("applicability",{}).get("active",True):continue\n        flags=ctx.program.definitions[instance["definition"]].get("selection_flags",{})\n        combo_declared = combo_declared or "abnormal_combo_immunes" in flags'),
 ('    # Only explicit native named status indices','    result["abnormal_combos"] = sorted(set(result["abnormal_combos"])-set(result["abnormal_combo_immunes"]))\n    if not combo_declared:result.pop("abnormal_combo_immunes",None)\n    # Only explicit native named status indices')])
 edit('domains/buffs.py',[
 ('        self.ctx = context','        self.ctx = context\n        from .applicability import ApplicabilitySystem\n        self.applicability=ApplicabilitySystem(context,self)'),
 ('            controls = self.ctx.program.definitions[instance["definition"]].get("control", {})','            if not self.applicability.control(instance):continue\n            controls = self.ctx.program.definitions[instance["definition"]].get("control", {})'),
 ('        for instance in instances:\n            definition', '        for instance in instances:\n            if not self.applicability.active(instance):continue\n            definition'),
 ('            self.ctx.resources.sync_capacities(target, capacities_before, "buff_applied")','            self.applicability.reconcile()\n            self.ctx.resources.sync_capacities(target, capacities_before, "buff_applied")'),
 ('            if definition.get("control", {}).get("interrupt"):','            current=next((x for x in self._instances(target) if x["id"]==uid),None)\n            if definition.get("control", {}).get("interrupt") and current is not None and self.applicability.control(current):'),
 ('            if interval_units == 0:','            if interval_units == 0 and current is not None and self.applicability.active(current):'),
 ('                available = self.ctx.aura_available(center) and self.ctx.aura_available(parent["source"])','                available = self.applicability.active(parent) and self.ctx.aura_available(center) and self.ctx.aura_available(parent["source"])'),
 ('    def reconcile(self, session=None):\n        self.toggles.reconcile()','    def reconcile(self, session=None):\n        self.applicability.reconcile()\n        self.toggles.reconcile()'),
 ('        total = self.ctx.get(target, ("spatial", "distance_travelled"), 0)','''        total = self.ctx.get(target, ("spatial", "distance_travelled"), 0)
        if not self.applicability.active(instance):
            values=self._instances(target)
            for item in values:
                if item["id"]==instance["id"]:item["blackboard"]["distance_cursor"]=total
            self.ctx.set(target,("buffs","instances"),values)
            return'''),
 ('        cause = self.ctx.emit("buff.periodic",', '        active=self.applicability.active(instance)\n        cause = self.ctx.emit("buff.periodic",'),
 ('        for effect in definition.get("effects", ()):\n            self.ctx.effects.execute(instance["source"]', '        for effect in definition.get("effects", ()):\n            current=self._active(payload)\n            if current is None or not self.applicability.active(current):break\n            self.ctx.effects.execute(instance["source"]'),
 ('                for subscription in definition.get("events", ()):','                if not self.applicability.active(instance):continue\n                for subscription in definition.get("events", ()):')])
 edit('domains/toggles.py',[( 'active=self.ctx.active(owner) and self.ctx.active(instance[\'source\'])', 'active=self.buffs.applicability.active(instance) and self.ctx.active(owner) and self.ctx.active(instance[\'source\'])')])
 edit('domains/effects.py',[( '            definition = self.ctx.program.definitions[instance["definition"]]\n            for hook', '            if getattr(getattr(self.ctx,'buffs',None),'applicability',None) is not None and not self.ctx.buffs.applicability.active(instance):continue\n            definition = self.ctx.program.definitions[instance["definition"]]\n            for hook')])
 edit('domains/context.py',[
 ('    def set(self, ref, path, value):\n        return self.session.commit([Intent("set", self.session.world.resolve(ref), tuple(path), value)])','''    def set(self, ref, path, value):
        if path and path[0]=="selection_state" and self.buffs is not None and self.buffs.applicability.enabled:
            with self.session.atomic():
                result=self.session.commit([Intent("set",self.session.world.resolve(ref),tuple(path),value)])
                self.buffs.reconcile();return result
        return self.session.commit([Intent("set", self.session.world.resolve(ref), tuple(path), value)])'''),
 ('or (self.buffs is not None and self.buffs.toggles.enabled):','or (self.buffs is not None and (self.buffs.toggles.enabled or self.buffs.applicability.enabled)):'),
 ('        event_id = self.session.emit(event, payload, cause=cause)','        if self.buffs is not None:self.buffs.applicability.reconcile()\n        event_id = self.session.emit(event, payload, cause=cause)')])
 edit('domains/resources.py',[( '    def adjust(self, ref, resource, delta=None, *, value=None, source=None, ability=None, effect=None):','''    def adjust(self, ref, resource, delta=None, *, value=None, source=None, ability=None, effect=None):
        if getattr(getattr(getattr(self.ctx,'buffs',None),'applicability',None),'enabled',False):
            with self.ctx.session.atomic():return self._adjust_applicability(ref,resource,delta,value=value,source=source,ability=ability,effect=effect)
        return self._adjust_applicability(ref,resource,delta,value=value,source=source,ability=ability,effect=effect)

    def _adjust_applicability(self, ref, resource, delta=None, *, value=None, source=None, ability=None, effect=None):''')])
if __name__=='__main__':main()
