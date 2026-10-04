"""Profile one declared prefix; this is performance evidence, not stage acceptance."""
import argparse
import cProfile
import hashlib
import json
from pathlib import Path
import pstats
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--commands', type=Path, required=True)
    parser.add_argument('--ticks', type=int, default=300)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path)
    parser.add_argument('--unprofiled', action='store_true')
    args = parser.parse_args()
    if args.runtime_root:
        sys.path.insert(0, str(args.runtime_root.resolve()))
    import ark_sim
    if args.runtime_root and not Path(ark_sim.__file__).resolve().is_relative_to(args.runtime_root.resolve()):
        raise ValueError('candidate runtime was not actually imported')
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import digest
    from tools.verify_v2_baseline import observations
    program = Compiler().compile(args.package)
    sim = Engine.create(program, seed=953816614)
    for command in json.loads(args.commands.read_bytes()):
        payload = dict(command); at = payload.pop('at'); sim.submit(payload, at=at)
    profile = cProfile.Profile()
    started = time.perf_counter()
    if not args.unprofiled:
        profile.enable()
    sim.advance(args.ticks)
    if not args.unprofiled:
        profile.disable()
    elapsed = time.perf_counter()-started
    stats = None if args.unprofiled else pstats.Stats(profile)
    functions = []
    for (path, line, name), (primitive, total, own, cumulative, callers) in (sorted(stats.stats.items(), key=lambda item: -item[1][3])[:40] if stats else []):
        functions.append({'file': path, 'line': line, 'function': name, 'primitive_calls': primitive,
            'total_calls': total, 'own_seconds': round(own, 4), 'cumulative_seconds': round(cumulative, 4)})
    data = {'schema': 'ark-sim/runtime-prefix-profile/v1', 'scope': 'profiled_prefix_not_full_stage',
        'implementation_sha256': implementation_digest(), 'package_sha256': hashlib.sha256(args.package.read_bytes()).hexdigest(),
        'commands_sha256': hashlib.sha256(args.commands.read_bytes()).hexdigest(), 'ticks': args.ticks,
        'elapsed_profiled_seconds': elapsed if not args.unprofiled else None,
        'elapsed_seconds': elapsed, 'profiler_enabled': not args.unprofiled,
        'runtime_module': ark_sim.__file__, 'semantic_state_sha256': digest({'time': sim.session.time,
            'world': sim.session.world.snapshot(), 'scheduler': sim.session.scheduler.snapshot(),
            'random': sim.session.random.snapshot(), 'reaction_budget': sim.session.reaction_budget}),
        'program_fingerprint': program.fingerprint, 'runtime_fingerprint': sim.runtime_fingerprint,
        'events': len(sim.session.events), 'functions': functions,
        'observations': observations(sim), 'formal_stage_approved': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'ticks': args.ticks, 'elapsed_profiled_seconds': elapsed, 'events': len(sim.session.events),
        'top_functions': functions[:12]}, ensure_ascii=True))


if __name__ == '__main__':
    main()
