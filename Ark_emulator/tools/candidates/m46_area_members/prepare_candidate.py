"""Opt-in pure membership; old continuous-radius dispatch remains unchanged."""
from pathlib import Path
import shutil,json,hashlib
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m44_chapter02_integrated_candidate';OUT=ROOT.parent/'unpack_work/campaign_m46_area_members_candidate'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
assert core(BASE)=='81d12ea08787d4edeed139ab55dc73e424644a1b4b8f48360fb9b114b25203da'
if not OUT.exists():shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
def edit(name,before,after):
 p=OUT/'ark_sim'/name;raw=p.read_bytes();old=before.encode();new=after.encode()
 if b'\r\n' in raw:old=old.replace(b'\n',b'\r\n');new=new.replace(b'\n',b'\r\n')
 if new in raw:return
 if old in raw:
  assert raw.count(old)==1;raw=raw.replace(old,new);p.write_bytes(raw)
 else:assert new in raw
edit('content/schemas.py','EFFECT_FIELDS = {','EFFECT_FIELDS = {"membership_rule", ')
edit('content/schemas.py','    fields(effect, EFFECT_FIELDS, path)','''    fields(effect, EFFECT_FIELDS, path)
    if "membership_rule" in effect and (effect.get("op") != "area" or not isinstance(effect["membership_rule"], str) or not effect["membership_rule"]):
        raise ContentError(f"{path}.membership_rule: area-only nonempty explicit rule required")''')
edit('content/schemas.py','        number(effect.get("radius"), f"{path}.radius", 0)','''        if effect.get("membership_rule") is None:
            number(effect.get("radius"), f"{path}.radius", 0)
        else:
            if not isinstance(effect["membership_rule"], str) or not effect["membership_rule"]:
                raise ContentError(f"{path}.membership_rule: nonempty rule required")
            if "radius" in effect:
                raise ContentError(f"{path}: radius and membership_rule are mutually exclusive")
            offsets = effect.get("parameters", {}).get("offsets")
            if offsets is not None and (not isinstance(offsets, (list, tuple)) or not offsets or any(not isinstance(x, (list, tuple)) or len(x)!=2 or any(type(v) is not int for v in x) for x in offsets)):
                raise ContentError(f"{path}.parameters.offsets: nonempty integer cell-offset pairs required")''')
edit('content/capabilities.py','    def effect(item, path, scopes):\n        local = [*scopes, item.get("rules", {})]','    def effect(item, path, scopes):\n        local = [*scopes, item.get("rules", {})]\n        if item.get("op") == "area" and item.get("membership_rule"):\n            require("area.members", path+".membership_rule", explicit=item["membership_rule"])')
edit('domains/effects.py','''                members = []
                for entity in self.ctx.session.world.entities():''','''                members = []
                if effect.get("membership_rule"):
                    candidates = [entity for entity in self.ctx.session.world.entities()
                        if entity["components"].get("spatial", {}).get("position") is not None
                        and getattr(self.ctx, "selectable", self.ctx.alive)(entity["id"])
                        and not any("tag" in f and f["tag"] not in entity["tags"] for f in effect.get("filters", []))]
                    result = self.ctx.calc("area.members", {"center_position": position,
                        "candidates": candidates, "parameters": thaw(effect.get("parameters", {}))},
                        source=source, target=target, owner=source, ability=ability, effect=effect, rule_id=effect["membership_rule"], extra={"ability": ability, "effect": effect})
                    members = thaw(result)
                    allowed = {entity["id"] for entity in candidates}
                    if not isinstance(members, list) or any(type(ref) is not int or ref not in allowed for ref in members) or len(members)!=len(set(members)):
                        raise ValueError("area.members must return unique allowed integer candidate IDs")
                for entity in (() if effect.get("membership_rule") else self.ctx.session.world.entities()):''')
edit('domains/effects.py','''                    "members": members, "radius": effect["radius"]}, cause)''','''                    "members": members, **({"membership_rule": effect["membership_rule"], "parameters": thaw(effect.get("parameters", {}))}
                    if effect.get("membership_rule") else {"radius": effect["radius"]})}, cause)''')
p=OUT/'ark_sim/presets/providers.py';raw=p.read_bytes();marker=b'\ndef selector_grid(inputs, params, context):';code='''
def area_cell_offsets(inputs, params, context):
    from ark_sim.domains.spatial import project_cell
    options = dict(params, **dict(inputs["parameters"]))
    offsets = options.get("offsets")
    if not isinstance(offsets, (list, tuple)) or not offsets or any(not isinstance(x,(list,tuple)) or len(x)!=2 or any(type(v) is not int for v in x) for x in offsets):
        raise ValueError("area cell offsets require nonempty integer pairs")
    row, col = project_cell(inputs["center_position"])
    cells = {(row+dr,col+dc) for dr,dc in offsets}
    return [entity["id"] for entity in inputs["candidates"] if project_cell(entity["components"]["spatial"]["position"]) in cells]

'''.encode()
if b'\r\n' in raw:marker=marker.replace(b'\n',b'\r\n');code=code.replace(b'\n',b'\r\n')
if b'def area_cell_offsets' not in raw:assert raw.count(marker)==1;p.write_bytes(raw.replace(marker,code+marker))
edit('domains/providers.py','    "ark.selector.grid": ark.selector_grid,','    "ark.selector.grid": ark.selector_grid,\n    "ark.area.cell_offsets": ark.area_cell_offsets,')
p=OUT/'ark_sim/rules/contracts.json';d=json.loads(p.read_bytes())
d['contracts']=[c for c in d['contracts'] if c['id']!='area.members']
if True:
 d['contracts'].append({'id':'area.members','kind':'calculation','owner':'effect','inputs':[{'name':'center_position','type':'value_map','required':True},{'name':'candidates','type':'entity_list','required':True},{'name':'parameters','type':'value_map','required':True}],'outputType':'entity_list','outputSchema':{'type':'entity_list','items':{'type':'integer'}},'implementations':['expression','graph','provider'],'pureEvaluation':True,'writesStateDirectly':False,'description':'Opt-in area membership at actual impact center; unique allowed candidate IDs, no selection ordering/randomness.'})
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'candidate':str(OUT),'core':core(OUT)}))
