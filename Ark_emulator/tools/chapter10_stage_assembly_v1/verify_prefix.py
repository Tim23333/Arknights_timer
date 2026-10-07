"""Bounded original source prefix, public commands and complete ordered CP/head."""
import argparse
import json
import os
import hashlib
import sys
import traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--expected-core', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_root.resolve()
    sys.path.insert(0, str(runtime));sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw, digest
    from ark_sim.tools.replay import replay
    from tools.campaign_ordered_checkpoint import write_ordered, load_bound
    from tools.chapter10_stage_assembly_v1.providers import providers
    assert implementation_digest() == args.expected_core
    package = ROOT / 'packages/campaign/chapter10_stage_models/level_main_10-14.source_draft.v2.life99999.json'
    commands = ROOT / 'scenarios/campaign/chapter10/level_main_10-14/public_plan_v1_finite/commands.json'
    paths = [package, commands, Path(__file__), ROOT / 'tools/chapter10_stage_assembly_v1/providers.py']
    paths += [p for p in (runtime / 'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py', '.json')]
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    before = {str(p): sha(p) for p in paths}
    result = {'schema': 'ark-sim/chapter10-public-prefix/v1', 'core': args.expected_core,
              'source_before': before, 'whole_stage': False, 'client_verified': False}
    try:
        data = json.loads(package.read_bytes())
        all_commands = json.loads(commands.read_bytes())
        data['scenarioDraft']['commands'] = [c for c in all_commands if c['at'] < 601]
        registry = providers()
        program = Compiler(providers=registry).compile(data)
        continuous = Engine.create(program, providers=registry, seed=program.scenario['seed'])
        continuous.advance(601)
        staged = Engine.create(program, providers=registry, seed=program.scenario['seed'])
        pins = []
        for tick in (149, 151, 599, 600):
            staged.advance(tick - staged.session.time)
            path = Path(os.environ['ARKSIM_RUN_DIR']) / (str(tick) + '.checkpoint.json')
            pin = write_ordered(path, staged.checkpoint())
            staged = Engine.restore(program, load_bound(path, pin), providers=registry)
            pins.append({'tick': tick, 'sha256': pin})
        staged.advance(601 - staged.session.time)
        head = replay(program, continuous.export_replay(), providers=registry)
        assert continuous.checkpoint() == staged.checkpoint() == head.checkpoint()
        assert list(continuous.session.events) == list(staged.session.events) == list(head.session.events)
        outcomes = [thaw(e) for e in continuous.session.events if e['type'] in ('command.accepted', 'command.rejected')]
        enemy = [actor for actor in continuous.session.world.entities() if 'enemy' in actor['tags']]
        result.update(outcomes=outcomes, observed_enemy_births=[{'id': e['id'], 'definition': e['definition_id']} for e in enemy],
                      DP=continuous.ctx.resources.current('system/battle', 'dp'),
                      base_life=continuous.ctx.resources.current('system/battle', 'life'),
                      operator_HP=continuous.ctx.resources.current('c10_myrtle', 'hp'),
                      checkpoints=pins, complete_checkpoint_digest=digest(continuous.checkpoint()), full_CP_head_equal=True)
        assert len(outcomes) == 2 and all(e['type'] == 'command.accepted' for e in outcomes)
        assert continuous.ctx.resources.current('system/battle', 'life') == 99999
        assert continuous.ctx.get('c10_myrtle', ('elemental',)) is not None
        assert len(enemy) >= 2
        result['passed'] = True
    except Exception:
        result['passed'] = False
        result['error'] = traceback.format_exc()
    result['source_after'] = {str(p): sha(p) for p in paths}
    result['source_guard_equal'] = before == result['source_after']
    result['actual_exit'] = 0 if result['passed'] and result['source_guard_equal'] else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    assert not args.output.exists()
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'actual_exit': result['actual_exit'], 'error': result.get('error')}))
    return result['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
