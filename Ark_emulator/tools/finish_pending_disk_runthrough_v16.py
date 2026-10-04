"""Finish saved disk-run original receipts with independently resumable phases."""
import argparse,gc,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.run_campaign_disk_runthrough_v15 import sha,write,comparable


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--package',type=Path,required=True);ap.add_argument('--evidence-helper',type=Path,required=True);args=ap.parse_args()
    sys.path.insert(0,str(args.runtime_root.resolve()))
    import ark_sim
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    original_path=args.output.with_suffix('.original.json');original=json.loads(original_path.read_bytes())
    if not original['process_complete']:raise ValueError('Only actual completed originals can recover proofs')
    assert Path(ark_sim.__file__).resolve().parent==args.runtime_root.resolve()/'ark_sim' and implementation_digest()==original['implementation']
    for name,pin in original['source_at_start'].items():
        if sha(name)!=pin:raise ValueError('Original source changed: '+name)
    journal=original['journal'];assert sha(journal['path'])==journal['sha256']
    assert sha(args.package)==original['package_sha256']
    spec=importlib.util.spec_from_file_location('selected_disk_helper',args.evidence_helper);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    assert sha(args.evidence_helper)==original['source_at_start'][str(args.evidence_helper.resolve())]
    program=Compiler().compile(json.loads(args.package.read_bytes()));assert program.fingerprint==original['program']
    record=json.loads(args.output.with_suffix('.replay.json').read_bytes());report=dict(original);end=original['end_tick']
    guards=[Path(__file__),original_path,args.output.with_suffix('.replay.json'),Path(journal['path'])]
    before={str(p.resolve()):sha(p) for p in guards};report['recovery']={'helper':str(Path(__file__).resolve()),'source_start':before,'completed_phases':{}}
    for phase in ('continuation','replay'):
        checkpoint_path=args.output.with_suffix('.'+phase+'.terminal.checkpoint.json')
        metadata_path=args.output.with_suffix('.'+phase+'.terminal.metadata.json')
        observation_path=args.output.with_suffix('.'+phase+'.observation.json')
        sim=None
        try:
            if metadata_path.exists():
                metadata=json.loads(metadata_path.read_bytes());sim=Engine.restore(program,helper.load_checkpoint(metadata));assert sim.session.time==end
                print(json.dumps({'phase':phase,'restored_terminal':end}),flush=True)
            else:
                if phase=='continuation':
                    assert sha(original['checkpoint'])==original['checkpoint_sha256']
                    cp=json.loads(Path(original['checkpoint']).read_bytes());sim=Engine.restore(program,cp)
                else:
                    # Replay to the beginning only; all recorded public commands
                    # remain submitted at their exact original submission times.
                    start=dict(record);start['until']=0
                    if any(c.get('submitted_at',0)!=0 for c in record['commands']):raise ValueError('Phase runner requires original all-at-zero submissions')
                    sim=replay(program,start,event_journal_path=args.output.with_suffix('.'+phase+'.recovery.active.jsonl'))
                while sim.session.time<end:
                    sim.session.advance(min(200,end-sim.session.time))
                    print(json.dumps({'phase':phase,'tick':sim.session.time,'target':end,'events':len(sim.session._events._records)}),flush=True)
                metadata=helper.write_checkpoint(sim,checkpoint_path);write(metadata_path,metadata)
                print(json.dumps({'phase':phase,'terminal_checkpoint_saved':end}),flush=True)
            if observation_path.exists():
                observed=json.loads(observation_path.read_bytes())
                assert sha(observed['export']['path'])==observed['export']['sha256']
            else:
                observed=helper.observations(sim,args.output.with_suffix('.'+phase+'.recovery.events.jsonl'));write(observation_path,observed)
            same=comparable(observed)==original['observations']
            report['recovery']['completed_phases'][phase]={'equal':same,'observation':observed,'terminal_checkpoint':metadata}
            if phase=='continuation':report['checkpoint_equal']=report['durable_checkpoint_equal']=same;report['checkpoint_error']=None
            else:report['replay_equal']=same;report['replay_error']=None
        except Exception as caught:
            error={'type':type(caught).__name__,'message':str(caught)}
            if phase=='continuation':report['checkpoint_equal']=report['durable_checkpoint_equal']=False;report['checkpoint_error']=error
            else:report['replay_equal']=False;report['replay_error']=error
        finally:del sim;gc.collect()
        write(args.output.with_suffix('.recovery.'+phase+'.json'),report)
    after={str(p.resolve()):sha(p) for p in guards};report['recovery']['source_end']=after
    report['source_at_completion']={name:sha(name) for name in original['source_at_start']};report['core_at_completion']=implementation_digest()
    report['identity_stable']=original['source_at_start']==report['source_at_completion'] and before==after and implementation_digest()==original['implementation']
    report['passed']=report['checkpoint_equal'] and report['replay_equal'] and report['identity_stable']
    write(args.output,report);print(json.dumps({'passed':report['passed'],'checkpoint_equal':report['checkpoint_equal'],'replay_equal':report['replay_equal']}),flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
