"""Isolated generic buff.application capability on exact frozen7a04; no live edits."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate'
DEST = ROOT.parent/'unpack_work/campaign_buff_application_v7_candidate'
PIN = '7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90'


def replace(path, old, new):
    text = path.read_text(encoding='utf8')
    if text.count(old) != 1: raise ValueError('Unexpected source patch anchor: '+str(path))
    path.write_text(text.replace(old, new), encoding='utf8', newline='\n')


def main():
    sys.path.insert(0, str(BASE))
    from ark_sim.adapters.api import implementation_digest
    if implementation_digest() != PIN: raise ValueError('Exact frozen baseline required')
    if DEST.exists(): raise ValueError('Refuse overwriting an existing candidate')
    shutil.copytree(BASE/'ark_sim', DEST/'ark_sim', ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(Path(__file__).with_name('buff_application_runtime.py'), DEST/'ark_sim/domains/buff_application.py')
    buffs = DEST/'ark_sim/domains/buffs.py'
    replace(buffs, 'def apply(self, source, target, buff_id, stacks=1, *, aura_parent=None, toggle_parent=None):',
                   'def apply(self, source, target, buff_id, stacks=1, *, aura_parent=None, toggle_parent=None, duration_override=None):')
    replace(buffs, '            if duration < 0 or interval < 0:',
        '            if duration_override is not None:\n                if type(duration_override) not in (int, float) or not math.isfinite(duration_override) or duration_override < 0: raise ValueError("Invalid duration override")\n                duration = duration_override\n            if duration < 0 or interval < 0:')
    replace(buffs, 'from ark_sim.contracts import Intent, thaw', 'from ark_sim.contracts import Intent, thaw\nimport math')
    effects = DEST/'ark_sim/domains/effects.py'
    replace(effects, '            elif operation == "apply_buff":',
        '            elif operation == "buff_application":\n                from .buff_application import execute\n                execute(self, source, target, effect, cause)\n            elif operation == "apply_buff":')
    replace(effects, '                context.update(source_buff_ids=active_ids(source), target_buff_ids=active_ids(target), owner_buff_ids=active_ids(holder))',
        '                from .selection import DEFAULT_STATE\n                source_selection_state = self.ctx.spatial.selection_state(source, DEFAULT_STATE) if source is not None else {}\n                target_selection_state = self.ctx.spatial.selection_state(target, DEFAULT_STATE)\n                context.update(source_selection_state=source_selection_state, target_selection_state=target_selection_state, source_buff_ids=active_ids(source), target_buff_ids=active_ids(target), owner_buff_ids=active_ids(holder))')
    replace(effects, '                    "samples": samples, "states": {"buff": instance, "source_buff_ids": context["source_buff_ids"],',
        '                    "samples": samples, "states": {"source_selection_state": source_selection_state, "target_selection_state": target_selection_state, "buff": instance, "source_buff_ids": context["source_buff_ids"],')
    schemas = DEST/'ark_sim/content/schemas.py'
    replace(schemas, "EFFECT_FIELDS = {", "EFFECT_FIELDS = {'application_rule', 'allowed', ")
    replace(schemas, "'effects': {'spawn_on_tiles'", "'effects': {'buff_application','spawn_on_tiles'")
    replace(schemas, '    if effect.get("op") == "spawn_on_tiles":',
        '    if effect.get("op") == "buff_application":\n        from ..domains.buff_application import validate_effect as validate_application_effect\n        try: validate_application_effect(effect)\n        except ValueError as error: raise ContentError(path+": "+str(error))\n    if effect.get("op") == "spawn_on_tiles":')
    compiler = DEST/'ark_sim/content/compiler.py'
    anchor = '        def walk(value, path, root_kind=None, location=()):\n            if isinstance(value, Mapping):\n'
    replace(compiler, anchor, anchor+
        '                if value.get("op") == "buff_application":\n                    for ident in value["allowed"]:\n                        if definitions[ident].get("kind") != "buff": raise CompileError(path+": allowed application ID must be Buff")\n                    if definitions[value["application_rule"]].get("contract") != "buff.application": raise CompileError(path+": incompatible application contract")\n')
    path = DEST/'ark_sim/rules/contracts.json'; catalog = json.loads(path.read_bytes())
    catalog['contracts'].append({'id':'buff.application','kind':'calculation','owner':'target',
        'inputs':[{'name':k,'type':'record_list' if k=='instances' else 'entity_list' if k=='allowed' else 'record','required':True} for k in ('source','target','status','instances','request','allowed','attributes')],
        'outputType':'record','implementations':['expression','graph','provider'],'pureEvaluation':True,'writesStateDirectly':False})
    path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'candidate':str(DEST),'base':PIN,'live_unchanged':True}))


if __name__ == '__main__': main()
