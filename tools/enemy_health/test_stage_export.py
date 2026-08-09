# -*- coding: utf-8 -*-
import json
import unittest
from types import SimpleNamespace

from tools.enemy_health.stage_export import (
    SCHEMA_NAME, build_stage_export, classify_tile, normalize_map_snapshot,
)


class StageExportTests(unittest.TestCase):
    def test_tile_categories_cover_strategy_markers(self):
        self.assertEqual(classify_tile('tile_start'), 'enemy_spawn')
        self.assertEqual(classify_tile('tile_flystart'), 'enemy_spawn')
        self.assertEqual(classify_tile('tile_end'), 'friendly_goal')
        self.assertEqual(classify_tile('tile_wall', 1), 'highland')
        self.assertEqual(classify_tile('tile_volcano'), 'device')

    def test_snapshot_is_json_safe_and_keeps_spawn_lifecycle(self):
        info = SimpleNamespace(
            eid='enemy_1007_slime', name='源石虫', code='A1',
            lifecycle='departed', spawn_order=1, route_index=0,
            spawn_kind='scheduled', spawn_source='', spawn_condition='',
            spawn_frame=123, end_frame=456, end_reason='death',
        )
        record = {
            'info': info, 'key': info.eid, 'roster_id': -1, 'spawn_order': 1,
            'wave_index': 0, 'fragment_index': 0, 'action_index': 0,
            'spawn_index': 0, 'route_index': 0, 'spawn_kind': 'scheduled',
            'nominal_spawn_time': 2.0, 'spawn_frame': 123,
            'end_frame': 456, 'end_reason': 'death', 'managed': True,
        }
        reader = SimpleNamespace(
            _spawn_plan=[record], _runtime_spawn_plan=[], _roster_last={-1: info},
            _level_map_data={
                'mapId': 'map_test', 'rows': 1, 'cols': 2,
                'tiles': [
                    {'row': 0, 'col': 0, 'tileKey': 'tile_start'},
                    {'row': 0, 'col': 1, 'tileKey': 'tile_end'},
                ],
            },
            _routes_export=[{'index': 0, 'start': {'row': 0, 'col': 0},
                             'end': {'row': 0, 'col': 1}}],
            plan_level_id='level_test',
        )
        payload = build_stage_export(reader, {'code': 'T-1', 'name': '测试关'})
        self.assertEqual(payload['schema'], SCHEMA_NAME)
        self.assertEqual(payload['stage']['code'], 'T-1')
        self.assertEqual(payload['map']['tiles'][0]['category'], 'enemy_spawn')
        self.assertEqual(payload['enemySpawns'][0]['actualStartFrame'], 123)
        self.assertEqual(payload['enemySpawns'][0]['endFrame'], 456)
        self.assertEqual(payload['enemySpawns'][0]['endReason'], 'death')
        json.dumps(payload, ensure_ascii=False)

    def test_map_normalization_does_not_require_runtime_objects(self):
        result = normalize_map_snapshot({
            'rows': 1, 'cols': 1,
            'tiles': [{'row': 0, 'col': 0, 'tileKey': 'tile_telin'}],
        })
        self.assertEqual(result['tiles'][0]['category'], 'teleport_in')


if __name__ == '__main__':
    unittest.main()
