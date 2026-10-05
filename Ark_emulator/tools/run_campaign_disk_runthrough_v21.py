"""Pinned full process with authenticated finite descendant birth accounting."""
import argparse
from collections import Counter
import gc,hashlib,importlib.util,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def write(path,value):
    from tools.campaign_streaming_evidence import write_canonical
    write_canonical(path,value)


def bounded_progress(sim):
    # Never call events/snapshot/default checkpoint: those deliberately
    # materialize the full disk history for their existing public contract.
    with sim.session._lock:
        state=sim.ctx.state()
        return {'tick':sim.session.time,'kills':state['kills'],'leaks':state['leaks'],'pending':state['pending_waves'],
            'finished':state['finished'],'event_count':len(sim.session._events._records),
            'alive_enemies':[{'id':e['id'],'definition':e['definition_id'],'position':dict(e['components']['spatial']['position']),
                'hp':{k:r['current'] for k,r in e['components'].get('resources',{}).items()}} for e in sim.session.world.entities() if 'enemy' in e['tags'] and sim.ctx.alive(e['id'])]}


def comparable(observation):return {k:observation[k] for k in ('snapshot','events','event_count','continuation_state')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('runtime-root','package','commands','output','evidence-helper'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--expected-core',required=True);parser.add_argument('--helper-sha256',required=True)
    parser.add_argument('--providers-module',type=Path,required=True);parser.add_argument('--providers-sha256',required=True)
    parser.add_argument('--public-dialogue-driver',action='store_true')
    parser.add_argument('--max-ticks',type=int,default=30000);parser.add_argument('--checkpoint-at',type=int,default=700)
    args=parser.parse_args();runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime))
    import ark_sim
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw
    from ark_sim.tools.replay import replay
    from tools.campaign_dynamic_birth_ledger_v1 import audit_births
    assert Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim' and implementation_digest()==args.expected_core
    if sha(args.evidence_helper)!=args.helper_sha256:raise ValueError('Evidence helper bytes differ')
    if args.output.exists() or args.output.with_suffix('.active.jsonl').exists():raise FileExistsError('Preserve existing run')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('selected_disk_evidence',args.evidence_helper);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    if sha(args.providers_module)!=args.providers_sha256:raise ValueError('Provider module bytes differ')
    selected_pin_before=sha(args.providers_module)
    pspec=importlib.util.spec_from_file_location('selected_source_providers',args.providers_module)
    pmodule=importlib.util.module_from_spec(pspec);pspec.loader.exec_module(pmodule)
    providers=pmodule.providers()
    if sha(args.providers_module)!=selected_pin_before or selected_pin_before!=args.providers_sha256:raise ValueError('Selected provider module changed during load or registry construction')
    if sha(args.evidence_helper)!=args.helper_sha256:raise ValueError('Selected evidence helper changed during load')
    # Actual content provider callables and imported helper files also bind.
    provider_sources=[]
    import inspect
    for record in providers.values():
        from collections.abc import Mapping
        function=record.get('callable',record.get('evaluate')) if isinstance(record,Mapping) else record
        if not callable(function) and hasattr(function,'evaluate'):function=function.evaluate
        if not callable(function):raise ValueError('Selected provider record requires actual callable body')
        try:path=inspect.getsourcefile(function)
        except TypeError:path=inspect.getsourcefile(type(function))
        if path:provider_sources.append(Path(path))
    guarded=[Path(__file__),ROOT/'tools/campaign_dynamic_birth_ledger_v1.py',args.package,args.commands,args.evidence_helper,args.providers_module,
        *provider_sources,ROOT/'tools/campaign_ordered_checkpoint.py',
        ROOT/'tools/campaign_streaming_evidence.py',runtime/'ark_sim/rules/contracts.json',runtime/'ark_sim/content/presets/ark_standard.json']
    # Wrapper helpers deliberately delegate to preserved publication modules.
    # Bind those actual consumed source files as well as the selected entry.
    pending=[helper];seen=set()
    while pending:
        module=pending.pop()
        if id(module) in seen:continue
        seen.add(id(module))
        if getattr(module,'__file__',None):guarded.append(Path(module.__file__))
        pending.extend(getattr(module,key) for key in ('_v12','_v13') if hasattr(module,key))
    guarded=list(dict.fromkeys(p.resolve() for p in guarded))
    if args.public_dialogue_driver:
        from tools.control_driver.public_ack_v2 import PublicAckDriver
        guarded.append(ROOT/'tools/control_driver/public_ack_v2.py')
    before={str(p.resolve()):sha(p) for p in guarded}
    if before[str(args.providers_module.resolve())]!=args.providers_sha256 or before[str(args.evidence_helper.resolve())]!=args.helper_sha256:raise ValueError('Selected provider/helper pin differs before execution')
    package=json.loads(args.package.read_bytes());commands=json.loads(args.commands.read_bytes());scene=package['scenarioDraft']
    profile=scene['metadata']['runthrough_profile'];life=profile['base_life_resource']
    if scene['resources'][life]['initial']!=99999 or scene['resources'][life]['capacity']!=99999:raise ValueError('Base life99999 required')
    program=Compiler(providers=providers).compile(package);sim=Engine.create(program,providers=providers,seed=scene['seed'],event_journal_path=args.output.with_suffix('.active.jsonl'))
    expected=Counter()
    for wave in scene['timeline']['waves']:
        for fragment in wave['fragments']:
            for action in fragment['actions']:
                if action['kind']=='spawn':expected[action['spawn']['definition']]+=action.get('count',1)
    for command in commands:
        action=dict(command);tick=action.pop('at');sim.submit(action,at=tick)
    driver=PublicAckDriver(sim) if args.public_dialogue_driver else None
    checkpoint_driver=None;driver_final=None
    checkpoint=None;error=None;last=max((c['at'] for c in commands),default=-1)
    try:
        while sim.session.time<args.max_ticks and (not sim.ctx.state()['finished'] or sim.session.time<=last):
            target=min(sim.session.time+100,args.max_ticks)
            if checkpoint is None and sim.session.time<args.checkpoint_at<=target:target=args.checkpoint_at
            if driver is not None:driver.advance_to(target)
            else:sim.session.advance(target-sim.session.time)
            if checkpoint is None and sim.session.time==args.checkpoint_at:
                checkpoint=helper.write_checkpoint(sim,args.output.with_suffix('.checkpoint.json'));helper.load_checkpoint(checkpoint)
                if driver is not None:
                    checkpoint_driver={'path':str(args.output.with_suffix('.driver.checkpoint.json').resolve())}
                    write(checkpoint_driver['path'],driver.checkpoint())
                    checkpoint_driver['sha256']=sha(checkpoint_driver['path'])
            progress=bounded_progress(sim);print(json.dumps({k:v for k,v in progress.items() if k!='alive_enemies'}),flush=True)
            write(args.output.with_suffix('.progress.json'),progress)
    except Exception as caught:error={'phase':'forward_execution','type':type(caught).__name__,'message':str(caught)}
    state=thaw(sim.ctx.state());end=sim.session.time;actors=thaw(sim.session.world.entities());actual=Counter(e['definition_id'] for e in sim.session.world.entities() if 'enemy' in e['tags'])
    complete=bool(error is None and state['finished'] and state['pending_waves']==0 and state['timeline']['phase']=='complete'
        and state['kills']+state['leaks']==sum(actual.values()) and not any(sim.ctx.alive(e['id']) for e in sim.session.world.entities() if 'enemy' in e['tags']))
    report={'schema':'ark-sim/campaign-runthrough/v1','passed':False,'process_complete':complete,'actual_game_accuracy_verified':False,
        'accuracy_status':'Source-reference model; user feedback pending','providers_module_sha256':args.providers_sha256,'implementation':args.expected_core,'runtime_module':ark_sim.__file__,
        'program':program.fingerprint,'runtime':sim.runtime_fingerprint,'package_sha256':before[str(args.package.resolve())],
        'commands_sha256':before[str(args.commands.resolve())],'profile':profile,'seed':scene['seed'],'end_tick':end,'state':state,
        'base_life_final':sim.ctx.resources.current('system/battle',life),'expected_native_births':dict(expected),'actual_births':dict(actual),
        'checkpoint_equal':False,'durable_checkpoint_equal':False,'replay_equal':False,'source_at_start':before,'forward_error':error,
        'pending_model_gaps':package['manifest']['metadata'].get('pending_model_gaps',[]),'commands':[],
        'evidence_format':'owned insertion-order disk journal; complete event values',
        'checkpoint':checkpoint['path'] if checkpoint else None,'checkpoint_sha256':checkpoint['sha256'] if checkpoint else None,
        'checkpoint_encoding':'insertion-order JSON; loaded from actual saved bytes',
        'checkpoint_event_reference':checkpoint['event_reference'] if checkpoint else None,'checkpoint_error':None,'replay_error':None}
    if driver is not None:driver_final=driver.checkpoint()
    report['public_dialogue_driver']=bool(driver is not None)
    report['driver_checkpoint']=checkpoint_driver;report['driver_final']=driver_final;report['driver_equal']=driver is None
    observation=helper.observations(sim,args.output.with_suffix('.events.jsonl'));report['observations']=comparable(observation)
    export=observation['export'];report['journal']={'path':export['path'],'sha256':export['sha256'],'events':export['count'],'bytes':export['bytes']}
    terminal=None
    with Path(export['path']).open('r',encoding='utf8') as file:
        for line in file:
            event=json.loads(line)
            if event['type'] in ('command.accepted','command.rejected'):report['commands'].append(event)
            if event['type']=='scenario.finished' and terminal is None:terminal=event['time']
    try:
        with Path(export['path']).open('r',encoding='utf8') as file:
            birth_audit=audit_births(program,actors,state,(json.loads(line) for line in file))
        report['birth_ledger']=birth_audit
        report['expected_births']=dict(Counter(birth_audit['native_births'])+Counter(birth_audit['authenticated_descendants']))
    except Exception as caught:
        complete=False
        report['birth_ledger_error']={'type':type(caught).__name__,'message':str(caught)}
    report['process_complete']=complete
    report['terminal_tick']=terminal;report['last_scheduled_command_at']=last
    record=sim.export_replay();write(args.output.with_suffix('.replay.json'),record);write(args.output.with_suffix('.original.json'),report)
    del sim;gc.collect()
    if complete:
        restored=None
        try:
            if checkpoint is None:raise ValueError('Explicit checkpoint not reached')
            restored=Engine.restore(program,helper.load_checkpoint(checkpoint),providers=providers)
            if checkpoint_driver is not None:
                if sha(checkpoint_driver['path'])!=checkpoint_driver['sha256']:raise ValueError('Driver disk checkpoint bytes differ')
                saved=json.loads(Path(checkpoint_driver['path']).read_bytes())
                resumed_driver=PublicAckDriver(restored,saved);resumed_driver.advance_to(end)
                report['driver_equal']=resumed_driver.checkpoint()==driver_final
            else:restored.session.advance(end-restored.session.time)
            observed=helper.observations(restored,args.output.with_suffix('.continued.events.jsonl'))
            report['continuation_journal']=observed['export'];report['checkpoint_equal']=report['durable_checkpoint_equal']=comparable(observed)==report['observations']
        except Exception as caught:report['checkpoint_error']={'type':type(caught).__name__,'message':str(caught)}
        finally:del restored;gc.collect()
        write(args.output.with_suffix('.checkpoint_result.json'),report)
        repeated=None
        try:
            repeated=replay(program,record,providers=providers,event_journal_path=args.output.with_suffix('.replay.active.jsonl'))
            observed=helper.observations(repeated,args.output.with_suffix('.replayed.events.jsonl'))
            report['replayed_journal']=observed['export'];report['replay_equal']=comparable(observed)==report['observations']
        except Exception as caught:report['replay_error']={'type':type(caught).__name__,'message':str(caught)}
        finally:del repeated;gc.collect()
    report['source_at_completion']={str(p.resolve()):sha(p) for p in guarded};report['core_at_completion']=implementation_digest()
    report['identity_stable']=report['source_at_completion']==before and report['core_at_completion']==args.expected_core and sha(args.providers_module)==args.providers_sha256 and sha(args.evidence_helper)==args.helper_sha256
    report['passed']=complete and report['checkpoint_equal'] and report['replay_equal'] and report['identity_stable'] and report['driver_equal']
    write(args.output,report);print(json.dumps({'passed':report['passed'],'complete':complete,'events':report['observations']['event_count'],'checkpoint_equal':report['checkpoint_equal'],'replay_equal':report['replay_equal']}),flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
