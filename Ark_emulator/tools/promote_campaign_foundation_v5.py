"""Promote the combined foundation only after its own full/base/peer gates."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT.parent / 'unpack_work/campaign_campaign_foundation_v5_candidate'
OLD = '71d33fa18662ae4f19c326988448e4dbb2764e503eec7bf3058e63c6a1182be2'
NEW = '82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'
EVIDENCE = ROOT / 'validation/campaign/campaign_foundation_v5'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(path):
    return {file.relative_to(path).as_posix(): sha(file) for file in path.rglob('*')
            if file.is_file() and file.suffix in ('.py', '.json')}


def core(path):
    return subprocess.check_output([sys.executable, '-c',
        'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',
        str(path)], cwd=path, text=True).strip()


def verify_pins(pins):
    for name, checksum in pins.items():
        assert sha(name) == checksum, name


def main():
    assert core(ROOT) == OLD and core(CANDIDATE) == NEW
    suite_path = EVIDENCE / 'full_suite/verification.json'
    suite = json.loads(suite_path.read_bytes())
    assert suite['passed'] and suite['core'] == NEW and suite['exitcode'] == 0
    assert suite['identity_stable'] and suite['guards_start'] == suite['guards_end']
    assert len(suite['cases']) == 1219 and not suite['collection_skips']
    assert all(case['outcome'] == 'passed' for case in suite['cases'])
    assert suite['all_other_1218_expectations_unchanged']
    assert all(Path(name).is_relative_to(CANDIDATE / 'ark_sim') for name in suite['actual_modules'].values())
    verify_pins(suite['guards_end'])
    baseline_path = EVIDENCE / 'baseline/verification.identity.json'
    assert sha(baseline_path) == 'bf12f8cf247813ba5f3f519d749e4ac27c40e6b362c7b534f11897873b562fd5'
    baseline = json.loads(baseline_path.read_bytes())
    assert baseline['passed'] and baseline['exit_code'] == 0 and baseline['identity_stable']
    assert baseline['implementation_sha256'] == NEW
    assert baseline['source_at_start'] == baseline['source_at_completion']
    verify_pins(baseline['source_at_completion'])
    peer_path = ROOT / 'validation/campaign/chapter08_foundation_independent_final_v1/freeze.json'
    assert sha(peer_path) == 'f28ba53e08df3a7d0fc8bbce970195398b4a0152b92e48d90afe80d2610af732'
    peer = json.loads(peer_path.read_bytes())
    assert peer['status'] == 'passed' and peer['actual_exit'] == 0 and peer['core'] == NEW
    assert peer['independent_unique_cases'] == 20 and peer['paired_fullvalue_context_cache_keyorder_cases'] == 3
    assert peer['no_author_fixture_import'] and peer['no_candidate_primary_source_mutation']
    verify_pins(peer['pins'])
    merge_path = EVIDENCE / 'merge.json'
    assert sha(merge_path) == '22396ee94fcd4f24b47010ccd186ceb27654088cfcfc6cc2696688b275f42856'
    merge = json.loads(merge_path.read_bytes())
    assert merge['core'] == NEW
    before, after = inventory(ROOT / 'ark_sim'), inventory(CANDIDATE / 'ark_sim')
    assert set(before) == set(after) and len(after) == 101
    assert {('ark_sim/' + key): value for key, value in after.items()} == merge['files']
    changes = {name for name in after if before[name] != after[name]}
    assert changes == {'kernel/world.py', 'kernel/session.py', 'kernel/transaction.py',
                       'domains/context.py', 'domains/lifecycle.py', 'domains/timeline.py'}
    backup = ROOT.parent / 'unpack_work/primary_71d_before_foundation_v5'
    output = ROOT / 'validation/campaign/campaign_foundation_v5_primary/promotion.json'
    assert not backup.exists() and not output.exists()
    shutil.copytree(ROOT / 'ark_sim', backup / 'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    assert inventory(backup / 'ark_sim') == before and core(backup) == OLD
    for name in sorted(changes):
        shutil.copyfile(CANDIDATE / 'ark_sim' / name, ROOT / 'ark_sim' / name)
    assert inventory(ROOT / 'ark_sim') == after and core(ROOT) == NEW
    output.parent.mkdir(parents=True)
    output.write_bytes((json.dumps({'passed': True, 'primary_before': OLD, 'primary_after': NEW,
        'changes': sorted(changes), 'before': before, 'after': after, 'backup': str(backup),
        'own_suite_sha': sha(suite_path), 'own_baseline_sha': sha(baseline_path),
        'independent_peer_sha': sha(peer_path), 'merge_sha': sha(merge_path),
        'all101files_equal_to_candidate': True,
        'scope': 'Trusted transaction World forks, exact cached leaf semantics, source opt-in wave tracking and reaction atomic rollback; no old stage result identity migration.'},
        ensure_ascii=False, indent=2) + '\n').encode('utf8'))
    print(json.dumps({'passed': True, 'core': NEW, 'promotion_sha': sha(output)}))


if __name__ == '__main__':
    main()
