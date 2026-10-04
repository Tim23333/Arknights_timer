"""Run frozen simulation/CP/head in the fixed log root, then remove raw logs."""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    policy = json.loads((ROOT/'tools/simulation_log_policy.json').read_bytes())
    log_root = Path(policy['log_root']).resolve()
    arguments = sys.argv[1:]
    if '--help' in arguments or '-h' in arguments:
        print('V19 uses all V18 arguments; --output selects the retained compact report.\n'
              'Raw simulation/CP/head files always live under '+str(log_root/'runs')+' and are cleaned after completion.\n'
              'Failure logs are also cleaned; compact report and worker exit remain retained.')
        raise SystemExit(subprocess.call([sys.executable,str(ROOT/'tools/run_campaign_disk_runthrough_v18.py'),'--help']))
    try:
        output_index = arguments.index('--output') + 1
        requested = Path(arguments[output_index]).resolve()
    except (ValueError, IndexError):
        raise ValueError('An explicit --output compact report is required')
    if requested.exists():
        raise FileExistsError(requested)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    label = re.sub(r'[^a-zA-Z0-9_-]', '_', requested.parent.name+'_'+requested.stem)[:80]
    run_dir = log_root/'runs'/(label+'_'+stamp)
    run_dir.mkdir(parents=True,exist_ok=False)
    worker_output = run_dir/'result.json'
    arguments[output_index] = str(worker_output)
    command=[sys.executable,str(ROOT/'tools/run_campaign_disk_runthrough_v18.py'),*arguments]
    # The wrapper preserves the original simulation helper and source guards.
    # Cleanup starts only after the child and both validation passes exit.
    process = subprocess.Popen(command,cwd=ROOT)
    code = process.wait()
    receipts = log_root/'receipts'/run_dir.name
    receipts.mkdir(parents=True)
    import shutil,hashlib
    report_files=[]
    for path in run_dir.glob('*.json'):
        if any(word in path.name for word in ('checkpoint','replay','progress','driver')):
            if not path.name.endswith('.checkpoint_result.json'):
                continue
        if path.stat().st_size > 5*1024*1024:
            continue
        dest=receipts/path.name
        shutil.copyfile(path,dest)
        report_files.append({'path':str(dest),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
    if worker_output.exists():
        requested.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(worker_output,requested)
    completion={'worker_exit':code,'run_directory':str(run_dir),'requested_compact_report':str(requested),
                'receipts':report_files,'raw_logs_removed_after_validation':False,
                'raw_logs_available_for_future_replay':False,'source_runner':'run_campaign_disk_runthrough_v18.py'}
    marker=receipts/'completion.json'
    marker.write_text(json.dumps(completion,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    cleanup=subprocess.call([sys.executable,str(ROOT/'tools/cleanup_simulation_logs.py'),
        '--run-dir',str(run_dir),'--apply','--minimum-age-minutes','0','--completed-pid',str(process.pid)],cwd=ROOT)
    completion['cleanup_exit']=cleanup
    completion['raw_logs_removed_after_validation']=cleanup==0
    marker.write_text(json.dumps(completion,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'worker_exit':code,'cleanup_exit':cleanup,'compact_report':str(requested),
                      'log_root':str(log_root),'receipt':str(marker)},ensure_ascii=False))
    raise SystemExit(code if code else cleanup)


if __name__=='__main__':
    main()
