"""Actual untouched native routes and map masks; geometry-only probe actors."""
import os
import json
import hashlib
import traceback
from copy import deepcopy
from pathlib import Path
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.domains.spatial import GridTopology
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter10_environment_v1.build import ROOT, PLAN, SOURCE, build

OUT = ROOT / 'validation/campaign/chapter10_environment_v1'
LOG = Path(os.environ['ARKSIM_RUN_DIR'])


def fixture(stage, index):
    module = build()
    row = module['manifest']['metadata']['stages'][stage]
    route = row['routes'][str(index)]
    package = {'schemaVersion': 2, 'rules': deepcopy(module['rules']),
        'entities': [{'id': 'unit/ch10/environment/probe', 'kind': 'entity', 'tags': ['enemy'],
            'components': {'attributes': {'base': {'max_hp': 7019, 'atk': 0, 'def': 0, 'mres': 0, 'move_speed': 1}},
                'resources': {'hp': {'role': 'health', 'initial': 7019, 'capacity': 7019}},
                'selection_state': {'side': 1, 'motion': 1, 'category': 1}, 'spatial': {},
                'lifecycle': {'policy': 'policy/ark_lifecycle'}}}],
        'scenarioDraft': {'id': 'scene/ch10/environment/' + stage + '/' + str(index), 'ruleset': 'ruleset/ark_standard',
            'seed': 10317, 'map': deepcopy(row['map']), 'objectives': {},
            'resources': {'life': {'initial': 99999, 'capacity': 99999}},
            'rules': {'movement.path': 'rule/ch10/environment/diagonal_path', 'movement.speed': 'rule/ch10/environment/native_speed'},
            'initialEntities': [{'definition': 'unit/ch10/environment/probe', 'instanceAlias': 'mover',
                                 'position': deepcopy(route['startPosition']), 'route': deepcopy(route)}],
            'metadata': {'scope': 'Native route/map geometry with explicit test actor; not a native enemy or whole-stage acceptance',
                         'raw_native_route': json.loads(PLAN.read_bytes())['stages'][stage]['native_document']['routes'][index]}}}
    return package, row


def create(package):
    return Engine.create(Compiler().compile(package), providers=BUILTIN_PROVIDERS, seed=10317)


def route_case(stage, index):
    package, row = fixture(stage, index)
    sim = create(package)
    checkpoint = None
    start = 0
    collected = []
    while sim.ctx.active('mover') and sim.session.time < 5500:
        sim.advance(30)
        new = list(sim.session.events)[start:]
        start += len(new)
        collected.extend(thaw(event) for event in new if event['type'] in (
            'movement.disappeared', 'movement.appeared', 'movement.wait', 'entity.exited', 'movement.tile_portal')))
        if checkpoint is None and sim.ctx.route_hidden('mover'):
            path = LOG / (stage + '.hidden.checkpoint.json')
            pin = write_ordered(path, sim.checkpoint())
            checkpoint = {'path': str(path), 'sha256': pin, 'tick': sim.session.time}
    diagnostic = {'stage': stage, 'route': index, 'end_tick': sim.session.time,
                  'active': sim.ctx.active('mover'), 'events': collected, 'checkpoint': checkpoint,
                  'life': sim.ctx.resources.current('system/battle', 'life')}
    (OUT / (stage + '.actual_probe.json')).write_text(json.dumps(diagnostic, indent=2) + '\n', encoding='utf8')
    assert not sim.ctx.active('mover') and checkpoint is not None
    hidden = [event for event in collected if event['type'] == 'movement.disappeared']
    appeared = [event for event in collected if event['type'] == 'movement.appeared']
    assert len(hidden) == len(appeared) == 1
    pair = next(pair for pair in row['portal_pairs'] if pair['route'] == index)
    assert appeared[0]['payload']['position'] == pair['exit']
    assert diagnostic['life'] == 99998
    restored = Engine.restore(sim.program, load_bound(checkpoint['path'], checkpoint['sha256']), providers=BUILTIN_PROVIDERS)
    restored.advance(sim.session.time - restored.session.time)
    head = replay(sim.program, sim.export_replay(), providers=BUILTIN_PROVIDERS)
    assert sim.checkpoint() == restored.checkpoint() == head.checkpoint()
    assert list(sim.session.events) == list(restored.session.events) == list(head.session.events)
    diagnostic['full_CP_head_equal'] = True
    return diagnostic


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pins = [PLAN, SOURCE, Path(__file__), ROOT / 'tools/chapter10_environment_v1/build.py']
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    before = {str(p): sha(p) for p in pins}
    report = {'schema': 'ark-sim/chapter10-environment-actual/v1', 'core': implementation_digest(),
              'source_before': before, 'scope': 'Actual native environment operands, isolated route probes',
              'whole_stage': False, 'native_enemy_behavior_verified': False, 'client_verified': False, 'cases': []}
    try:
        module = build()
        for stage, row in module['manifest']['metadata']['stages'].items():
            grid = GridTopology(row['map'])
            for cell in row['special_cells']['tile_fence']:
                assert not grid.passable(cell['row'], cell['col'])
                assert grid.tile(cell['row'], cell['col'])['passableMask'] == 2
                assert grid.tile(cell['row'], cell['col'])['buildableType'] == 1
        report['cases'].append({'case': 'all_native_map_cells_and_fence_options', 'passed': True})
        for stage, index in [('level_main_10-14', 22), ('level_main_10-15', 6)]:
            report['cases'].append({'case': stage + '_unshortened_route', 'passed': True, 'facts': route_case(stage, index)})
        report['passed'] = True
    except Exception:
        report['passed'] = False
        report['error'] = traceback.format_exc()
    report['source_after'] = {str(p): sha(p) for p in pins}
    report['source_guard_equal'] = report['source_after'] == before
    report['actual_exit'] = 0 if report['passed'] and report['source_guard_equal'] else 1
    (OUT / 'actual.v1.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'actual_exit': report['actual_exit'], 'error': report.get('error')}))
    return report['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
