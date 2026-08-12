import json
import unittest
from dataclasses import dataclass, field

from backend.app.battle_session_cache import BattleSessionCache
from tools.enemy_health.enemy_reader import EnemyInfo


@dataclass
class _Character:
    name: str
    damage_total: float = 0.0
    buffs: list = field(default_factory=list)


def _runtime(frame=100, state=2, hp=100.0, ok=True):
    enemy = EnemyInfo(0x1234)
    enemy.eid = 'enemy_test'
    enemy.name = '测试敌人'
    enemy.hp = hp
    enemy.max_hp = 200.0
    return {
        'ok': ok,
        'state': state,
        'speed_level': 1,
        'time_scale': 1.0,
        'play_time': frame / 30,
        'fixed_frame': frame,
        'frame_consistent': True,
        'enemies': [enemy] if ok else [],
        'characters': [_Character('测试干员', 321.5)] if ok else [],
        'character_stats_history': [_Character('已离场干员', 99.0)],
    }


def _rng(role='imp', total=2, start=1, engine_id=100):
    return {
        'id': engine_id,
        'role': role,
        'label': role,
        'total': total,
        'cursor': total,
        'cursor2': total + 1,
        'status': 'ok',
        'history': [
            {'seq': seq, 'frac': seq / 10, 'raw': 0xDEADBEEF}
            for seq in range(start, total + 1)
        ],
        'predictions': [{'n': 1, 'frac': 0.75, 'raw': 0x12345678}],
    }


class BattleSessionCacheTests(unittest.TestCase):
    def test_finished_empty_frame_keeps_last_complete_playing_runtime(self):
        cache = BattleSessionCache('3.5.0')
        cache.observe_runtime(_runtime(120, hp=87.5), {'stageId': 'main_01-07'})
        cache.observe_runtime(_runtime(121, state=3, ok=False),
                              {'stageId': 'main_01-07'})

        bundle = cache.bundle()
        self.assertTrue(bundle['session']['finalized'])
        self.assertEqual(bundle['session']['finalReason'], 'battle_finished')
        self.assertEqual(bundle['runtime']['battle']['fixed_frame'], 120)
        self.assertEqual(bundle['runtime']['enemies'][0]['hp'], 87.5)
        self.assertEqual(bundle['runtime']['characters'][0]['damage_total'], 321.5)
        json.dumps(bundle, ensure_ascii=False)

    def test_address_failure_freezes_without_overwriting_last_complete_frame(self):
        cache = BattleSessionCache()
        cache.observe_runtime(_runtime(500, hp=66.0))
        cache.finalize('address_invalid')
        cache.observe_runtime({
            'ok': False, 'state': -1, 'fixed_frame': None,
            'enemies': [], 'characters': [],
        })
        self.assertEqual(cache.bundle()['runtime']['enemies'][0]['hp'], 66.0)

    def test_same_stage_restart_creates_new_session_on_frame_rollback(self):
        cache = BattleSessionCache()
        cache.observe_runtime(_runtime(900), {'stageId': 'same_stage'})
        old_session = cache.bundle()['session']['id']
        cache.finalize('battle_finished')
        cache.observe_runtime(_runtime(10, hp=190.0), {'stageId': 'same_stage'})
        bundle = cache.bundle()
        self.assertNotEqual(bundle['session']['id'], old_session)
        self.assertFalse(bundle['session']['finalized'])
        self.assertEqual(bundle['runtime']['battle']['fixed_frame'], 10)
        self.assertEqual(bundle['runtime']['enemies'][0]['hp'], 190.0)

    def test_same_stage_finished_then_playing_starts_new_session_even_without_rollback(self):
        cache = BattleSessionCache()
        cache.observe_runtime(_runtime(100), {'stageId': 'same_stage'})
        old_session = cache.bundle()['session']['id']
        cache.finalize('battle_finished')
        cache.observe_runtime(_runtime(120, hp=180.0), {'stageId': 'same_stage'})
        self.assertNotEqual(cache.bundle()['session']['id'], old_session)
        self.assertEqual(cache.bundle()['runtime']['enemies'][0]['hp'], 180.0)

    def test_pending_stage_scan_does_not_replace_completed_battle_before_playing(self):
        cache = BattleSessionCache()
        old_export = {'stage': {'stageId': 'old'}, 'enemySpawns': [{'id': '1'}]}
        cache.observe_stage({'stageId': 'old'}, old_export)
        cache.observe_runtime(_runtime(400), {'stageId': 'old'})
        cache.finalize('battle_finished')
        cache.observe_stage({'stageId': 'new'},
                            {'stage': {'stageId': 'new'}, 'enemySpawns': []})
        self.assertEqual(cache.bundle()['stage']['stageId'], 'old')
        self.assertEqual(cache.stage_export()['stage']['stageId'], 'old')

        cache.observe_runtime(_runtime(1, hp=200.0), {'stageId': 'new'})
        self.assertEqual(cache.bundle()['stage']['stageId'], 'new')
        self.assertEqual(cache.stage_export()['stage']['stageId'], 'new')

    def test_deploy_empty_failure_does_not_erase_operations(self):
        cache = BattleSessionCache()
        cache.observe_deploy(
            [{'op': 0, 'timestamp': 1.2}],
            {'state': 2, 'playTime': 1.2},
            {'stageId': 'stage'}, squad=[{'charId': 'char_test'}])
        cache.observe_deploy([], {'state': 3, 'playTime': 10.0})
        deploy = cache.deploy_state()
        self.assertEqual(len(deploy['liveEvents']), 1)
        self.assertEqual(deploy['squad'][0]['charId'], 'char_test')

    def test_rng_history_merges_and_raw_values_are_not_cached(self):
        cache = BattleSessionCache()
        cache.observe_rng({'imp': _rng(total=2, start=1)})
        cache.observe_rng({'imp': _rng(total=4, start=3)})
        role = cache.rng_role('imp')
        self.assertEqual([item['seq'] for item in role['history']], [1, 2, 3, 4])
        self.assertNotIn('raw', json.dumps(role))

    def test_new_rng_object_cannot_overwrite_finalized_battle(self):
        cache = BattleSessionCache()
        cache.observe_runtime(_runtime(300))
        cache.observe_rng({'imp': _rng(total=8, start=7, engine_id=100)})
        cache.finalize('battle_finished')
        cache.observe_rng({'imp': _rng(total=0, start=1, engine_id=200)})
        self.assertEqual(cache.rng_role('imp')['id'], 100)
        self.assertEqual(cache.rng_role('imp')['total'], 8)

    def test_old_rng_tracker_cannot_leak_into_new_battle_cache(self):
        cache = BattleSessionCache()
        cache.observe_runtime(_runtime(300))
        cache.observe_rng({'imp': _rng(total=8, start=7, engine_id=100)})
        cache.finalize('battle_finished')
        cache.observe_runtime(_runtime(1, hp=200.0))
        cache.observe_rng({'imp': _rng(total=8, start=7, engine_id=100)})
        self.assertIsNone(cache.rng_role('imp'))
        cache.observe_rng({'imp': _rng(total=0, start=1, engine_id=200)})
        self.assertEqual(cache.rng_role('imp')['id'], 200)


if __name__ == '__main__':
    unittest.main()
