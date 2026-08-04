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


if __name__ == '__main__':
    unittest.main()
