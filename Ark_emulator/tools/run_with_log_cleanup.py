"""Run a command in NEW fixed logs; {run_dir} arguments and environment are set."""
import argparse,hashlib,json,os,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.cleanup_simulation_logs_v2 import FIXED_LOG_ROOT,linked,root_fields,pid_stamp
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8');tmp.replace(path)
def new_run(path):
    policy=json.loads((ROOT/'tools/simulation_log_policy.json').read_bytes())
    if Path(policy['log_root']).resolve()!=FIXED_LOG_ROOT:raise ValueError('Log policy must use fixed E:/ArkSimLogs')
    path=Path(path).absolute()
    if linked(path) or not path.resolve().is_relative_to(FIXED_LOG_ROOT/'runs') or path.resolve()==FIXED_LOG_ROOT/'runs':raise ValueError('NEW child directory inside E:/ArkSimLogs/runs required')
    path.mkdir(parents=True,exist_ok=False);return path.resolve()
def environment(run_dir):return {**os.environ,'ARKSIM_RUN_DIR':str(run_dir),'TMP':str(run_dir),'TEMP':str(run_dir)}
def compact_worker(source,destination):
    source=Path(source);destination=Path(destination)
    if source.stat().st_size<=1024*1024:destination.write_bytes(source.read_bytes());return
    keep={'schema','passed','process_complete','checkpoint_equal','durable_checkpoint_equal','replay_equal','identity_stable','driver_equal','implementation','program','runtime','package_sha256','commands_sha256','providers_module_sha256','seed','end_tick','base_life_final','accuracy_status','actual_game_accuracy_verified'}
    with source.open('rb') as f:prefix=f.read(65536).decode('utf8',errors='replace')
    result={}
    for key,start in root_fields(prefix):
        if key not in keep:continue
        try:value,_=json.JSONDecoder().raw_decode(prefix,start+len(prefix[start:])-len(prefix[start:].lstrip()))
        except ValueError:continue
        if isinstance(value,(str,int,float,bool,type(None))):result[key]=value
    result.update(original_bytes=source.stat().st_size,original_sha256=sha(source),bounded_summary=True);save(destination,result)
def start_lease(run_dir,process):save(run_dir/'run.lease.json',{'worker_pid':process.pid,'worker_stamp':pid_stamp(process.pid),'completed':False})
def finish(run_dir,worker_exit,metadata=None,process=None):
    receipts=FIXED_LOG_ROOT/'receipts'/run_dir.name;receipts.mkdir(parents=True,exist_ok=True);marker=receipts/'completion.json';result_path=receipts/'cleanup.result.json'
    record={'schema':'ark-sim/run-completion/v2','worker_exit':worker_exit,'run_directory':str(run_dir),'updated_utc':datetime.now(timezone.utc).isoformat(),'raw_logs_removed_after_validation':False,**(metadata or {})};save(marker,record)
    cleanup_exit=2
    if process is not None and process.poll() is None:
        record.update(cleanup_exit=3,cleanup_error='Worker still alive: cleanup deferred');cleanup_exit=3
    else:
        lease=run_dir/'run.lease.json'
        if lease.exists():save(lease,{'completed':True})
        try:
            cleaning=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs_v2.py'),'--run-dir',str(run_dir),'--apply','--minimum-age-minutes','0','--completed-pid',str(os.getpid()),'--result-json',str(result_path)],cwd=ROOT,capture_output=True,text=True,encoding='utf8')
            result=json.loads(result_path.read_bytes()) if result_path.exists() else None
            valid=(isinstance(result,dict) and result.get('actual_exit')==cleaning.returncode==0 and result.get('apply') is True and result.get('error_count')==0 and result.get('remaining_files')==0 and result.get('protected_files')==0 and result.get('fully_cleaned') is True)
            cleanup_exit=cleaning.returncode or (0 if valid else 3);record.update(cleanup_exit=cleanup_exit,cleanup_result=result,raw_logs_removed_after_validation=valid)
            if not valid:record['cleanup_error']='Cleanup failed or retained raw files; see cleanup result'
        except Exception as error:record.update(cleanup_exit=2,cleanup_error=str(error))
    save(marker,record);print(json.dumps({'worker_exit':worker_exit,'cleanup_exit':cleanup_exit,'raw_logs_removed':record['raw_logs_removed_after_validation'],'receipt':str(marker)},ensure_ascii=False));return worker_exit if worker_exit else cleanup_exit
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-dir',type=Path,required=True);parser.add_argument('command',nargs=argparse.REMAINDER);args=parser.parse_args()
    command=args.command[1:] if args.command and args.command[0]=='--' else args.command
    if not command:parser.error('Command after -- required')
    run_dir=new_run(args.run_dir);command=[a.replace('{run_dir}',str(run_dir)) for a in command];code=1;error=None;process=None
    try:
        with (run_dir/'stdout.log').open('wb') as output,(run_dir/'stderr.log').open('wb') as errors:
            process=subprocess.Popen(command,cwd=ROOT,env=environment(run_dir),stdout=output,stderr=errors);start_lease(run_dir,process)
            try:code=process.wait()
            except BaseException:
                if process.poll() is None:process.terminate();process.wait()
                raise
    except BaseException as caught:error={'type':type(caught).__name__,'message':str(caught)}
    return finish(run_dir,code,{'command':command,'worker_error':error,'source_inputs_preserved':True},process)
if __name__=='__main__':raise SystemExit(main())
