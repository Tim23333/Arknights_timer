"""Merge frozen M24 decisions and M25 eligibility on their M23 ancestor."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT.parent/'unpack_work'
OUT = WORK/'campaign_m26_decision_eligibility_candidate'
REPORT = ROOT/'validation/campaign/m26_integration'
SOURCES = {
    'base': (WORK/'campaign_m23_roster_candidate', '0258f171d31daffb7b917e2ebad2603505e5fa762e99ef4a71b3b30342d62381'),
    'decision': (WORK/'campaign_m24_enemy_fsm_candidate', 'c4fc6cb000208e2518c9bf55b742773c1276fc87bdca8241b58a95bd11e80f22'),
    'eligibility': (WORK/'campaign_m25_eligibility_candidate', '281dc1fc3fc35e83adad37146b2bfb16afa92c5086f29fc22e881f116eb80ace'),
}


def core(path):
    code = 'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable, '-c', code, str(path)], cwd=path, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for path, pin in SOURCES.values():
        if core(path) != pin:
            raise ValueError('Frozen source core drift: '+str(path))
    if OUT.exists() or OUT.parent.resolve() != WORK.resolve():
        raise ValueError('A fresh named integration candidate is required')
    shutil.copytree(SOURCES['decision'][0]/'ark_sim', OUT/'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    # The baseline loader reads this one offline JSON. No V1 Python is copied.
    baseline = SOURCES['base'][0]/'ark_emulator/levels/packs/level_main_00-01.json'
    if not baseline.exists():
        raise ValueError('Offline baseline JSON is required')
    dest = OUT/'ark_emulator/levels/packs/level_main_00-01.json'; dest.parent.mkdir(parents=True); shutil.copyfile(baseline, dest)
    REPORT.mkdir(parents=True, exist_ok=True)
    changes, conflicts = [], []
    incoming, base = SOURCES['eligibility'][0]/'ark_sim', SOURCES['base'][0]/'ark_sim'
    for path in sorted(p for p in incoming.rglob('*') if p.is_file() and p.suffix in ('.py', '.json')):
        relative = path.relative_to(incoming); ancestor = base/relative; current = OUT/'ark_sim'/relative
        if ancestor.exists() and path.read_bytes() == ancestor.read_bytes():
            continue
        if not ancestor.exists():
            if current.exists() and current.read_bytes() != path.read_bytes():
                raise ValueError('New file collision '+str(relative))
            current.parent.mkdir(parents=True, exist_ok=True); current.write_bytes(path.read_bytes()); status = 'new'
        elif current.read_bytes() == ancestor.read_bytes():
            current.write_bytes(path.read_bytes()); status = 'replace_unchanged_parent'
        else:
            scratch = REPORT/'merge_inputs'; scratch.mkdir(exist_ok=True); normalized = []
            for role, file in (('current', current), ('base', ancestor), ('incoming', path)):
                temporary = scratch/(relative.as_posix().replace('/', '__')+'.'+role)
                temporary.write_bytes(file.read_bytes().replace(b'\r\n', b'\n')); normalized.append(str(temporary))
            result = subprocess.run(['git', 'merge-file', '--diff3', '-p', *normalized], capture_output=True)
            if result.returncode not in range(8):
                raise RuntimeError(result.stderr.decode('utf8', errors='replace'))
            current.write_bytes(result.stdout); status = 'merged' if result.returncode == 0 else 'manual_conflict'
            if result.returncode:
                conflicts.append({'path': relative.as_posix(), 'regions': result.returncode})
        changes.append({'path': relative.as_posix(), 'status': status, 'incoming_sha256': sha(path),
                        'base_sha256': sha(ancestor) if ancestor.exists() else None, 'result_sha256': sha(current)})
    report = {'schema': 'ark-sim/decision-eligibility-merge/v1', 'source_cores': {k:p for k,(_,p) in SOURCES.items()},
              'candidate': str(OUT), 'changes': changes, 'conflicts': conflicts, 'runnable': False, 'formal_approved': False}
    (REPORT/'merge_initial.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'files': len(changes), 'conflicts': conflicts, 'candidate': str(OUT)}))


if __name__ == '__main__':
    main()
