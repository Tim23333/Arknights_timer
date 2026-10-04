"""Generic owned attachments and explicit damage flags on frozen M75."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m75_periodic_packets_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m78_owned_attachment_candidate'
PIN='348c5671adfd73adb501c67a3dd4c51ce4f88228e45dcc6b1026c6eb2822bd57'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def edit(name,before,after,count=1):
    p=OUT/'ark_sim'/name;s=p.read_text(encoding='utf8')
    if s.count(before)!=count:raise ValueError('Changed attachment anchor '+name+':'+before)
    p.write_text(s.replace(before,after),encoding='utf8',newline='')
def main():
    assert core(BASE)==PIN
    if OUT.exists():raise ValueError('Candidate exists; no overwrite')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    f=Path('ark_emulator/levels/packs/level_main_00-01.json');(OUT/f).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/f,OUT/f)
    shutil.copyfile(Path(__file__).with_name('attachments.py'),OUT/'ark_sim/domains/attachments.py')
    edit('domains/context.py','        self.periodic_fields = None','        self.periodic_fields = None\n        self.attachments = None')
    edit('domains/context.py','        if self.periodic_fields is not None:\n            with session.atomic():',
        '        if self.periodic_fields is not None or self.attachments is not None:\n            with session.atomic():')
    edit('adapters/api.py','        self._commands = []',
        '        if any(d.get("kind") == "attachment" for d in program.definitions.values()):\n            from ark_sim.domains.attachments import AttachmentSystem\n            self.ctx.attachments = AttachmentSystem(self.ctx)\n        self._commands = []')
    edit('adapters/api.py','        if self.ctx.periodic_fields is not None:\n            self.session.register_handler',
        '        if self.ctx.attachments is not None:\n            for name, handler in self.ctx.attachments.handlers.items(): self.session.register_handler(name, handler)\n            self.session.add_system(self.ctx.attachments.tick, phase=0)\n        if self.ctx.periodic_fields is not None:\n            self.session.register_handler')
    edit('domains/effects.py','        source = self.ctx.session.world.resolve(source)',
        '        if effect.get("op") == "begin_attachment" or "damage_flags" in effect or "bind_to_cast" in effect:\n            from ark_sim.content.schemas import validate_effect, DEFAULT_CAPABILITIES\n            validate_effect(effect, "runtime.explicit_owned_effect", DEFAULT_CAPABILITIES)\n        source = self.ctx.session.world.resolve(source)')
    edit('domains/effects.py','            elif operation == "apply_buff":\n                self.ctx.buffs.apply(source, target, effect["buff"], effect.get("stacks", 1))',
        '            elif operation == "begin_attachment":\n                if self.ctx.attachments is None: raise ValueError("Attachment capability was not loaded")\n                self.ctx.attachments.begin(source, target, effect["attachment"], ability, cast, cause)\n            elif operation == "apply_buff":\n                if effect.get("bind_to_cast") and not self.ctx.abilities._active(source, cast.get("id")):\n                    raise ValueError("Cast-bound buff has no active owner")\n                uid = self.ctx.buffs.apply(source, target, effect["buff"], effect.get("stacks", 1))\n                if effect.get("bind_to_cast"):\n                    self.ctx.abilities.bind_buff(source, cast.get("id"), target, uid)')
    edit('domains/effects.py','if operation == "damage" and is_attack and self.ctx.alive(source)',
        'if operation == "damage" and is_attack and effect.get("damage_flags", {}).get("source_attack_type", "NORMAL") == "NORMAL" and self.ctx.alive(source)')
    edit('domains/effects.py','"amount": actual, "ability": ability.get("id"), "resource": resource}, cause)',
        '"amount": actual, "ability": ability.get("id"), "resource": resource,\n                     **({"damage_flags": thaw(effect["damage_flags"])} if "damage_flags" in effect else {})}, cause)')
    edit('domains/resources.py','        rows = []\n        if event == "damage.accepted"',
        '        rows = []\n        if event == "damage.accepted" and payload.get("damage_flags", {}).get("ignore_for_sp") is True:\n            return rows\n        if event == "damage.accepted"')
    edit('domains/abilities.py','            if params.get("cancel_pending_attacks"):',
        '            forbidden = activation.get("forbidden_source_flags", [])\n            if forbidden:\n                from .selection import DEFAULT_STATE\n                if set(forbidden) & set(self.ctx.spatial.selection_state(source, DEFAULT_STATE)["abnormal_flags"]):\n                    raise ActivationRejected("Ability source has a forbidden status")\n            if params.get("cancel_pending_attacks"):')
    edit('domains/abilities.py','            if params.get("wait_for_projectiles"):\n                cast["pending_projectiles"]',
        '            if ability.get("wait_for_channels"):\n                cast["pending_channels"] = 0\n                cast["channel_recovery_units"] = self.ctx.quantize(recovery)\n            if params.get("wait_for_projectiles"):\n                cast["pending_projectiles"]')
    edit('domains/abilities.py','            for (holder, resource), before in resources_before.items():\n                current',
        '            if ability.get("wait_for_channels"):\n                self.ctx.set(source, ("runtime", "casts", cast_id, "started_event"), started_event)\n            for (holder, resource), before in resources_before.items():\n                current')
    edit('domains/abilities.py','    def finish(self, session, payload):',Path(__file__).with_name('ability_methods.py').read_text(encoding='utf8')+'''    def finish(self, session, payload):
        cast = self._active(payload["source"], payload["cast"])
        if cast and ("owned_buffs" in cast or "pending_channels" in cast):
            with session.atomic():
                return self._finish(session, payload)
        return self._finish(session, payload)

    def _finish(self, session, payload):''')
    edit('domains/abilities.py','        if cast.get("pending_projectiles", 0):','        if cast.get("pending_projectiles", 0) or cast.get("pending_channels", 0):')
    edit('domains/abilities.py','        if cast["parameters"].get("wait_for_projectiles"):\n            self.ctx.set',
        '        self._release_cast_buffs(source, cast)\n        if "pending_channels" in cast:\n            self.ctx.set(source, ("runtime", "cooldowns", cast["ability"]), session.time+cast["channel_recovery_units"])\n        if cast["parameters"].get("wait_for_projectiles"):\n            self.ctx.set')
    edit('domains/abilities.py','            for cast in selected.values():\n                self.ctx.emit',
        '            for cast in selected.values():\n                if getattr(self.ctx, "attachments", None) is not None: self.ctx.attachments.cancel_cast(source, cast["id"])\n                self._release_cast_buffs(source, cast)\n                self.ctx.emit')
    edit('domains/lifecycle.py','        if self.ctx.terrain is None:\n            return self._retire',
        '        if self.ctx.terrain is None and getattr(self.ctx, "attachments", None) is None:\n            return self._retire')
    edit('domains/lifecycle.py','        self.ctx.abilities.interrupt(ref, reason)',
        '        self.ctx.abilities.interrupt(ref, reason)\n        if getattr(self.ctx, "attachments", None) is not None: self.ctx.attachments.target_invalid(ref)')
    edit('domains/lifecycle.py','        if getattr(self.ctx, "controls", None) is None:',
        '        if getattr(self.ctx, "controls", None) is None and getattr(self.ctx, "attachments", None) is None:')
    edit('domains/lifecycle.py','        if result["finished"]:',
        '        if result["finished"] and result.get("result") == "victory" and getattr(self.ctx, "attachments", None) is not None and self.ctx.attachments.completion_pending():\n            return\n        if result["finished"]:')
    edit('domains/lifecycle.py','            self.ctx.state_update(finished=True, result=result["result"], finished_at=session.time)',
        '            self.ctx.state_update(finished=True, result=result["result"], finished_at=session.time)\n            if getattr(self.ctx, "attachments", None) is not None: self.ctx.attachments.terminate_all()')
    edit('domains/movement.py','        spec = selector.get("eligibility")',
        '        if selector.get("exclude_abnormal_flags"):\n            from .selection import DEFAULT_STATE\n            if set(selector["exclude_abnormal_flags"]) & set(self.selection_state(candidate, DEFAULT_STATE)["abnormal_flags"]): return False\n        spec = selector.get("eligibility")')
    edit('content/dependencies.py','REFERENCE_KEYS = {','REFERENCE_KEYS = {"attachment", "target_buff", "source_recovery_buff",')
    edit('content/schemas.py','\nFIELDS = {','\nFIELDS = {"attachment": {"duration_seconds", "flight_lifetime_seconds", "step_interval_seconds", "refresh_interval_seconds", "motion", "target_buff", "effect", "damage_integral", "source_cancel_flags", "ignored_owned_source_flags", "force_reach_on_timeout", "lifecycle", "max_packets", "completion_blocking", "source_recovery_buff", "recovery_on"}, ')
    edit('content/schemas.py','"ability": {','"ability": {"wait_for_channels",')
    edit('content/schemas.py','"selector": {','"selector": {"exclude_abnormal_flags",')
    edit('content/schemas.py','EFFECT_FIELDS = {','EFFECT_FIELDS = {"attachment", "bind_to_cast", "damage_flags",')
    edit('content/schemas.py','"effects": {','"effects": {"begin_attachment",')
    edit('content/schemas.py','    if "membership_rule" in effect and',
        '    if "bind_to_cast" in effect and (effect.get("op") != "apply_buff" or type(effect["bind_to_cast"]) is not bool):\n        raise ContentError(path+": bind_to_cast requires apply_buff and strict bool")\n    if effect.get("op") == "begin_attachment" and not isinstance(effect.get("attachment"), str):\n        raise ContentError(path+": begin_attachment requires an explicit reference")\n    if "damage_flags" in effect:\n        flags = effect["damage_flags"]\n        if effect.get("op") != "damage" or not isinstance(flags, Mapping) or set(flags) != {"source_attack_type", "ignore_for_sp"} or flags["source_attack_type"] not in {"NORMAL", "SPLASH", "BUFF", "ADDITION", "NONE"} or type(flags["ignore_for_sp"]) is not bool:\n            raise ContentError(path+": explicit typed actor damage_flags required")\n    if "membership_rule" in effect and')
    edit('content/schemas.py','    elif kind == "selector":',
        '    elif kind == "attachment":\n        from ..domains.attachments import validate_profile\n        try: validate_profile(definition)\n        except ValueError as error: raise ContentError(identifier+": "+str(error)) from error\n        validate_effect(definition["effect"], identifier+".effect", capabilities)\n    elif kind == "selector":\n        flags = definition.get("exclude_abnormal_flags", [])\n        if not isinstance(flags, (list, tuple)) or any(type(flag) is not int or not 0 <= flag < 46 for flag in flags):\n            raise ContentError(identifier+": exclude_abnormal_flags requires typed enum values")')
    edit('content/schemas.py','    elif kind == "ability":',
        '    elif kind == "ability":\n        if "wait_for_channels" in definition and type(definition["wait_for_channels"]) is not bool:\n            raise ContentError(identifier+": wait_for_channels requires strict bool")')
    edit('content/schemas.py','        activation = definition.get("activation", {})',
        '        activation = definition.get("activation", {})\n        flags = activation.get("forbidden_source_flags", [])\n        if not isinstance(flags, (list, tuple)) or any(type(flag) is not int or not 0 <= flag < 46 for flag in flags):\n            raise ContentError(identifier+": forbidden_source_flags requires typed enum values")')
    edit('content/schemas.py','fields(activation, {','fields(activation, {"forbidden_source_flags",')
    edit('content/compiler.py','                    expected = {', '                    expected = {') if False else None
    edit('content/compiler.py','expected = {"projectile_definition":', 'expected = {"attachment": {"attachment"}, "target_buff": {"buff"}, "source_recovery_buff": {"buff"}, "projectile_definition":')
    edit('content/capabilities.py','        if op == "apply_terrain_overlay":',
        '        if op == "begin_attachment":\n            chosen = definitions[item["attachment"]]\n            if chosen.get("kind") != "attachment": raise ContentError(path+": attachment kind required")\n        if op == "apply_terrain_overlay":')
    edit('content/capabilities.py','        if _definition.get("kind") == "entity" and _definition.get("rules",{}).get("targeting.availability"):',
        '        if _definition.get("kind") == "attachment":\n            require("projectile.trajectory", _id+".motion", explicit=_definition["motion"]["rule"])\n            require("time.quantize", _id+".clock")\n        if _definition.get("kind") == "entity" and _definition.get("rules",{}).get("targeting.availability"):')
    edit('content/capabilities.py','        definition = definitions[identifier]\n        local = [*scopes, definition.get("rules", {})]',
        '''        definition = definitions[identifier]
        def has_channel(value):
            if isinstance(value, Mapping):
                return value.get("op") == "begin_attachment" or any(has_channel(child) for key, child in value.items() if key not in {"metadata", "parameters"})
            return isinstance(value, (list, tuple)) and any(has_channel(child) for child in value)
        if has_channel(definition) and not definition.get("wait_for_channels"):
            raise ContentError(path+": begin_attachment requires explicit wait_for_channels")
        local = [*scopes, definition.get("rules", {})]''')
    edit('content/capabilities.py','    for identifier, definition in definitions.items():\n        kind, scopes = definition.get("kind"), [definition.get("rules", {})]',
        '    for identifier, definition in definitions.items():\n        if definition.get("kind") == "attachment":\n            effect(definition["effect"], identifier+".effect", [])\n        kind, scopes = definition.get("kind"), [definition.get("rules", {})]')
    report={'parent_core':PIN,'core':core(OUT),'sources':{str(p.relative_to(OUT)):sha(p) for p in sorted((OUT/'ark_sim').rglob('*.py'))}}
    path=ROOT/'validation/campaign/m78_attachments/composition.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'core':report['core']}))
if __name__=='__main__':main()
