"""Three-way integrate frozen features into a new checkout, retaining conflicts."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT.parent/'unpack_work'
OUT = WORK/'campaign_m21_integration_candidate'
REPORT = ROOT/'validation/campaign/m21_integration'
SOURCES = {
    'portal': (WORK/'campaign_m18_portal_candidate', '283ed55d0aaab3b9d6aaeb4806209182b5b6bb746882d52403ba9ef124a3d999'),
    'projectile': (WORK/'campaign_m17_projectile_candidate', 'b964bef82bbc9f6a05cad76740e81030dc9b3d72e82641c3b809d65fb2df875e'),
    'dormant': (WORK/'campaign_m20_dormant_source_candidate', 'b506ee18e7137c3658f1fe8ce77b4b612bf48bceb9b02446f2dfcb7d91abbf0d'),
    'projectile_parent': (WORK/'campaign_m15_category_candidate', 'f98a638812a18a01d10505dadd48b01de410ac27e992230881bc01c4f9a993b9'),
    'dormant_parent': (WORK/'campaign_m16_terrain_candidate', '669982006a81507973d8f3c3abb1f694d7ee9831de67ad2de1c0b3ea441df571'),
}


def core(path):
    code = 'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable, '-c', code, str(path)], cwd=path, text=True).strip()


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for path, pin in SOURCES.values():
        if core(path) != pin: raise ValueError('frozen feature source drift: '+str(path))
    if OUT.exists() or OUT.parent.resolve() != WORK.resolve(): raise ValueError('fresh named integration candidate required')
    shutil.copytree(SOURCES['portal'][0]/'ark_sim', OUT/'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    REPORT.mkdir(parents=True, exist_ok=True); changes = []; conflicts = []
    for feature, parent in (('projectile', 'projectile_parent'), ('dormant', 'dormant_parent')):
        incoming, base = SOURCES[feature][0]/'ark_sim', SOURCES[parent][0]/'ark_sim'
        files = sorted(p for p in incoming.rglob('*') if p.is_file() and p.suffix in ('.py', '.json'))
        for path in files:
            relative = path.relative_to(incoming); ancestor = base/relative; current = OUT/'ark_sim'/relative
            if ancestor.exists() and path.read_bytes() == ancestor.read_bytes(): continue
            if not ancestor.exists():
                if current.exists() and current.read_bytes() != path.read_bytes(): raise ValueError('new file collision '+str(relative))
                current.parent.mkdir(parents=True, exist_ok=True); current.write_bytes(path.read_bytes()); status = 'new'
            elif current.read_bytes() == ancestor.read_bytes():
                current.write_bytes(path.read_bytes()); status = 'replace_unchanged_parent'
            else:
                scratch = REPORT/'merge_inputs'; scratch.mkdir(exist_ok=True)
                normalized = []
                for role, file in (('current', current), ('base', ancestor), ('incoming', path)):
                    temporary = scratch/(feature+'_'+relative.as_posix().replace('/', '__')+'.'+role)
                    temporary.write_bytes(file.read_bytes().replace(b'\r\n', b'\n')); normalized.append(str(temporary))
                result = subprocess.run(['git', 'merge-file', '--diff3', '-p', *normalized], capture_output=True)
                if result.returncode not in (0, 1, 2, 3, 4, 5, 6, 7):
                    raise RuntimeError(result.stderr.decode('utf8', errors='replace'))
                current.write_bytes(result.stdout); status = 'merged' if result.returncode == 0 else 'manual_conflict'
                if result.returncode: conflicts.append({'feature': feature, 'path': relative.as_posix(), 'conflict_regions': result.returncode})
            changes.append({'feature': feature, 'path': relative.as_posix(), 'status': status,
                'incoming_sha256': sha(path), 'base_sha256': sha(ancestor) if ancestor.exists() else None, 'result_sha256': sha(current)})
        # Resolve one feature completely before applying another feature that
        # touches the same files. An unresolved candidate is not a runtime.
        if conflicts: break
    report = {'schema': 'ark-sim/feature-three-way-integration/v1', 'source_cores': {k: p for k, (_, p) in SOURCES.items()},
        'candidate': str(OUT), 'changes': changes, 'conflicts': conflicts, 'runnable': False, 'formal_approved': False}
    (REPORT/'merge_initial.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'files': len(changes), 'conflicts': conflicts, 'candidate': str(OUT)}))


if __name__ == '__main__': main()
