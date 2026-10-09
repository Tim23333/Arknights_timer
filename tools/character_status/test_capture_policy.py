"""Capture switches must stop exclusive IO and cannot relabel cached values."""

import struct
import unittest
from unittest.mock import Mock

from tools.character_status.character_reader import CharacterInfo, CharacterReader
from tools.enemy_health import game_structs as gs
from tools.enemy_health.enemy_reader import EnemyInfo, EnemyReader


class _Policy:
    generation = 7

    def __init__(self, enabled=()):
        self.selected = set(enabled)

    def enabled(self, field_id, layer='collect'):
        return field_id in self.selected

    def group_enabled(self, domain, group):
        from backend.app.field_policy import FIELD_REGISTRY
        return any(spec.domain == domain and spec.group == group
                   and self.enabled(spec.id) for spec in FIELD_REGISTRY.values())


class _Memory:
    @staticmethod
    def is_ptr(value):
        return isinstance(value, int) and value >= 0x1000


class CapturePolicyTests(unittest.TestCase):
    def test_departure_metadata_retains_observed_frame_but_never_invents_one(self):
        from backend.app.field_policy import PolicyStore
        self.enemy.set_capture_policy(PolicyStore().snapshot())
        info = EnemyInfo(0)
        info.eid, info.planned, info.lifecycle = 'enemy_test', True, 'departed'
        info.end_reason, info.end_frame = 'death', 95
        self.enemy._stamp_fields(info, 110, historical=True)
        self.assertEqual(info.field_states['enemy.end_frame']['sourceFrame'], 95)
        self.assertEqual(info.field_states['enemy.end_frame']['collectionState'], 'historical')
        info.end_frame, info.end_reason = None, ''
        self.enemy._stamp_fields(info, 111, historical=True)
        self.assertEqual(info.field_states['enemy.end_frame']['collectionState'], 'unavailable')
        self.assertEqual(info.field_states['enemy.end_reason']['collectionState'], 'unavailable')

    def test_never_sampled_departed_enemy_retains_known_identity_and_lifecycle(self):
        # ROOT CAUSE: blanket historical stamping required an earlier live sample
        # even for identity and lifecycle already known from the spawn schedule.
        from backend.app.field_policy import PolicyStore
        from backend.app.services.websocket_api import WebSocketApi
        store = PolicyStore()
        self.enemy.set_capture_policy(store.snapshot())
        info = EnemyInfo(0)
        info.eid, info.name, info.code = 'enemy_test', '测试敌人', 'T1'
        self.enemy._handbook_codes = {'enemy_test': 'T1'}
        info.planned, info.lifecycle = True, 'departed'
        self.enemy._stamp_fields(info, 110, historical=True)
        self.assertEqual(info.field_states['enemy.name']['collectionState'], 'static')
        self.assertEqual(info.field_states['enemy.code']['collectionState'], 'static')
        self.assertEqual(info.field_states['enemy.life_status']['collectionState'], 'current')
        self.assertEqual(info.field_states['enemy.hp']['collectionState'], 'unavailable')
        api = WebSocketApi(False, 'test', policy_provider=store.snapshot)
        api.publish_runtime({'fixed_frame': 110, 'enemies': [info]})
        row = api.local_snapshot()['enemies']['items'][0]
        self.assertEqual(row['name'], '测试敌人')
        self.assertEqual(row['code'], 'T1')
        self.assertEqual(row['lifecycle'], 'departed')
        self.assertNotIn('hp', row)

    def test_code_cannot_fall_back_to_local_enemy_database(self):
        self.enemy._db = {'enemy_test': {'name': '旧名称', 'code': 'LOCAL'}}
        self.assertEqual(self.enemy._remember_enemy_name('enemy_test', '内存名称'), ('内存名称', ''))

    def test_pending_enemy_lifecycle_is_known_without_a_runtime_instance(self):
        from backend.app.field_policy import PolicyStore
        self.enemy.set_capture_policy(PolicyStore().snapshot())
        info = EnemyInfo(0)
        info.eid, info.name, info.planned, info.lifecycle = 'enemy_test', '测试敌人', True, 'pending'
        self.enemy._stamp_fields(info, 110)
        self.assertEqual(info.field_states['enemy.name']['collectionState'], 'static')
        self.assertEqual(info.field_states['enemy.life_status']['collectionState'], 'current')
        self.assertEqual(info.field_states['enemy.hp']['collectionState'], 'unavailable')

    def test_handbook_io_is_skipped_when_code_collection_is_disabled(self):
        self.enemy.mc.pid = 77
        self.enemy.set_capture_policy(_Policy({'enemy.name'}))
        self.enemy._handbook.load = Mock()
        self.enemy._load_handbook_codes()
        self.enemy._handbook.load.assert_not_called()
        self.assertEqual(self.enemy._handbook_codes, {})

    def test_code_uses_validated_memory_and_reenable_revalidates_known_root(self):
        self.enemy.mc.pid = 77
        self.enemy._db = {'enemy_test': {'name': '测试', 'code': 'LOCAL'}}
        self.enemy.set_capture_policy(_Policy({'enemy.name'}))
        self.enemy._handbook.load = Mock(return_value={'enemy_test': 'MEM'})
        enabled = _Policy({'enemy.name', 'enemy.code'})
        enabled.generation = 8
        self.enemy.set_capture_policy(enabled)
        self.enemy._handbook.load.assert_called_once_with(locate=False, log=self.enemy.log)
        self.assertEqual(self.enemy._remember_enemy_name('enemy_test'), ('测试', 'MEM'))

    def setUp(self):
        self.enemy = EnemyReader(mc=_Memory())
        self.character = CharacterReader(self.enemy)

    def test_attributes_only_decode_enabled_indices(self):
        data = bytearray(gs.Il2CppArray.ITEMS
                         + gs.AttributeType.E_NUM * gs.OBSCURED_FP_SIZE)
        struct.pack_into('<i', data, gs.Il2CppArray.MAX_LENGTH, gs.AttributeType.E_NUM)
        for index in range(gs.AttributeType.E_NUM):
            struct.pack_into('<QQ', data,
                             gs.Il2CppArray.ITEMS + index * gs.OBSCURED_FP_SIZE,
                             0, (index + 1) * gs.FP_ONE)
        info = EnemyInfo(0x2000)
        self.enemy._apply_cached_data(data, info, indices={1, 3})
        self.assertEqual(set(info.attributes), {1, 3})
        self.assertEqual(info.attributes[1], 2.0)

    def test_character_attribute_failure_does_not_reuse_previous_value(self):
        info = CharacterInfo(0x2000, attr_ptr=0x3000)
        self.character._attr_cached[info.addr] = 0x4000
        self.character._attr_snapshots[info.addr] = {0: 2500.0}
        self.character._batch = Mock(return_value=[None])
        self.character._refresh_attributes({info.addr: info})
        self.assertEqual(info.attributes, {})
        self.assertNotIn(info.addr, self.character._attr_snapshots)

    def test_character_capture_off_skips_exclusive_groups(self):
        self.character.set_capture_policy(_Policy())
        self.character._read_container = Mock(return_value=[0x2000])
        self.character._batch = Mock(return_value=[bytes(gs.CharacterFields.READ_SIZE)])
        self.character._fill_new_identities = Mock()
        for name in ('_refresh_attributes', '_refresh_runtime',
                     '_refresh_positions_and_blocking', '_refresh_damage_stats',
                     '_refresh_skills', '_refresh_buff_counts',
                     '_finalize_character_action'):
            setattr(self.character, name, Mock())
        snapshot = self.character.poll_fast()
        self.assertTrue(snapshot['ok'])
        self.character._refresh_attributes.assert_not_called()
        self.character._refresh_positions_and_blocking.assert_not_called()
        self.character._refresh_damage_stats.assert_not_called()
        self.character._refresh_skills.assert_not_called()
        self.character._refresh_buff_counts.assert_not_called()
        self.character._finalize_character_action.assert_not_called()
        self.assertEqual(snapshot['policy_generation'], 7)
        self.assertEqual(snapshot['characters'][0].field_states['character.hp']['collectionState'],
                         'not_collected')

    def test_enemy_runtime_failure_does_not_carry_previous_state(self):
        info = EnemyInfo(0x2000)
        info.state_ptr = 0x3000
        self.enemy._runtime_snapshot[info.addr] = {'state_id': gs.EnemyState.MOVE,
                                                  'shield': 456.0}
        self.enemy._chan = Mock()
        self.enemy._chan.batch_read.side_effect = lambda reqs: [None] * len(reqs)
        self.enemy._refresh_runtime_chan([info.addr], {info.addr: info})
        self.assertNotIn('state_id', self.enemy._runtime_snapshot[info.addr])
        self.assertNotIn('shield', self.enemy._runtime_snapshot[info.addr])

    def test_policy_switch_clears_value_caches_but_keeps_address_topology(self):
        self.enemy._attr_cache[0x2000] = 0x3000
        self.enemy._attr_snapshot[0x2000] = {0: 5000.0}
        self.enemy._runtime_snapshot[0x2000] = {'shield': 10.0}
        self.enemy.set_capture_policy(_Policy())
        self.assertEqual(self.enemy._attr_cache[0x2000], 0x3000)
        self.assertEqual(self.enemy._attr_snapshot, {})
        self.assertEqual(self.enemy._runtime_snapshot, {})

    def test_enemy_runtime_capture_off_reads_only_internal_state(self):
        info = EnemyInfo(0x2000)
        info.state_ptr = 0x3000
        info.shield_controller_ptr = 0x4000
        info.ep_ptr = 0x5000
        self.enemy.set_capture_policy(_Policy())
        requests = []
        self.enemy._chan = Mock()
        def read(reqs):
            requests.extend(reqs)
            return [bytes(size) for _address, size in reqs]
        self.enemy._chan.batch_read.side_effect = read
        self.enemy._refresh_runtime_chan([info.addr], {info.addr: info})
        self.assertEqual(requests, [(0x3000 + gs.StateMachineFields.CURRENT_STATE_ID, 0x10)])
        self.assertNotIn('shield', self.enemy._runtime_snapshot[info.addr])

    def test_unread_runtime_default_is_marked_unavailable(self):
        self.enemy.set_capture_policy(_Policy({'enemy.shield'}))
        info = EnemyInfo(0x2000)
        self.enemy._stamp_fields(info, 101)
        self.assertEqual(info.field_states['enemy.shield']['collectionState'], 'unavailable')
        self.assertEqual(info.field_states['enemy.shield']['sourceFrame'], 101)

    def test_disabled_details_do_not_read_memory(self):
        self.enemy.set_capture_policy(_Policy())
        self.character.set_capture_policy(_Policy())
        self.enemy._detail_batch_read = Mock()
        self.assertIsNone(self.enemy.read_enemy_detail(0x2000))
        self.assertIsNone(self.character.read_character_detail(0x2000))
        self.enemy._detail_batch_read.assert_not_called()

    def test_character_attribute_pointer_switch_drops_old_array(self):
        self.character._attr_sources[0x2000] = 0x3000
        self.character._attr_cached[0x2000] = 0x4000
        self.character._batch = Mock(side_effect=lambda reqs: [None] * len(reqs))
        info = CharacterInfo(0x2000, attr_ptr=0x5000)
        self.character._refresh_attributes({info.addr: info})
        self.assertNotIn(info.addr, self.character._attr_cached)
        self.assertEqual(info.attributes, {})

    def test_policy_switch_reloads_identity_values_when_reenabled(self):
        self.character._identities[0x2000] = {'cid': 'char_test', 'name': ''}
        self.enemy._names[0x2000] = ('enemy_test', '', '')
        self.enemy.set_capture_policy(_Policy({'enemy.name'}))
        self.character.set_capture_policy(_Policy({'character.name'}))
        self.assertEqual(self.enemy._names, {})
        self.assertEqual(self.character._identities, {})

    def test_derived_enemy_fields_require_successful_dependency_reads(self):
        from backend.app.field_policy import PolicyStore
        self.enemy.set_capture_policy(PolicyStore().snapshot())
        info = EnemyInfo(0x2000)
        info.action = {'phase': 'idle', 'next_action': 'wrong prediction'}
        self.enemy._runtime_snapshot[info.addr] = {'state_id': 2}
        self.enemy._stamp_fields(info, 100)
        self.assertEqual(info.field_states['enemy.next_action']['collectionState'], 'unavailable')
        self.assertEqual(info.field_states['enemy.action_phase']['collectionState'], 'unavailable')
        self.assertEqual(info.field_states['enemy.hp']['collectionState'], 'unavailable')

    def test_dependent_character_fields_do_not_claim_success_from_defaults(self):
        from backend.app.field_policy import PolicyStore
        self.character.set_capture_policy(PolicyStore().snapshot())
        info = CharacterInfo(0x2000, action={'phase': 'idle'})
        self.character._runtime_snapshots[info.addr] = {'state_id': 1}
        self.character._stamp_fields(info, 100)
        self.assertEqual(info.field_states['character.next_action']['collectionState'], 'unavailable')
        self.assertEqual(info.field_states['character.hp']['collectionState'], 'unavailable')

    def test_historical_enemy_source_is_not_rewritten_to_current_frame(self):
        from backend.app.field_policy import PolicyStore
        self.enemy.set_capture_policy(PolicyStore().snapshot())
        info = EnemyInfo(0x2000)
        info.lifecycle = 'departed'
        info.field_states['enemy.hp'] = {'collectionState': 'current', 'sourceFrame': 91,
                                       'latestKnownFrame': 91, 'acceptedFrame': 91,
                                       'generation': 0, 'reason': ''}
        self.enemy._stamp_fields(info, 110, historical=True)
        self.assertEqual(info.field_states['enemy.hp']['sourceFrame'], 91)
        self.assertEqual(info.field_states['enemy.hp']['collectionState'], 'historical')

    def test_active_planned_enemy_keeps_successful_attributes_and_hp(self):
        # ROOT CAUSE: planned identifies membership in the spawn schedule, not
        # whether an instance has entered the field. The policy adapter rejected
        # successful reads for all active enemies still bound to that schedule.
        from backend.app.field_policy import PolicyStore
        self.enemy.set_capture_policy(PolicyStore().snapshot())
        info = EnemyInfo(0x2000)
        self.enemy._copy_plan_metadata(info, {'roster_id': 1, 'spawn_order': 1}, 'active')
        info.attributes = {0: 28000.0, 1: 500.0}
        self.enemy._stamp_fields(info, 100)
        self.assertTrue(info.planned)
        self.assertEqual(info.field_states['enemy.attr_0']['collectionState'], 'current')
        self.assertEqual(info.field_states['enemy.attr_1']['collectionState'], 'current')
        self.assertEqual(info.field_states['enemy.hp']['collectionState'], 'current')
        self.assertEqual(info.field_states['enemy.attr_0']['sourceFrame'], 100)

    def test_pending_enemy_attributes_do_not_claim_current_read_success(self):
        from backend.app.field_policy import PolicyStore
        self.enemy.set_capture_policy(PolicyStore().snapshot())
        info = EnemyInfo(0x2000)
        self.enemy._copy_plan_metadata(info, {'roster_id': 1, 'spawn_order': 1}, 'pending')
        info.attributes = {0: 28000.0}  # Static/old values are not a live HP read.
        self.enemy._stamp_fields(info, 100)
        self.assertEqual(info.field_states['enemy.attr_0']['collectionState'], 'unavailable')
        self.assertEqual(info.field_states['enemy.hp']['collectionState'], 'unavailable')

    def test_active_planned_enemy_failed_attribute_stays_unavailable(self):
        from backend.app.field_policy import PolicyStore
        self.enemy.set_capture_policy(PolicyStore().snapshot())
        info = EnemyInfo(0x2000)
        self.enemy._copy_plan_metadata(info, {'roster_id': 1, 'spawn_order': 1}, 'active')
        self.enemy._stamp_fields(info, 100)
        self.assertEqual(info.field_states['enemy.attr_0']['collectionState'], 'unavailable')
        self.assertEqual(info.field_states['enemy.hp']['collectionState'], 'unavailable')

    def test_active_planned_enemy_disabled_attribute_is_not_collected(self):
        self.enemy.set_capture_policy(_Policy({'enemy.hp'}))
        info = EnemyInfo(0x2000)
        self.enemy._copy_plan_metadata(info, {'roster_id': 1, 'spawn_order': 1}, 'active')
        info.attributes = {0: 28000.0}
        self.enemy._stamp_fields(info, 100)
        self.assertEqual(info.field_states['enemy.attr_0']['collectionState'], 'not_collected')
        self.assertEqual(info.field_states['enemy.hp']['collectionState'], 'unavailable')

    def test_disabled_element_damage_never_enters_source_layout_batch(self):
        self.character.set_capture_policy(_Policy({'character.damage_total'}))
        self.enemy.bc_addr = 0x2000
        self.character._damage_logger_addr = 0x3000
        self.character._damage_stats_addr = 0x4000
        self.character._damage_list_addr = 0x5000
        self.character._damage_list_signature = (0x6000, 1)
        self.character._damage_entries = {'char_test': {'addr': 0x7000, 'lists': {
            'elements': {'list': 0x8000, 'data': 0x9000, 'count': 3},
            'breaks': {'list': 0xA000, 'data': 0xB000, 'count': 3}}}}
        batches = []
        self.character._batch = lambda reqs: (batches.append(list(reqs)) or [None] * len(reqs))
        self.character._rebuild_damage_layout = Mock()
        self.character._refresh_damage_layout()
        addresses = {addr for batch in batches for addr, _size in batch}
        self.assertNotIn(0x8000, addresses)
        self.assertNotIn(0x9000, addresses)
        self.assertNotIn(0xA000, addresses)
        self.assertNotIn(0xB000, addresses)

    def test_failed_clock_cannot_reuse_previous_successful_frame(self):
        self.enemy.bc_addr = 0x2000
        self.enemy._bc_static_fields = 0x3000
        self.enemy._fixed_frame_snap = 99
        self.enemy._scheduler_time_snap = 7.5
        self.enemy._bc_snap = (2, 1, 1.0, 7.5)
        self.enemy._chan = Mock()
        self.enemy._chan.batch_read.side_effect = lambda reqs: [
            None if addr == 0x3000 + gs.BattleControllerStaticFields.FIXED_FRAME_COUNT
            else bytes(size) for addr, size in reqs]
        result = self.enemy._poll_fast_impl()
        self.assertFalse(result['ok'])
        self.assertIsNone(self.enemy._fixed_frame_snap)
        self.assertIsNone(self.enemy._scheduler_time_snap)
        self.assertIsNone(self.enemy._bc_snap)

    def test_failed_tail_clock_is_not_a_successful_cached_guard(self):
        self.enemy.bc_addr = 0x2000
        self.enemy._bc_static_fields = 0x3000
        self.enemy._fixed_frame_snap = 100
        self.enemy._chan = Mock()
        self.enemy._chan.batch_read.return_value = [None, bytes(0xC0)]
        guard = self.enemy.read_frame_guard_fast()
        self.assertIsNone(guard['frame'])
        self.assertEqual(self.enemy._fixed_frame_snap, 100)

    def test_failed_damage_entry_cannot_reuse_orphan_list_values(self):
        r = self.character
        self.enemy.bc_addr = 0x2000
        r._damage_logger_addr, r._damage_stats_addr = 0x3000, 0x4000
        r._damage_list_addr, r._damage_list_signature = 0x5000, (0x6000, 1)
        r._damage_pairs_signature = ((0x7000, 0x8000),)
        r._damage_entries = {'char_test': {'addr': 0x8000, 'key_ptr': 0x7000,
            'lists': {'types': {'list': 0x9000, 'data': 0xA000, 'count': 5}}}}
        blocks = {}
        blocks[0x2000 + gs.BattleControllerFields.M_LOGGER] = struct.pack('<Q', 0x3000)
        logger = bytearray(gs.BattleLoggerFields.READ_SIZE)
        struct.pack_into('<Q', logger, gs.BattleLoggerFields.STATS, 0x4000)
        blocks[0x3000] = logger
        stats = bytearray(gs.BattleStatsFields.READ_SIZE)
        struct.pack_into('<Q', stats, gs.BattleStatsFields.CHAR_ADVANCED_STATS, 0x5000)
        blocks[0x4000] = stats
        head = bytearray(0x20)
        struct.pack_into('<Q', head, gs.ListInternal.ITEMS, 0x6000)
        struct.pack_into('<i', head, gs.ListInternal.SIZE, 1)
        blocks[0x5000] = head
        blocks[0x6000 + gs.Il2CppArray.ITEMS] = struct.pack('<QQ', 0x7000, 0x8000)
        blocks[0xA000] = struct.pack('<5f', 0, 900, 0, 0, 0)
        r._batch = lambda reqs: [blocks.get(addr) for addr, _size in reqs]
        r._refresh_damage_layout()
        self.assertNotIn('char_test', r._damage_entries)
        self.assertFalse(r._damage_attribution_read_ok)

    def test_failed_damage_read_does_not_publish_previous_global_summary(self):
        self.character.set_capture_policy(_Policy({'character.damage_total',
            'character.global_total_damage', 'character.unattributed_damage'}))
        self.character._global_damage_summary.unattributed_damage_total = 50
        self.character._read_container = Mock(return_value=[])
        self.character._refresh_damage_layout = Mock()
        result = self.character.poll_fast()
        self.assertTrue(result['ok'])
        self.assertEqual(result['characters'], [])
        self.assertIsNone(result['global_damage_summary'])

    def test_policy_aware_enemy_detail_never_mutates_primary_runtime(self):
        self.enemy.set_capture_policy(_Policy({'enemy_detail.attributes'}))
        self.enemy._read_detail_frame = Mock(return_value=100)
        self.enemy._detail_batch_read = Mock(return_value=[bytes(gs.EnemyFields.READ_SIZE)])
        self.enemy._fill_name = Mock()
        self.enemy._refresh_runtime_chan = Mock()
        info = self.enemy.read_enemy_detail(0x2000, heavy_only=False)
        self.assertIsNotNone(info)
        self.enemy._fill_name.assert_not_called()
        self.enemy._refresh_runtime_chan.assert_not_called()

    def test_character_detail_identity_cannot_write_shared_primary_names(self):
        policy = _Policy({'character.name'})
        self.enemy._detail_context.active = True
        self.enemy._detail_context.policy = policy
        self.enemy._names[0x2000] = ('char_current', 'current name', '')
        block = bytearray(gs.BattleCharacterDataFields.READ_SIZE)
        struct.pack_into('<Q', block, gs.BattleCharacterDataFields.ID, 0x4000)
        self.character._batch = Mock(return_value=[block])
        self.enemy._read_strings = Mock(return_value={0x4000: 'char_old'})
        self.character._fill_new_identities({0x2000: CharacterInfo(0x2000, data_ptr=0x3000)})
        self.assertEqual(self.enemy._names[0x2000], ('char_current', 'current name', ''))

    def test_supported_current_dependencies_keep_successful_prediction(self):
        from backend.app.field_policy import PolicyStore
        self.enemy.set_capture_policy(PolicyStore().snapshot())
        info = EnemyInfo(0x2000)
        info.attributes = {0: 100.0}
        info.action = {'phase': 'idle'}
        self.enemy._skill_cd[info.addr] = []
        self.enemy._runtime_snapshot[info.addr] = {
            'state_id': 2, 'abnormal_flags': [], 'abnormal_combos': []}
        self.enemy._stamp_fields(info, 100)
        self.assertEqual(info.field_states['enemy.hp']['collectionState'], 'current')
        self.assertEqual(info.field_states['enemy.next_action']['collectionState'], 'current')

    def test_unimplemented_detail_fields_are_explicitly_unavailable(self):
        self.enemy._read_detail_frame = Mock(return_value=100)
        info = EnemyInfo(0x2000)
        policy = _Policy({'enemy_detail.attackRange', 'enemy_detail.effectFrames'})
        self.enemy._stamp_detail(info, 'enemy_detail', policy, 100, set())
        for key in ('attackRange', 'effectFrames'):
            state = info.field_states['enemy_detail.' + key]
            self.assertEqual(state['collectionState'], 'unavailable')
            self.assertEqual(state['reason'], 'unsupported_in_source')


if __name__ == '__main__':
    unittest.main()
