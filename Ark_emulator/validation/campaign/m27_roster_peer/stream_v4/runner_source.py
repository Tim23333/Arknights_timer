"""Full life99999 process and replay with streaming evidence export.

V4 also preserves explicit failure reports for durable continuation errors.
V3 additionally preserves and re-loads durable checkpoint insertion order.
V2 binds actual decoded input bytes once; old running helpers remain frozen.
This new runner preserves full canonical
snapshot/event hashes, adds complete continuation-state comparison and saves
the full event journal as JSONL without expanding all payloads together.
"""
import argparse
from collections import Counter
import gc
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.campaign_streaming_evidence import observations,export_events,write_canonical
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-root','package','commands','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--expected-core',required=True);parser.add_argument('--max-ticks',type=int,default=30000)
    parser.add_argument('--checkpoint-at',type=int,default=700);parser.add_argument('--no-replay',action='store_true')
    args=parser.parse_args();runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime))
    import ark_sim
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw
    from ark_sim.tools.replay import replay
    if Path(ark_sim.__file__).resolve().parent!=runtime/'ark_sim' or implementation_digest()!=args.expected_core:
        raise ValueError('Wrong explicit streaming runtime')
    helper=ROOT/'tools/campaign_streaming_evidence.py'
    guarded=[Path(__file__),helper,ROOT/'tools/campaign_ordered_checkpoint.py',args.package,args.commands,runtime/'ark_sim/rules/contracts.json',runtime/'ark_sim/content/presets/ark_standard.json']
    package_bytes=args.package.read_bytes();command_bytes=args.commands.read_bytes()
    actual_inputs={str(args.package.resolve()):hashlib.sha256(package_bytes).hexdigest(),
                   str(args.commands.resolve()):hashlib.sha256(command_bytes).hexdigest()}
    before={str(p.resolve()):actual_inputs[str(p.resolve())] if str(p.resolve()) in actual_inputs else sha(p) for p in guarded}
    package=json.loads(package_bytes);commands=json.loads(command_bytes);scene=package['scenarioDraft']
    profile=scene['metadata']['runthrough_profile'];life=profile['base_life_resource']
    if scene['resources'][life]['initial']!=99999 or scene['resources'][life]['capacity']!=99999:raise ValueError('Life99999 required')
    program=Compiler().compile(package);sim=Engine.create(program,seed=scene['seed']);expected=Counter()
    for wave in scene['timeline']['waves']:
        for fragment in wave['fragments']:
            for action in fragment['actions']:
                if action['kind']=='spawn':expected[action['spawn']['definition']]+=action.get('count',1)
    for command in commands:
        action=dict(command);tick=action.pop('at');sim.submit(action,at=tick)
    checkpoint=None;checkpoint_error=None;checkpoint_sha=None;checkpoint_path=args.output.with_suffix('.checkpoint.json')
    while sim.session.time<args.max_ticks and not sim.ctx.state()['finished']:
        target=min(sim.session.time+100,args.max_ticks)
        if checkpoint is None and sim.session.time<args.checkpoint_at<=target:target=args.checkpoint_at
        sim.advance(target-sim.session.time)
        if checkpoint is None and sim.session.time==args.checkpoint_at:
            # Keep only the bounded checkpoint prefix in memory; save it for
            # review/recovery. No event is dropped from the active simulation.
            checkpoint=sim.checkpoint();checkpoint_sha=write_ordered(checkpoint_path,checkpoint)
            # Resume proof uses this exact durable byte sequence, not the
            # unsaved in-memory checkpoint with a different key order.
            try:checkpoint=load_bound(checkpoint_path,checkpoint_sha)
            except Exception as error:
                checkpoint=False
                checkpoint_error={'phase':'initial_durable_read','type':type(error).__name__,'message':str(error)}
        state=sim.ctx.state();print(json.dumps({'tick':sim.session.time,'kills':state['kills'],'leaks':state['leaks'],
            'pending':state['pending_waves'],'life':sim.ctx.resources.current('system/battle',life),'finished':state['finished']}),flush=True)
    state=sim.ctx.state();end=sim.session.time
    actual=Counter(e['definition_id'] for e in sim.session.world.entities() if 'enemy' in e['tags'])
    complete=bool(state['finished'] and state['pending_waves']==0 and state['timeline']['phase']=='complete'
        and actual==expected and state['kills']+state['leaks']==sum(expected.values())
        and not any(sim.ctx.alive(e['id']) for e in sim.session.world.entities() if 'enemy' in e['tags']))
    report={'schema':'ark-sim/campaign-runthrough/v1','process_complete':complete,'passed':False,
        'actual_game_accuracy_verified':False,'accuracy_status':'Declared model; native comparison remains pending',
        'implementation':args.expected_core,'runtime_module':ark_sim.__file__,'program':program.fingerprint,'runtime':sim.runtime_fingerprint,
        'package_sha256':actual_inputs[str(args.package.resolve())],'commands_sha256':actual_inputs[str(args.commands.resolve())],
        'decoded_input_sha256':actual_inputs,'profile':profile,'seed':scene['seed'],'end_tick':end,
        'state':state,'base_life_final':sim.ctx.resources.current('system/battle',life),'expected_births':dict(expected),'actual_births':dict(actual),
        'commands':[thaw(e) for e in sim.session.events if e['type'] in ('command.accepted','command.rejected')],
        'final_entities':[{'id':e['id'],'definition':e['definition_id'],'alive':sim.ctx.alive(e['id']),
            'resources':{key:data['current'] for key,data in e['components'].get('resources',{}).items()},
            'position':thaw(e['components'].get('spatial',{}).get('position'))} for e in sim.session.world.entities()],
        'checkpoint_equal':None,'replay_equal':None,'formal_approved':False,
        'pending_model_gaps':package['manifest']['metadata'].get('pending_model_gaps',[]),'source_at_start':before,
        'evidence_format':'canonical-stream-v1; all full events retained','checkpoint':str(checkpoint_path) if checkpoint is not None else None,
        'checkpoint_sha256':checkpoint_sha,'checkpoint_encoding':'insertion-order JSON; loaded from actual saved bytes',
        'durable_checkpoint_equal':None,'checkpoint_error':checkpoint_error,'replay_error':None}
    print('Hashing full original state and events...',flush=True);report['observations']=observations(sim)
    print('Exporting complete original event journal...',flush=True);report['journal']=export_events(args.output.with_suffix('.events.jsonl'),sim)
    record=sim.export_replay();write_canonical(args.output.with_suffix('.replay.json'),record)
    write_canonical(args.output.with_suffix('.original.json'),report)
    del sim;gc.collect()
    if complete and not args.no_replay:
        print('Checking complete checkpoint continuation...',flush=True)
        restored=None
        try:
            if checkpoint is None:raise ValueError('Explicit checkpoint not reached')
            if checkpoint_error is not None:raise ValueError('Initial durable checkpoint read failed: '+checkpoint_error['message'])
            checkpoint=load_bound(checkpoint_path,checkpoint_sha)
            restored=Engine.restore(program,checkpoint);restored.advance(end-restored.session.time)
            report['checkpoint_equal']=report['observations']==observations(restored)
            report['durable_checkpoint_equal']=report['checkpoint_equal']
        except Exception as error:
            report['checkpoint_equal']=False;report['durable_checkpoint_equal']=False
            report['checkpoint_error']={'phase':'durable_continuation','type':type(error).__name__,'message':str(error)}
        finally:
            del restored,checkpoint;gc.collect()
        write_canonical(args.output.with_suffix('.checkpoint_result.json'),report)
        print('Checking complete recorded-command replay...',flush=True)
        replayed=None
        try:
            replayed=replay(program,record);report['replay_equal']=report['observations']==observations(replayed)
        except Exception as error:
            report['replay_equal']=False;report['replay_error']={'type':type(error).__name__,'message':str(error)}
        finally:del replayed;gc.collect()
    after={str(p.resolve()):sha(p) for p in guarded};report['source_at_completion']=after
    report['identity_stable']=before==after and implementation_digest()==args.expected_core
    report['passed']=bool(complete and report['identity_stable'] and (args.no_replay or report['checkpoint_equal'] and report['replay_equal']))
    write_canonical(args.output,report)
    print(json.dumps({'process_complete':complete,'passed':report['passed'],'kills':state['kills'],'leaks':state['leaks'],
        'checkpoint_equal':report['checkpoint_equal'],'replay_equal':report['replay_equal'],'actual_game_accuracy_verified':False}),flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
