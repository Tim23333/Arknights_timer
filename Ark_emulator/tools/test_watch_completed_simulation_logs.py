"""Actual process identity and cleanup failure handling for old run completion."""
import json
from tools import watch_completed_simulation_logs as watch


def test_reused_pid_is_an_exit_and_other_processes_are_not_tracked(monkeypatch):
    stamps = {11: 100, 12: 200, 13: None}
    monkeypatch.setattr(watch, 'pid_stamp', lambda pid: stamps.get(pid))
    rows = [{'ProcessId': 11, 'CommandLine': 'python run_campaign_disk_runthrough_v19.py'},
            {'ProcessId': 12, 'CommandLine': 'python unrelated.py'},
            {'ProcessId': 13, 'CommandLine': 'python run_campaign_disk_runthrough_v20.py'}]
    tracked = watch.tracked_runs(rows)
    assert tracked == {11: 100}
    assert not watch.expired_runs(tracked)
    stamps[11] = 300
    assert watch.expired_runs(tracked) == [11]


def test_exit_runs_v2_and_retries_failed_cleanup_before_completion(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, 'FIXED_LOG_ROOT', tmp_path)
    monkeypatch.setattr(watch, 'processes', lambda: [])
    monkeypatch.setattr(watch, 'tracked_runs', lambda rows: {11: 100})
    monkeypatch.setattr(watch, 'expired_runs', lambda rows: list(rows))
    monkeypatch.setattr(watch, 'pid_stamp', lambda pid: 777)
    calls = []
    exits = iter([2, 0])
    def cleaning(command, cwd):
        calls.append(command)
        return next(exits)
    monkeypatch.setattr(watch.subprocess, 'call', cleaning)
    statuses = []
    monkeypatch.setattr(watch.time, 'sleep', lambda seconds: statuses.append(
        json.loads((tmp_path / 'cleanup/legacy_watch_status.json').read_bytes())['status']))
    assert watch.main() == 0
    assert statuses == ['cleanup_retry'] and len(calls) == 2
    assert all('cleanup_simulation_logs_v2.py' in command[1] for command in calls)
    assert all(command[-2:] == ['--minimum-age-minutes', '0'] for command in calls)
    final = json.loads((tmp_path / 'cleanup/legacy_watch_status.json').read_bytes())
    assert final['status'] == 'complete' and final['last_cleanup_exit'] == 0
    assert final['remaining_runs'] == []
