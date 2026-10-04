"""Publish the frozen, independently reviewed generic chapter-five V2 core."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT.parent / 'unpack_work/campaign_chapter05_complete_v3_candidate'
BACKUP = ROOT.parent / 'unpack_work/primary_frost_v5_before_chapter05_v3_promotion'
OUT = ROOT / 'validation/campaign/chapter05_v3_primary'
OLD = '7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90'
NEW = '8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'
PINS = {
    'freeze': ('validation/campaign/chapter05_complete_v1/freeze_v3.json', '2cc6c4e2184329c6bdd49c309fa8c6fe65af461a21ae3ccbc6847bc016202890'),
    'suite': ('validation/campaign/chapter05_complete_v1/full_v3.json', '81e68c99b4fde2723cca3df28a07f02006a8fce1561081ae23ed196dddcd0be5'),
    'baseline_guard': ('validation/campaign/chapter05_complete_v1/baseline_v3_guard.json', 'a656233ad8e7c829a5038640a651970dc674a8515ad83a5a1c49770fb75d42a6'),
    'source_chain': ('validation/campaign/chapter05_complete_v1/source_chain_disk_v3.json', 'a94a4a3b42cdb743f280751dd6a3a06f27fd4d05366c8e270e6e0f6d48d8e9aa'),
    'independent_join': ('validation/campaign/c5_joint_source_independent_v2/verification.json', '077b67cea980332a6cc86bcb54e3694359bbcff45f62ee4acdffb9e39e0ca92c'),
    'independent_stages': ('validation/campaign/c5_joint_source_independent_v2/stage_verified.json', 'ee1288cdb5184a9f33ca505b40ab15ef0c679d6a7cf57f9e490d7d2c1c9de8ac'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py', '.json'}}


def identity(root):
    code = 'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable, '-c', code, str(root)], cwd=root, text=True).strip()


def verify_guards(values):
    for path, pin in values.items():
        assert sha(Path(path)) == pin, path


def main():
    assert identity(ROOT) == OLD and identity(CANDIDATE) == NEW
    proofs = {}
    for name, (path, pin) in PINS.items():
        assert sha(ROOT / path) == pin, name
        proofs[name] = json.loads((ROOT / path).read_bytes())
    freeze = proofs['freeze']
    assert freeze['parent_core'] == OLD and freeze['core'] == NEW
    for path, pin in freeze['receipts'].items():
        assert sha(ROOT / path) == pin, path
    suite = proofs['suite']
    assert suite['core'] == NEW and suite['exitcode'] == 0
    assert len(suite['cases']) == 1219 and all(c['outcome'] == 'passed' for c in suite['cases'])
    assert suite['guards_start'] == suite['guards_end']
    verify_guards(suite['guards_end'])
    assert all(Path(p).is_relative_to(CANDIDATE / 'ark_sim') for p in suite['actual_modules'].values())
    baseline_guard = proofs['baseline_guard']
    assert baseline_guard['core'] == NEW and baseline_guard['exitcode'] == 0
    verify_guards(baseline_guard['guards'])
    baseline_path = ROOT / 'validation/campaign/chapter05_complete_v1/baseline_v3.json'
    assert sha(baseline_path) == baseline_guard['baseline_sha']
    baseline = json.loads(baseline_path.read_bytes())
    assert baseline['passed'] and baseline['level_00_01']['final_state']['kills'] == 11
    assert all(v['replay_equal'] and v['damage'] == v['expected'] for v in baseline['custom_rulesets'].values())
    chain = proofs['source_chain']
    assert chain['core'] == NEW and chain['exitcode'] == 0 and all(c['outcome'] == 'passed' for c in chain['cases'])
    joined = proofs['independent_join']
    assert joined['core'] == NEW and joined['guards_equal']
    assert joined['guards_before'] == joined['guards_after']
    verify_guards(joined['guards_after'])
    assert len(joined['results']) == 3 and all(c['passed'] for c in joined['results'])
    stages = proofs['independent_stages']['results']
    assert len(stages) == 2 and all(c['passed'] for c in stages)
    before, candidate = files(ROOT / 'ark_sim'), files(CANDIDATE / 'ark_sim')
    assert not set(before) - set(candidate), 'Unexpected primary-only files'
    changes = {name for name in candidate if before.get(name) != candidate[name]}
    frozen = {str(Path(name)).replace('\\', '/').removeprefix('ark_sim/'): row for name, row in freeze['files'].items()}
    assert changes == set(frozen) and len(changes) == 16
    for name, row in frozen.items():
        assert before.get(name) == row['parent_sha'] and candidate[name] == row['sha'], name
        assert sha(ROOT / 'validation/campaign/chapter05_complete_v1/source_files_v3/ark_sim' / name) == row['sha']
    assert not BACKUP.exists() and not (OUT / 'promotion.json').exists()
    shutil.copytree(ROOT / 'ark_sim', BACKUP / 'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    assert files(BACKUP / 'ark_sim') == before and identity(BACKUP) == OLD
    for name in sorted(changes):
        destination = ROOT / 'ark_sim' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CANDIDATE / 'ark_sim' / name, destination)
    assert files(ROOT / 'ark_sim') == candidate and identity(ROOT) == identity(CANDIDATE) == NEW
    OUT.mkdir(parents=True, exist_ok=True)
    receipt = OUT / 'promotion.json'
    with receipt.open('x', encoding='utf8') as f:
        json.dump({'passed': True, 'primary_before': OLD, 'primary_after': NEW, 'backup': str(BACKUP),
                   'files_before': before, 'files_after': candidate, 'changed_files': sorted(changes),
                   'proof_pins': PINS, 'suite_passed': 1219,
                   'scope': 'Exact frozen generic core publication; whole-stage and client approvals remain separate'}, f, indent=2)
    print(json.dumps({'passed': True, 'core': NEW, 'files': len(candidate), 'changed': len(changes), 'receipt_sha': sha(receipt)}))


if __name__ == '__main__':
    main()
