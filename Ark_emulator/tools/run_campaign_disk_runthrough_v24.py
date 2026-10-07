"""V23 bounded ACK simulation/CP/head with automatic cleanup V2."""
import re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.run_with_log_cleanup import new_run,environment,finish,compact_worker,sha,start_lease
from tools.cleanup_simulation_logs_v2 import FIXED_LOG_ROOT,classify
def main():
    arguments=sys.argv[1:]
    if '--help' in arguments or '-h' in arguments:
        print('V24 retains V23 arguments and guards. --output retains a bounded report; raw logs always use E:/ArkSimLogs/runs and cleanup V2 after success or failure.')
        return subprocess.call([sys.executable,str(ROOT/'tools/run_campaign_disk_runthrough_v23.py'),'--help'])
    try:index=arguments.index('--output')+1;requested=Path(arguments[index]).resolve()
    except (ValueError,IndexError):raise ValueError('Explicit --output compact report required')
    if requested.exists():raise FileExistsError(requested)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');label=re.sub(r'[^a-zA-Z0-9_-]','_',requested.parent.name+'_'+requested.stem)[:80]
    run_dir=new_run(FIXED_LOG_ROOT/'runs'/(label+'_'+stamp));worker_output=run_dir/'result.json';arguments[index]=str(worker_output)
    command=[sys.executable,str(ROOT/'tools/run_campaign_disk_runthrough_v23.py'),*arguments];code=1;error=None;reports=[];process=None
    try:
        process=subprocess.Popen(command,cwd=ROOT,env=environment(run_dir));start_lease(run_dir,process)
        try:code=process.wait()
        except BaseException:
            if process.poll() is None:process.terminate();process.wait()
            raise
        receipts=FIXED_LOG_ROOT/'receipts'/run_dir.name;receipts.mkdir(parents=True,exist_ok=True)
        for path in run_dir.glob('*.json'):
            if path.name=='run.lease.json':continue
            if classify(path,[run_dir]) is not None:continue
            if any(word in path.name for word in ('checkpoint','replay','progress','driver')) and not path.name.endswith('.checkpoint_result.json'):continue
            if path.stat().st_size>5*1024*1024:continue
            dest=receipts/path.name;compact_worker(path,dest);reports.append({'path':str(dest),'sha256':sha(dest)})
        if worker_output.exists():requested.parent.mkdir(parents=True,exist_ok=True);compact_worker(worker_output,requested)
    except BaseException as caught:error={'type':type(caught).__name__,'message':str(caught)}
    return finish(run_dir,code or (1 if error else 0),{'requested_compact_report':str(requested),'receipts':reports,'worker_error':error,'source_runner':'run_campaign_disk_runthrough_v23.py','raw_logs_available_for_future_replay':False},process)
if __name__=='__main__':raise SystemExit(main())
