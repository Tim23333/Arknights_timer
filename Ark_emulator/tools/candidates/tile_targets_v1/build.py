"""Reproducible isolated candidate; never rewrites the frozen M94 parent."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT.parent / 'unpack_work/campaign_m94_complete_c4_candidate'
OUT = ROOT.parent / 'unpack_work/campaign_tile_targets_v10_candidate'
PIN = 'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def core(root):
    return hashlib.sha256(json.dumps({str(p.relative_to(root / 'ark_sim')): sha(p)
        for p in sorted((root / 'ark_sim').rglob('*.py'))}, sort_keys=True,
        ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def edit(name, old, new):
    p = OUT / 'ark_sim' / name
    source = p.read_text(encoding='utf8')
    assert source.count(old) == 1, (name, old)
    p.write_text(source.replace(old, new), encoding='utf8', newline='')


def main():
    assert core(BASE) == PIN
    if OUT.exists():
        raise FileExistsError('Preserve existing candidate')
    shutil.copytree(BASE / 'ark_sim', OUT / 'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(Path(__file__).with_name('tile_targets.py'), OUT / 'ark_sim/domains/tile_targets.py')
    edit('content/schemas.py', "'ability': {", "'ability': {'tile_selector',")
    edit('content/schemas.py', 'COMPONENT_FIELDS = {', 'COMPONENT_FIELDS = {"tile_occupancy": {"blocks_deployment", "exclusive", "targetable", "withdrawable"},')
    edit('content/schemas.py', '    if effect.get("op") not in capabilities["effects"]:',
        '    if effect.get("op") == "spawn_on_tiles":\n        from ..domains.tile_targets import validate_effect as validate_tile_effect\n        try:validate_tile_effect(effect)\n        except ValueError as error:raise ContentError(path+": "+str(error))\n    if effect.get("op") not in capabilities["effects"]:')
    edit('content/schemas.py', '    elif kind == "ability":',
        '    elif kind == "ability":\n        if "tile_selector" in definition:\n            from ..domains.tile_targets import validate_selector\n            validate_selector(definition["tile_selector"])\n            if definition.get("selector") or definition.get("target_capture") == "each_hit":\n                raise ContentError(identifier+": tile selection requires independent start capture")')
    edit('content/schemas.py', '        if "selection_state" in components:',
        '        if "tile_occupancy" in components:\n            from ..domains.tile_targets import validate_occupancy\n            validate_occupancy(components["tile_occupancy"])\n        if "selection_state" in components:')
    edit('content/schemas.py', "'effects': {", "'effects': {'spawn_on_tiles',")
    edit('domains/abilities.py', '            requires_targets = mode == "automatic_attack"',
        '            tile_candidates = None\n            if ability.get("tile_selector"):\n                from .tile_targets import query\n                tile_candidates = query(self.ctx, source, ability["tile_selector"])\n            requires_targets = mode == "automatic_attack"')
    edit('domains/abilities.py', '            if requires_targets and not targets:',
        '            if requires_targets and not (tile_candidates[:ability["tile_selector"]["limit"]] if tile_candidates is not None else targets):')
    edit('domains/abilities.py', '            if event_payload:',
        '            if tile_candidates is not None:\n                from .tile_targets import select\n                cast["tile_targets"] = select(self.ctx, source, ability["tile_selector"], tile_candidates, cause)\n            if event_payload:')
    edit('domains/effects.py', '        if effect.get("selector"):',
        '        if effect["op"] == "spawn_on_tiles":\n            from .tile_targets import spawn_on_tiles\n            spawn_on_tiles(self.ctx, source, effect, ability, cast, cause)\n            return\n        if effect.get("selector"):')
    edit('domains/deployment.py', '    decision = context.calc("deploy.eligibility", {',
        '    token_occupied = False\n    if inside and getattr(context,"tile_targets_enabled",False):\n        from .tile_targets import blocks_deployment\n        token_occupied = blocks_deployment(context, position)\n    decision = context.calc("deploy.eligibility", {')
    edit('domains/deployment.py', '"occupied": any(e["components"].get("spatial", {}).get("position") == position for e in actors)',
        '"occupied": token_occupied or any(e["components"].get("spatial", {}).get("position") == position for e in actors)')
    edit('domains/lifecycle.py', '        if not has_connectivity and self.ctx.terrain is None',
        '        if not definition.get("components",{}).get("tile_occupancy") and not (kwargs.get("component_overrides") or {}).get("tile_occupancy") and not has_connectivity and self.ctx.terrain is None')
    edit('domains/lifecycle.py', '        spatial["facing"] = facing',
        '        spatial["facing"] = facing\n        if "tile_occupancy" in components:\n            from .tile_targets import validate_placement\n            validate_placement(self.ctx, components["tile_occupancy"], spatial["position"])')
    edit('domains/lifecycle.py', '            plan = self.ctx.get(ref, (\'runtime\', \'activation_plan\'))',
        '            if self.ctx.get(ref,("tile_occupancy",)) is not None:\n                from .tile_targets import validate_placement\n                validate_placement(self.ctx,self.ctx.get(ref,("tile_occupancy",)),self.ctx.get(ref,("spatial","position")),exclude=ref)\n            plan = self.ctx.get(ref, (\'runtime\', \'activation_plan\'))')
    edit('adapters/api.py', 'value.get("op")=="instant_kill"', 'value.get("op") in {"instant_kill", "spawn_on_tiles"}')
    edit('adapters/api.py', '            spec = self.ctx.get(ref, ("deployable",), {})',
        '            if self.ctx.get(ref,("tile_occupancy","withdrawable"),True) is False:\n                raise ValueError("entity is not manually withdrawable")\n            spec = self.ctx.get(ref, ("deployable",), {})')
    edit('adapters/api.py', '        self.ctx.movement = MovementSystem(self.ctx)',
        '        def uses_tiles(value):\n            if isinstance(value,dict) or hasattr(value,"items"):\n                return "tile_occupancy" in value or "tile_selector" in value or any(uses_tiles(v) for k,v in value.items() if k not in {"metadata","parameters","payload"})\n            return isinstance(value,(list,tuple)) and any(uses_tiles(v) for v in value)\n        self.ctx.tile_targets_enabled = uses_tiles(program.definitions) or uses_tiles(program.scenario)\n        self.ctx.movement = MovementSystem(self.ctx)')
    p=OUT/'ark_sim/domains/context.py';s=p.read_text(encoding='utf8')
    anchor="        if 'tile_field_owner' in self.entity(ref)['tags']:\n            return False"
    assert s.count(anchor)==2
    p.write_text(s.replace(anchor,"        if 'tile_field_owner' in self.entity(ref)['tags'] or self.get(ref,(\"tile_occupancy\",\"targetable\"),True) is False:\n            return False"),encoding='utf8',newline='')
    edit('domains/movement.py', "                      and 'tile_field_owner' not in e['tags']",
        "                      and 'tile_field_owner' not in e['tags']\n                      and e['components'].get('tile_occupancy',{}).get('targetable',True)")
    edit('content/capabilities.py', '        if op == "begin_attachment":',
        '        if op == "spawn_on_tiles":\n            token = definitions[item["definition"]]\n            if token.get("kind") != "entity" or not token.get("components",{}).get("tile_occupancy"):\n                raise ContentError(path+": tile token requires an entity with tile_occupancy")\n        if op == "begin_attachment":')
    edit('content/capabilities.py', '        abilities_seen.add(identifier)',
        '        abilities_seen.add(identifier)\n        definition = definitions[identifier]\n        for row in definition.get("timeline", []):\n            for item in ([row["effect"]] if "effect" in row else row.get("effects", [])):\n                if item.get("op") == "spawn_on_tiles" and not definition.get("tile_selector"):\n                    raise ContentError(path+": spawn_on_tiles requires tile_selector")')
    report = {'parent_core': PIN, 'core': core(OUT), 'candidate': str(OUT),
        'changed': [str(p.relative_to(OUT / 'ark_sim')) for p in sorted((OUT / 'ark_sim').rglob('*.py'))
            if not (BASE / 'ark_sim' / p.relative_to(OUT / 'ark_sim')).exists() or
            sha(p) != sha(BASE / 'ark_sim' / p.relative_to(OUT / 'ark_sim'))]}
    target = ROOT / 'validation/campaign/tile_targets_v1/composition_v10.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf8') as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
