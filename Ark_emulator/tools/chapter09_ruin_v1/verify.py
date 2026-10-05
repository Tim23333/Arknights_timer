"""Actual native melee destroys ally rubble; full disk CP/head retain every field."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
CORE = '2c385c9c4a9e383988a3ff8d8d96827f0e473dde0630a3d6d92aa35c5f0dccb0'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.runtime_root.resolve())); sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import digest, thaw
    from ark_sim.tools.replay import replay
    from tools.chapter09_stage_assembly_v1.providers import providers
    from tools.chapter09_ruin_v1.build import BODY, build
    from tools.campaign_ordered_checkpoint import write_ordered, load_bound
    assert implementation_digest() == CORE
    log = Path(os.environ['ARKSIM_RUN_DIR'])
    report = {'core': CORE, 'passed': False, 'cases': []}
    paths = [Path(__file__), ROOT / 'tools/chapter09_ruin_v1/build.py',
             ROOT / 'packages/campaign/chapter09_consumers/ruin/module.v1.json']
    paths += [p for p in (args.runtime_root.resolve() / 'ark_sim').rglob('*')
              if p.is_file() and p.suffix in ('.py', '.json') and 'validation' not in p.parts]
    guard = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    report['guards_start'] = guard()

    def fixture(old=False):
        native = ROOT / 'packages/campaign/chapter09_consumers/ordinary/enemy_1165_duhond.module.v1.json'
        p = json.loads(native.read_bytes())
        module = build()
        if old:
            previous = json.loads((ROOT / 'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v2.life99999.json').read_bytes())
            module = {'definitions': [deepcopy(next(d for d in previous['definitions'] if d['id'] == BODY))]}
        p.setdefault('definitions', []).extend(module['definitions'])
        uid = p['entities'][0]['id']
        route = {'startPosition': {'row': 1, 'col': 2}, 'endPosition': {'row': 1, 'col': 4},
                 'motionMode': 0, 'checkpoints': []}
        p['scenarioDraft'] = {'id': 'scene/ch9/ruin/actual/' + str(old), 'ruleset': 'ruleset/ark_standard',
            'map': {'rows': 3, 'cols': 5}, 'objectives': {},
            'initialEntities': [{'definition': BODY, 'instanceAlias': 'ruin', 'position': {'row': 1, 'col': 2}},
                                {'definition': uid, 'instanceAlias': 'enemy', 'position': {'row': 1, 'col': 2}, 'route': route}]}
        return p

    try:
        old = Engine.create(Compiler(providers=providers()).compile(fixture(True)), providers=providers())
        old.advance(100)
        assert old.ctx.resources.current('ruin', 'hp') == 100 and old.ctx.spatial.blocked_by('enemy') is not None
        assert not any(e['type'] == 'ability.started' for e in old.session.events)
        report['cases'].append({'case': 'true_previous_content_counter', 'end_tick': 100,
            'ruin_HP': 100, 'enemy_still_blocked': True, 'actual_ability_starts': 0})
        p = fixture(); program = Compiler(providers=providers()).compile(p)
        a = Engine.create(program, providers=providers()); a.advance(10)
        checkpoint = log / 'before_native_hit.checkpoint.json'
        pin = write_ordered(checkpoint, a.checkpoint())
        b = Engine.restore(program, load_bound(checkpoint, pin), providers=providers())
        a.advance(110); b.advance(110)
        head = replay(program, a.export_replay(), providers=providers())
        assert a.checkpoint() == b.checkpoint() == head.checkpoint()
        assert list(a.session.events) == list(b.session.events) == list(head.session.events)
        assert not a.ctx.alive('ruin') and a.ctx.spatial.blocked_by('enemy') is None
        assert a.ctx.state()['kills'] == 0
        deaths = [thaw(e) for e in a.session.events if e['type'] == 'entity.died']
        hits = [thaw(e) for e in a.session.events if e['type'] == 'damage.applied']
        report['cases'].append({'case': 'actual_duhond_combat_and_route_release', 'end_tick': 120,
            'CPP_head_full_equal': True, 'ruin_dead': True, 'native_enemy_kills': 0,
            'enemy_blocker': None, 'native_damage_events': hits, 'death_events': deaths,
            'final_checkpoint_digest': digest(a.checkpoint()), 'checkpoint_sha': pin})
        report['guards_end'] = guard(); assert report['guards_start'] == report['guards_end']
        report.update(passed=True, actual_exit=0, whole_stage=False, client_verified=False)
    except Exception as error:
        report.update(actual_exit=1, error=str(error), traceback=traceback.format_exc())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists(): raise FileExistsError(args.output)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'passed': report['passed'], 'actual_exit': report['actual_exit'], 'error': report.get('error')}))
    return report['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
