import unittest

from backend.app.character_ui import (
    CHARACTER_COLUMN_INDEX, build_character_overview,
    default_character_precision,
    format_character_column, precision_column_defs,
)
from tools.character_status import CharacterInfo
from tools.enemy_health import game_structs as gs


class CharacterUiTests(unittest.TestCase):
    def test_defaults_include_two_decimal_numeric_columns(self):
        decimals = default_character_precision()
        self.assertEqual(decimals['hp'], 2)
        self.assertEqual(decimals['sp'], 2)
        self.assertIn('detail', CHARACTER_COLUMN_INDEX)

    def test_precision_list_tracks_visible_columns(self):
        visible = {'hp', 'attr_1', 'name'}
        keys = {key for key, _label in precision_column_defs(visible)}
        self.assertEqual(keys, {'hp', 'attr_1'})

    def test_infinite_skill_timer_is_not_rendered_as_large_cd(self):
        character = CharacterInfo(1, name='测试', sp=10, max_sp=20)
        character.skill = {
            'name': '无限技能',
            'runtime': {
                'cooldown_remaining': 179999.0,
                'cooldown_period': 180000.0,
            },
        }
        text = format_character_column(
            'skill', character, default_character_precision())
        self.assertNotIn('180000', text)
        self.assertIn('SP', text)

    def test_ready_skill_always_keeps_stable_sp_text(self):
        character = CharacterInfo(1, name='测试', sp=50, max_sp=50)
        character.skill = {'name': '测试技能', 'ready': True, 'runtime': {}}
        text = format_character_column(
            'skill', character, default_character_precision())
        self.assertIn('SP 50.00/50', text)
        self.assertNotIn('就绪', text)

    def test_action_phase_and_countdown_are_rendered(self):
        character = CharacterInfo(1, state_id=gs.CharacterState.ATTACK)
        character.action = {
            'name': '普通攻击后摇', 'remaining_frames': 9,
            'remaining': 0.3, 'remaining_kind': '后摇剩余',
            'next_action': '等待游戏判定',
            'next_action_confidence': 'unselected',
        }
        self.assertEqual(
            format_character_column('action_phase', character, {}),
            '普通攻击后摇')
        self.assertEqual(
            format_character_column('remaining_time', character, {}),
            '9 帧 / 0.30 秒（后摇剩余）')
        self.assertEqual(
            format_character_column('next_action', character, {}),
            '[未预选] 等待游戏判定')

    def test_damage_columns_use_runtime_battle_stats(self):
        character = CharacterInfo(
            1, damage_total=1234.5, healing_total=88.0,
            global_total_damage=1500.0,
            unattributed_tracking_enabled=True)
        character.damage_by_type = {1: 1000.0, 2: 234.5}
        decimals = default_character_precision()
        self.assertEqual(
            format_character_column('damage_total', character, decimals),
            '1234.50')
        self.assertEqual(
            format_character_column('damage_physical', character, decimals),
            '1000.00')
        self.assertEqual(
            format_character_column('global_total_damage', character, decimals),
            '1500.00')

    def test_global_summary_marks_unavailable_damage_type_breakdown(self):
        character = CharacterInfo(
            -1, name='无来源&全局伤害统计', damage_total=250.0,
            global_total_damage=1500.0, unattributed_damage_total=250.0,
            is_global_damage_summary=True)
        decimals = default_character_precision()
        self.assertEqual(
            format_character_column('damage_total', character, decimals),
            '250.00')
        self.assertEqual(
            format_character_column('damage_element', character, decimals),
            '未分类')

    def test_overview_merges_duplicate_operator_and_excludes_tokens(self):
        first = CharacterInfo(
            1, cid='char_a', name='甲', damage_total=120.0,
            healing_total=30.0)
        duplicate = CharacterInfo(
            2, cid='char_a', name='甲', damage_total=120.0,
            healing_total=30.0)
        token = CharacterInfo(
            3, cid='token_a', name='召唤物', is_token=True,
            damage_total=999.0)
        global_row = CharacterInfo(
            -1, name='无来源&全局伤害统计', damage_total=500.0,
            is_global_damage_summary=True)
        rows = build_character_overview(
            [first, duplicate, token, global_row])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], '甲')
        self.assertEqual(rows[0]['damage'], 120.0)
        self.assertEqual(rows[0]['healing'], 30.0)


if __name__ == '__main__':
    unittest.main()
