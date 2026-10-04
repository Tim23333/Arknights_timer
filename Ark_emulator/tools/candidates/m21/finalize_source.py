"""Record the integration's immutable terrain-metadata preflight fix."""
from pathlib import Path
import ast
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
from prepare_candidate import OUT, REPORT, SOURCES, core, sha


def main():
    path = OUT/'ark_sim/domains/terrain.py'; text = path.read_text(encoding='utf8')
    old = "        allowed=set(base)|PATCH_FIELDS|{'groundPassable','movementCost'}\n        if set(options)-allowed:raise ValueError('terrain tile-options rule returned unsupported fields')"
    new = """        normalized=PATCH_FIELDS|{'groundPassable','movementCost'}
        for key,value in options.items():
            if key not in normalized and (key not in base or value!=base[key]):
                raise ValueError('terrain rule cannot change base tile identity or behavior metadata')
        # A partial numeric result inherits immutable source identity/metadata;
        # adding active mechanics requires a separately implemented dispatcher.
        options={**base,**options}"""
    if new not in text:
        if text.count(old) != 1: raise ValueError('unreviewed terrain source shape')
        path.write_text(text.replace(old, new), encoding='utf8', newline='\n')
    effects = OUT/'ark_sim/domains/effects.py'; effect_source = effects.read_text(encoding='utf8')
    old_gate = "            if operation not in {'activate_predefined', 'retire', 'emit', 'remove_buff', 'remove_terrain_overlay'} and not self.ctx.get(target, ('runtime', 'active'), True):"
    new_gate = """            if (operation not in {'activate_predefined', 'retire', 'emit', 'remove_buff', 'remove_terrain_overlay'}
                    and not (operation == 'area' and effect.get('center_position') is not None)
                    and not self.ctx.get(target, ('runtime', 'active'), True)):"""
    if new_gate not in effect_source:
        if effect_source.count(old_gate) != 1: raise ValueError('unreviewed inactive area gate')
        effects.write_text(effect_source.replace(old_gate, new_gate), encoding='utf8', newline='\n')
    for source, pin in SOURCES.values():
        if core(source) != pin: raise ValueError('frozen source changed')
    for file in (OUT/'ark_sim').rglob('*.py'):
        ast.parse(file.read_text(encoding='utf8'), filename=str(file))
    report = {'schema': 'ark-sim/integrated-candidate-source/v1', 'implementation': core(OUT), 'formal_approval': False,
        'source_pins': {k: pin for k, (_, pin) in SOURCES.items()},
        'integration_fix': 'Only normalized numeric tile fields may change; immutable base identity and behavior metadata inherited or exact-equal',
        'files': {p.relative_to(OUT).as_posix(): sha(p) for p in sorted((OUT/'ark_sim').rglob('*')) if p.is_file() and p.suffix in ('.py', '.json')}}
    (REPORT/'source.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'implementation': report['implementation'], 'files': len(report['files']), 'formal_approval': False}))


if __name__ == '__main__': main()
