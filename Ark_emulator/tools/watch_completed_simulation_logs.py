"""Clean protected legacy runs once their current worker process exits."""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.cleanup_simulation_logs import processes


def main():
    policy_path=ROOT/'tools/simulation_log_policy.json'
    policy=json.loads(policy_path.read_bytes())
    log_root=Path(policy['log_root'])
    initial=[row for row in processes() if 'run_campaign_disk_runthrough_v' in (row.get('CommandLine') or '')]
    remaining={row['ProcessId']:row for row in initial}
    note=log_root/'cleanup'/'legacy_watch_status.json'
    while remaining:
        alive={row['ProcessId'] for row in processes()}
        exited=[pid for pid in remaining if pid not in alive]
        if exited:
            for pid in exited:remaining.pop(pid)
            subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs.py'),
                            '--legacy','--apply','--minimum-age-minutes','0'],cwd=ROOT,check=True)
        note.write_text(json.dumps({'remaining_pids':list(remaining),'updated_utc':datetime.now(timezone.utc).isoformat(),
                                  'status':'watching' if remaining else 'complete'},indent=2)+'\n',encoding='utf8')
        if remaining:time.sleep(30)


if __name__=='__main__':main()
