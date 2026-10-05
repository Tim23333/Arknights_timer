"""Clean existing campaign runs when their actual process identities exit."""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.cleanup_simulation_logs_v2 import FIXED_LOG_ROOT, pid_stamp, processes


def tracked_runs(rows):
    tracked = {}
    for row in rows:
        if 'run_campaign_disk_runthrough_v' not in (row.get('CommandLine') or ''):
            continue
        pid = row['ProcessId']
        stamp = pid_stamp(pid)
        if stamp is not None:
            tracked[pid] = stamp
    return tracked


def expired_runs(tracked):
    return [pid for pid, stamp in tracked.items() if pid_stamp(pid) != stamp]


def main():
    remaining = tracked_runs(processes())
    note = FIXED_LOG_ROOT / 'cleanup' / 'legacy_watch_status.json'
    note.parent.mkdir(parents=True, exist_ok=True)
    pending_cleanup = False
    last_cleanup_exit = None
    while True:
        exited = expired_runs(remaining)
        for pid in exited:
            remaining.pop(pid)
        pending_cleanup = pending_cleanup or bool(exited)
        if pending_cleanup:
            last_cleanup_exit = subprocess.call(
                [sys.executable, str(ROOT / 'tools/cleanup_simulation_logs_v2.py'),
                 '--legacy', '--apply', '--minimum-age-minutes', '0'], cwd=ROOT)
            pending_cleanup = last_cleanup_exit != 0
        status = 'cleanup_retry' if pending_cleanup else ('watching' if remaining else 'complete')
        value = {'schema': 'ark-sim/completed-run-watch/v2', 'watcher_pid': os.getpid(),
                 'watcher_stamp': pid_stamp(os.getpid()),
                 'remaining_runs': [{'pid': pid, 'stamp': stamp} for pid, stamp in remaining.items()],
                 'updated_utc': datetime.now(timezone.utc).isoformat(),
                 'status': status, 'last_cleanup_exit': last_cleanup_exit}
        temporary = note.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf8')
        temporary.replace(note)
        if not remaining and not pending_cleanup:
            return 0
        time.sleep(30)


if __name__ == '__main__':
    raise SystemExit(main())
