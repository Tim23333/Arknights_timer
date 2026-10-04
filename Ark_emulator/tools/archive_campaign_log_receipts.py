"""Seal already verified campaign results before user-requested log deletion."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'validation/campaign/runthrough/archived_logs.receipts.v1.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    registry_path = ROOT / 'validation/campaign/runthrough/registry.json'
    progress_path = ROOT / 'validation/campaign/runthrough/register_06_16_source_v1/progress.json'
    registry = json.loads(registry_path.read_bytes())
    progress = json.loads(progress_path.read_bytes())
    assert progress['registry_sha256'] == sha(registry_path)
    assert progress['counts']['process_complete'] == 12
    prior = {row['native_id']: row for row in progress['cases']}
    rows = {}
    for key, entry in registry['cases'].items():
        evidence = prior[key]
        assert evidence['process_status'] == 'complete'
        assert evidence['determinism_status'] == evidence['durable_checkpoint_status'] == 'verified'
        report_path = ROOT / entry['report']
        report = json.loads(report_path.read_bytes())
        assert report['passed'] is True and report['process_complete'] is True
        assert report['checkpoint_equal'] is True and report['durable_checkpoint_equal'] is True and report['replay_equal'] is True
        assert report['identity_stable'] is True
        source_paths = {field: ROOT / entry[field] for field in ('package', 'parent_package', 'commands')}
        rows[key] = {'entry': entry, 'prior_verified_progress': evidence,
                     'report_sha': sha(report_path), 'source_sha': {field: sha(path) for field, path in source_paths.items()},
                     'implementation': report['implementation'], 'process_complete': True,
                     'durable_checkpoint_equal': True, 'replay_equal': True,
                     'journals_recorded_by_original_validation': {name: report.get(name) for name in
                         ('journal', 'continuation_journal', 'replayed_journal', 'checkpoint_sha256', 'checkpoint_event_reference')},
                     'log_retention': 'User requested deletion after completed validation; historical verification preserved, raw logs no longer available',
                     'live_journals_reverified_here': False, 'client_verified': False}
    assert len(rows) == 12
    value = {'schema': 'ark-sim/completed-log-archive/v1', 'registry_sha': sha(registry_path),
             'prior_progress_sha': sha(progress_path), 'cases': rows,
             'scope': 'Previously verified completed runs, pinned compact receipts and unchanged source inputs; not a fresh raw-journal verification'}
    assert not OUT.exists()
    OUT.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
    print(json.dumps({'archived_completed_cases': len(rows), 'sha': sha(OUT)}))


if __name__ == '__main__':
    main()
