import struct
import unittest
from collections import deque

from tools.character_status.character_reader import (
    CharacterInfo, CharacterReader, _decrypt_obscured_int,
)
from tools.enemy_health import game_structs as gs
from tools.enemy_health.enemy_reader import EnemyReader


class CharacterReaderTests(unittest.TestCase):
    @staticmethod
    def _action_reader(now=10.0, frame=300):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        core = EnemyReader(mc=FakeMem())
        core._scheduler_time_snap = now
        core._fixed_frame_snap = frame
        core._frame_duration_snap = 1 / 30
        return CharacterReader(core)

    def test_obscured_int_decode(self):
        key = 0x12345678
        expected = 37
        data = struct.pack('<II', key, key ^ expected)
        self.assertEqual(_decrypt_obscured_int(data, 0), expected)

    def test_character_state_is_independent_from_enemy_state(self):
        self.assertEqual(gs.CharacterState.NAMES[1], '待机')
        self.assertEqual(gs.CharacterState.NAMES[4], '技能中')
        self.assertEqual(gs.CharacterState.NAMES[9], '冻结')

    def test_character_attack_post_action_uses_state_deadline(self):
        reader = self._action_reader(now=10.0, frame=300)
        info = CharacterInfo(0x1000, state_id=gs.CharacterState.ATTACK)
        info.action = {'state_time': 10.4, 'attack': {'casting': False}}
        reader._finalize_character_action(info)
        self.assertEqual(info.action['phase'], 'ability_recovery')
        self.assertEqual(info.action['remaining_frames'], 12)
        self.assertAlmostEqual(info.action['remaining'], 0.4)

    def test_character_manual_skill_ready_waits_for_player_not_timer(self):
        reader = self._action_reader()
        info = CharacterInfo(0x1000, state_id=gs.CharacterState.IDLE)
        info.skill = {'name': '测试技能', 'type': 1, 'ready': True, 'runtime': {}}
        reader._finalize_character_action(info)
        self.assertEqual(info.action['phase'], 'idle_skill_manual')
        self.assertEqual(info.action['remaining_kind'], '玩家操作')
        self.assertNotIn('remaining_frames', info.action)
        self.assertEqual(info.action['next_action_confidence'], 'unselected')
        self.assertEqual(info.action['next_action'], '等待游戏判定')

    def test_character_attack_uses_exact_spine_remaining_time(self):
        reader = self._action_reader(now=10.0, frame=300)
        info = CharacterInfo(0x1000, state_id=gs.CharacterState.ATTACK)
        info.action = {
            'animation_remaining': 1.2,
            'attack': {'casting': True, 'cast_start_frame': 270},
        }
        reader._finalize_character_action(info)
        self.assertEqual(info.action['phase'], 'ability_casting')
        self.assertEqual(info.action['remaining_frames'], 36)
        self.assertAlmostEqual(info.action['remaining'], 1.2)
        self.assertEqual(info.action['clock_source'], 'spine/state_gate')
        self.assertEqual(info.action['next_action_confidence'], 'unselected')

    def test_character_runtime_animator_falls_back_to_character_field(self):
        runtime_animator = 0x12345000
        block = bytearray(gs.CharacterFields.READ_SIZE)
        struct.pack_into('<Q', block, gs.UnitFields.ANIMATOR, 0)
        struct.pack_into('<Q', block, gs.CharacterFields.RUNTIME_ANIMATOR,
                         runtime_animator)
        info = CharacterReader._parse_main(0x1000, bytes(block))
        self.assertEqual(info.action['animator_addr'], runtime_animator)

    def test_status_text_and_unit_kind(self):
        info = CharacterInfo(0x1234, is_token=True)
        info.abnormal_flags[0] = 1  # STUNNED
        self.assertIn('眩晕', info.status_text())
        self.assertEqual(info.unit_kind, '召唤物/装置')

    def test_merge_detail_keeps_fast_runtime(self):
        live = CharacterInfo(1, sp=12, max_sp=20)
        live.skill = {
            'name': '技能', 'current_sp': 12, 'max_sp': 20,
            'runtime': {'cooldown_remaining': 1.25},
        }
        detail = CharacterInfo(1)
        detail.skill = {
            'name': '技能', 'description': '完整说明',
            'runtime': {'cooldown_remaining': 9.0},
            'blackboard': [{'key': 'atk_scale', 'value': 1.5}],
        }
        merged = CharacterReader.merge_detail(live, detail)
        self.assertEqual(merged.skill['runtime']['cooldown_remaining'], 1.25)
        self.assertEqual(merged.skill['description'], '完整说明')
        self.assertEqual(merged.skill['current_sp'], 12)

    def test_global_damage_summary_uses_unattributed_difference(self):
        snapshots = {
            'char_a': {'damage_total': 100.0},
            'token_b': {'damage_total': 25.5},
        }
        summary = CharacterReader._make_global_damage_summary(
            125.5, snapshots, 180.0, 54.5)
        self.assertTrue(summary.is_global_damage_summary)
        self.assertEqual(summary.name, '无来源&全局伤害统计')
        self.assertAlmostEqual(summary.global_total_damage, 180.0)
        self.assertAlmostEqual(summary.attributed_damage_total, 125.5)
        self.assertAlmostEqual(summary.unattributed_damage_total, 54.5)
        self.assertAlmostEqual(summary.damage_total, 54.5)
        self.assertAlmostEqual(summary.observed_enemy_damage_total, 180.0)

    def test_global_damage_summary_suppresses_float_noise(self):
        summary = CharacterReader._make_global_damage_summary(
            -100.0, {'char_a': {'damage_total': 100.0}}, 100.005, 0.005)
        self.assertEqual(summary.global_total_damage, 100.0)
        self.assertEqual(summary.unattributed_damage_total, 0.0)

    def test_disabled_unattributed_tracking_clears_observed_total(self):
        reader = CharacterReader.__new__(CharacterReader)
        reader._unattributed_tracking_enabled = True
        reader._observed_enemy_damage_total = 88.0
        reader._observed_enemy_hp = {(1, 1): 100.0}
        reader._seen_enemy_damage_keys = {(1, 1)}
        reader._committed_unattributed_damage = 88.0
        reader._pending_observed_damage = deque([[0.0, 10.0]])
        reader._pending_attributed_damage = deque()
        reader._last_observed_damage_total = 88.0
        reader._last_attributed_damage_total = 50.0
        reader._update_unattributed_tracking(False, None, 50.0)
        self.assertFalse(reader._unattributed_tracking_enabled)
        self.assertEqual(reader._observed_enemy_damage_total, 0.0)
        self.assertEqual(reader._observed_enemy_hp, {})

    def test_unattributed_reconciliation_waits_for_late_source_stats(self):
        reader = CharacterReader.__new__(CharacterReader)
        reader._observed_enemy_damage_total = 2269.79
        reader._last_observed_damage_total = 0.0
        reader._last_attributed_damage_total = 0.0
        reader._pending_observed_damage = deque()
        reader._pending_attributed_damage = deque()
        reader._committed_unattributed_damage = 0.0
        reader._reconcile_unattributed_damage(0.0, now=1.0)
        reader._observed_enemy_damage_total = 5883.59
        reader._reconcile_unattributed_damage(3458.0, now=1.2)
        self.assertEqual(reader._committed_unattributed_damage, 0.0)
        reader._reconcile_unattributed_damage(3458.0, now=2.1)
        self.assertAlmostEqual(
            reader._committed_unattributed_damage, 2425.59, places=2)

    def test_damage_history_keeps_retreated_operator_peak(self):
        reader = CharacterReader.__new__(CharacterReader)
        reader._damage_history = {}
        infos = {
            1: CharacterInfo(1, cid='char_a', name='甲',
                             damage_total=120.0, healing_total=30.0),
            2: CharacterInfo(2, cid='char_b', name='乙', is_token=True,
                             damage_total=50.0),
        }
        reader._record_damage_history(infos, {})
        # 撤退后不在 infos 中，但游戏仍保留统计条目时继续跟踪累计值。
        reader._record_damage_history({}, {
            'char_a': {'damage_total': 150.0, 'healing_total': 25.0}})
        history = reader._damage_history
        self.assertEqual(history['char_a']['damage_total'], 150.0)
        self.assertEqual(history['char_a']['healing_total'], 30.0)
        self.assertEqual(history['char_a']['name'], '甲')
        self.assertTrue(history['char_b']['is_token'])
        # 统计读数抖动/变小时历史峰值不回退。
        reader._record_damage_history({}, {
            'char_a': {'damage_total': 90.0, 'healing_total': 10.0}})
        self.assertEqual(history['char_a']['damage_total'], 150.0)
        self.assertEqual(history['char_a']['healing_total'], 30.0)

    def test_reset_damage_tracking_clears_history(self):
        reader = CharacterReader.__new__(CharacterReader)
        reader._damage_history = {'char_a': {'damage_total': 150.0}}
        reader._damage_snapshots = {'char_a': {}}
        reader._observed_enemy_hp = {(1, 1): 100.0}
        reader._seen_enemy_damage_keys = {(1, 1)}
        reader._pending_observed_damage = deque([[0.0, 10.0]])
        reader._pending_attributed_damage = deque()
        reader._reset_damage_tracking()
        self.assertEqual(reader._damage_history, {})
        self.assertEqual(reader._damage_snapshots, {})

    def test_every_runtime_group_is_refreshed_on_every_poll(self):
        reader = self._action_reader()
        addr = 0x1000
        main = bytes(gs.CharacterFields.READ_SIZE)
        calls = {name: 0 for name in (
            'container', 'attributes', 'runtime', 'blocking',
            'damage', 'skills', 'buffs')}

        def container():
            calls['container'] += 1
            return [addr]

        reader._read_container = container
        reader._batch = lambda reqs: [main for _req in reqs]
        reader._fill_new_identities = lambda infos: None
        reader._finalize_character_action = lambda info: info.action
        for method, key in (
                ('_refresh_attributes', 'attributes'),
                ('_refresh_runtime', 'runtime'),
                ('_refresh_positions_and_blocking', 'blocking'),
                ('_refresh_skills', 'skills'),
                ('_refresh_buff_counts', 'buffs')):
            setattr(reader, method,
                    lambda infos, key=key: calls.__setitem__(key, calls[key] + 1))

        def damage(infos, enemies=None, track_unattributed_damage=False):
            calls['damage'] += 1

        reader._refresh_damage_stats = damage
        self.assertTrue(reader.poll_fast()['ok'])
        self.assertTrue(reader.poll_fast()['ok'])
        self.assertTrue(all(value == 2 for value in calls.values()), calls)
        self.assertEqual(
            (reader.LIST_EVERY, reader.SKILL_EVERY,
             reader.BUFF_COUNT_EVERY, reader.DAMAGE_LAYOUT_EVERY),
            (1, 1, 1, 1))

    def test_stable_blocking_chain_uses_one_batch_without_skipping_layers(self):
        reader = self._action_reader()
        addr, manager, blocked_list = 0x1000, 0x2000, 0x3000
        info = CharacterInfo(addr, blocked_manager_ptr=manager)
        manager_data = bytearray(0x20)
        struct.pack_into('<i', manager_data,
                         gs.BlockedEnemyManagerFields.TOTAL_VOLUME, 2)
        struct.pack_into('<Q', manager_data,
                         gs.BlockedEnemyManagerFields.BLOCKED_ENEMIES,
                         blocked_list)
        list_data = bytearray(0x20)
        struct.pack_into('<i', list_data, gs.ListInternal.SIZE, 1)
        reader._blocked_layouts[addr] = {
            'manager': manager, 'list': blocked_list}
        memory = {manager: bytes(manager_data), blocked_list: bytes(list_data)}
        batches = []

        def batch(reqs):
            if reqs:
                batches.append(list(reqs))
            return [memory.get(ptr, b'') for ptr, _size in reqs]

        reader._batch = batch
        reader._refresh_positions_and_blocking({addr: info})
        self.assertEqual(len(batches), 1)
        self.assertEqual({ptr for ptr, _size in batches[0]},
                         {manager, blocked_list})
        self.assertEqual((info.blocked_count, info.blocked_total_volume), (1, 2))

    def test_stable_buff_chain_uses_one_batch_without_skipping_layers(self):
        reader = self._action_reader()
        addr, container, double, buff_list = 0x1000, 0x2000, 0x3000, 0x4000
        info = CharacterInfo(addr, buff_container_ptr=container)
        container_data = bytearray(0x30)
        struct.pack_into('<Q', container_data, gs.BuffContainerFields.M_BUFFS,
                         double)
        double_data = bytearray(0x28)
        struct.pack_into('<Q', double_data,
                         gs.DoubleBufferedListFields.M_INTERNAL_LIST, buff_list)
        list_data = bytearray(0x20)
        struct.pack_into('<i', list_data, gs.ListInternal.SIZE, 7)
        reader._buff_layouts[addr] = {
            'container': container, 'double': double, 'list': buff_list}
        memory = {
            container: bytes(container_data), double: bytes(double_data),
            buff_list: bytes(list_data),
        }
        batches = []

        def batch(reqs):
            if reqs:
                batches.append(list(reqs))
            return [memory.get(ptr, b'') for ptr, _size in reqs]

        reader._batch = batch
        reader._refresh_buff_counts({addr: info})
        self.assertEqual(len(batches), 1)
        self.assertEqual({ptr for ptr, _size in batches[0]},
                         {container, double, buff_list})
        self.assertEqual(info.buff_count, 7)

    def test_stable_skill_chain_uses_one_batch_without_skipping_layers(self):
        reader = self._action_reader()
        addr, skill, ability, timer = 0x1000, 0x2000, 0x3000, 0x4000
        info = CharacterInfo(addr, skill_ptr=skill)
        skill_data = bytearray(gs.BasicSkillFields.READ_SIZE)
        struct.pack_into('<Q', skill_data, gs.BasicSkillFields.ABILITY, ability)
        ability_data = bytearray(gs.AbilityFields.READ_SIZE)
        struct.pack_into('<Q', ability_data, gs.AbilityFields.COOLDOWN_TIMER, timer)
        timer_data = bytes(0x20)
        reader._skill_runtime_layouts[addr] = {
            'skill': skill, 'ability': ability, 'timer': timer}
        memory = {
            skill: bytes(skill_data), ability: bytes(ability_data),
            timer: timer_data,
        }
        batches = []

        def batch(reqs):
            if reqs:
                batches.append(list(reqs))
            return [memory.get(ptr, b'') for ptr, _size in reqs]

        reader._batch = batch
        reader._refresh_skills({addr: info})
        self.assertEqual(len(batches), 1)
        self.assertEqual({ptr for ptr, _size in batches[0]},
                         {skill, ability, timer})
        self.assertEqual(info.skill['runtime']['ability_addr'], ability)

    def test_stable_damage_layout_and_values_share_one_batch(self):
        reader = self._action_reader()
        bc, logger, stats = 0x1000, 0x2000, 0x3000
        outer_list, outer_items = 0x4000, 0x5000
        key, entry_addr = 0x6000, 0x7000
        list_ptrs = {'elements': 0x8000, 'breaks': 0x9000, 'types': 0xA000}
        item_ptrs = {'elements': 0xB000, 'breaks': 0xC000, 'types': 0xD000}
        counts = {'elements': 5, 'breaks': 5, 'types': 6}
        reader.core.bc_addr = bc
        reader._damage_logger_addr = logger
        reader._damage_stats_addr = stats
        reader._damage_list_addr = outer_list
        reader._damage_list_signature = (outer_items, 1)
        reader._damage_pairs_signature = ((key, entry_addr),)
        reader._damage_entries = {
            'char_test': {
                'addr': entry_addr, 'key_ptr': key,
                'lists': {
                    kind: {
                        'list': list_ptrs[kind],
                        'data': item_ptrs[kind] + gs.Il2CppArray.ITEMS,
                        'count': counts[kind],
                    }
                    for kind in list_ptrs
                },
            },
        }
        reader._tick = 1

        logger_slot = struct.pack('<Q', logger)
        logger_block = bytearray(gs.BattleLoggerFields.READ_SIZE)
        struct.pack_into('<Q', logger_block, gs.BattleLoggerFields.STATS, stats)
        stats_block = bytearray(gs.BattleStatsFields.READ_SIZE)
        struct.pack_into('<Q', stats_block,
                         gs.BattleStatsFields.CHAR_ADVANCED_STATS, outer_list)
        struct.pack_into('<f', stats_block, gs.BattleStatsFields.TOTAL_DAMAGE, 10.0)
        outer_head = bytearray(0x20)
        struct.pack_into('<Q', outer_head, gs.ListInternal.ITEMS, outer_items)
        struct.pack_into('<i', outer_head, gs.ListInternal.SIZE, 1)
        entry_block = bytearray(gs.CharAdvancedStatsFields.READ_SIZE)
        struct.pack_into('<f', entry_block,
                         gs.CharAdvancedStatsFields.OUTPUT_DAMAGE_TOTAL, -10.0)
        for kind, offset in (
                ('elements', gs.CharAdvancedStatsFields.OUTPUT_ELEMENT_DAMAGE_TOTAL),
                ('breaks', gs.CharAdvancedStatsFields.OUTPUT_EP_BREAK_COUNT),
                ('types', gs.CharAdvancedStatsFields.OUTPUT_DAMAGE_BY_TYPE_TOTAL)):
            struct.pack_into('<Q', entry_block, offset, list_ptrs[kind])

        memory = {
            bc + gs.BattleControllerFields.M_LOGGER: logger_slot,
            logger: bytes(logger_block), stats: bytes(stats_block),
            outer_list: bytes(outer_head),
            outer_items + gs.Il2CppArray.ITEMS: struct.pack('<QQ', key, entry_addr),
            entry_addr: bytes(entry_block),
        }
        for kind in list_ptrs:
            head = bytearray(0x20)
            struct.pack_into('<Q', head, gs.ListInternal.ITEMS, item_ptrs[kind])
            struct.pack_into('<i', head, gs.ListInternal.SIZE, counts[kind])
            memory[list_ptrs[kind]] = bytes(head)
        memory[item_ptrs['elements'] + gs.Il2CppArray.ITEMS] = struct.pack(
            '<5f', 0, 0, 0, 0, 0)
        memory[item_ptrs['breaks'] + gs.Il2CppArray.ITEMS] = struct.pack(
            '<5i', 0, 0, 0, 0, 0)
        memory[item_ptrs['types'] + gs.Il2CppArray.ITEMS] = struct.pack(
            '<6f', 0, 10, 0, 0, 0, 0)
        batches = []

        def batch(reqs):
            if reqs:
                batches.append(list(reqs))
            return [memory.get(ptr, b'')[:size] for ptr, size in reqs]

        reader._batch = batch
        reader._refresh_damage_layout()
        info = CharacterInfo(0xE000, cid='char_test')
        reader._refresh_damage_stats({info.addr: info})
        self.assertEqual(len(batches), 1)
        self.assertAlmostEqual(info.damage_total, 10.0)
        self.assertAlmostEqual(reader._battle_stats_total_damage, 10.0)


if __name__ == '__main__':
    unittest.main()
