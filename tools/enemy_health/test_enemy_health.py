# -*- coding: utf-8 -*-
import struct
import tempfile
import unittest
from pathlib import Path

from tools.enemy_health import game_structs as gs
from tools.enemy_health.enemy_reader import EnemyInfo, EnemyReader
from tools.enemy_health.memcore import find_running_emulator_adbs


class EnemyDetailModelTests(unittest.TestCase):
    def test_running_mumu_process_resolves_new_layout_adb(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / 'MuMu Player 12'
            process = root / 'nx_main' / 'MuMuNxMain.exe'
            adb = root / 'nx_device' / '12.0' / 'shell' / 'adb.exe'
            process.parent.mkdir(parents=True)
            adb.parent.mkdir(parents=True)
            process.touch()
            adb.touch()
            found = find_running_emulator_adbs([
                ('MuMuNxMain.exe', str(process)),
            ])
            self.assertEqual([item['adb_path'] for item in found], [str(adb)])

    def test_all_current_attributes_are_declared(self):
        self.assertEqual(gs.AttributeType.E_NUM, 38)
        self.assertEqual({idx for idx, _, _ in gs.ATTRIBUTE_DEFS},
                         set(range(0, 9)) | set(range(13, 38)))

    def test_anger_translation_and_damage_value(self):
        self.assertEqual(gs.ELEMENT_CN_NAMES[gs.ElementType.ANGER], '狂躁损伤')
        enemy = EnemyInfo(1)
        enemy.attributes[gs.AttributeType.MAX_EP] = 1000.0
        enemy.ep_remaining[gs.ElementType.ANGER] = 625.5
        self.assertEqual(enemy.element_damage(gs.ElementType.ANGER),
                         (374.5, 625.5, 1000.0))

    def test_runtime_none_slot_overrides_boss_base_ep_limit(self):
        enemy = EnemyInfo(1)
        enemy.attributes[gs.AttributeType.MAX_EP] = 1000.0
        enemy.ep_remaining[gs.ElementType.NONE] = 2000.0
        enemy.ep_remaining[gs.ElementType.SANITY] = 1325.0
        self.assertEqual(enemy.element_damage(gs.ElementType.SANITY),
                         (675.0, 1325.0, 2000.0))

    def test_common_statuses_are_combined(self):
        enemy = EnemyInfo(1)
        enemy.abnormal_flags[0] = 1       # STUNNED
        enemy.abnormal_flags[23] = 2      # COLD
        enemy.abnormal_flags[16] = 1      # FROZEN
        self.assertEqual(enemy.status_text(), '眩晕、冻结、寒冷')

    def test_short_counter_array_decoder(self):
        data = bytearray(gs.Il2CppArray.ITEMS + gs.AbnormalFlag.E_NUM * 2)
        struct.pack_into('<i', data, gs.Il2CppArray.MAX_LENGTH, gs.AbnormalFlag.E_NUM)
        struct.pack_into('<h', data, gs.Il2CppArray.ITEMS + 23 * 2, 3)
        values = EnemyReader._decode_short_array(bytes(data), gs.AbnormalFlag.E_NUM)
        self.assertEqual(values[23], 3)
        self.assertEqual(len(values), gs.AbnormalFlag.E_NUM)

    def test_status_resistance_uses_inverse_storage(self):
        enemy = EnemyInfo(1)
        enemy.attributes[gs.AttributeType.ONE_MINUS_STATUS_RESISTANCE] = 0.65
        self.assertAlmostEqual(enemy.status_resistance, 0.35)

    def test_spawn_plan_lifecycle_transitions(self):
        reader = EnemyReader(mc=object())
        reader._set_spawn_plan([
            {'key': 'enemy_a'}, {'key': 'enemy_a'}, {'key': 'enemy_b'},
        ], 'test/level')
        rows = reader._merge_enemy_roster([], 0)
        self.assertEqual([row.lifecycle for row in rows],
                         ['pending', 'pending', 'pending'])

        first = EnemyInfo(0x1000)
        first.eid = 'enemy_a'
        rows = reader._merge_enemy_roster([first], 1)
        self.assertEqual([row.lifecycle for row in rows],
                         ['active', 'pending', 'pending'])
        self.assertEqual(rows[0].spawn_order, 1)

        rows = reader._merge_enemy_roster([], 1)
        self.assertEqual([row.lifecycle for row in rows],
                         ['departed', 'pending', 'pending'])
        second = EnemyInfo(0x2000)
        second.eid = 'enemy_a'
        rows = reader._merge_enemy_roster([second], 2)
        self.assertEqual([row.lifecycle for row in rows],
                         ['departed', 'active', 'pending'])

    def test_midbattle_attach_uses_spawned_prefix(self):
        reader = EnemyReader(mc=object())
        reader._set_spawn_plan([{'key': 'enemy_a'} for _ in range(3)])
        live = [EnemyInfo(0x1000), EnemyInfo(0x2000)]
        for enemy in live:
            enemy.eid = 'enemy_a'
        rows = reader._merge_enemy_roster(live, 3)
        self.assertEqual([row.lifecycle for row in rows],
                         ['departed', 'active', 'active'])
        self.assertEqual([row.spawn_order for row in rows], [1, 2, 3])

    def test_spawn_eta_uses_scheduler_fixed_clock(self):
        reader = EnemyReader(mc=object())
        reader._set_spawn_plan([{
            'key': 'enemy_a', 'action_ptr': 0x1000, 'spawn_index': 0,
            'wave_index': 0, 'fragment_index': 0,
        }])
        reader._fragment_start_time = 50.0
        reader._action_queue_entries = [{
            'action_ptr': 0x1000, 'occurrence': 0, 'time_offset': 10.0,
        }]
        rows = reader._apply_spawn_timing(
            [reader._spawn_plan[0]['info']], scheduler_time=55.25)
        self.assertAlmostEqual(rows[0].spawn_eta, 4.75)
        self.assertEqual(rows[0].spawn_condition, '按当前调度计时')

    def test_future_wave_does_not_guess_specific_death_trigger(self):
        reader = EnemyReader(mc=object())
        reader._set_spawn_plan([
            {'key': 'enemy_a', 'wave_index': 0, 'fragment_index': 0},
            {'key': 'enemy_b', 'wave_index': 1, 'fragment_index': 0,
             'wave_max_wait': 15.0},
        ])
        reader._current_wave_index = 0
        rows = reader._apply_spawn_timing(
            [record['info'] for record in reader._spawn_plan], None)
        self.assertEqual(rows[1].spawn_condition,
                         '等待上一波清场或最长等待 15 秒后进入下一波')
        self.assertNotIn('enemy_a', rows[1].spawn_condition)

    def test_summoned_enemy_does_not_claim_same_key_scheduled_slot(self):
        reader = EnemyReader(mc=object())
        reader._set_spawn_plan([
            {'key': 'enemy_a', 'spawn_kind': 'scheduled'},
            {'key': 'enemy_a', 'spawn_kind': 'summoned'},
        ])
        enemy = EnemyInfo(0x1000)
        enemy.eid = 'enemy_a'
        enemy.is_summon = True
        rows = reader._merge_enemy_roster([enemy], 0)
        self.assertEqual([row.lifecycle for row in rows], ['pending', 'active'])

    def test_unit_manager_and_scheduler_sources_are_stably_deduplicated(self):
        self.assertEqual(
            EnemyReader._union_enemy_ptrs([3, 1, 2], [1, 4, 3]),
            [3, 1, 2, 4])

if __name__ == '__main__':
    unittest.main()
