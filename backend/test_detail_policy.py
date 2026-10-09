"""Async detail isolation, policy cancellation and sampling provenance regressions."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from backend.app.field_policy import PolicyStore
from backend.desktop_app import EnemyPollWorker
from tools.character_status.character_reader import CharacterInfo
from tools.enemy_health.enemy_reader import EnemyInfo


class _InlineThread:
    def __init__(self, *, target, **kwargs):
        self.target = target

    def start(self):
        self.target()


class DetailPolicyTests(unittest.TestCase):
    def test_async_enemy_result_is_discarded_after_generation_changes(self):
        store = PolicyStore()
        policy = store.snapshot()
        reader = SimpleNamespace(bc_addr=0x3000)
        worker = EnemyPollWorker(reader, policy_provider=store.snapshot)
        worker._active_policy = policy
        worker.set_detail_target(0x2000)

        def read(addr, **kwargs):
            store.commit({'enemy.name': {'display': False}})
            return EnemyInfo(addr)
        reader.read_enemy_detail = Mock(side_effect=read)
        with patch('backend.desktop_app.threading.Thread', _InlineThread):
            worker._start_detail_refresh(0x2000)
        reader.read_enemy_detail.assert_called_once_with(0x2000, heavy_only=True, policy=policy)
        self.assertIsNone(worker._detail_heavy_cache)
        self.assertFalse(worker._detail_loading)

    def test_enemy_detail_does_not_mutate_basic_canonical_entity(self):
        reader = SimpleNamespace(bc_addr=0x3000)
        worker = EnemyPollWorker(reader)
        enemy = EnemyInfo(0x2000)
        worker.set_detail_target(enemy.addr)
        worker._detail_due = float('inf')
        worker._detail_heavy_cache = {
            'session': reader.bc_addr, 'identity': (enemy.id_ptr, enemy.data_ptr),
            'raw_attributes': {1: 700.0}, 'buffs': [{'key': 'test_buff'}],
            'field_states': {'enemy_detail.buffs': {'sourceFrame': 99,
                             'latestKnownFrame': 101, 'collectionState': 'current'}},
        }
        snapshot = {'ok': True, 'enemies': [enemy]}
        worker._append_detail(snapshot)
        self.assertEqual(enemy.raw_attributes, {})
        self.assertEqual(enemy.buffs, [])
        self.assertIsNot(snapshot['detail_enemy'], enemy)
        self.assertEqual(snapshot['detail_enemy'].raw_attributes[1], 700.0)
        self.assertEqual(snapshot['detail_enemy'].field_states['enemy_detail.buffs']['sourceFrame'], 99)

    def test_character_detail_does_not_mutate_basic_canonical_entity(self):
        reader = SimpleNamespace(bc_addr=0x3000)
        worker = EnemyPollWorker(reader)
        live = CharacterInfo(0x2000, cid='char_test', data_ptr=0x4000)
        detail = CharacterInfo(0x2000, cid='char_test', data_ptr=0x4000,
                               buffs=[{'key': 'test_buff'}])
        detail._detail_session = reader.bc_addr
        worker.set_character_detail_target(live.addr)
        worker._character_detail_due = float('inf')
        worker._character_detail_cache = detail
        snapshot = {'character_ok': True, 'characters': [live]}
        worker._append_character_detail(snapshot)
        self.assertEqual(live.buffs, [])
        self.assertIsNot(snapshot['detail_character'], live)
        self.assertEqual(snapshot['detail_character'].buffs, [{'key': 'test_buff'}])

    def test_actual_completion_updates_known_frame_without_rewriting_source(self):
        worker = EnemyPollWorker(SimpleNamespace(bc_addr=0), latest_frame_provider=lambda: 102)
        detail = EnemyInfo(0x2000)
        detail.field_states = {'enemy_detail.buffs': {'sourceFrame': 99,
                               'acceptedFrame': 100, 'collectionState': 'unavailable'}}
        worker._finish_detail_metadata(detail)
        record = detail.field_states['enemy_detail.buffs']
        self.assertEqual(record['sourceFrame'], 99)
        self.assertEqual(record['acceptedFrame'], 100)
        self.assertEqual(record['latestKnownFrame'], 102)
        self.assertEqual(record['collectionState'], 'unavailable')

    def test_enemy_address_reuse_cannot_replay_previous_details(self):
        worker = EnemyPollWorker(SimpleNamespace(bc_addr=0x3000))
        live = EnemyInfo(0x2000)
        live.id_ptr, live.data_ptr = 0x5000, 0x6000
        worker.set_detail_target(live.addr)
        worker._detail_due = float('inf')
        worker._detail_heavy_cache = {'session': 0x3000, 'identity': (0x4000, 0x6000),
                                      'buffs': [{'key': 'old_buff'}]}
        snapshot = {'ok': True, 'enemies': [live]}
        worker._append_detail(snapshot)
        self.assertEqual(snapshot['detail_enemy'].buffs, [])

    def test_external_address_reuse_cannot_replay_previous_details(self):
        requests = {'enemy_detail': {'scopeAll': True, 'rateHz': 1},
                    'character_detail': {'scopeAll': True, 'rateHz': 1}}
        worker = EnemyPollWorker(SimpleNamespace(bc_addr=0x3000),
                                 detail_request_provider=lambda: requests)
        enemy = EnemyInfo(0x2000)
        enemy.id_ptr, enemy.data_ptr = 0x5000, 0x6000
        old_enemy = EnemyInfo(enemy.addr)
        old_enemy.id_ptr, old_enemy.data_ptr = 0x4000, 0x6000
        character = CharacterInfo(0x7000, cid='char_new', data_ptr=0x8000)
        old_character = CharacterInfo(character.addr, cid='char_old', data_ptr=0x8000)
        worker._external_enemy_details = {enemy.addr: old_enemy}
        worker._external_character_details = {character.addr: old_character}
        worker._external_detail_due = float('inf')
        snapshot = {'ok': True, 'enemies': [enemy], 'characters': [character]}
        worker._append_external_details(snapshot)
        self.assertEqual(snapshot['external_enemy_details'], [])
        self.assertEqual(snapshot['external_character_details'], [])


if __name__ == '__main__':
    unittest.main()
