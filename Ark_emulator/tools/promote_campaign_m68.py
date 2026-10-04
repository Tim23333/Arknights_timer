"""Publish reviewed M68 bytes into the primary V2 checkout, preserving M12."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT.parent / 'unpack_work/campaign_m68_deployment_integrated_candidate'
BACKUP = ROOT.parent / 'unpack_work/primary_m12_before_m68_promotion'
OUT = ROOT / 'validation/campaign/m68_primary'
OLD = 'bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11'
NEW = '1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root):
    return {str(p.relative_to(root)).replace('\\', '/'): sha(p)
            for p in sorted(root.rglob('*')) if p.is_file()
            and '__pycache__' not in p.parts and p.suffix in ('.py', '.json')}


def identity(root):
    code = "import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())"
    return subprocess.check_output([sys.executable, '-c', code, str(root)], cwd=root, text=True).strip()


def main():
    assert identity(ROOT) == OLD and identity(CANDIDATE) == NEW
    proofs = {'full_suite': OUT.parent/'m68_integration/full_suite_20261003.json',
              'independent_deployment': OUT.parent/'m68_roster_peer/final_review.json'}
    for path in proofs.values():
        report = json.loads(path.read_text(encoding='utf8'))
        assert report['passed'] and report['core_start'] == report['core_end'] == NEW
    assert sha(proofs['independent_deployment']) == 'd237c74d1b77c53d92e0ca1d7217489ae4d728536c7107236b8dbb972168f6bd'
    before, candidate = files(ROOT/'ark_sim'), files(CANDIDATE/'ark_sim')
    assert not (set(before)-set(candidate)), 'Unexpected primary files require manual review'
    assert not BACKUP.exists(), 'Preserved backup already exists; inspect before retry'
    shutil.copytree(ROOT/'ark_sim', BACKUP/'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    assert files(BACKUP/'ark_sim') == before and identity(BACKUP) == OLD
    for name in candidate:
        destination = ROOT/'ark_sim'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CANDIDATE/'ark_sim'/name, destination)
    after = files(ROOT/'ark_sim')
    assert after == candidate and identity(ROOT) == NEW and identity(CANDIDATE) == NEW
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'passed': True, 'primary_before': OLD, 'primary_after': NEW,
              'backup': str(BACKUP), 'files_before': before, 'files_after': after,
              'candidate': str(CANDIDATE), 'proof_sha256': {k: sha(p) for k,p in proofs.items()},
              'scope': 'Byte-identical primary publication; old evidence keeps its original identity'}
    (OUT/'promotion.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'passed': True, 'core': NEW, 'files': len(after), 'backup': str(BACKUP)}))


if __name__ == '__main__':
    main()
