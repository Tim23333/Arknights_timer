from pathlib import Path
import shutil,hashlib,json
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate';OUT=ROOT.parent/'unpack_work/campaign_m49_visibility_candidate';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
assert core(BASE)=='a829685336bc55af4d5b3098f6eca9887ce870906ab20429ec43de789630fbc9'
if not OUT.exists():shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
def edit(name,old,new):
 p=OUT/'ark_sim'/name;b=p.read_bytes();a=old.encode();c=new.encode()
 if b'\r\n' in b:a=a.replace(b'\n',b'\r\n');c=c.replace(b'\n',b'\r\n')
 if c in b:return
 assert b.count(a)==1,(name,old);p.write_bytes(b.replace(a,c))
(OUT/'ark_sim/domains/toggles.py').write_bytes(Path(__file__).with_name('toggles.py').read_bytes())
edit('domains/buffs.py','        self.ctx = context\n','        self.ctx = context\n        from .toggles import ToggleSystem\n        self.toggles = ToggleSystem(context, self)\n')
edit('domains/buffs.py','def apply(self, source, target, buff_id, stacks=1, *, aura_parent=None):','def apply(self, source, target, buff_id, stacks=1, *, aura_parent=None, toggle_parent=None):')
edit('domains/buffs.py','            if definition.get("aura"):\n                instance["aura_members"]','            if toggle_parent is not None:\n                instance["toggle_parent"] = toggle_parent\n            if definition.get("toggle") and existing and existing.get("toggle_state"):\n                instance["toggle_state"] = existing["toggle_state"]\n            if definition.get("aura"):\n                instance["aura_members"]')
edit('domains/buffs.py','            for item in removed:\n                for member, child','            for item in removed:\n                self.toggles.remove(target, item)\n                for member, child')
edit('domains/buffs.py','    def reconcile(self, session=None):\n','    def reconcile(self, session=None):\n        self.toggles.reconcile()\n')
edit('domains/context.py','        if self.resources is not None and self.resources.has_custom_freeze_rules:', '        if (self.resources is not None and self.resources.has_custom_freeze_rules) or (self.buffs is not None and self.buffs.toggles.enabled):')
edit('domains/context.py','        event_id = self.session.emit(event, payload, cause=cause)\n','        event_id = self.session.emit(event, payload, cause=cause)\n        if self.buffs is not None:self.buffs.toggles.pulse(event, payload)\n')
edit('domains/movement.py','    def qualifies(self, source, candidate, selector, ability=None, effect=None):','''    def available(self, source, candidate, selector=None, ability=None, effect=None, observable=False):
        binding = self.ctx.definition(candidate).get('rules', {}).get('targeting.availability')
        if binding is None:return True
        from .selection import DEFAULT_STATE
        selector = selector or {}
        inputs = {'source':self.ctx.entity(source), 'candidate':self.ctx.entity(candidate),
            'selector':thaw(selector), 'ability':thaw(ability or {}), 'effect':thaw(effect or {}),
            'selection_states':{'source':self.selection_state(source,DEFAULT_STATE), 'candidate':self.selection_state(candidate,DEFAULT_STATE)}}
        if observable:
            result = self.ctx.calc('targeting.availability', inputs,source=source,target=candidate,owner=candidate,ability=ability,effect=effect,rule_id=binding)
        else:
            result = thaw(self.ctx.rules.evaluate('targeting.availability',inputs,rule_id=binding,context={'time':self.ctx.session.time,'quantum':self.ctx.session.quantum,'source':self.ctx.entity(source),'target':self.ctx.entity(candidate),'owner':self.ctx.entity(candidate),'rule_scope':{'source':self.ctx.definition_bindings(source),'target':self.ctx.definition_bindings(candidate),'ability':(ability or {}).get('rules',{}),'effect':(effect or {}).get('rules',{})}}).value)
        if type(result) is not bool:raise ValueError('targeting.availability must return strict bool')
        return result

    def qualifies(self, source, candidate, selector, ability=None, effect=None, observable=False):''')
edit('domains/movement.py','''        spec = selector.get("eligibility")
        if spec is None:''','''        if not self.available(source,candidate,selector,ability,effect,observable):return False
        spec = selector.get("eligibility")
        if spec is None:''')
edit('domains/movement.py','            if not self.qualifies(source, ref, definition, ability, effect):','            if not self.qualifies(source, ref, definition, ability, effect, observable=True):')
edit('domains/movement.py','                self._blocking()\n        finally:','                self._blocking()\n                self._blocking_reconciling = False\n                self.ctx.buffs.toggles.reconcile()\n        finally:')
edit('domains/effects.py','''                        and getattr(self.ctx, "selectable", self.ctx.alive)(entity["id"])
                        and not any''','''                        and getattr(self.ctx, "selectable", self.ctx.alive)(entity["id"])
                        and self.ctx.spatial.available(source,entity["id"],ability=ability,effect=effect,observable=True)
                        and not any''')
edit('domains/effects.py','''                    if math.hypot(pos["row"]-position["row"], pos["col"]-position["col"]) > effect["radius"]:''','''                    if not self.ctx.spatial.available(source,entity["id"],ability=ability,effect=effect,observable=True):
                        continue
                    if math.hypot(pos["row"]-position["row"], pos["col"]-position["col"]) > effect["radius"]:''')
# Optional immunity projection: legacy complete defaults remain sufficient.
edit('domains/selection.py','FIELDS = BOOLS | set(MASKS) | set(SETS) | {"side"}','MANDATORY_FIELDS = BOOLS | set(MASKS) | set(SETS) | {"side"}\nSETS["abnormal_immunes"] = 46\nFIELDS = MANDATORY_FIELDS | {"abnormal_immunes"}\nDEFAULT_STATE = {**{x:False for x in BOOLS}, **{x:0 for x in MASKS}, **{x:[] for x in SETS}, "side":0}')
edit('domains/selection.py','    if complete and set(state) != FIELDS:','    if complete and not MANDATORY_FIELDS <= set(state):')
edit('domains/selection.py','    result=thaw(defaults)\n','    result=thaw(defaults)\n    immunity_declared = "abnormal_immunes" in defaults\n    result.setdefault("abnormal_immunes", [])\n')
edit('domains/selection.py','    validate_state(base)\n','    validate_state(base)\n    immunity_declared = immunity_declared or "abnormal_immunes" in base\n')
edit('domains/selection.py','        for key,value in flags.items():\n','        immunity_declared = immunity_declared or "abnormal_immunes" in flags\n        for key,value in flags.items():\n')
edit('domains/selection.py','    # Only explicit native named status indices become corresponding flags.','    result["abnormal_flags"] = sorted(set(result["abnormal_flags"]) - set(result["abnormal_immunes"]))\n    # Only explicit native named status indices become corresponding flags.')
edit('domains/selection.py','    return result\n','    if not immunity_declared:result.pop("abnormal_immunes", None)\n    return result\n')
edit('content/schemas.py','"buff": {','"buff": {"toggle", ')
edit('content/schemas.py','    elif kind == "buff":\n','    elif kind == "buff":\n        if "toggle" in definition:\n            from ..domains.toggles import validate\n            validate(definition["toggle"],identifier+".toggle")\n')
edit('content/capabilities.py','    for _id, _definition in definitions.items():','    for _id, _definition in definitions.items():\n        if _definition.get("kind") == "buff" and _definition.get("toggle"):\n            spec=_definition["toggle"];require("passive.toggle",_id+".toggle",explicit=spec["rule"])\n            child=definitions[spec["buff"]]\n            if child.get("kind") != "buff" or child.get("duration_seconds") is not None or child.get("duration_rule") or child.get("toggle") or child.get("stacking",{}).get("mode") != "independent":raise ContentError(_id+": toggle child requires permanent independent non-toggle Buff")\n        if _definition.get("kind") == "entity" and _definition.get("rules",{}).get("targeting.availability"):\n            require("targeting.availability",_id+".rules",explicit=_definition["rules"]["targeting.availability"])')
p=OUT/'ark_sim/rules/contracts.json';d=json.loads(p.read_bytes());d['contracts']=[c for c in d['contracts'] if c['id'] not in ['passive.toggle','targeting.availability']]
for ident,owner,inputs in [('passive.toggle','owner',[('owner','entity_snapshot'),('source','entity_snapshot'),('blocked_by',{'type':'integer','nullable':True}),('blocker_active','boolean'),('clock','record'),('state','record'),('parameters','record')]),('targeting.availability','target',[('source','entity_snapshot'),('candidate','entity_snapshot'),('selector','record'),('ability','record'),('effect','record'),('selection_states','record')])]:
 d['contracts'].append({'id':ident,'kind':'calculation','owner':owner,'inputs':[{'name':name,**(typ if isinstance(typ,dict) else {'type':typ}),'required':True} for name,typ in inputs],'outputType':'boolean','implementations':['expression','graph','provider'],'pureEvaluation':True,'writesStateDirectly':False})
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'candidate':str(OUT),'core':core(OUT)}))
