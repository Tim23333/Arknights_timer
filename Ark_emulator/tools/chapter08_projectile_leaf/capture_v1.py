"""Capture full source simulation evidence under one explicitly selected runtime."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--core', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ticks', type=int, default=400)
    args = parser.parse_args()
    sys.path.insert(0, str(args.runtime.resolve()))
    sys.path.insert(1, str(ROOT))
    import ark_sim
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw
    from tools.chapter08_joint_v4.test_first_screen_native7_v1 import package
    from tools.chapter08_bsnake.screen_policy_v1 import providers
    assert Path(ark_sim.__file__).resolve().is_relative_to(args.runtime.resolve())
    assert implementation_digest() == args.core
    started = time.perf_counter()
    reg = providers()
    s = Engine.create(Compiler(providers=reg).compile(package()), providers=reg, seed=81843)
    s.submit({'action': 'skill', 'source': 'director', 'ability': 'ability/firstscreen/kill'}, at=1)
    s.advance(args.ticks)
    elapsed = time.perf_counter() - started
    data = {'core': args.core, 'checkpoint': s.checkpoint(), 'events': thaw(tuple(s.session.events)),
            'replay': s.export_replay()}
    assert not args.output.exists()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf8', newline='\n')
    args.output.with_suffix('.timing.json').write_text(json.dumps({'core': args.core, 'ticks': args.ticks,
        'simulation_seconds': elapsed, 'events': len(s.session.events)}) + '\n', encoding='utf8')
    print(json.dumps({'core': args.core, 'seconds': elapsed, 'events': len(s.session.events)}), flush=True)


if __name__ == '__main__':
    main()
