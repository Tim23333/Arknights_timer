"""Authenticate archived completed forward/CP proof; run only missing head.

Default mode compiles and checks identities without creating a Simulation.
--execute requires the exact successful preflight receipt hash. Original raw
journals were deleted under the user policy; historical proof is reused openly.
"""
import argparse,hashlib,importlib.util,json,sys,gc,os,traceback
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=Path('E:/ArkSimLogs/receipts/paused_20261005/07_18_82db_finite_v3_pinned_public_v1_20261004T174311161028Z')
PRIOR=ARCHIVE/'result.checkpoint_result.json';REPLAY=ARCHIVE/'result.replay.json'
STOP=ROOT/'validation/campaign/paused_20261005/runs.stopped.json';CLOSE=ROOT/'validation/campaign/paused_20261005/closeout.json'
PINS={PRIOR:'d021462f31924b58f6a0b327ca71f75a02c31cc6974fa0cb358608df941a18e3',REPLAY:'2641134208063c5cff6d093da57acf48650ad445742a802f93063134fb4e1f62',STOP:'3f2b73e37bf14cebb0e7e3f1d6ef89d98bcb17adad6eaeefbcf223c0b9c59a04',CLOSE:'e7f2750e452b482f97b29ae24d07c6e25d4e70a19c69f07154e782f5541e26b1'}
CORE='82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'
OUTROOT=ROOT/'validation/campaign/chapter07_head_recovery_v21'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def write(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def authenticate():
    for p,h in PINS.items():
        if sha(p)!=h:raise ValueError('Pinned archived proof drift: '+str(p))
    d=load(PRIOR);stopped=load(STOP);close=load(CLOSE)
    run=next(r for r in stopped['runs'] if r['name']==ARCHIVE.name)
    saved={Path(r['saved']).name:r for r in run['saved_small_records']}
    for path,h in [(PRIOR,PINS[PRIOR]),(REPLAY,PINS[REPLAY])]:
        row=saved[path.name]
        if Path(row['saved']).resolve()!=path.resolve() or row['sha256']!=h or row['bytes']!=path.stat().st_size:raise ValueError('Archive copy not certified by pause receipt')
    if ARCHIVE.name not in close['stopped_run_names'] or stopped['direct_restore_available_after_cleanup'] is not False or close['cleanup']['remaining_files']!=0:raise ValueError('Missing explicit raw-deletion closeout')
    if not all(d[k] is True for k in ['process_complete','checkpoint_equal','durable_checkpoint_equal','driver_equal']):raise ValueError('Historical forward/CP proof incomplete')
    if set(d['observations'])!={'snapshot','events','event_count','continuation_state'} or d['observations']['event_count']!=7215116:raise ValueError('Incomplete original four-observation boundary')
    if d['journal']['sha256']!=d['continuation_journal']['sha256']:raise ValueError('Historical journal continuation hash differs')
    if d['checkpoint_sha256']!=saved['result.checkpoint.json']['sha256']:raise ValueError('Archived original checkpoint receipt mismatch')
    if any(Path(d[k]['path']).exists() for k in ['journal','continuation_journal']):raise ValueError('Historical raw unexpectedly exists; this mode only reuses certified archived proof')
    guards={str(p):sha(p) for p in PINS};guards[str(Path(__file__).resolve())]=sha(__file__)
    for path,h in d['source_at_start'].items():
        if sha(path)!=h:raise ValueError('Original source drift: '+path)
        guards[path]=h
    if len(d['source_at_start'])!=28:raise ValueError('Expected original complete28 source guard')
    runtime=Path(d['runtime_module']).resolve().parents[1];sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT))
    import ark_sim
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import _validated_record
    if Path(ark_sim.__file__).resolve().parent!=runtime/'ark_sim' or implementation_digest()!=CORE or d['implementation']!=CORE:raise ValueError('Frozen82 runtime import/core differs')
    package_path=next(Path(x) for x in d['source_at_start'] if 'native_draft' in x)
    provider_path=next(Path(x) for x in d['source_at_start'] if 'runner_' in Path(x).name and 'providers' in Path(x).name)
    helper_path=next(Path(x) for x in d['source_at_start'] if Path(x).name=='campaign_streaming_evidence_v14.py')
    providers=module('selected_v21_recovery_providers',provider_path).providers();helper=module('selected_v21_recovery_evidence',helper_path)
    package=load(package_path);scene=package['scenarioDraft'];life=scene['metadata']['runthrough_profile']['base_life_resource']
    if scene['resources'][life]['initial']!=99999 or scene['resources'][life]['capacity']!=99999:raise ValueError('Original base-only overlay differs')
    program=Compiler(providers=providers).compile(package)
    if program.fingerprint!=d['program']:raise ValueError('Actual compiled original program differs')
    record=_validated_record(program,load(REPLAY))
    if record['runtime_fingerprint']!=d['runtime'] or record['until']!=d['end_tick'] or record['seed']!=d['seed']:raise ValueError('Historical replay identity/end/seed differs')
    commands_path=next(Path(x) for x in d['source_at_start'] if Path(x).name=='commands.json')
    if sha(commands_path)!=d['commands_sha256']:raise ValueError('Original public command file drift')
    commands=load(commands_path)
    actions=sorted(record['commands'],key=lambda r:r['order']);ordinary=[r for r in actions if r['action'].get('action')!='control_ack']
    if [dict(c) for c in commands]!=[dict(r['action'],at=r['at']) for r in ordinary]:raise ValueError('Original public source commands/order differ')
    for item in d['driver_final']['submitted']:
        matches=[r for r in actions if r['action']=={'action':'control_ack','control':item['control'],'step':item['step']} and r['at']==item['at'] and r['submitted_at']==item['submitted_at']]
        if len(matches)!=1 or item['at']!=item['submitted_at']+1:raise ValueError('Original external driver ACK ledger differs')
    for mod in tuple(sys.modules.values()):
        path=getattr(mod,'__file__',None)
        if path:
            p=Path(path).resolve()
            if p.suffix=='.py' and (p.is_relative_to(ROOT/'tools') or p.is_relative_to(runtime/'ark_sim')):guards[str(p)]=sha(p)
    return d,program,providers,helper,record,guards
def preflight(path):
    if Path(path).exists():raise FileExistsError('Preserve prior preflight')
    try:d,program,providers,helper,record,guards=authenticate()
    except Exception as error:
        write(path,{'passed':False,'head_started':False,'simulation_created':False,'error':str(error),'traceback':traceback.format_exc()})
        raise
    report={'schema':'ark-sim/archived-missing-head-preflight/v21','passed':True,'historical_forward_CP_proof_reused':True,'historical_raw_deleted_cannot_be_fresh_read':True,'simulation_created':False,'head_started':False,'original_report_sha256':PINS[PRIOR],'archive_pins':{str(p):h for p,h in PINS.items()},'implementation':CORE,'program':program.fingerprint,'record_runtime':record['runtime_fingerprint'],'fresh_runtime_check_pending_until_execute':True,'original_source_count':28,'guards':guards,'target_observations':d['observations'],'commands':len(record['commands']),'public_ACKs':len(d['driver_final']['submitted']),'until':record['until'],'required_gate':'Root reviews this exact preflight SHA before execute; new complete head must match all4 original persisted observations. No new forward/CP.'}
    write(path,report);print(json.dumps({'passed':True,'head_started':False,'preflight':str(path),'sha256':sha(path)}))
def execute(args):
    if not args.preflight or not args.preflight_sha or sha(args.preflight)!=args.preflight_sha:raise ValueError('Exact authenticated preflight required')
    pf=load(args.preflight)
    if pf['passed'] is not True or pf['head_started'] is not False:raise ValueError('Incomplete preflight')
    for p,h in pf['guards'].items():
        if sha(p)!=h:raise ValueError('Preflight source drift: '+p)
    run=Path(os.environ['ARKSIM_RUN_DIR']).resolve()
    if not run.is_relative_to(Path('E:/ArkSimLogs/runs').resolve()) or not (run/'run.lease.json').exists():raise ValueError('Managed fixed E run and real lease required')
    if not args.output or args.output.exists() or not args.output.resolve().is_relative_to(OUTROOT.resolve()):raise ValueError('New compact output within V21 validation required')
    d,program,providers,helper,record,guards=authenticate()
    from ark_sim import Engine
    from ark_sim.adapters.api import implementation_digest
    result={'schema':'ark-sim/archived-forward-new-head-recovery/v21','passed':False,'historical_forward_CP_proof_reused':True,'historical_raw_deleted_cannot_be_fresh_read':True,'preflight':str(args.preflight),'preflight_sha256':args.preflight_sha,'original_report':str(PRIOR),'original_report_sha256':PINS[PRIOR],'historical_observations':d['observations'],'head_terminated':False,'source_at_start':guards}
    try:
        sim=Engine.create(program,providers=providers,seed=record['seed'],random_algorithm=record['random_algorithm'],event_journal_path=run/'head.active.jsonl')
        if sim.runtime_fingerprint!=d['runtime']:raise ValueError('Actual new head runtime fingerprint differs')
        ordered=sorted(record['commands'],key=lambda r:r['order']);cursor=0
        while sim.session.time<record['until']:
            while cursor<len(ordered) and ordered[cursor]['submitted_at']==sim.session.time:
                row=ordered[cursor];sim.submit(row['action'],at=row['at']);cursor+=1
            target=min(sim.session.time+100,record['until'])
            if cursor<len(ordered):target=min(target,ordered[cursor]['submitted_at'])
            if target<=sim.session.time:raise ValueError('Original submission cursor missed historical boundary')
            sim.session.advance(target-sim.session.time)
            state=sim.ctx.state();print(json.dumps({'phase':'new_head_only','tick':target,'kills':state['kills'],'leaks':state['leaks'],'pending':state['pending_waves'],'finished':state['finished']}),flush=True)
        while cursor<len(ordered) and ordered[cursor]['submitted_at']==sim.session.time:
            row=ordered[cursor];sim.submit(row['action'],at=row['at']);cursor+=1
        if cursor!=len(ordered):raise ValueError('Not all original commands submitted')
        actual=helper.observations(sim,run/'head.events.jsonl');observed={k:actual[k] for k in ('snapshot','events','event_count','continuation_state')}
        from tools.control_driver.public_ack_v2 import PublicAckDriver
        # The frozen driver validates a list of all7M events. Reconstruct the
        # same exact checkpoint with a streaming audit, without retaining the
        # complete event objects in RAM or inserting a new ACK command.
        waiting=[];responses=[];event_count=0
        for event in sim.session._events.iter_records():
            event_count+=1
            if event['type']=='control.awaiting_ack':waiting.append(event)
            if event['type'] in ('command.accepted','command.rejected'):responses.append(event)
        actual_submitted=[]
        for event in waiting:
            action={'action':'control_ack','control':event['payload']['control'],'step':event['payload']['step']}
            matches=[row for row in ordered if row['action']==action]
            if len(matches)!=1:raise ValueError('Actual awaited event has absent/ambiguous original ACK')
            row=matches[0]
            if row['submitted_at']<event['time'] or row['at']!=row['submitted_at']+1:raise ValueError('Actual ACK ordering/response clock differs')
            actual_submitted.append({'event':event['id'],'control':action['control'],'step':action['step'],'submitted_at':row['submitted_at'],'at':row['at']})
        actual_driver={'policy':PublicAckDriver.POLICY,'program':program.fingerprint,'runtime':sim.runtime_fingerprint,'at':sim.session.time,'cursor':event_count,'submitted':actual_submitted}
        driver_equal=actual_driver==d['driver_final']
        state=sim.ctx.state();expected=Counter(d['expected_births']);births=Counter(e['definition_id'] for e in sim.session.world.entities() if 'enemy' in e['tags'])
        after={p:sha(p) for p in guards};equal=observed==d['observations'];identity=after==guards and implementation_digest()==CORE
        result.update(head_terminated=True,new_head_observations=observed,all4_observations_equal=equal,full_driver_equal=driver_equal,actual_driver=actual_driver,public_command_outcomes_equal=responses==d['commands'],source_at_completion=after,identity_stable=identity,actual_head_export=actual['export'],head_wave_conservation=births==expected and state['kills']+state['leaks']==sum(expected.values()),head_state=state,actual_core=implementation_digest())
        result['passed']=equal and driver_equal and identity and result['head_wave_conservation'] and result['public_command_outcomes_equal'];del sim;gc.collect()
    except Exception as error:result.update(error=str(error),traceback=traceback.format_exc())
    write(args.output,result);print(json.dumps({'passed':result['passed'],'output':str(args.output)}),flush=True);return 0 if result['passed'] else 1
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--preflight-output',type=Path);parser.add_argument('--execute',action='store_true');parser.add_argument('--preflight',type=Path);parser.add_argument('--preflight-sha');parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.execute:return execute(args)
    if not args.preflight_output or not args.preflight_output.resolve().is_relative_to(OUTROOT.resolve()):raise ValueError('Explicit new V21 preflight output required')
    preflight(args.preflight_output);return 0
if __name__=='__main__':raise SystemExit(main())
