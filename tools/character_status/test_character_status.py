import struct
import unittest

from tools.character_status.character_reader import (
    CharacterInfo, CharacterReader, _decrypt_obscured_int,
)
from tools.enemy_health import game_structs as gs


class CharacterReaderTests(unittest.TestCase):
    def test_obscured_int_decode(self):
        key = 0x12345678
        expected = 37
        data = struct.pack('<II', key, key ^ expected)
        self.assertEqual(_decrypt_obscured_int(data, 0), expected)

    def test_character_state_is_independent_from_enemy_state(self):
        self.assertEqual(gs.CharacterState.NAMES[1], '待机')
        self.assertEqual(gs.CharacterState.NAMES[4], '技能中')
        self.assertEqual(gs.CharacterState.NAMES[9], '冻结')

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


if __name__ == '__main__':
    unittest.main()
