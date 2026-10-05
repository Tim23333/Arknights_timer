"""Separate aerial selection/blocking from ground routing through real commands."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--core', required=True); parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    runtime = args.runtime_root.resolve(); sys.path.insert(0, str(runtime)); sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler, Engine
    from ark_sim.tools.replay import replay
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import digest
    assert implementation_digest() == args.core
    files = [Path(__file__), *[p for p in (runtime / 'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py', '.json')]]
    guard = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before = guard(); results = []; artifacts = []; log = Path(os.environ['ARKSIM_RUN_DIR'])

    def data(independent=True):
        spatial = {'motion_mode': 1}
        if independent: spatial['route_motion_mode'] = 0
        actor = {'id': 'unit/motion/hover', 'kind': 'entity', 'tags': ['enemy'], 'components': {
            'attributes': {'base': {'max_hp': 711, 'atk': 0, 'def': 0, 'mres': 0, 'move_speed': 2, 'mass_level': 2}},
            'resources': {'hp': {'role': 'health', 'initial': 711, 'capacity': 711}},
            'spatial': spatial, 'selection_state': {'side': 1, 'motion': 2, 'category': 1, 'unit_type': 2},
            'abilities': ['ability/motion/land']}}
        blocker = {'id': 'unit/motion/blocker', 'kind': 'entity', 'components': {
            'attributes': {'base': {'max_hp': 911, 'block_count': 3}}, 'resources': {'hp': {'role': 'health', 'initial': 911, 'capacity': 911}},
            'spatial': {}, 'selection_state': {'side': 0, 'motion': 1, 'category': 1, 'unit_type': 1},
            'deployable': {'base_cost': 1, 'terrain': 'ground', 'capacity': 1, 'cooldown_seconds': 0}}}
        tiles = [{'tileKey': 'tile_floor', 'buildableType': 1, 'passableMask': 3} for _ in range(21)]
        tiles[9] = {'tileKey': 'tile_wall', 'buildableType': 0, 'passableMask': 2}
        return {'schemaVersion': 2, 'entities': [actor, blocker], 'abilities': [{
            'id': 'ability/motion/land', 'kind': 'ability', 'activation': {'mode': 'manual'},
            'timeline': [{'at': 0, 'effect': {'op': 'set_motion_mode', 'target': 'source', 'value': 0,
                                            'parameters': {'route_motion_mode': 0}}}]}],
            'scenarioDraft': {'id': 'scene/motion/hover', 'ruleset': 'ruleset/ark_standard',
                'map': {'rows': 3, 'cols': 7, 'tiles': tiles}, 'resources': {'life': {'initial': 99999, 'capacity': 99999}},
                'initialEntities': [{'definition': actor['id'], 'instanceAlias': 'hover', 'position': {'row': 1, 'col': 0},
                    'route': {'startPosition': {'row': 1, 'col': 0}, 'endPosition': {'row': 1, 'col': 6}, 'motionMode': 0, 'checkpoints': []}},
                    {'definition': blocker['id'], 'instanceAlias': 'blocker', 'position': {'row': 1, 'col': 0}, 'deployed': True}]}}

    def create(p): return Engine.create(Compiler().compile(p), seed=927)

    def modes():
        s = create(data()); assert s.ctx.get('hover', ('spatial', 'route', 'motionMode')) == 0
        assert s.ctx.get('hover', ('selection_state', 'motion')) == 2
        s.ctx.spatial.blocking(); assert s.ctx.spatial.blocked_by('hover') is None
        path = s.ctx.spatial.grid.path({'row': 1, 'col': 0}, {'row': 1, 'col': 6}, s.ctx.get('hover', ('spatial', 'route', 'motionMode')))
        assert {'row': 1, 'col': 2} not in list(path)
        s.submit({'action': 'skill', 'source': 'hover', 'ability': 'ability/motion/land'}, at=0); s.advance(1)
        assert s.ctx.get('hover', ('spatial', 'route', 'motionMode')) == 0
        assert s.ctx.get('hover', ('selection_state', 'motion')) == 1
        s.ctx.spatial.blocking(); assert s.ctx.spatial.blocked_by('hover') == s.session.world.resolve('blocker')
        legacy = create(data(False)); assert legacy.ctx.get('hover', ('spatial', 'route', 'motionMode')) == 1

    def cpp():
        p = data(); p['scenarioDraft']['commands'] = [{'at': 35, 'action': 'skill', 'source': 'hover', 'ability': 'ability/motion/land'}]
        s = create(p); s.advance(17); path = log / 'hover.checkpoint.json'; path.write_text(json.dumps(s.checkpoint()), encoding='utf8')
        r = Engine.restore(s.program, json.loads(path.read_bytes())); s.advance(50); r.advance(50)
        h = replay(s.program, s.export_replay()); assert s.checkpoint() == r.checkpoint() == h.checkpoint()
        artifacts.append({'path': str(path), 'sha': hashlib.sha256(path.read_bytes()).hexdigest(), 'end_digest': digest(s.checkpoint()), 'CPP_head_equal': True})

    def invalid():
        for value in (True, -1, 2, 'WALK'):
            p = data(); p['entities'][0]['components']['spatial']['route_motion_mode'] = value
            try: Compiler().compile(p)
            except ValueError: pass
            else: raise AssertionError('Invalid route motion enum compiled')
        s = create(data()); before = s.checkpoint()
        try: s.ctx.effects.execute('hover', ['hover'], {'op': 'set_motion_mode', 'value': 1, 'parameters': {'route_motion_mode': True}})
        except ValueError: pass
        else: raise AssertionError('Invalid runtime route mode accepted')
        assert s.checkpoint() == before

    for name, fn in [('ground_route_aerial_selection_then_real_blocking', modes), ('public_command_CPP_full_head', cpp), ('invalid_explicit_enum_compile_and_atomic_runtime', invalid)]:
        try: fn(); results.append({'case': name, 'passed': True})
        except Exception as error: results.append({'case': name, 'passed': False, 'error': str(error), 'traceback': traceback.format_exc()})
    after = guard(); record = {'core': args.core, 'actual_exit': 0 if all(r['passed'] for r in results) and before == after else 1,
        'results': results, 'source_start': before, 'source_end': after, 'source_equal': before == after,
        'artifacts': artifacts, 'comparison_exclusions': [], 'whole_stage': False}
    args.output.parent.mkdir(parents=True, exist_ok=True); assert not args.output.exists(); args.output.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
    return record['actual_exit']


if __name__ == '__main__': raise SystemExit(main())
