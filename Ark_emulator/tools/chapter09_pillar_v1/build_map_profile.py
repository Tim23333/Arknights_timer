"""Exact native C9 cell blackboards and static fence profiles, no key rewrites."""
import json
import hashlib
from pathlib import Path
from tools.chapter08_joint_v4.stage_converter_reusable_v2 import map_plan
from tools.chapter09_pillar_v1.bigforce import profile

ROOT = Path(__file__).resolve().parents[2]


def build(native):
    plan = map_plan(native); plan.pop('coordinate_conversion')
    plan['tile_mechanics'] = {}; plan['tile_cell_mechanics'] = {}
    for index, tile in enumerate(plan['tiles']):
        if tile.get('blackboard'):
            board = {r['key']: r['value'] for r in tile['blackboard']}
            key = str(index // plan['cols']) + ':' + str(index % plan['cols'])
            if board == {'base_force_level': 1.0}:
                plan['tile_cell_mechanics'][key] = profile()
            elif board == {'damage': 180.0, 'duration': 300.0, 'atk': 0.5, 'attack_speed': 50.0}:
                plan['tile_cell_mechanics'][key] = {'type': 'occupancy_buff_field',
                    'definition': 'unit/ch8/environment/infection_field', 'expected_blackboard': board}
            else:
                raise ValueError('C9 source tile operand requires an implemented exact consumer')
            if tile['tileKey'] == 'tile_bigforce':
                plan['tile_mechanics']['tile_bigforce'] = profile()
        elif tile['tileKey'] == 'tile_fence':
            authored = {'type': 'declared_static_tile',
                'expected_options': {k: tile[k] for k in ('buildableType', 'passableMask', 'heightType')},
                'expected_blackboard': tile['blackboard'], 'expected_effects': tile['effects']}
            if 'tile_fence' in plan['tile_mechanics'] and plan['tile_mechanics']['tile_fence'] != authored:
                raise ValueError('Conflicting static fence data')
            plan['tile_mechanics']['tile_fence'] = authored
    return plan


def main():
    source = ROOT / 'packages/campaign/chapter09_source_prepare/source.plan.v1.json'
    data = json.loads(source.read_bytes())
    output = ROOT / 'packages/campaign/chapter09_consumers/pillars/native_maps.profile.v1.json'
    if output.exists(): raise FileExistsError(output)
    value = {'schema': 'ark-sim/ch9-source-map-consumers/v1',
        'source_sha': hashlib.sha256(source.read_bytes()).hexdigest(),
        'builder_sha': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'maps': {key: build(stage['native_document']) for key, stage in data['stages'].items()},
        'required_cell_field_core': '11b414e7b4ddbff8c2fcd1689655b1c9c486047ae805bf79eda27417b5759899',
        'whole_stage': False}
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'source_native_maps': len(value['maps']), 'cells': {key: len(v['tile_cell_mechanics']) for key, v in value['maps'].items()}}))


if __name__ == '__main__': main()
