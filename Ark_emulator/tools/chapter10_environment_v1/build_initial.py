"""Exact chapter10 route/map operands bound to existing generic tile mechanics."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from tools.build_reference_stage_scenario_v2 import map_plan, route_ir

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'packages/campaign/chapter10_source_prepare/source.plan.v1.json'
SOURCE = ROOT / 'packages/campaign/chapter10_source_prepare/environment.native.v1.json'
TRANSITION = 'rule/ch10/environment/living_transition'


def build():
    plan = json.loads(PLAN.read_bytes())
    source = json.loads(SOURCE.read_bytes())
    stages = {}
    for name, row in plan['stages'].items():
        native = row['native_document']
        mp = map_plan(native)
        profiles = {'tile_telin': {'type': 'route_checkpoint_portal', 'role': 'entry'},
                    'tile_telout': {'type': 'route_checkpoint_portal', 'role': 'exit'}}
        cells = {key: [{'row': i // mp['cols'], 'col': i % mp['cols'], 'tile': deepcopy(tile)}
                       for i, tile in enumerate(mp['tiles']) if tile['tileKey'] == key]
                 for key in ('tile_telin', 'tile_telout', 'tile_fence')}
        if cells['tile_fence']:
            expected = {'buildableType': 1, 'passableMask': 2, 'heightType': 'LOWLAND'}
            assert all({key: cell['tile'][key] for key in expected} == expected for cell in cells['tile_fence'])
            assert all(cell['tile']['blackboard'] is None and cell['tile']['effects'] is None for cell in cells['tile_fence'])
            profiles['tile_fence'] = {'type': 'declared_static_tile', 'expected_options': expected,
                                     'expected_blackboard': None, 'expected_effects': None}
        mp['tile_mechanics'] = profiles
        routes, pairs = {}, []
        for index in row['features']['used_routes']:
            route = route_ir(native['routes'][index], mp['rows'])
            if any(cp['type'] in ('DISAPPEAR', 'APPEAR_AT_POS') for cp in route['checkpoints']):
                route['transition_policy'] = {'rule': TRANSITION, 'parameters': {
                    'hidden_effects': 'reject', 'hidden_auras': 'suspend',
                    'launched_source_effects': 'retain', 'resource_timers': 'continue'}}
            if any(any((cp.get('reachOffset') or {}).values()) for cp in route['checkpoints']):
                route['reach_offset_policy'] = {'rule': 'rule/ch10/environment/checkpoint_cartesian',
                                               'parameters': {'axis_signs': {'row': -1, 'col': 1}}}
            last, hidden, entry = route['startPosition'], False, None
            for cp_index, cp in enumerate(route['checkpoints']):
                if cp['type'] == 'MOVE':
                    last = cp['position']
                elif cp['type'] == 'DISAPPEAR':
                    assert not hidden
                    hidden, entry = True, deepcopy(last)
                    assert mp['tiles'][entry['row'] * mp['cols'] + entry['col']]['tileKey'] == 'tile_telin'
                elif cp['type'] == 'APPEAR_AT_POS':
                    assert hidden
                    exit_pos = deepcopy(cp['position'])
                    assert mp['tiles'][exit_pos['row'] * mp['cols'] + exit_pos['col']]['tileKey'] == 'tile_telout'
                    pairs.append({'route': index, 'appear_checkpoint': cp_index, 'entry': entry,
                                  'exit': exit_pos, 'native_appear': deepcopy(native['routes'][index]['checkpoints'][cp_index])})
                    hidden, last = False, exit_pos
            assert not hidden
            routes[str(index)] = route
        assert len(pairs) == (8 if name == 'level_main_10-14' else 7)
        stages[name] = {'map': mp, 'routes': routes, 'portal_pairs': pairs, 'special_cells': cells,
                        'native_options': deepcopy(native['options'])}
    return {'schemaVersion': 2, 'manifest': {'id': 'package/ch10/environment/native_v1', 'metadata': {
        'source_locks': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                         (PLAN, SOURCE, Path(__file__), ROOT / 'tools/build_reference_stage_scenario_v2.py')},
        'native_prefabs': source['prefabs'], 'stages': stages,
        'reference_policy': 'Exact native map operands overlay empty prefab defaults. Only declared DISAPPEAR/WAIT/APPEAR executes portals. No nearest-pair inference. Fence ground exclusion/flight allowance and melee build mask retained.',
        'client_verified': False, 'whole_stage_executed': False}},
        'rules': [{'id': TRANSITION, 'kind': 'rule', 'contract': 'movement.transition',
                   'implementation': {'type': 'provider', 'provider': 'ark.movement.living_transition'}},
                  {'id': 'rule/ch10/environment/checkpoint_cartesian', 'kind': 'rule', 'contract': 'movement.checkpoint',
                   'implementation': {'type': 'provider', 'provider': 'model.movement.checkpoint'}},
                  {'id': 'rule/ch10/environment/diagonal_path', 'kind': 'calculation_rule',
                   'extends': 'rule/ark_movement_path', 'parameters': {'use_route_diagonal': True, 'corner_cut': False}},
                  {'id': 'rule/ch10/environment/native_speed', 'kind': 'rule', 'contract': 'movement.speed',
                   'implementation': {'type': 'expression', 'expression': 'inputs.movement_parameters.base_speed * parameters.multiplier'},
                   'parameters': {'multiplier': .5}}]}


if __name__ == '__main__':
    output = ROOT / 'packages/campaign/chapter10_consumers/environment/module.v1.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    assert not output.exists()
    output.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'path': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}))
