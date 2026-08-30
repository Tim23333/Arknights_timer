# -*- coding: utf-8 -*-
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings, Qt, QModelIndex
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem,
)

from backend.app.enemy_buff_descriptions import (
    buff_chinese_name, describe_active_buff, describe_blackboard, describe_global_buff,
)
from backend.app.enemy_ui import (
    DEFAULT_VISIBLE_COLUMNS, ENEMY_COLUMN_DEFS, ENEMY_COLUMN_INDEX,
    EnemyColumnDialog, EnemyDetailDialog, apply_column_order,
    default_precision_values, format_column_value, format_skill_cd, load_column_order,
    precision_column_defs, load_visible_columns, save_column_order,
    visible_enemy_rows,
)
from tools.enemy_health import game_structs as gs
from tools.enemy_health.enemy_reader import EnemyInfo
from backend.desktop_app import (
    AdbSelectionDialog, CoachWindow, EnemyPollWorker, _enemy_mini_stylesheet,
    _format_enemy_read_mode, _system_prefers_dark, _theme_stylesheet,
    probe_adb_executable,
)


class EnemyFormattingTests(unittest.TestCase):
    def test_skill_ready_requires_actual_zero(self):
        self.assertIn('0.04/10.00s', format_skill_cd(
            [('skill', 0.04, 10.0)], prec=2))
        self.assertNotIn('/10.00s', format_skill_cd(
            [('skill', 0.0, 10.0)], prec=2))

    def test_precise_position_never_falls_back_to_old_position(self):
        enemy = EnemyInfo(0x1000)
        enemy.pos_x, enemy.pos_y = 1.0, 2.0
        self.assertEqual(format_column_value(
            'precise_pos', enemy, {'precise_pos': 2}), '-')
        enemy.precise_pos_x, enemy.precise_pos_y = 1.125, 2.25
        enemy.precise_pos_valid = True
        self.assertEqual(format_column_value(
            'precise_pos', enemy, {'precise_pos': 2}), '(1.12, 2.25)')


class EnemyUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_precision_columns_follow_current_visible_numeric_columns(self):
        visible = {'name', 'ep_sanity', 'attr_1', 'skill', 'detail'}
        self.assertEqual(
            precision_column_defs(visible),
            [('attr_1', '攻击'), ('ep_sanity', '神经损伤剩余'), ('skill', '技能 CD')],
        )

    def test_default_main_table_precision_is_two_decimals(self):
        values = default_precision_values()
        self.assertEqual(values['default'], 2)
        self.assertTrue(all(value == 2 for value in values.values()))

    def test_enemy_read_channel_status_only_accepts_memsrv_v4(self):
        self.assertEqual(
            _format_enemy_read_mode({
                'read_mode': 'fast', 'read_backend': 'srv',
            'memsrv_version': 4}),
            '设备快照（memsrv v4）')
        self.assertEqual(
            _format_enemy_read_mode({'read_mode': 'fast', 'read_backend': 'sh'}),
            '检测中')
        self.assertEqual(
            _format_enemy_read_mode({'read_mode': 'slow', 'read_backend': 'adb'}),
            '检测中')

    def test_poll_worker_marks_paused_snapshot_only_when_frame_is_consistent(self):
        class Reader:
            def __init__(self, end_frame):
                self.end_frame = end_frame

            @staticmethod
            def poll_fast():
                return {
                    'ok': True, 'strict_60hz': True, 'fixed_frame': 123,
                    'time_scale': 0.0, 'play_time': 10.0, 'enemies': [],
                }

            def read_frame_guard_fast(self):
                return {'frame': self.end_frame, 'time_scale': 0.0,
                        'play_time': 10.0}

        consistent = EnemyPollWorker(Reader(123))._collect_complete_snapshot()
        crossed = EnemyPollWorker(Reader(124))._collect_complete_snapshot()
        self.assertTrue(consistent['paused_snapshot'])
        self.assertTrue(consistent['pause_consistent'])
        self.assertFalse(crossed['frame_consistent'])
        self.assertFalse(crossed['pause_consistent'])

    def test_poll_worker_coalesces_ui_wakeups_to_latest_snapshot(self):
        worker = EnemyPollWorker(object())
        worker._publish_snapshot({'sequence': 1})
        worker._publish_snapshot({'sequence': 2})
        latest = worker.take_latest_snapshot()
        self.assertEqual(latest['sequence'], 2)
        self.assertEqual(latest['dropped_ui_snapshots'], 1)
        self.assertIsNone(worker.take_latest_snapshot())

    def test_poll_worker_keeps_last_complete_playing_frame_when_error_overwrites_ui(self):
        worker = EnemyPollWorker(object())
        complete = {
            'ok': True, 'state': gs.BattleState.PLAYING,
            'fixed_frame': 777, 'frame_consistent': True, 'enemies': [],
        }
        worker._publish_snapshot(complete)
        worker._publish_snapshot({
            'ok': False, 'state': -1, 'fixed_frame': None,
            'frame_consistent': True, 'enemies': [],
        })
        self.assertFalse(worker.take_latest_snapshot()['ok'])
        self.assertEqual(
            worker.take_last_complete_snapshot()['fixed_frame'], 777)

    def test_enemy_column_fit_fills_viewport_and_protects_hp_text(self):
        table = QTableWidget(1, len(ENEMY_COLUMN_DEFS))
        table.setHorizontalHeaderLabels([col['label'] for col in ENEMY_COLUMN_DEFS])
        visible = {'row', 'name', 'hp', 'spawn_wait', 'detail'}
        for idx, col in enumerate(ENEMY_COLUMN_DEFS):
            table.setColumnHidden(idx, col['key'] not in visible)
        table.setItem(0, ENEMY_COLUMN_INDEX['row'], QTableWidgetItem('1'))
        table.setItem(0, ENEMY_COLUMN_INDEX['name'], QTableWidgetItem('梅菲斯特'))
        table.setItem(0, ENEMY_COLUMN_INDEX['spawn_wait'], QTableWidgetItem('已出场'))
        hp = QProgressBar()
        hp.setFormat('17123.01/28000.00')
        table.setCellWidget(0, ENEMY_COLUMN_INDEX['hp'], hp)
        table.setCellWidget(0, ENEMY_COLUMN_INDEX['detail'], QPushButton('详情'))
        table.resize(900, 260)
        table.show()
        self.app.processEvents()

        holder = type('Holder', (), {})()
        holder.enemy_table = table
        holder._enemy_visible_cols = visible
        holder._widths_fitted = False
        CoachWindow._fit_enemy_columns(holder)

        widths = [table.columnWidth(idx) for idx, col in enumerate(ENEMY_COLUMN_DEFS)
                  if col['key'] in visible]
        self.assertLessEqual(abs(sum(widths) - (table.viewport().width() - 2)), 2)
        expected_hp = min(table.fontMetrics().horizontalAdvance(hp.format()) + 26, 245)
        self.assertGreaterEqual(table.columnWidth(ENEMY_COLUMN_INDEX['hp']), expected_hp)
        table.close()

    def test_enemy_mini_mode_expands_to_twenty_and_supports_mouse_actions(self):
        with tempfile.TemporaryDirectory() as temp_dir, \
                patch.object(CoachWindow, '_start_hook_server', lambda self: None), \
                patch.object(CoachWindow, '_start_ws_server', lambda self: None), \
                patch.object(CoachWindow, '_start_workers', lambda self: None), \
                patch.object(CoachWindow, '_start_timers', lambda self: None):
            window = CoachWindow()
            window._settings = QSettings(
                str(Path(temp_dir) / 'settings.ini'), QSettings.Format.IniFormat)
            window.show()
            self.app.processEvents()
            enemies = []
            for index in range(25):
                enemy = EnemyInfo(0x1000 + index)
                enemy.roster_id = index + 1
                enemy.spawn_order = index + 1
                enemy.eid = f'enemy_{index}'
                enemy.name = f'敌人 {index}'
                enemy.hp = enemy.max_hp = 100.0
                enemies.append(enemy)
            window._render_enemy_table(enemies)
            window._enter_enemy_mini_mode()
            self.app.processEvents()
            mini = window._enemy_mini
            self.assertIsNotNone(mini)
            self.assertFalse(window.isVisible())
            self.assertIs(window.enemy_table.window(), mini)
            self.assertEqual((mini.opacity_slider.minimum(), mini.opacity_slider.maximum()),
                             (25, 100))
            mini.opacity_slider.setValue(35)
            self.app.processEvents()
            # 背景采用 RGBA 透明，文字不再随整个原生窗口一起变淡。
            self.assertEqual(mini.windowOpacity(), 1.0)
            self.assertIn('rgba(', mini.styleSheet())
            self.assertIn('font-weight:600', mini.styleSheet())
            self.assertIn('border:2px solid', mini.styleSheet())

            name_item = window.enemy_table.item(0, ENEMY_COLUMN_INDEX['name'])
            click_pos = window.enemy_table.visualItemRect(name_item).center()
            with patch.object(window, '_open_enemy_detail') as open_detail:
                QTest.mouseClick(window.enemy_table.viewport(), Qt.MouseButton.LeftButton,
                                 pos=click_pos)
                self.app.processEvents()
                QTest.mouseClick(window.enemy_table.viewport(), Qt.MouseButton.RightButton,
                                 pos=click_pos)
                self.app.processEvents()
                self.assertEqual(open_detail.call_count, 2)
                open_detail.assert_called_with(1)

            mini.set_locked(True)
            self.app.processEvents()
            self.assertTrue(mini.locked)
            self.assertFalse(mini.toolbar.isVisible())
            self.assertTrue(
                bool(mini.windowFlags() & Qt.WindowType.WindowTransparentForInput))
            self.assertEqual(mini._locked_visible_rows, 20)

            viewport = window.enemy_table.viewport()
            first_cell = window.enemy_table.visualItemRect(
                window.enemy_table.item(0, ENEMY_COLUMN_INDEX['name'])).center()
            global_pos = viewport.mapToGlobal(first_cell)
            scroll = window.enemy_table.verticalScrollBar()
            scroll.setValue(0)
            mini._on_locked_wheel(global_pos.x(), global_pos.y(), -120)
            self.assertGreater(scroll.value(), 0)
            scroll.setValue(0)
            global_pos = viewport.mapToGlobal(first_cell)
            with patch.object(window, '_open_enemy_detail') as open_detail:
                mini._on_locked_right_click(global_pos.x(), global_pos.y())
                open_detail.assert_called_once_with(1)

            mini.toggle_locked()
            self.app.processEvents()
            self.assertFalse(mini.locked)
            self.assertTrue(mini.toolbar.isVisible())
            window._exit_enemy_mini_mode()
            self.app.processEvents()
            self.assertIsNone(window._enemy_mini)
            self.assertIs(window.enemy_table.parent(), window._enemy_table_host)
            self.assertTrue(window.isVisible())
            window.close()

    def test_main_sections_collapse_and_enemy_table_uses_freed_height(self):
        with patch.object(CoachWindow, '_start_hook_server', lambda self: None), \
                patch.object(CoachWindow, '_start_ws_server', lambda self: None), \
                patch.object(CoachWindow, '_start_workers', lambda self: None), \
                patch.object(CoachWindow, '_start_timers', lambda self: None):
            window = CoachWindow()
            window.resize(1180, 760)
            window.show()
            self.app.processEvents()

            sections = window._collapsible_sections
            self.assertEqual(
                set(sections), {
                    'timer', 'game', 'enemy', 'enemy_table',
                    'character', 'character_table', 'rng', 'custom',
                })
            self.assertTrue(all(not section.is_collapsed()
                                for section in sections.values()))
            initial_table_height = window.enemy_table.height()

            # “只保留敌人数据”现在还需要收起新增的干员区块与“更多自定义选项”。
            for key in ('timer', 'game', 'character', 'character_table', 'rng',
                        'custom'):
                sections[key].set_collapsed(True)
            self.app.processEvents()

            self.assertTrue(window.lbl_enemy_compact_game.isVisible())
            self.assertTrue(sections['game'].content_widget.isHidden())
            self.assertLess(sections['game'].maximumHeight(), 100)
            self.assertGreater(window.enemy_table.height(), initial_table_height)
            self.assertEqual(window.enemy_table.maximumHeight(), 16777215)

            with patch.object(
                    window._provider, 'get_game_data',
                    return_value={'game_time': 12.345, 'frame_count': 741}):
                window._tick_fast()
            self.assertEqual(
                window.lbl_enemy_compact_game.text(),
                '游戏时间：12.345s\n逻辑帧：F741')

            sections['game'].set_collapsed(False)
            self.app.processEvents()
            self.assertFalse(window.lbl_enemy_compact_game.isVisible())
            self.assertFalse(sections['game'].content_widget.isHidden())
            window.close()

    def test_every_main_section_can_float_and_dock_without_recreating_content(self):
        with patch.object(CoachWindow, '_start_hook_server', lambda self: None), \
                patch.object(CoachWindow, '_start_ws_server', lambda self: None), \
                patch.object(CoachWindow, '_start_workers', lambda self: None), \
                patch.object(CoachWindow, '_start_timers', lambda self: None):
            window = CoachWindow()
            window.show()
            self.app.processEvents()
            self.assertTrue(all(section.btn_float.isVisible()
                                for section in window._collapsible_sections.values()))

            section = window._collapsible_sections['character_table']
            content = section.content_widget
            table = window.character_table
            section.float_content()
            self.app.processEvents()
            floating = section._float_window
            self.assertTrue(section.is_floating())
            self.assertIsNotNone(floating)
            self.assertIsNone(floating.parentWidget())
            self.assertIs(content.parent(), floating)
            self.assertIs(table.window(), floating)
            self.assertEqual(section.btn_float.text(), '显示浮窗')
            self.assertLess(section.maximumHeight(), 100)

            window.showMinimized()
            self.app.processEvents()
            self.assertTrue(floating.isVisible())
            self.assertFalse(bool(
                floating.windowState() & Qt.WindowState.WindowMinimized))
            window.showNormal()
            self.app.processEvents()

            section.dock_content()
            self.app.processEvents()
            self.assertFalse(section.is_floating())
            self.assertIs(content.parent(), section)
            self.assertIs(table.window(), window)
            self.assertEqual(section.btn_float.text(), '浮窗')

            section.float_content()
            floating = section._float_window
            floating.close()
            self.app.processEvents()
            self.assertFalse(section.is_floating())
            self.assertIs(content.parent(), section)
            window.close()

    def test_adb_probe_handles_executable_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='adb path ') as temp_dir:
            adb_path = Path(temp_dir) / 'adb.exe'
            adb_path.touch()
            completed = subprocess.CompletedProcess(
                [str(adb_path), 'version'], 0,
                stdout='Android Debug Bridge version 1.0.41\n', stderr='')
            with patch('backend.desktop_app.subprocess.run', return_value=completed) as run:
                ok, detail = probe_adb_executable(str(adb_path))
            self.assertTrue(ok)
            self.assertIn('Android Debug Bridge', detail)
            self.assertEqual(run.call_args.args[0], [str(adb_path), 'version'])

    def test_adb_selection_dialog_has_running_emulator_detection(self):
        dialog = AdbSelectionDialog(None, '', '127.0.0.1:16384')
        self.assertEqual(dialog.btn_auto_detect.text(), '自动探测运行中模拟器')
        self.assertEqual(dialog.btn_refresh_devices.text(), '刷新设备地址')
        self.assertTrue(dialog.path_combo.isEditable())
        self.assertTrue(dialog.device_combo.isEditable())
        self.assertEqual(dialog.selected_serial(), '127.0.0.1:16384')
        dialog.close()

    def test_light_and_dark_themes_style_table_headers_and_rows_together(self):
        light = _theme_stylesheet(False)
        dark = _theme_stylesheet(True)
        for stylesheet in (light, dark):
            self.assertIn('QHeaderView::section', stylesheet)
            self.assertIn('alternate-background-color', stylesheet)
            self.assertIn('QProgressBar', stylesheet)
            self.assertIn('QPushButton[buttonRole="primary"]', stylesheet)
        self.assertIn('#e8ecf1', light)
        self.assertIn('#202124', light)
        self.assertIn('#343434', dark)
        self.assertIn('#e8e8e8', dark)

    def test_enemy_mini_styles_keep_text_opaque_in_both_themes(self):
        dark = _enemy_mini_stylesheet(True, 35)
        light = _enemy_mini_stylesheet(False, 35)
        self.assertIn('background-color:rgba(', dark)
        self.assertIn('color:#ffffff', dark)
        self.assertIn('color:#11151a', light)
        self.assertIn('font-weight:700', dark)
        self.assertIn('gridline-color:rgba(', light)

    def test_system_theme_prefers_qt_color_scheme(self):
        class Hints:
            def colorScheme(self):
                return Qt.ColorScheme.Light

        class FakeApp:
            def styleHints(self):
                return Hints()

        self.assertFalse(_system_prefers_dark(FakeApp()))

    def test_column_specific_precision_for_attribute_and_element_damage(self):
        enemy = EnemyInfo(1)
        enemy.attributes[gs.AttributeType.ATK] = 123.456
        enemy.attributes[gs.AttributeType.MAX_EP] = 1000.0
        enemy.ep_remaining[gs.ElementType.SANITY] = 625.5
        decimals = {'default': 4, 'attr_1': 2, 'ep_sanity': 1}
        self.assertEqual(format_column_value('attr_1', enemy, decimals), '123.46')
        self.assertEqual(
            format_column_value('ep_sanity', enemy, decimals),
            '625.5/1000.0 (62.5%)',
        )

    def test_boss_element_column_uses_remaining_runtime_capacity(self):
        enemy = EnemyInfo(1)
        enemy.attributes[gs.AttributeType.MAX_EP] = 1000.0
        enemy.ep_remaining[gs.ElementType.NONE] = 2000.0
        enemy.ep_remaining[gs.ElementType.SANITY] = 818.82
        self.assertEqual(
            format_column_value(
                f'attr_{gs.AttributeType.MAX_EP}', enemy,
                {'default': 2, f'attr_{gs.AttributeType.MAX_EP}': 2}),
            '2000.00',
        )
        self.assertEqual(
            format_column_value(
                'ep_sanity', enemy, {'default': 2, 'ep_sanity': 2}),
            '818.82/2000.00 (40.94%)',
        )

    def test_shield_column_includes_mouse_king_magic_barrier(self):
        enemy = EnemyInfo(1)
        enemy.special_shield = 14001.0
        enemy.special_shield_mask = 4
        self.assertEqual(
            format_column_value('shield', enemy, {'default': 2, 'shield': 2}),
            '法术 14001.00',
        )

    def test_next_action_column_marks_prediction_confidence(self):
        enemy = EnemyInfo(1)
        enemy.action = {
            'next_action_rule': '技能：Boss规则技能',
            'next_action_rule_confidence': 'rule_calculated',
            'next_action': '技能：测试技能',
            'next_action_confidence': 'confirmed',
        }
        self.assertEqual(
            format_column_value('next_action', enemy, {'default': 2}),
            '[Boss规则] [规则计算] 技能：Boss规则技能\n'
            '[含CD] [确定] 技能：测试技能')

    def test_existing_column_settings_enable_new_shield_column_only_once(self):
        with tempfile.TemporaryDirectory() as td:
            settings = QSettings(str(Path(td) / 'settings.ini'), QSettings.IniFormat)
            key = 'enemy_table/visible_columns'
            settings.setValue(key, 'name,hp')
            self.assertIn('shield', load_visible_columns(settings, key))
            settings.setValue(key, 'name,hp')  # 模拟用户升级后主动取消护盾列
            self.assertNotIn('shield', load_visible_columns(settings, key))

    def test_column_order_defaults_to_definition_order(self):
        all_keys = [col['key'] for col in ENEMY_COLUMN_DEFS]
        with tempfile.TemporaryDirectory() as td:
            settings = QSettings(str(Path(td) / 's.ini'), QSettings.IniFormat)
            self.assertEqual(
                load_column_order(settings, 'enemy_table/column_order', all_keys),
                all_keys)

    def test_column_order_filters_invalid_and_appends_missing(self):
        with tempfile.TemporaryDirectory() as td:
            settings = QSettings(str(Path(td) / 's.ini'), QSettings.IniFormat)
            settings.setValue('k', 'hp,bogus,row')
            self.assertEqual(
                load_column_order(settings, 'k', ['row', 'name', 'hp', 'skill']),
                ['hp', 'row', 'name', 'skill'])

    def test_column_order_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            settings = QSettings(str(Path(td) / 's.ini'), QSettings.IniFormat)
            all_keys = ['row', 'name', 'hp']
            save_column_order(settings, 'k', ['hp', 'row', 'name'])
            self.assertEqual(load_column_order(settings, 'k', all_keys),
                             ['hp', 'row', 'name'])

    def test_apply_column_order_moves_visual_sections_only(self):
        table = QTableWidget(1, 4)
        table.setItem(0, 0, QTableWidgetItem('a'))
        index = {'c1': 0, 'c2': 1, 'c3': 2, 'c4': 3}
        apply_column_order(table, ['c3', 'c1', 'c2', 'c4'], index)
        header = table.horizontalHeader()
        self.assertEqual(header.visualIndex(2), 0)
        self.assertEqual(header.visualIndex(0), 1)
        self.assertEqual(header.visualIndex(1), 2)
        self.assertEqual(header.visualIndex(3), 3)
        # 逻辑寻址不受影响：仍按列定义下标取到同一单元格
        self.assertEqual(table.item(0, 0).text(), 'a')
        table.deleteLater()

    def test_column_dialog_order_list_syncs_with_checks(self):
        visible = {'name', 'hp'}
        order = ['hp'] + [col['key'] for col in ENEMY_COLUMN_DEFS]
        dlg = EnemyColumnDialog(None, visible, order)
        self.assertEqual(dlg.ordered_keys(), ['hp', 'name'])
        dlg.checks['row'].setChecked(True)     # 新勾选的列追加到末尾
        self.assertEqual(dlg.ordered_keys(), ['hp', 'name', 'row'])
        dlg.checks['hp'].setChecked(False)     # 取消勾选即从顺序中移除
        self.assertEqual(dlg.ordered_keys(), ['name', 'row'])
        self.assertEqual(dlg.values(), {'name', 'row'})
        dlg.deleteLater()

    def test_column_dialog_order_list_supports_move(self):
        visible = {'name', 'hp', 'row'}
        order = [col['key'] for col in ENEMY_COLUMN_DEFS]
        dlg = EnemyColumnDialog(None, visible, order)
        self.assertEqual(dlg.ordered_keys(), ['row', 'name', 'hp'])
        # 等价于 InternalMove 拖放：把 hp (第 2 行) 移到最前
        model = dlg.order_list.model()
        self.assertTrue(model.moveRow(QModelIndex(), 2, QModelIndex(), 0))
        self.assertEqual(dlg.ordered_keys(), ['hp', 'row', 'name'])
        dlg.deleteLater()

    def test_column_dialog_preset_restores_default_set_in_definition_order(self):
        dlg = EnemyColumnDialog(None, {'hp'}, ['hp'])
        dlg._set_checked(DEFAULT_VISIBLE_COLUMNS)
        expected = [col['key'] for col in ENEMY_COLUMN_DEFS
                    if col['key'] in DEFAULT_VISIBLE_COLUMNS]
        self.assertEqual(dlg.ordered_keys(), expected)
        self.assertEqual(dlg.values(), set(DEFAULT_VISIBLE_COLUMNS))
        dlg.deleteLater()

    def test_custom_shield_buff_has_clear_chinese_description(self):
        buff = {
            'key': 'mousek_shield[a]', 'custom_shield_value': 4667.0,
            'custom_shield_mask': 4, 'has_shield': False,
            'attribute_modifiers': [], 'abnormal_flags': [],
            'abnormal_immunes': [], 'abnormal_antis': [],
            'abnormal_combos': [], 'abnormal_combo_immunes': [],
        }
        self.assertEqual(buff_chinese_name(buff), '法术屏障（分段）')
        description = describe_active_buff(buff)
        self.assertIn('当前分段剩余 4667', description)
        self.assertIn('完整屏障为所有有效分段之和', description)

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
        rows = {
            dialog.overview.item(row, 0).text(): dialog.overview.item(row, 1).text()
            for row in range(dialog.overview.rowCount())
        }
        self.assertEqual(rows['当前生命'], '75.5')
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
        self.assertEqual(visible_enemy_rows([pending, departed, active]), [active, pending])
        self.assertEqual(visible_enemy_rows(
            [pending, departed, active], hide_departed=False),
            [active, pending, departed])

    def test_enemy_action_phase_and_countdown_are_rendered(self):
        enemy = EnemyInfo(0x1000)
        enemy.action = {
            'name': '战斗动作后摇', 'remaining_frames': 15,
            'remaining': 0.5, 'remaining_kind': '后摇剩余',
        }
        self.assertEqual(
            format_column_value('action_phase', enemy, {}), '战斗动作后摇')
        self.assertEqual(
            format_column_value('remaining_time', enemy, {}),
            '15 帧 / 0.50 秒（后摇剩余）')

    def test_living_enemies_are_stably_sorted_above_pending_and_dead(self):
        pending_a = EnemyInfo(0)
        pending_a.roster_id = 1
        pending_b = EnemyInfo(0)
        pending_b.roster_id = 2
        alive_a = EnemyInfo(0x1000)
        alive_a.roster_id = 3
        alive_b = EnemyInfo(0x2000)
        alive_b.roster_id = 4
        dead = EnemyInfo(0x3000)
        dead.roster_id = 5
        dead.alive = False
        rows = visible_enemy_rows(
            [pending_a, alive_a, pending_b, dead, alive_b], hide_departed=False)
        self.assertEqual(rows, [alive_a, alive_b, pending_a, pending_b, dead])

    def test_main_table_physically_reorders_when_pending_enemy_spawns(self):
        with tempfile.TemporaryDirectory() as temp_dir, \
                patch.object(CoachWindow, '_start_hook_server', lambda self: None), \
                patch.object(CoachWindow, '_start_ws_server', lambda self: None), \
                patch.object(CoachWindow, '_start_workers', lambda self: None), \
                patch.object(CoachWindow, '_start_timers', lambda self: None):
            window = CoachWindow()
            window._settings = QSettings(
                str(Path(temp_dir) / 'settings.ini'), QSettings.Format.IniFormat)
            pending = EnemyInfo(0)
            pending.roster_id = 11
            pending.spawn_order = 1
            alive = EnemyInfo(0x2000)
            alive.roster_id = 22
            alive.spawn_order = 2

            window._render_enemy_table([pending, alive])
            row_col = ENEMY_COLUMN_INDEX['row']
            self.assertEqual(
                [window.enemy_table.item(row, row_col).data(Qt.UserRole)
                 for row in range(window.enemy_table.rowCount())],
                [22, 11])

            pending.lifecycle = 'active'
            pending.addr = 0x1000
            window._render_enemy_table([pending, alive])
            self.assertEqual(
                [window.enemy_table.item(row, row_col).data(Qt.UserRole)
                 for row in range(window.enemy_table.rowCount())],
                [11, 22])
            window.close()


if __name__ == '__main__':
    unittest.main()
