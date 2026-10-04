"""Typed initial cooldown and qualified radius primary union on frozen M94."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate';OUT=ROOT.parent/'unpack_work/campaign_frost_combat_v5_candidate'
PIN='cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def edit(name,old,new):
 p=OUT/'ark_sim'/name;s=p.read_text(encoding='utf8');assert s.count(old)==1,(name,old);p.write_text(s.replace(old,new),encoding='utf8',newline='')
def main():
 assert core(BASE)==PIN
 if OUT.exists():raise FileExistsError('Preserve existing candidate')
 shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 f=Path('ark_emulator/levels/packs/level_main_00-01.json');(OUT/f).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/f,OUT/f)
 edit('content/schemas.py',"'ability': {","'ability': {'initial_cooldown_seconds',")
 edit('content/schemas.py','    elif kind == "ability":','    elif kind == "ability":\n        if "initial_cooldown_seconds" in definition:\n            number(definition["initial_cooldown_seconds"], identifier+".initial_cooldown_seconds", 0)')
 shutil.copyfile(Path(__file__).with_name('ability_timing.py'),OUT/'ark_sim/domains/ability_timing.py')
 edit('content/schemas.py','COMPONENT_FIELDS = {','COMPONENT_FIELDS = {"ability_timing": {"initial_cooldowns"},')
 edit('content/schemas.py','        abilities = components.get("abilities", [])','        abilities = components.get("abilities", [])\n        if "ability_timing" in components:\n            from ark_sim.domains.ability_timing import validate_overrides\n            try:validate_overrides(components["ability_timing"], abilities)\n            except ValueError as error:raise ContentError(identifier+": "+str(error)) from error')
 edit('domains/lifecycle.py','        for overlay in components.get("terrain_overlays", ()):', '        from .ability_timing import initialize\n        initialize(self.ctx,ref,components)\n        for overlay in components.get("terrain_overlays", ()):')
 edit('domains/lifecycle.py','        if not has_connectivity and self.ctx.terrain is None', '        from .ability_timing import requires_atomic\n        has_initial_clocks=requires_atomic(self.ctx,definition,kwargs.get("component_overrides") or {})\n        if not has_initial_clocks and not has_connectivity and self.ctx.terrain is None')
 edit('domains/death_projectiles.py','def qualified_radius(inputs,params,context):',Path(__file__).with_name('radius_validation.py').read_text(encoding='utf8')+'\ndef qualified_radius(inputs,params,context):')
 edit('domains/death_projectiles.py',"    if set(options)!={'radius','eligibility'} or type(options['radius']) not in (int,float) or not math.isfinite(options['radius']) or options['radius']<0:\n        raise ValueError('qualified radius requires explicit finite radius and eligibility')",'    validate_radius_parameters(options)')
 edit('domains/death_projectiles.py',"    projection=context['area_selection_states'];center=inputs['center_position'];result=[]", "    projection=context['area_selection_states'];center=inputs['center_position'];result=[]\n    primary=None\n    if options.get('include_primary',False):\n        target=context.get('target')\n        if not isinstance(target,Mapping) or type(target.get('id')) is not int:\n            raise ValueError('qualified radius include_primary requires a captured target')\n        primary=target['id']")
 edit('domains/death_projectiles.py',"        if math.hypot(pos['row']-center['row'],pos['col']-center['col'])>options['radius']:continue", "        if actor['id']!=primary and math.hypot(pos['row']-center['row'],pos['col']-center['col'])>options['radius']:continue")
 edit('content/capabilities.py',"            require('targeting.eligibility',path+'.eligibility',explicit=options['eligibility']['rule'])", "            from ark_sim.domains.death_projectiles import validate_radius_parameters\n            try:validate_radius_parameters(options)\n            except ValueError as error:raise ContentError(path+': '+str(error)) from error\n            require('targeting.eligibility',path+'.eligibility',explicit=options['eligibility']['rule'])")
 receipt()
def receipt():
 report={'parent_core':PIN,'core':core(OUT),'changed':[str(p.relative_to(OUT/'ark_sim')) for p in sorted((OUT/'ark_sim').rglob('*.py')) if not (BASE/'ark_sim'/p.relative_to(OUT/'ark_sim')).exists() or sha(p)!=sha(BASE/'ark_sim'/p.relative_to(OUT/'ark_sim'))]}
 dest=ROOT/('validation/campaign/frost_combat_v1/composition_'+OUT.name+'.json');dest.parent.mkdir(parents=True,exist_ok=True)
 with dest.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
 print(json.dumps(report))
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--receipt-only',action='store_true');args=parser.parse_args()
 if args.receipt_only:receipt()
 else:main()
