# -*- coding: utf-8 -*-
import struct
import unittest

from tools.enemy_health import game_structs as gs
from tools.enemy_health.buff_descriptions import (
    buff_chinese_name, describe_active_buff, describe_blackboard, describe_global_buff,
)
from tools.enemy_health.enemy_reader import EnemyInfo, EnemyReader


class EnemyDetailModelTests(unittest.TestCase):
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

    def test_buff_chinese_name_and_attribute_formula(self):
        self.assertEqual(buff_chinese_name({'key': 'common_silence_immue'}), '沉默免疫')
        buff = {
            'key': 'unknown_speed_buff',
            'attribute_modifiers': [{
                'name': '移动速度', 'addition': 0.0, 'multiplier': 0.0,
                'final_addition': 0.0, 'final_scaler': 0.7,
            }],
            'abnormal_flags': [], 'abnormal_immunes': [], 'abnormal_antis': [],
            'abnormal_combos': [], 'abnormal_combo_immunes': [], 'has_shield': False,
        }
        self.assertEqual(buff_chinese_name(buff), '移动速度调整')
        self.assertIn('移动速度：最终倍率 ×0.7', describe_active_buff(buff))

    def test_blackboard_and_known_global_buff_description(self):
        rows = [
            {'key': 'enemy', 'value': 0.0, 'value_str': 'enemy_1042_frostd'},
            {'key': 'physical', 'value': 1.0, 'value_str': ''},
            {'key': 'magical', 'value': 1.0, 'value_str': ''},
            {'key': 'damage_resistance', 'value': 0.7, 'value_str': ''},
            {'key': 'range_radius', 'value': 2.5, 'value_str': ''},
        ]
        self.assertIn('作用于物理伤害：是', describe_blackboard(rows))
        enemy = EnemyInfo(1)
        enemy.eid = 'enemy_1042_frostd'
        enemy.name = '寒霜'
        buff = {'key': 'damage_scale[type]', 'blackboard': rows,
                'applies_to_selected': True}
        desc = describe_global_buff(buff, enemy)
        self.assertIn('寒霜（enemy_1042_frostd）', desc)
        self.assertIn('物理、法术伤害抗性规则', desc)
        self.assertIn('不直接等同于固定减伤百分比', desc)


if __name__ == '__main__':
    unittest.main()
