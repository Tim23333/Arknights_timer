"""Finish missing CP/replay proofs of a persisted complete original run."""
import argparse,gc,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.campaign_ordered_checkpoint import load_bound
from tools.campaign_streaming_evidence import observations,write_canonical


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--case',required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    args.output=args.output.resolve();runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime))
    import ark_sim
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    entry=json.loads((ROOT/'validation/campaign/runthrough/registry.json').read_bytes())['cases'][args.case]
    if Path(ark_sim.__file__).resolve().parent!=runtime/'ark_sim' or implementation_digest()!=entry['implementation']:raise ValueError('Wrong recovery runtime')
    original=args.output.with_suffix('.original.json');report=json.loads(original.read_bytes());original_sha=sha(original)
    if not report['process_complete'] or report['implementation']!=entry['implementation']:raise ValueError('Recovery requires an already complete original source process')
    original_start=report['source_at_start'];current={name:sha(name) for name in original_start}
    if current!=original_start:raise ValueError('Original source identity changed')
    package=ROOT/entry['package'];commands=ROOT/entry['commands']
    if sha(package)!=report['package_sha256'] or sha(commands)!=report['commands_sha256']:raise ValueError('Original input bytes changed')
    journal=Path(report['journal']['path']);journal=journal if journal.is_absolute() else ROOT/journal
    if sha(journal)!=report['journal']['sha256']:raise ValueError('Original complete journal bytes changed')
    guards=[Path(__file__),original,ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/campaign_streaming_evidence.py',args.output.with_suffix('.replay.json'),Path(report['checkpoint'])]
    before={str(p.resolve()):sha(p) for p in guards};start_core=implementation_digest()
    program=Compiler().compile(package)
    if program.fingerprint!=report['program']:raise ValueError('Recompiled original program differs')
    record=json.loads(args.output.with_suffix('.replay.json').read_bytes())
    checkpoint=load_bound(Path(report['checkpoint']),report['checkpoint_sha256'])
    print('Continuing saved original checkpoint under exact source identity...',flush=True)
    restored=None
    try:
        restored=Engine.restore(program,checkpoint)
        while restored.session.time<report['end_tick']:
            restored.advance(min(200,report['end_tick']-restored.session.time))
            print(json.dumps({'phase':'checkpoint_continuation','tick':restored.session.time,'target':report['end_tick'],'events':len(restored.session.events)}),flush=True)
        report['checkpoint_equal']=report['observations']==observations(restored)
        report['durable_checkpoint_equal']=report['checkpoint_equal'];report['checkpoint_error']=None
    except Exception as error:
        report['checkpoint_equal']=False;report['durable_checkpoint_equal']=False;report['checkpoint_error']={'phase':'recovery_durable_continuation','type':type(error).__name__,'message':str(error)}
    finally:del restored,checkpoint;gc.collect()
    report['recovery_checkpoint_source_start']=before
    write_canonical(args.output.with_suffix('.recovery.checkpoint_result.json'),report)
    if report['checkpoint_equal']:
        print('Replaying all recorded commands from original start...',flush=True)
        repeated=None
        try:
            repeated=replay(program,record);report['replay_equal']=report['observations']==observations(repeated);report['replay_error']=None
        except Exception as error:
            report['replay_equal']=False;report['replay_error']={'type':type(error).__name__,'message':str(error)}
        finally:del repeated;gc.collect()
    else:report['replay_equal']=False
    after={str(p.resolve()):sha(p) for p in guards};end_core=implementation_digest()
    report['source_at_completion']={name:sha(name) for name in original_start};report['core_at_completion']=end_core
    report['recovery']={'schema':'ark-sim/persisted-original-recovery/v1','original_report_sha256':original_sha,
        'source_at_start':before,'source_at_completion':after,'core_start':start_core,'core_end':end_core,
        'scope':'Original full journal/value hashes kept; missing proofs actually executed under original program/core'}
    report['identity_stable']=original_start==report['source_at_completion'] and before==after and end_core==start_core==entry['implementation']
    report['passed']=bool(report['process_complete'] and report['identity_stable'] and report['checkpoint_equal'] and report['replay_equal'])
    write_canonical(args.output,report);print(json.dumps({'passed':report['passed'],'checkpoint_equal':report['checkpoint_equal'],'replay_equal':report['replay_equal']}),flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
