"""Recover completed legacy forward runs through public segmented execution.

Original reports/journals remain immutable. Each completed proof phase is saved
before the next phase; no legacy Simulation.advance full-history snapshot.
"""
import argparse,gc,hashlib,json,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.campaign_ordered_checkpoint import load_bound
from tools.campaign_streaming_evidence import observations,write_canonical
from tools.finish_pending_runthrough_v17 import segmented_replay
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def absolute(path):
    p=Path(path);return p if p.is_absolute() else ROOT/p
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True)
    ap.add_argument('--case',required=True);ap.add_argument('--original',type=Path,required=True)
    ap.add_argument('--record',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--step',type=int,default=200);args=ap.parse_args();assert args.step>0
    sys.path.insert(0,str(args.runtime_root.resolve()))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    import ark_sim
    original=json.loads(args.original.read_bytes());registry=ROOT/'validation/campaign/runthrough/registry.json'
    entry=json.loads(registry.read_bytes())['cases'][args.case]
    assert original['process_complete'] and original['implementation']==entry['implementation']==implementation_digest()
    assert Path(ark_sim.__file__).resolve().parent==args.runtime_root.resolve()/'ark_sim'
    assert {p:sha(p) for p in original['source_at_start']}==original['source_at_start']
    assert sha(ROOT/entry['package'])==original['package_sha256'] and sha(ROOT/entry['commands'])==original['commands_sha256']
    checkpoint=absolute(original['checkpoint']);assert sha(checkpoint)==original['checkpoint_sha256']
    journal=absolute(original['journal']['path']);assert sha(journal)==original['journal']['sha256']
    program=Compiler().compile(ROOT/entry['package']);assert program.fingerprint==original['program']
    record=json.loads(args.record.read_bytes());assert record['until']==original['end_tick'] and record['runtime_fingerprint']==original['runtime'] and record['seed']==original['seed']
    guards=[Path(__file__),args.original,args.record,checkpoint,registry,ROOT/'tools/campaign_streaming_evidence.py',
        ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/finish_pending_runthrough_v17.py']
    before={str(p.resolve()):sha(p) for p in guards};report=dict(original);started=time.monotonic()
    def progress(sim,phase):
        print(json.dumps({'phase':phase,'tick':sim.session.time,'target':original['end_tick'],
            'events':len(sim.session.events),'elapsed_seconds':round(time.monotonic()-started,2)}),flush=True)
    for phase in ('continuation','replay'):
        receipt=args.output.with_suffix('.'+phase+'.json');sim=None
        try:
            if receipt.exists():
                saved=json.loads(receipt.read_bytes());assert saved['original_sha']==sha(args.original) and saved['core']==entry['implementation'] and saved['source_guards']==before
                observed=saved['observations'];assert observed==original['observations']
            else:
                if phase=='continuation':
                    sim=Engine.restore(program,load_bound(checkpoint,original['checkpoint_sha256']))
                    while sim.session.time<original['end_tick']:
                        sim.session.advance(min(args.step,original['end_tick']-sim.session.time));progress(sim,phase)
                else:sim=segmented_replay(program,record,args.step,lambda s:progress(s,phase))
                assert sim.session.time==original['end_tick'];observed=observations(sim)
                assert observed==original['observations']
                saved={'original_sha':sha(args.original),'core':entry['implementation'],'source_guards':before,
                    'observations':observed,'equal':True,'phase':phase}
                with receipt.open('x',encoding='utf8') as f:json.dump(saved,f,separators=(',',':'))
            if phase=='continuation':report.update(checkpoint_equal=True,durable_checkpoint_equal=True,checkpoint_error=None)
            else:report.update(replay_equal=True,replay_error=None)
        except Exception as error:
            details={'phase':phase,'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()}
            if phase=='continuation':report.update(checkpoint_equal=False,durable_checkpoint_equal=False,checkpoint_error=details)
            else:report.update(replay_equal=False,replay_error=details)
            report['passed']=False;write_canonical(args.output,report);raise
        finally:del sim;gc.collect()
    after={str(p.resolve()):sha(p) for p in guards};report['source_at_completion']={p:sha(p) for p in original['source_at_start']}
    report['core_at_completion']=implementation_digest();report['identity_stable']=before==after and report['source_at_completion']==original['source_at_start'] and implementation_digest()==entry['implementation']
    report['recovery']={'schema':'ark-sim/legacy-segmented-recovery/v20','original':str(args.original),'original_sha256':sha(args.original),
        'source_start':before,'source_end':after,'elapsed_seconds':time.monotonic()-started}
    report['passed']=bool(report['checkpoint_equal'] and report['replay_equal'] and report['identity_stable']);write_canonical(args.output,report)
    print(json.dumps({'passed':report['passed'],'checkpoint_equal':report['checkpoint_equal'],'replay_equal':report['replay_equal']}),flush=True)
    raise SystemExit(0 if report['passed'] else 1)
if __name__=='__main__':main()
