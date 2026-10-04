import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_frost_combat_v5_candidate'
OUT=ROOT.parent/'unpack_work/campaign_ability_arbitration_v3_candidate'
PIN='df98feb41687d1b560d27d24bcbc7aad8bbb2f7ace48aaa67aca5816fe95e86b'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def edit(name,old,new):
    path=OUT/'ark_sim'/name;source=path.read_text(encoding='utf8');assert source.count(old)==1,(name,old)
    path.write_text(source.replace(old,new),encoding='utf8',newline='')
def main():
    assert core(BASE)==PIN
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(Path(__file__).with_name('ability_arbitration.py'),OUT/'ark_sim/domains/ability_arbitration.py')
    edit('content/schemas.py','COMPONENT_FIELDS = {','COMPONENT_FIELDS = {"ability_arbitration": None,')
    edit('content/schemas.py','        abilities = components.get("abilities", [])',
        '        abilities = components.get("abilities", [])\n        if "ability_arbitration" in components:\n            from ..domains.ability_arbitration import validate as validate_arbitration\n            validate_arbitration(components["ability_arbitration"], abilities)')
    edit('domains/lifecycle.py','        has_initial_clocks=requires_atomic(self.ctx,definition,kwargs.get("component_overrides") or {})',
        '        has_initial_clocks=requires_atomic(self.ctx,definition,kwargs.get("component_overrides") or {})\n        from .ability_arbitration import requires_atomic as needs_arbitration_atomic\n        has_initial_clocks=has_initial_clocks or needs_arbitration_atomic(definition,kwargs.get("component_overrides") or {})')
    edit('domains/lifecycle.py','        from .ability_timing import initialize',
        '        from .ability_arbitration import initialize as initialize_arbitration\n        initialize_arbitration(self.ctx,ref,components)\n        from .ability_timing import initialize')
    edit('domains/lifecycle.py','        merge(components, thaw(component_overrides or {}))',
        '        merge(components, thaw(component_overrides or {}))\n        if "ability_arbitration" in components:\n            from .ability_arbitration import validate as validate_arbitration\n            validate_arbitration(components["ability_arbitration"],components.get("abilities",[]),self.ctx.program.definitions)')
    edit('domains/abilities.py','            replace_ready = None',
        '            if entity["components"].get("ability_arbitration") is not None:\n                from .ability_arbitration import tick as arbitrate\n                arbitrate(self,source)\n                continue\n            replace_ready = None')
    edit('content/capabilities.py','        entity_scopes[identifier] = scopes',
        '        if "ability_arbitration" in components:\n            from ..domains.ability_arbitration import validate as validate_arbitration\n            validate_arbitration(components["ability_arbitration"],components.get("abilities",[]),definitions)\n            if any(row["attack_clock"] for row in components["ability_arbitration"]["entries"]):\n                require("time.interval",identifier+".ability_arbitration",scopes)\n                require("time.quantize",identifier+".ability_arbitration",scopes)\n        entity_scopes[identifier] = scopes')
    edit('content/capabilities.py','        if merged.get("terrain_overlays"):',
        '        if "ability_arbitration" in merged:\n            from copy import deepcopy\n            effective=deepcopy(definition.get("components",{}))\n            def merge_effective(dst,src):\n                for key,value in src.items():\n                    if isinstance(value,dict) and isinstance(dst.get(key),dict):merge_effective(dst[key],value)\n                    else:dst[key]=deepcopy(value)\n            merge_effective(effective,item.get("components",{}))\n            from ..domains.ability_arbitration import validate as validate_arbitration\n            validate_arbitration(effective["ability_arbitration"],effective.get("abilities",[]),definitions)\n        if merged.get("terrain_overlays"):')
    dest=ROOT/'validation/campaign/ability_arbitration_v1/composition_v3.json';dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('x',encoding='utf8') as f:json.dump({'parent_core':PIN,'core':core(OUT),'candidate':str(OUT)},f,indent=2)
    print(json.dumps({'core':core(OUT)}))
if __name__=='__main__':main()
