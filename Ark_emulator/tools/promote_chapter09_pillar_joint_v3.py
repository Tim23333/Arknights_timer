"""Promote verified finite zero-health ownership and optional-context repair."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT.parent / 'unpack_work/campaign_c9_pillar_channel_joint_v3_candidate'
OLD = 'f0c2944cc89788b9277cbafe55ba1d9dcbdfe1e2f29c3619ce3fd1da9a6b7e9c'
NEW = '4d42e2b6cf646ebe2291d695f82d968e5d4669217069a37bcc8b2babb850f7a4'


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def core(p):
    return subprocess.check_output([sys.executable, '-c',
        'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',
        str(p.resolve())], cwd=ROOT, text=True).strip()


def inventory(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*')
            if p.is_file() and p.suffix in ('.py', '.json') and 'validation' not in p.relative_to(root).parts}


def pins(rows):
    for name, expected in rows.items(): assert sha(name) == expected, name


def read(relative, expected):
    path = ROOT / relative; assert sha(path) == expected, relative
    return path, json.loads(path.read_bytes())


def main():
    assert core(ROOT) == OLD and core(CANDIDATE) == NEW
    full_path, full = read('validation/campaign/chapter09_pillar_channel_joint_v3/full.107.json',
        '9d59dc5c684095e92315edc01487a6dfcf278f62d76c619b692ff153174711b4')
    assert full['passed'] and full['exitcode'] == 0 and full['core'] == NEW and full['identity_stable']
    assert len(full['cases']) == 1219 and all(x['outcome'] == 'passed' for x in full['cases'])
    assert not full['collection_skips'] and full['all_other_1218_expectations_unchanged']
    assert full['guards_start'] == full['guards_end']; pins(full['guards_end'])
    assert all(Path(path).is_relative_to(CANDIDATE / 'ark_sim') for path in full['actual_modules'].values())
    baseline_path, baseline = read('validation/campaign/chapter09_pillar_channel_joint_v3/baseline/verification.identity.json',
        '4eafd2e87316bcae0981074b9a4fdaab3ef267231b0eb9f7d1c3e3fa19ca146c')
    assert baseline['passed'] and baseline['exit_code'] == 0 and baseline['identity_stable']
    assert baseline['implementation_sha256'] == NEW
    assert baseline['source_at_start'] == baseline['source_at_completion']; pins(baseline['source_at_completion'])
    peer_path, peer = read('validation/campaign/chapter09_depletion_peer_joint_v3/peer.result.v3.json',
        'a9b9e26e5db45f278d93417fa48d0f14bed9dc5bb1ab7e63b1c169f551acf33e')
    assert peer['core'] == NEW and peer['passed'] == 40 and peer['failed'] == 0
    assert peer['source_test_begin_end_guards_equal'] and peer['source_current_guard_equal']
    assert peer['full_checkpoint_strict_equal'] and peer['CPP_head_scenarios'] == 20
    assert all(x['actual_exit'] == 0 and x['failed'] == 0 for x in peer['actual_runs'])
    for row in peer['source_inventory']: assert sha(CANDIDATE / row['path']) == row['candidate_sha256']
    pins(peer['helpers'])
    assert peer['cleanup']['remaining_files'] == peer['cleanup']['error_count'] == 0
    own = []
    for name, count in [('clock_map.author.json', 25), ('author.initial.json', 12), ('author.regression.json', 10),
                        ('author.context.json', 2), ('author.restore.json', 5), ('domain46.json', 46)]:
        path = ROOT / 'validation/campaign/chapter09_pillar_channel_joint_v3' / name
        report = json.loads(path.read_bytes()); assert report['actual_exit'] == 0
        assert (report.get('core') or report['core_before']) == NEW
        assert len(report.get('cases', report.get('results', []))) == count
        own.append({'path': str(path), 'sha': sha(path), 'cases': count})
    before = inventory(ROOT / 'ark_sim'); after = inventory(CANDIDATE / 'ark_sim')
    assert not set(before) - set(after)
    changes = [name for name in after if before.get(name) != after[name]]
    backup = ROOT.parent / 'unpack_work/primary_f0c_before_chapter09_pillar_joint_v3'
    output = ROOT / 'validation/campaign/chapter09_pillar_primary_v3/promotion.json'
    assert not backup.exists() and not output.exists()
    shutil.copytree(ROOT / 'ark_sim', backup / 'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    assert inventory(backup / 'ark_sim') == before and core(backup) == OLD
    for relative in changes:
        destination = ROOT / 'ark_sim' / relative; destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CANDIDATE / 'ark_sim' / relative, destination)
    assert inventory(ROOT / 'ark_sim') == after and core(ROOT) == NEW
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps({'passed': True, 'primary_before': OLD, 'primary_after': NEW,
        'changed_files': changes, 'before': before, 'after': after, 'backup': str(backup),
        'own_full_sha': sha(full_path), 'own_baseline_sha': sha(baseline_path), 'fresh_peer_sha': sha(peer_path),
        'own_short_reports': own, 'scope': 'Finite zero-health owner stages/callbacks and real owned tile casts, restored lineage, optional-context compatibility and absent-feature permission rejection',
        'old53ee_full_failure_preserved': True, 'cross_catalog_equivalence_failure_preserved': True,
        'historical_stage_receipts_not_migrated': True, 'positive_health_damage_trigger_candidate_promoted': False,
        'source_inventory_excludes_validation_logs': True, 'existing_compact_validation_reports_preserved': True,
        'whole_campaign_complete': False, 'client_verified': False}, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': True, 'core': NEW, 'changed_files': len(changes), 'promotion_sha': sha(output)}))


if __name__ == '__main__': main()
