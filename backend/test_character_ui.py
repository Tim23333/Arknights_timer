import unittest

from backend.app.character_ui import (
    CHARACTER_COLUMN_INDEX, default_character_precision,
    format_character_column, precision_column_defs,
)
from tools.character_status import CharacterInfo


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

    def test_damage_columns_use_runtime_battle_stats(self):
        character = CharacterInfo(1, damage_total=1234.5, healing_total=88.0)
        character.damage_by_type = {1: 1000.0, 2: 234.5}
        decimals = default_character_precision()
        self.assertEqual(
            format_character_column('damage_total', character, decimals),
            '1234.50')
        self.assertEqual(
            format_character_column('damage_physical', character, decimals),
            '1000.00')


if __name__ == '__main__':
    unittest.main()
