"""Promote only after this exact core's full, baseline and two fresh peer gates."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT.parent / 'unpack_work/campaign_c9_foundation_v9_candidate'
OLD = '5c729384f50e078bd3d3ac9d211360b17bc486588770914efe92ef5b4e983826'
NEW = '56f380fab9715b8edcb589b2c3fc3863d740cb149ab31e19b3f6fe3a1720fcf6'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def core(path):
    return subprocess.check_output([sys.executable, '-c',
        'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',
        str(path.resolve())], cwd=ROOT, text=True).strip()


def inventory(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in path.rglob('*')
            if p.is_file() and p.suffix in {'.py', '.json'}}


def pins(group, base=None):
    for name, value in group.items():
        path = Path(name) if base is None else base / name
        assert sha(path) == value, str(path)


def main():
    assert core(ROOT) == OLD and core(CANDIDATE) == NEW
    full_path = ROOT / 'validation/campaign/chapter09_foundation_v9/full.106.v9.json'
    assert sha(full_path) == 'cbb948b3ead6babbc980485bda3f41ad143b3c1f33050ad8e72f20d41fc49685'
    full = json.loads(full_path.read_bytes())
    assert full['passed'] and full['exitcode'] == 0 and full['identity_stable'] and full['core'] == NEW
    assert len(full['cases']) == 1219 and not full['collection_skips'] and all(r['outcome'] == 'passed' for r in full['cases'])
    assert full['guards_start'] == full['guards_end'] and full['all_other_1218_expectations_unchanged']
    pins(full['guards_end'])
    assert all(Path(p).is_relative_to(CANDIDATE / 'ark_sim') for p in full['actual_modules'].values())
    baseline_path = ROOT / 'validation/campaign/chapter09_foundation_v9/baseline/verification.identity.json'
    assert sha(baseline_path) == '6e78b51cb1aff71f996d5fb89ca1d77d1d1adfa7deb4fac38c5849691d6e131e'
    baseline = json.loads(baseline_path.read_bytes())
    assert baseline['passed'] and baseline['exit_code'] == 0 and baseline['identity_stable'] and baseline['implementation_sha256'] == NEW
    assert baseline['source_at_start'] == baseline['source_at_completion']; pins(baseline['source_at_completion'])
    content_path = ROOT / 'validation/campaign/chapter09_content_peer_v9/peer.result.v9.json'
    assert sha(content_path) == '50e68afbc6a063b2bbfca73ef73557a321ebce3b32d609639431d6d4197677c8'
    content = json.loads(content_path.read_bytes())
    assert content['runtime'] == NEW and content['fresh_tests']['total_passed'] == 27 and content['fresh_tests']['total_failed'] == 0
    assert content['source_guard']['start_end_equal']; pins(content['source_guard']['source_hashes']); pins(content['peer_files'])
    peer_path = ROOT / 'validation/campaign/chapter09_joint_peer_v9/peer.result.v9.json'
    assert sha(peer_path) == 'aa1d4e17e0d8639a8c8672af73933ee5b495ff31010de9cde8008b0256fb374f'
    peer = json.loads(peer_path.read_bytes())
    assert peer['runtime'] == NEW and peer['fresh_tests']['passed'] == 45 and peer['fresh_tests']['failed'] == 0
    assert peer['verdict'] == 'passed_same45_fresh_generic_gate' and peer['source_guard']['start_end_equal']
    pins(peer['source_guard']['hashes'], CANDIDATE)
    pins(peer['peer_file_locks'])
    before = inventory(ROOT / 'ark_sim'); after = inventory(CANDIDATE / 'ark_sim')
    assert not set(before) - set(after), 'Candidate cannot silently delete source files'
    changed = [k for k in after if before.get(k) != after[k]]
    backup = ROOT.parent / 'unpack_work/primary_5c_before_chapter09_foundation_v9'
    output = ROOT / 'validation/campaign/chapter09_foundation_primary_v9/promotion.json'
    assert not backup.exists() and not output.exists()
    shutil.copytree(ROOT / 'ark_sim', backup / 'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    assert inventory(backup / 'ark_sim') == before and core(backup) == OLD
    for rel in changed:
        dest = ROOT / 'ark_sim' / rel; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CANDIDATE / 'ark_sim' / rel, dest)
    assert inventory(ROOT / 'ark_sim') == after and core(ROOT) == NEW
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps({'passed': True, 'primary_before': OLD, 'primary_after': NEW,
        'changed_files': changed, 'before': before, 'after': after, 'backup': str(backup),
        'own_full_sha': sha(full_path), 'own_baseline_sha': sha(baseline_path),
        'content_peer_sha': sha(content_path), 'generic_peer_sha': sha(peer_path),
        'scope': 'Generic elemental resources, causal cache rollback, linked clocks, optional invisibility and real depletion-source rebirth skip. Old stage receipts retain their runtime identity.',
        'whole_campaign_complete': False}, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': True, 'core': NEW, 'promotion_sha': sha(output)}))


if __name__ == '__main__': main()
