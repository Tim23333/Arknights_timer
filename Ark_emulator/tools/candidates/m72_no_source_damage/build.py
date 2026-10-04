"""Create M72 from frozen M68, retaining all previous candidates."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate'
OUT = ROOT.parent/'unpack_work/campaign_m72_no_source_damage_candidate'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def core(root):
    return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p)
        for p in sorted((root/'ark_sim').rglob('*.py'))}, sort_keys=True, ensure_ascii=False,
        separators=(',', ':')).encode()).hexdigest()
def replace(path, before, after, count=1):
    text = path.read_text(encoding='utf8')
    if text.count(before) != count: raise ValueError(f'Changed anchor {path}: {before}')
    path.write_text(text.replace(before, after), encoding='utf8', newline='')

def main():
    if OUT.exists(): raise ValueError('Candidate exists; no overwrite')
    assert core(BASE) == '1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8'
    source = ROOT/'packages/campaign/chapter04_environment/source.reference.json'
    assert sha(source) == '148a5a8648801f8c7eee655d5c0daa1f4f7469cefe3abd2d304dcdc33a121dc8'
    shutil.copytree(BASE/'ark_sim', OUT/'ark_sim', ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    fixture = Path('ark_emulator/levels/packs/level_main_00-01.json')
    (OUT/fixture).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE/fixture, OUT/fixture)
    shutil.copyfile(Path(__file__).with_name('no_source_damage.py'), OUT/'ark_sim/domains/no_source_damage.py')
    effects = OUT/'ark_sim/domains/effects.py'
    replace(effects, '        source = self.ctx.session.world.resolve(source)',
        "        if effect.get('op') == 'no_source_damage':\n            from .no_source_damage import execute\n            return execute(self, source, targets, effect, ability, cast, cause)\n        source = self.ctx.session.world.resolve(source)")
    replace(effects, '"source": self.ctx.entity(source),', '"source": self.ctx.entity(source) if source is not None else {},', 5)
    replace(effects, '                    return [i["definition"] for i in self.ctx.get(ref,',
        '                    if ref is None: return []\n                    return [i["definition"] for i in self.ctx.get(ref,')
    replace(effects, '                    ref = source if binding["entity"] == "source" else target\n                    view = snapshot',
        '                    ref = source if binding["entity"] == "source" else target\n                    if ref is None: raise ValueError("Target hook cannot bind absent source attributes")\n                    view = snapshot')
    lifecycle = OUT/'ark_sim/domains/lifecycle.py'
    replace(lifecycle, '            self.retire(ref, "dead")',
        '            self.retire(ref, "dead", damage_attribution=event if event.get("source_policy") == "none" else None)')
    replace(lifecycle, '    def retire(self, ref, reason):', '    def retire(self, ref, reason, *, damage_attribution=None):')
    replace(lifecycle, 'return self._retire(ref, reason)', 'return self._retire(ref, reason, damage_attribution=damage_attribution)', 2)
    replace(lifecycle, '    def _retire(self, ref, reason):', '    def _retire(self, ref, reason, *, damage_attribution=None):')
    replace(lifecycle, '        self.ctx.emit(event, {"source": ref, "target": ref})',
        '        self.ctx.emit(event, {"source": ref, "target": ref} if damage_attribution is None else {**damage_attribution, "source": None, "target": ref}, damage_attribution.get("cause") if damage_attribution is not None else None)')
    resources = OUT/'ark_sim/domains/resources.py'
    replace(resources, '        rows = []\n        for entity in self.ctx.session.world.entities():',
        '        rows = []\n        if event == "damage.accepted" and payload.get("source_policy") == "none" and payload.get("ignore_for_sp") is True:\n            return rows\n        for entity in self.ctx.session.world.entities():')
    schema = OUT/'ark_sim/content/schemas.py'
    replace(schema, '"effects": {"set_motion_mode",', '"effects": {"no_source_damage", "set_motion_mode",')
    replace(schema, '    if "membership_rule" in effect and',
        '    no_source_fields = {"fixed_amount", "origin", "ignore_for_sp", "attack_type", "damage_without_modify", "node_is_env_damage", "env_blackboard_injected", "environmental"}\n    if effect.get("op") != "no_source_damage" and set(effect) & no_source_fields:\n        raise ContentError(path+": no-source fields require the explicit no_source_damage operation")\n    if effect.get("op") == "no_source_damage":\n        from ..domains.no_source_damage import validate_request\n        try: validate_request(effect)\n        except ValueError as error: raise ContentError(path+": "+str(error)) from error\n    if "membership_rule" in effect and')
    replace(schema, 'EFFECT_FIELDS = {', 'EFFECT_FIELDS = {"fixed_amount", "origin", "ignore_for_sp", "attack_type", "damage_without_modify", "node_is_env_damage", "env_blackboard_injected", "environmental", ')
    capabilities = OUT/'ark_sim/content/capabilities.py'
    replace(capabilities, '        if op == "damage":\n            require("damage.pipeline", path, local)',
        '        if op in {"damage", "no_source_damage"}:\n            require("damage.pipeline", path, local)\n            if op == "no_source_damage":\n                chosen = definitions[item["rules"]["damage.pipeline"]]\n                if any(binding["entity"] == "source" for binding in chosen.get("metadata", {}).get("input_bindings", {}).values()):\n                    raise ContentError(path+": no-source pipeline cannot bind actor attributes")')
    dependencies = OUT/'ark_sim/content/dependencies.py'
    replace(dependencies, 'if name in {"metadata", "parameters", "payload", "inputs", "expected_blackboard"}:',
        'if name == "origin" and item.get("op") == "no_source_damage":\n                    continue\n                if name in {"metadata", "parameters", "payload", "inputs", "expected_blackboard"}:')
    compiler=OUT/'ark_sim/content/compiler.py'
    replace(compiler, '            for key, child in value.items():\n                if key == "condition"',
        '            for key, child in value.items():\n                if key == "origin" and value.get("op") == "no_source_damage": continue\n                if key == "condition"')
    replace(compiler, '                for key, child in value.items():\n                    if key==\'blackboard\' and location[-3:]',
        '                for key, child in value.items():\n                    if key == "origin" and value.get("op") == "no_source_damage": continue\n                    if key==\'blackboard\' and location[-3:]')
    replace(compiler, '                if key not in {"dynamicReferences", "metadata", "parameters", "payload", "inputs"}:',
        '                if key == "origin" and value.get("op") == "no_source_damage": continue\n                if key not in {"dynamicReferences", "metadata", "parameters", "payload", "inputs"}:')
    replace(compiler, '            for key, child in value.items():\n                if key==\'blackboard\' and location[-3:]',
        '            for key, child in value.items():\n                if key == "origin" and value.get("op") == "no_source_damage": continue\n                if key==\'blackboard\' and location[-3:]')
    movement=OUT/'ark_sim/domains/movement.py'
    replace(movement, "        inputs = {'source':self.ctx.entity(source), 'candidate':self.ctx.entity(candidate),",
        "        source_view = self.ctx.entity(source) if source is not None else {}\n        source_state = self.selection_state(source, DEFAULT_STATE) if source is not None else {**thaw(DEFAULT_STATE), 'side': 2}\n        inputs = {'source':source_view, 'candidate':self.ctx.entity(candidate),")
    replace(movement, "'selection_states':{'source':self.selection_state(source,DEFAULT_STATE),", "'selection_states':{'source':source_state,")
    replace(movement, "'source':self.ctx.entity(source),'target':self.ctx.entity(candidate)", "'source':source_view,'target':self.ctx.entity(candidate)")
    api = OUT/'ark_sim/adapters/api.py'
    replace(api, '{"source": "system/battle", "targets": [],\n                "effect": thaw(entry["effect"])}',
        '{"source": None if entry["effect"].get("op") == "no_source_damage" else "system/battle", "targets": [],\n                "effect": thaw(entry["effect"])}')
    report = {'parent_core': core(BASE), 'core': core(OUT), 'environment_source_sha256': sha(source),
        'source_sha256': {str(p.relative_to(OUT)):sha(p) for p in sorted((OUT/'ark_sim').rglob('*.py'))}}
    target=ROOT/'validation/campaign/m72_no_source_damage/composition.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2)+'\n',encoding='utf8')
    print(json.dumps({'core':report['core']}))

if __name__ == '__main__': main()
