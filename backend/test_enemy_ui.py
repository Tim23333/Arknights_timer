# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QPushButton

from backend.app.enemy_buff_descriptions import (
    buff_chinese_name, describe_active_buff, describe_blackboard, describe_global_buff,
)
from backend.app.enemy_ui import (
    EnemyDetailDialog, format_column_value, precision_column_defs, visible_enemy_rows,
)
from tools.enemy_health import game_structs as gs
from tools.enemy_health.enemy_reader import EnemyInfo


class EnemyUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_precision_columns_follow_current_visible_numeric_columns(self):
        visible = {'name', 'ep_sanity', 'attr_1', 'skill', 'detail'}
        self.assertEqual(
            precision_column_defs(visible),
            [('attr_1', '攻击'), ('ep_sanity', '神经损伤'), ('skill', '技能 CD')],
        )

    def test_column_specific_precision_for_attribute_and_element_damage(self):
        enemy = EnemyInfo(1)
        enemy.attributes[gs.AttributeType.ATK] = 123.456
        enemy.attributes[gs.AttributeType.MAX_EP] = 1000.0
        enemy.ep_remaining[gs.ElementType.SANITY] = 625.5
        decimals = {'default': 4, 'attr_1': 2, 'ep_sanity': 1}
        self.assertEqual(format_column_value('attr_1', enemy, decimals), '123.46')
        self.assertEqual(
            format_column_value('ep_sanity', enemy, decimals),
            '374.5/1000.0 (37.5%)',
        )

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

    def test_detail_dialog_accepts_live_updates_without_manual_refresh_button(self):
        enemy = EnemyInfo(0x1234)
        enemy.eid = 'enemy_test'
        enemy.name = '测试敌人'
        enemy.hp = 100.0
        enemy.max_hp = 200.0
        dialog = EnemyDetailDialog(None, enemy)
        self.assertFalse(any(
            button.text() == '重新读取详情'
            for button in dialog.findChildren(QPushButton)))

        updated = EnemyInfo(0x1234)
        updated.eid = enemy.eid
        updated.name = enemy.name
        updated.hp = 75.5
        updated.max_hp = 200.0
        dialog.update_enemy(updated)
        self.assertEqual(dialog.overview.item(6, 1).text(), '75.5')
        self.assertIn('实时更新中', dialog.live_status.text())
        dialog.close()

    def test_pending_and_departed_lifecycle_display_and_filter(self):
        pending = EnemyInfo(0)
        pending.eid = 'enemy_pending'
        pending.spawn_order = 3
        pending.lifecycle = 'pending'
        departed = EnemyInfo(0x2000)
        departed.eid = 'enemy_departed'
        departed.lifecycle = 'departed'
        active = EnemyInfo(0x3000)
        active.eid = 'enemy_active'
        self.assertEqual(format_column_value('row', pending, {}, 0), '3')
        self.assertEqual(format_column_value('life_status', pending, {}), '未出场')
        self.assertEqual(format_column_value('attr_1', pending, {}), '-')
        self.assertEqual(format_column_value('life_status', departed, {}), '已离场')
        self.assertEqual(visible_enemy_rows([pending, departed, active]), [pending, active])
        self.assertEqual(visible_enemy_rows(
            [pending, departed, active], hide_departed=False),
            [pending, departed, active])


if __name__ == '__main__':
    unittest.main()
