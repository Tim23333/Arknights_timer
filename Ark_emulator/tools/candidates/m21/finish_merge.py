"""Resolve reviewed wiring unions, then merge the frozen dormant revision."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
from prepare_candidate import OUT, REPORT, SOURCES, core, sha


def resolve_union(relative, expected_left, expected_right, result):
    path = OUT/'ark_sim'/relative; text = path.read_text(encoding='utf8')
    pattern = r'<<<<<<<[^\n]+\n(.*?)\|\|\|\|\|\|\|[^\n]+\n(.*?)=======\n(.*?)>>>>>>>[^\n]+\n'
    matches = list(re.finditer(pattern, text, re.S))
    if len(matches) != 1: raise ValueError('expected one reviewed wiring conflict: '+relative)
    match = matches[0]
    if match[1] != expected_left or match[3] != expected_right: raise ValueError('unreviewed conflict changed: '+relative)
    path.write_text(text[:match.start()]+result+text[match.end():], encoding='utf8', newline='\n')


def main():
    for path, pin in SOURCES.values():
        if core(path) != pin: raise ValueError('frozen source drift')
    resolve_union('adapters/api.py', 'from ark_sim.domains.terrain import TerrainSystem\n',
        'from ark_sim.domains.projectiles import ProjectileSystem\n',
        'from ark_sim.domains.terrain import TerrainSystem\nfrom ark_sim.domains.projectiles import ProjectileSystem\n')
    resolve_union('domains/providers.py', 'BUILTIN_PROVIDERS = {\n    "ark.terrain.tile_options": ark.terrain_tile_options,\n',
        'from . import projectile_profiles\n\nBUILTIN_PROVIDERS = {"model.projectile.trajectory": projectile_profiles.trajectory, "model.projectile.collision": projectile_profiles.collision,\n',
        'from . import projectile_profiles\n\nBUILTIN_PROVIDERS = {\n    "ark.terrain.tile_options": ark.terrain_tile_options,\n    "model.projectile.trajectory": projectile_profiles.trajectory,\n    "model.projectile.collision": projectile_profiles.collision,\n')
    incoming = SOURCES['dormant'][0]/'ark_sim'; base = SOURCES['dormant_parent'][0]/'ark_sim'
    scratch = REPORT/'dormant_merge_inputs'; scratch.mkdir(exist_ok=True)
    changed = []; conflicts = []
    for path in sorted(p for p in incoming.rglob('*') if p.is_file() and p.suffix in ('.py', '.json')):
        rel = path.relative_to(incoming); ancestor = base/rel; current = OUT/'ark_sim'/rel
        if ancestor.exists() and path.read_bytes() == ancestor.read_bytes(): continue
        if not ancestor.exists() or current.read_bytes() == ancestor.read_bytes():
            current.parent.mkdir(parents=True, exist_ok=True); current.write_bytes(path.read_bytes()); status = 'replace_unchanged_parent'
        else:
            args = []
            for role, file in (('current', current), ('base', ancestor), ('incoming', path)):
                tmp = scratch/(rel.as_posix().replace('/', '__')+'.'+role)
                tmp.write_bytes(file.read_bytes().replace(b'\r\n', b'\n')); args.append(str(tmp))
            merged = subprocess.run(['git', 'merge-file', '--diff3', '-p', *args], capture_output=True)
            if merged.returncode < 0 or merged.returncode > 7: raise RuntimeError(merged.stderr.decode('utf8', errors='replace'))
            current.write_bytes(merged.stdout); status = 'merged' if merged.returncode == 0 else 'manual_conflict'
            if merged.returncode: conflicts.append({'path': rel.as_posix(), 'regions': merged.returncode})
        changed.append({'path': rel.as_posix(), 'status': status, 'source_sha256': sha(path), 'result_sha256': sha(current)})
    report = {'schema': 'ark-sim/feature-integration-second-pass/v1', 'passed': not conflicts, 'changes': changed, 'conflicts': conflicts,
        'wiring_unions': ['terrain + projectile imports', 'both pure provider registries retained'], 'formal_approval': False}
    (REPORT/'merge_second_pass.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'changed': len(changed), 'conflicts': conflicts}))


if __name__ == '__main__': main()
