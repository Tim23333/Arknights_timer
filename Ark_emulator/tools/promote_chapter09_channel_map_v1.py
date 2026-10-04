"""Promote the exact joined clock/map core only after its own complete gates."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT.parent / 'unpack_work/campaign_c9_channel_map_v1_candidate'
OLD = '56f380fab9715b8edcb589b2c3fc3863d740cb149ab31e19b3f6fe3a1720fcf6'
NEW = 'f0c2944cc89788b9277cbafe55ba1d9dcbdfe1e2f29c3619ce3fd1da9a6b7e9c'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def core(path):
    return subprocess.check_output([sys.executable, '-c',
        'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',
        str(path.resolve())], cwd=ROOT, text=True).strip()


def inventory(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in path.rglob('*')
            if p.is_file() and p.suffix in {'.py', '.json'}}


def pins(group):
    for name, value in group.items():
        assert sha(name) == value, name


def receipt(relative, expected):
    path = ROOT / relative
    assert sha(path) == expected, relative
    return path, json.loads(path.read_bytes())


def main():
    assert core(ROOT) == OLD and core(CANDIDATE) == NEW
    full_path, full = receipt('validation/campaign/chapter09_channel_map_v1/full.106.json',
        'c924481a92b700d75c1fec495fba49950bf518bbf6c3b5ebbf82ccf38563aec0')
    assert full['passed'] and full['exitcode'] == 0 and full['core'] == NEW and full['identity_stable']
    assert len(full['cases']) == 1219 and all(x['outcome'] == 'passed' for x in full['cases'])
    assert not full['collection_skips'] and full['all_other_1218_expectations_unchanged']
    assert full['guards_start'] == full['guards_end']; pins(full['guards_end'])
    assert all(Path(path).is_relative_to(CANDIDATE / 'ark_sim') for path in full['actual_modules'].values())
    baseline_path, baseline = receipt('validation/campaign/chapter09_channel_map_v1/baseline/verification.identity.json',
        'd861181002395a15de912027ac0e03ae2872e99925ef880a9c5193c373e1ee7d')
    assert baseline['passed'] and baseline['exit_code'] == 0 and baseline['identity_stable']
    assert baseline['implementation_sha256'] == NEW
    assert baseline['source_at_start'] == baseline['source_at_completion']; pins(baseline['source_at_completion'])
    author_path, author = receipt('validation/campaign/chapter09_channel_map_v1/author.json',
        'ab22aa3893134925608d1cc0e5f7367cc12bcef8d18d3ebab113d699716a16dd')
    assert author['passed'] and author['actual_exit'] == 0 and author['core'] == NEW and author['identity_stable']
    assert len(author['cases']) == 25 and author['guards_before'] == author['guards_after']; pins(author['guards_after'])
    peers = []
    for name, expected in [
        ('validation/campaign/chapter09_clock_peer_joined/peer.result.joined.json',
         '2f4082d9e6d13c6360c4ee2d3af519b6b2ad6e37ae0e3c74bdda61350f4d95d6'),
        ('validation/campaign/chapter09_cell_fields_peer_joined/peer.result.joined.json',
         'd6bcafb04580ba7a5e93895cc4f32d813240cc51784e4d33797b29aa2ed2e19a')]:
        path, peer = receipt(name, expected)
        assert peer['runtime'] == NEW and peer['fresh_pytest']['passed'] == 17
        assert peer['fresh_pytest']['failed'] == peer['fresh_pytest']['actual_exit'] == 0
        assert peer['full_state_tasks_RNG_events_cached_context_value_cause_equal_without_exclusions']
        assert peer['source_guard']['before_end_equal'] and peer['source_guard']['current_rechecked']
        pins(peer['source_guard']['hashes']); pins(peer['peer_files'])
        assert peer['cleanup']['remaining_CP_files'] == peer['cleanup']['error_count'] == 0
        peers.append({'path': str(path), 'sha256': sha(path)})
    envelope_path, envelope = receipt('validation/campaign/chapter09_cell_fields_peer_joined/nooptin.identity.envelope.json',
        '04d955a00fc3573d6b99f2da302503ed2ea1946c1c21201ec248850ca3571eb7')
    assert envelope['passed_identity_envelope_gate']
    assert set(envelope['all_checkpoint_difference_paths']) == {'$.program_fingerprint', '$.runtime_fingerprint'}
    assert envelope['all_complete_program_metadata_difference_paths'] == ['$.capabilities.effects']
    assert envelope['kernel_state_tasks_RNG_events_and_attribute_cache_exact_equal']
    assert envelope['cached_context_value_cause_not_removed']
    before, after = inventory(ROOT / 'ark_sim'), inventory(CANDIDATE / 'ark_sim')
    assert set(before) == set(after)
    changed = [name for name in after if before[name] != after[name]]
    assert len(changed) == 9
    backup = ROOT.parent / 'unpack_work/primary_56_before_chapter09_channel_map_v1'
    output = ROOT / 'validation/campaign/chapter09_channel_map_primary_v1/promotion.json'
    assert not backup.exists() and not output.exists()
    shutil.copytree(ROOT / 'ark_sim', backup / 'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    assert inventory(backup / 'ark_sim') == before and core(backup) == OLD
    for relative in changed:
        shutil.copyfile(CANDIDATE / 'ark_sim' / relative, ROOT / 'ark_sim' / relative)
    assert inventory(ROOT / 'ark_sim') == after and core(ROOT) == NEW
    output.parent.mkdir(parents=True)
    result = {'passed': True, 'primary_before': OLD, 'primary_after': NEW,
        'changed_files': changed, 'before': before, 'after': after, 'backup': str(backup),
        'own_full_sha': sha(full_path), 'own_baseline_sha': sha(baseline_path), 'own_author_sha': sha(author_path),
        'independent_peer_receipts': peers, 'independent_cases_in_single_batch': 17,
        'identity_envelope_sha': sha(envelope_path), 'historical_strict_identity_failure_preserved': True,
        'scope': 'Explicit per-cell native map operands and owned ability cooldown/interrupt protocols. No stage receipt identity migration.',
        'whole_campaign_complete': False, 'client_verified': False}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': True, 'core': NEW, 'changed_files': changed, 'promotion_sha': sha(output)}))


if __name__ == '__main__':
    main()
