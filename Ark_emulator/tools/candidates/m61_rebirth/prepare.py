"""Small rebirth wiring hunks; does not edit any existing frozen branch."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate/ark_sim';DEST=ROOT.parent/'unpack_work/campaign_m61_rebirth_candidate/ark_sim'
def edits(name,changes):
 p=DEST/name;s=(BASE/name).read_text(encoding='utf8')
 for old,new in changes:
  if old not in s:raise ValueError('Patch context:'+name)
  s=s.replace(old,new,1)
 p.write_text(s,encoding='utf8',newline='')
def main():
 edits('content/schemas.py',[
 ('    "selection_state": None,','    "selection_state": None,\n    "rebirth": None,'),
 ('"effects": {"set_motion_mode",','"effects": {"instant_kill", "set_motion_mode",'),
 ('    if effect["op"] == "retire":','''    if effect["op"] == "instant_kill":
        options=effect.get("parameters")
        if not isinstance(options,Mapping) or set(options)!={"cause","skip_rebirth"} or not isinstance(options["cause"],str) or not options["cause"] or not options["cause"].replace("_","").replace("-","").isalnum() or type(options["skip_rebirth"]) is not bool:
            raise ContentError(path+": instant_kill requires event-safe cause and explicit skip_rebirth bool")
        if effect.get("target","selected") in {"battle","scenario"}:raise ContentError(path+": instant_kill cannot target battle")
    if effect["op"] == "retire":'''),
 ('        if "selection_state" in components:','''        if "rebirth" in components:
            from ..domains.rebirth import validate
            validate(components["rebirth"],components)
            for key in ("on_begin","on_finish"):
                for i,effect in enumerate(components["rebirth"].get(key,[])):validate_effect(effect,identifier+".rebirth."+key+"["+str(i)+"]",capabilities)
        if "selection_state" in components:''')])
 edits('content/dependencies.py',[( '"interrupt_abilities"}', '"interrupt_abilities", "retain_buffs"}')])
 edits('content/compiler.py',[
 ('            check_freeze(resources, entity.get("components", {}).get("abilities", []), identifier)', '''            check_freeze(resources, entity.get("components", {}).get("abilities", []), identifier)
            if "rebirth" in entity.get("components",{}):
                from ..domains.rebirth import validate
                validate(entity["components"]["rebirth"],entity["components"],definitions)'''),
 ('            check_freeze(actual.get("resources", {}), actual.get("abilities", []), item.get("instanceAlias") or item["definition"])', '''            check_freeze(actual.get("resources", {}), actual.get("abilities", []), item.get("instanceAlias") or item["definition"])
            if "rebirth" in actual:
                from ..domains.rebirth import validate
                validate(actual["rebirth"],actual,definitions)''')])
 edits('content/capabilities.py',[
 ('        if op in {"retire",','        if op in {"instant_kill", "retire",'),
 ('        entity_scopes[identifier] = scopes','''        entity_scopes[identifier] = scopes
        if "rebirth" in components:
            require("resource.recovery", identifier+".rebirth.restore_rule", scopes, components["rebirth"]["restore_rule"])''')])
 edits('adapters/api.py',[
 ('        self.ctx.lifecycle = LifecycleSystem(self.ctx)','''        self.ctx.lifecycle = LifecycleSystem(self.ctx)
        def uses_rebirth(value):
            if isinstance(value,dict) or hasattr(value,"items"):
                return "rebirth" in value.get("components",{}) or value.get("op")=="instant_kill" or any(uses_rebirth(v) for k,v in value.items() if k not in {"metadata","parameters","payload"})
            return isinstance(value,(list,tuple)) and any(uses_rebirth(v) for v in value)
        if uses_rebirth(program.definitions) or uses_rebirth(program.scenario):
            from ark_sim.domains.rebirth import RebirthSystem
            self.ctx.rebirth=RebirthSystem(self.ctx)'''),
 ('        self.session.add_system(self.ctx.lifecycle.prune_expired, phase=0)','''        self.session.add_system(self.ctx.lifecycle.prune_expired, phase=0)
        if getattr(self.ctx,"rebirth",None) is not None:
            for name,handler in self.ctx.rebirth.handlers.items():self.session.register_handler(name,handler)
            self.session.add_system(self.ctx.rebirth.tick,phase=0)''')])
 edits('domains/lifecycle.py',[
 ('        parameters = parameters or {}','''        if "rebirth" in components:
            from .rebirth import validate
            validate(components["rebirth"],components,self.ctx.program.definitions)
            if getattr(self.ctx,"rebirth",None) is None:raise ValueError("rebirth feature was not compiled into runtime")
        parameters = parameters or {}'''),
 ('        lifecycle = self.ctx.get(ref, ("lifecycle",), {})','''        rebirth=getattr(self.ctx,"rebirth",None)
        if rebirth is not None and rebirth.consume(ref,event):return
        lifecycle = self.ctx.get(ref, ("lifecycle",), {})'''),
 ('        self.ctx.set(ref, ("runtime", "alive"), False)','''        rebirth=getattr(self.ctx,"rebirth",None)
        if rebirth is not None:rebirth.cancel(ref,reason)
        self.ctx.set(ref, ("runtime", "alive"), False)'''),
 ('        if getattr(self.ctx, "controls", None) is None:', '        if getattr(self.ctx, "controls", None) is None and getattr(self.ctx,"rebirth",None) is None:'),
 ('            self.ctx.state_update(finished=True, result=result["result"], finished_at=session.time)', '''            self.ctx.state_update(finished=True, result=result["result"], finished_at=session.time)
            if getattr(self.ctx,"rebirth",None) is not None:self.ctx.rebirth.cancel_all("battle_terminal")''')])
 edits('domains/effects.py',[
 ('        ability, cast = ability or {}, cast or {}','''        ability, cast = ability or {}, cast or {}
        if getattr(self.ctx,"rebirth",None) is not None and not self.ctx.rebirth.callback_allowed():return'''),
 ('                    and not self.ctx.get(target, (\'runtime\', \'active\'), True)):', '''                    and not self.ctx.get(target, ('runtime', 'active'), True)
                    and operation != "instant_kill"
                    and not (getattr(self.ctx,"rebirth",None) is not None and self.ctx.rebirth.effect_allowed(target))):'''),
 ('and not getattr(self.ctx, "effect_target_available", lambda ref: True)(target):', '''and not getattr(self.ctx, "effect_target_available", lambda ref: True)(target) and not (getattr(self.ctx,"rebirth",None) is not None and self.ctx.rebirth.effect_allowed(target)):'''),
 ('            if operation == \'activate_predefined\':','''            if operation == "instant_kill":
                if getattr(self.ctx,"rebirth",None) is None:raise ValueError("instant_kill feature not compiled")
                self.ctx.rebirth.instant_kill(source,target,effect["parameters"],ability,cast,cause)
            elif operation == 'activate_predefined':'''),
 ('            if cast.get("control_instance") and not self.ctx.controls.settle_effect(cast, operation): return', '''            if getattr(self.ctx,"rebirth",None) is not None:self.ctx.rebirth.settle_callback(operation)
            if cast.get("control_instance") and not self.ctx.controls.settle_effect(cast, operation): return''')])
 edits('domains/resources.py',[
 ('    def adjust(self, ref, resource, delta=None, *, value=None, source=None, ability=None, effect=None):','''    def adjust(self, ref, resource, delta=None, *, value=None, source=None, ability=None, effect=None):
        canonical=self.ctx.session.world.resolve(ref)
        rebirth=getattr(self.ctx,"rebirth",None)
        if rebirth is not None and (self.ctx.get(canonical,("rebirth",)) is not None or canonical in rebirth._requests):
            with self.ctx.session.atomic():return self._adjust(canonical,resource,delta,value=value,source=source,ability=ability,effect=effect)
        return self._adjust(canonical,resource,delta,value=value,source=source,ability=ability,effect=effect)

    def _adjust(self, ref, resource, delta=None, *, value=None, source=None, ability=None, effect=None):''')])
if __name__=='__main__':main()
