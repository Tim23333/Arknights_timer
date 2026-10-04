"""Promote ownfullytested leaf read/write without changing combat semantics."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT.parent / 'unpack_work/campaign_projectile_leaf_v1_candidate'
OLD = '20e8126120668fece832e8b6e23fd53a68fb013656a4476b5ad8e53850f6dd30'
NEW = '71d33fa18662ae4f19c326988448e4dbb2764e503eec7bf3058e63c6a1182be2'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(root):
    return {path.relative_to(root).as_posix(): sha(path) for path in root.rglob('*')
            if path.is_file() and path.suffix in ('.py', '.json')}


def core(root):
    return subprocess.check_output([sys.executable, '-c',
        'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',
        str(root)], cwd=root, text=True).strip()


def bound(path, expected):
    assert sha(path) == expected, str(path)
    return json.loads(path.read_bytes())


def pins(values):
    for name, checksum in values.items():
        assert sha(name) == checksum, name


def main():
    assert core(ROOT) == OLD and core(CAND) == NEW
    suite_path = ROOT / 'validation/campaign/chapter08_projectile_leaf_v1/full_suite/verification.json'
    suite = bound(suite_path, 'b2c2941ad83a35eb1599e2962e0f20ee41699f2c33620d9b544cc68b79441655')
    assert suite['passed'] and suite['core'] == NEW and suite['exitcode'] == 0 and suite['identity_stable']
    assert len(suite['cases']) == 1219 and not suite['collection_skips'] and all(case['outcome'] == 'passed' for case in suite['cases'])
    assert suite['guards_start'] == suite['guards_end'] and suite['all_other_1218_expectations_unchanged']
    pins(suite['guards_end'])
    assert all(Path(name).is_relative_to(CAND / 'ark_sim') for name in suite['actual_modules'].values())
    baseline_path = ROOT / 'validation/campaign/chapter08_projectile_leaf_v1/baseline/verification.identity.json'
    baseline = bound(baseline_path, 'ea164ee6274f6cde9102413a96f56837c951d60e495bbc87c383c5de73e5a6ae')
    assert baseline['passed'] and baseline['exit_code'] == 0 and baseline['implementation_sha256'] == NEW and baseline['identity_stable']
    assert baseline['source_at_start'] == baseline['source_at_completion']
    pins(baseline['source_at_completion'])
    peer_path = ROOT / 'validation/campaign/chapter08_projectile_leaf_independent_comparison_v2/freeze.json'
    peer = bound(peer_path, 'cd0a1f575b5c0943b5555aaf25d0b89c0017358c83be74f4d639b1d4900d48ce')
    assert peer['passed'] and peer['candidate_core'] == NEW and peer['parent_core'] == OLD and peer['guards_equal']
    assert peer['candidate_unique_checks'] == 4 and peer['paired_common_checks'] == 3
    assert peer['all_context_value_and_dict_orders_exact'] and peer['checked_nodes'] == 152981
    assert peer['candidate_guards_start'] == peer['candidate_guards_end'] and peer['parent_guards_start'] == peer['parent_guards_end']
    pins(peer['artifact_pins'])
    pins(peer['candidate_guards_end'])
    pins(peer['parent_guards_end'])
    before, after = inventory(ROOT / 'ark_sim'), inventory(CAND / 'ark_sim')
    assert set(before) == set(after) and len(after) == 101
    changes = {name for name, value in after.items() if before[name] != value}
    assert changes == {'kernel/world.py', 'domains/projectiles.py'}
    out = ROOT / 'validation/campaign/chapter08_projectile_leaf_v1_primary'
    backup = ROOT.parent / 'unpack_work/primary_20e_before_projectile_leaf_v1'
    assert not out.exists() and not backup.exists()
    shutil.copytree(ROOT / 'ark_sim', backup / 'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    assert inventory(backup / 'ark_sim') == before and core(backup) == OLD
    for name in changes:
        shutil.copyfile(CAND / 'ark_sim' / name, ROOT / 'ark_sim' / name)
    assert inventory(ROOT / 'ark_sim') == after and core(ROOT) == NEW
    out.mkdir()
    target = out / 'promotion.json'
    target.write_text(json.dumps({'passed': True, 'primary_before': OLD, 'primary_after': NEW,
        'changes': sorted(changes), 'before': before, 'after': after, 'backup': str(backup),
        'own_suite_sha': sha(suite_path), 'baseline_identity_sha': sha(baseline_path), 'peer_freeze_sha': sha(peer_path),
        'scope': 'Leafreadonly/projectilewrite optimization; exact comparison no numeric/context/order changes. WaveTrack independent candidate remains isolated.',
        'all101files_equal_to_candidate': True}, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'core': NEW, 'passed': True, 'promotion_sha': sha(target)}))


if __name__ == '__main__':
    main()
