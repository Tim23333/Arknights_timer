"""Complete stage execution and exact replay, without a zero-leak win criterion."""
import argparse
from collections import Counter
import gc
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value): path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--runtime-root', type=Path, required=True); parser.add_argument('--expected-core', required=True)
    parser.add_argument('--package', type=Path, required=True); parser.add_argument('--commands', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--max-ticks', type=int, default=30000)
    parser.add_argument('--checkpoint-at', type=int, default=700); parser.add_argument('--no-replay', action='store_true')
    args = parser.parse_args(); runtime = args.runtime_root.resolve(); sys.path.insert(0, str(runtime)); sys.path.insert(1, str(ROOT))
    import ark_sim
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw, digest
    from ark_sim.tools.replay import replay
    if Path(ark_sim.__file__).resolve().parent != runtime/'ark_sim' or implementation_digest() != args.expected_core:
        raise RuntimeError('wrong explicit runthrough runtime')
    guarded = {str(p.resolve()): sha(p) for p in (Path(__file__), args.package, args.commands, runtime/'ark_sim/rules/contracts.json', runtime/'ark_sim/content/presets/ark_standard.json')}
    package = json.loads(args.package.read_bytes()); commands = json.loads(args.commands.read_bytes()); scene = package['scenarioDraft']
    profile = scene['metadata']['runthrough_profile']; life = profile['base_life_resource']
    if scene['resources'][life]['initial'] != 99999 or scene['resources'][life]['capacity'] != 99999: raise ValueError('runthrough life override missing')
    seed = scene['seed']; program = Compiler().compile(package); sim = Engine.create(program, seed=seed)
    expected = Counter()
    for w in scene['timeline']['waves']:
        for f in w['fragments']:
            for a in f['actions']:
                if a['kind'] == 'spawn': expected[a['spawn']['definition']] += a.get('count', 1)
    for command in commands:
        action = dict(command); tick = action.pop('at'); sim.submit(action, at=tick)
    checkpoint = None
    while sim.session.time < args.max_ticks and not sim.ctx.state()['finished']:
        if checkpoint is None and sim.session.time < args.checkpoint_at:
            amount = min(100, args.checkpoint_at-sim.session.time)
        else: amount = min(100, args.max_ticks-sim.session.time)
        sim.advance(amount)
        if checkpoint is None and sim.session.time == args.checkpoint_at: checkpoint = sim.checkpoint()
        state = sim.ctx.state()
        print(json.dumps({'tick': sim.session.time, 'kills': state['kills'], 'leaks': state['leaks'], 'pending': state['pending_waves'], 'life': sim.ctx.resources.current('system/battle', life), 'finished': state['finished']}), flush=True)
    state = sim.ctx.state(); end = sim.session.time
    actual = Counter(e['definition_id'] for e in sim.session.world.entities() if 'enemy' in e['tags'])
    events = tuple(sim.session.events); records = [thaw(e) for e in events if e['type'] in ('command.accepted', 'command.rejected')]
    observations = {'snapshot': digest(sim.snapshot()), 'events': digest(thaw(events)), 'event_count': len(events)}
    complete = bool(state['finished'] and state['pending_waves'] == 0 and state['timeline']['phase'] == 'complete'
        and actual == expected and state['kills']+state['leaks'] == sum(expected.values())
        and not any(sim.ctx.alive(e['id']) for e in sim.session.world.entities() if 'enemy' in e['tags']))
    final_entities = [{'id': e['id'], 'definition': e['definition_id'], 'alive': sim.ctx.alive(e['id']),
        'resources': {name: data['current'] for name, data in e['components'].get('resources', {}).items()},
        'position': thaw(e['components'].get('spatial', {}).get('position'))} for e in sim.session.world.entities()]
    report = {'schema': 'ark-sim/campaign-runthrough/v1', 'process_complete': complete, 'passed': False,
        'actual_game_accuracy_verified': False, 'accuracy_status': 'model/source-only; client comparator and unresolved profiles pending',
        'implementation': args.expected_core, 'runtime_module': ark_sim.__file__, 'program': program.fingerprint, 'runtime': sim.runtime_fingerprint,
        'package_sha256': sha(args.package), 'commands_sha256': sha(args.commands), 'profile': profile, 'seed': seed,
        'end_tick': end, 'state': state, 'base_life_final': sim.ctx.resources.current('system/battle', life),
        'expected_births': dict(expected), 'actual_births': dict(actual), 'commands': records, 'final_entities': final_entities,
        'observations': observations, 'checkpoint_equal': None, 'replay_equal': None, 'formal_approved': False,
        'pending_model_gaps': package['manifest']['metadata'].get('pending_model_gaps', []), 'source_at_start': guarded}
    record = sim.export_replay(); write(args.output.with_suffix('.replay.json'), record)
    if complete and not args.no_replay:
        if checkpoint is None: raise ValueError('explicit checkpoint was not reached')
        del sim, events; gc.collect()
        restored = Engine.restore(program, checkpoint); restored.advance(end-restored.session.time)
        report['checkpoint_equal'] = observations == {'snapshot': digest(restored.snapshot()), 'events': digest(thaw(tuple(restored.session.events))), 'event_count': len(restored.session.events)}
        del restored; gc.collect()
        replayed = replay(program, record)
        report['replay_equal'] = observations == {'snapshot': digest(replayed.snapshot()), 'events': digest(thaw(tuple(replayed.session.events))), 'event_count': len(replayed.session.events)}
        del replayed; gc.collect()
    report['source_at_completion'] = {p: sha(Path(p)) for p in guarded}
    stable = implementation_digest() == args.expected_core and report['source_at_completion'] == guarded
    report['identity_stable'] = stable
    report['passed'] = bool(complete and stable and (args.no_replay or report['checkpoint_equal'] and report['replay_equal']))
    write(args.output, report)
    print(json.dumps({'process_complete': complete, 'passed': report['passed'], 'kills': state['kills'], 'leaks': state['leaks'], 'actual_game_accuracy_verified': False}))
    if not report['passed']: raise SystemExit(1)


if __name__ == '__main__': main()
