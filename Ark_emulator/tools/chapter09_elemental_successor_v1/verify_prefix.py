"""Fresh public chapter9 source prefixes after explicit EP receiver mounting."""
import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--stage', choices=('09-16', '09-17'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    runtime = args.runtime_root.resolve();sys.path.insert(0, str(runtime));sys.path.insert(1, str(ROOT))
    import ark_sim
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import digest, thaw
    from ark_sim.tools.replay import replay
    from tools.campaign_ordered_checkpoint import write_ordered, load_bound
    from tools.chapter09_elemental_successor_v1.build import CORE
    from tools.chapter09_elemental_successor_v1.providers import providers
    assert Path(ark_sim.__file__).resolve().parent == runtime / 'ark_sim' and implementation_digest() == CORE
    package = ROOT / f'packages/campaign/chapter09_stage_models/level_main_{args.stage}.elemental_successor.v1.life99999.finite_run_v1.json'
    plan = 'v1' if args.stage == '09-16' else 'v2'
    commands = ROOT / f'scenarios/campaign/chapter09/level_main_{args.stage}/public_plan_{plan}_finite/commands.json'
    p = json.loads(package.read_bytes());p['scenarioDraft']['commands'] = json.loads(commands.read_bytes())
    metadata = p['manifest']['metadata']
    bound_sources = {**metadata['source_locks'], **metadata['elemental_successor_binding']['source_locks']}
    assert all(sha(path) == value for path, value in bound_sources.items())
    registry = providers(args.stage)
    paths = [package, commands, Path(__file__), ROOT / 'tools/campaign_ordered_checkpoint.py',
             *map(Path, bound_sources)]
    paths += [f for f in (runtime / 'ark_sim').rglob('*') if f.is_file() and f.suffix in ('.py', '.json')]
    for provider in registry.values():
        body = provider.get('callable', provider.get('evaluate')) if isinstance(provider, dict) else provider
        if callable(body) and inspect.getsourcefile(body):
            paths.append(Path(inspect.getsourcefile(body)))
    paths = list(dict.fromkeys(paths))
    before = {str(path): sha(path) for path in paths}
    result = {'schema': 'ark-sim/chapter9-elemental-public-prefix/v1', 'core': CORE,
              'stage': args.stage, 'source_before': before, 'passed': False,
              'whole_stage': False, 'client_verified': False}
    try:
        program = Compiler(providers=registry).compile(p)
        original = Engine.create(program, providers=registry, seed=program.scenario['seed'])
        original.advance(91)
        cp_path = Path(os.environ['ARKSIM_RUN_DIR']) / 'public91.checkpoint.json'
        pin = write_ordered(cp_path, original.checkpoint())
        restored = Engine.restore(program, load_bound(cp_path, pin), providers=registry)
        end = 182 if args.stage == '09-16' else 245
        original.advance(end - 91);restored.advance(end - 91)
        head = replay(program, original.export_replay(), providers=registry)
        assert original.checkpoint() == restored.checkpoint() == head.checkpoint()
        assert list(original.session.events) == list(restored.session.events) == list(head.session.events)
        outcomes = [thaw(e) for e in original.session.events if e['type'] in ('command.accepted', 'command.rejected')]
        assert len(outcomes) == 2 and all(e['type'] == 'command.accepted' for e in outcomes)
        assert [e['payload']['action']['alias'] for e in outcomes] == ['c9_myrtle', 'c9_device1']
        device = original.session.world.resolve('c9_device1')
        assert not original.ctx.alive(device)
        ep = thaw(original.ctx.get('c9_myrtle', ('runtime', 'elemental')))
        assert set(ep['remaining']) == {'FIRE', 'DARK'} and ep['remaining'] == {'FIRE': 1000, 'DARK': 1000}
        assert original.ctx.resources.current('system/battle', 'life') == 99999
        result.update(passed=True, program=program.fingerprint, actual_outcomes=outcomes, end_tick=end,
                      device_retired=True, elemental_state=ep,
                      stock=original.ctx.resources.current('system/battle', 'stock_ch9_demolition'),
                      HP=original.ctx.resources.current('c9_myrtle', 'hp'),
                      DP=original.ctx.resources.current('system/battle', 'dp'),
                      checkpoint_sha256=pin, complete_CP_head_equal=True,
                      complete_checkpoint_digest=digest(original.checkpoint()))
    except Exception:
        result['error'] = traceback.format_exc()
    result['source_after'] = {str(path): sha(path) for path in paths}
    result['core_at_completion'] = implementation_digest()
    result['actual_modules'] = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
                               if name.startswith('ark_sim') and getattr(module, '__file__', None)}
    result['identity_stable'] = (before == result['source_after'] and result['core_at_completion'] == CORE
                                 and all(Path(path).is_relative_to(runtime / 'ark_sim') for path in result['actual_modules'].values()))
    result['actual_exit'] = 0 if result['passed'] and result['identity_stable'] else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf8')
    print(json.dumps({'passed': result['passed'], 'actual_exit': result['actual_exit'], 'error': result.get('error')}))
    return result['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
