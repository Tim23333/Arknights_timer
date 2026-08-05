# -*- coding: utf-8 -*-
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.enemy_health import game_structs as gs
from tools.enemy_health.enemy_reader import (
    EnemyInfo, EnemyReader, spine_track_remaining, summarize_custom_shields,
)
from tools.enemy_health.update_from_unpack import extract_preunpacked, parse_dump
from tools.enemy_health.memcore import (
    MemCore, find_running_emulator_adbs, query_adb_devices,
)


class EnemyDetailModelTests(unittest.TestCase):
    @staticmethod
    def _skill_memory(active_count=0, all_count=1):
        ep, active, all_skills = 0x1000, 0x2000, 0x3000
        active_items, skill, timer, data, key = 0x4000, 0x5000, 0x6000, 0x7000, 0x8000
        blocks = {}

        active_head = bytearray(0x20)
        struct.pack_into('<Q', active_head, gs.ListInternal.ITEMS, active_items)
        struct.pack_into('<i', active_head, gs.ListInternal.SIZE, active_count)
        blocks[(active, 0x20)] = bytes(active_head)
        if active_count:
            blocks[(active_items + gs.Il2CppArray.ITEMS, active_count * 8)] = \
                struct.pack('<Q', skill) * active_count

        all_head = bytearray(0x20)
        struct.pack_into('<i', all_head, gs.Il2CppArray.MAX_LENGTH, all_count)
        blocks[(all_skills, 0x20)] = bytes(all_head)
        if all_count:
            blocks[(all_skills + gs.Il2CppArray.ITEMS, all_count * 8)] = \
                struct.pack('<Q', skill) * all_count

        skill_block = bytearray(0x90)
        struct.pack_into('<Q', skill_block, gs.EnemySkillFields.M_COOLDOWN_TIMER, timer)
        struct.pack_into('<Q', skill_block, gs.EnemySkillFields.DATA, data)
        blocks[(skill, 0x90)] = bytes(skill_block)
        timer_block = bytearray(0x20)
        struct.pack_into('<Q', timer_block, gs.PeriodicTimerFields.M_PERIOD_TIME,
                         int(30 * gs.FP_ONE))
        struct.pack_into('<Q', timer_block, gs.PeriodicTimerFields.M_REMAINING_TIME,
                         int(12.5 * gs.FP_ONE))
        blocks[(timer, 0x20)] = bytes(timer_block)
        data_block = bytearray(0x28)
        struct.pack_into('<Q', data_block, gs.ESkillDataFields.PREFAB_KEY, key)
        blocks[(data, 0x28)] = bytes(data_block)
        return (ep, active, all_skills, skill, key), blocks

    def test_skill_cd_falls_back_to_all_skills_when_active_list_is_empty(self):
        (ep, active, all_skills, _skill, key), blocks = self._skill_memory()

        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

            @staticmethod
            def read_ustring(value):
                return 'FallbackSkill' if value == key else None

            @staticmethod
            def read(addr, size):
                return blocks.get((addr, size))

        reader = EnemyReader(mc=FakeMem())
        enemy_block = bytearray(gs.EnemyFields.READ_SIZE)
        struct.pack_into('<Q', enemy_block, gs.EnemyFields.M_SKILLS, active)
        struct.pack_into('<Q', enemy_block, gs.EnemyFields.M_ALL_SKILLS, all_skills)
        info = EnemyInfo(ep)
        reader._fill_skills(ep, bytes(enemy_block), info)
        self.assertEqual(info.skills, [('FallbackSkill', 12.5, 30.0)])
        self.assertEqual(reader._skill_ptrs[ep], [0x5000])

    def test_skill_cd_keeps_last_value_during_transient_container_read_failure(self):
        (ep, active, all_skills, skill, _key), blocks = self._skill_memory()

        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        class FakeChannel:
            @staticmethod
            def batch_read(reqs):
                # 两个容器头和技能块本轮都失败，模拟设备侧一次瞬态空读。
                return [None for _ in reqs]

        reader = EnemyReader(mc=FakeMem())
        reader._chan = FakeChannel()
        reader._skill_lp[ep] = active
        reader._skill_ap[ep] = all_skills
        reader._skill_ptrs[ep] = [skill]
        reader._skill_names[skill] = 'StableSkill'
        reader._skill_cd[ep] = [('StableSkill', 8.0, 30.0)]
        reader._refresh_skills_chan([ep])
        self.assertEqual(reader._skill_cd[ep], [('StableSkill', 8.0, 30.0)])

    def test_adb_commands_are_bound_to_selected_device(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            adb = Path(temp_dir) / 'adb.exe'
            adb.touch()
            completed = subprocess.CompletedProcess([], 0, stdout=b'ok', stderr=b'')
            with patch('tools.enemy_health.memcore.subprocess.run',
                       return_value=completed) as run:
                mc = MemCore(str(adb), adb_serial='127.0.0.1:16384')
                self.assertEqual(mc.adb('shell', 'id'), b'ok')
            self.assertEqual(
                run.call_args.args[0],
                [str(adb), '-s', '127.0.0.1:16384', 'shell', 'id'])

    def test_query_adb_devices_parses_serial_and_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            adb = Path(temp_dir) / 'adb.exe'
            adb.touch()
            output = (
                b'List of devices attached\n'
                b'127.0.0.1:16384\tdevice product:MuMu model:MuMu\n'
                b'127.0.0.1:7555\toffline\n')
            completed = subprocess.CompletedProcess([], 0, stdout=output, stderr=b'')
            with patch('tools.enemy_health.memcore.subprocess.run',
                       return_value=completed):
                rows = query_adb_devices(str(adb))
        self.assertEqual(rows[0]['serial'], '127.0.0.1:16384')
        self.assertEqual(rows[0]['state'], 'device')
        self.assertEqual(rows[1]['state'], 'offline')

    def test_game_package_is_auto_detected_on_selected_device(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            adb = Path(temp_dir) / 'adb.exe'
            adb.touch()
            mc = MemCore(str(adb), adb_serial='127.0.0.1:16384')
            mc.shell = lambda command, timeout=30: (
                '4321\n' if command == 'pidof com.hypergryph.arknights.bilibili' else '')
            package, pid = mc._pid_for_known_package()
        self.assertEqual(package, 'com.hypergryph.arknights.bilibili')
        self.assertEqual(pid, 4321)

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

    def test_running_nx_device_process_resolves_nx_main_adb(self):
        """新版 MuMu 布局: 进程在 nx_device/12.x/shell 下, adb 在 nx_main/ 下。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / 'MuMu Player 12'
            process = root / 'nx_device' / '12.0' / 'shell' / 'MuMuNxDevice.exe'
            adb = root / 'nx_main' / 'adb.exe'
            process.parent.mkdir(parents=True)
            adb.parent.mkdir(parents=True)
            process.touch()
            adb.touch()
            found = find_running_emulator_adbs([
                ('MuMuNxDevice.exe', str(process)),
            ])
            self.assertEqual([item['adb_path'] for item in found], [str(adb)])

    def test_known_mumu_serials_cover_preset_port_table(self):
        from tools.enemy_health.memcore import KNOWN_MUMU_SERIALS
        for i in range(7):
            self.assertIn(f'127.0.0.1:{16384 + 32 * i}', KNOWN_MUMU_SERIALS)
        self.assertIn('127.0.0.1:7555', KNOWN_MUMU_SERIALS)

    def test_find_mumu_adb_prefers_running_emulator_adb(self):
        from tools.enemy_health import memcore
        with tempfile.TemporaryDirectory() as temp_dir:
            adb = Path(temp_dir) / 'MuMu Player 12' / 'nx_main' / 'adb.exe'
            adb.parent.mkdir(parents=True)
            adb.touch()
            detected = [{'adb_path': str(adb), 'process_name': 'MuMuNxDevice.exe',
                         'process_path': ''}]
            with patch.object(memcore, 'load_adb_config', return_value={}), \
                    patch.object(memcore, 'find_running_emulator_adbs',
                                 return_value=detected):
                self.assertEqual(memcore.find_mumu_adb(), str(adb))

    def test_all_current_attributes_are_declared(self):
        self.assertEqual(gs.AttributeType.E_NUM, 38)
        self.assertEqual({idx for idx, _, _ in gs.ATTRIBUTE_DEFS},
                         set(range(0, 9)) | set(range(13, 38)))

    def test_august_offsets_and_new_abnormal_flag_are_loaded(self):
        self.assertEqual(gs.EntityFields.M_ATTRIBUTES, 0xB0)
        self.assertEqual(gs.EntityFields.ID, 0x148)
        self.assertEqual(gs.EnemyFields.DATA, 0x510)
        self.assertEqual(gs.EnemyFields.ATTACK_ABILITY_CASTED, 0x4E8)
        self.assertEqual(gs.EnemyFields.COMBAT_NEXT_ESCAPE_TIME, 0x4F8)
        self.assertEqual(gs.EnemyFields.ATTACK_WRAPPER, 0x550)
        self.assertEqual(gs.EnemyFields.COMBAT_WRAPPER, 0x558)
        self.assertEqual(gs.EnemyFields.READ_SIZE, 0x568)
        self.assertEqual(gs.BuffFields.IS_ACTUALLY_ENABLED, 0x1ED)
        self.assertEqual(gs.AbnormalFlag.E_NUM, 46)
        self.assertEqual(gs.ABNORMAL_FLAG_CN_NAMES[45], '地面束缚')

    def test_enemy_combat_post_action_uses_exact_deadline_frames(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        reader = EnemyReader(mc=FakeMem())
        enemy = EnemyInfo(0x1000)
        enemy.state_id = gs.EnemyState.COMBAT
        enemy.action = {
            'casting': False,
            'combat_escape_time': 12.0,
        }
        reader._finalize_enemy_action(
            enemy, now=11.5, frame=900, frame_duration=1 / 30)
        self.assertEqual(enemy.action['phase'], 'combat_recovery')
        self.assertEqual(enemy.action['remaining_frames'], 15)
        self.assertAlmostEqual(enemy.action['remaining'], 0.5)
        self.assertEqual(enemy.action['remaining_kind'], '后摇剩余')

    def test_enemy_casting_reports_elapsed_but_does_not_fabricate_remaining(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        reader = EnemyReader(mc=FakeMem())
        enemy = EnemyInfo(0x1000)
        enemy.state_id = gs.EnemyState.ATTACK
        enemy.action = {'casting': True, 'cast_start_frame': 120}
        reader._finalize_enemy_action(
            enemy, now=5.0, frame=138, frame_duration=1 / 30)
        self.assertEqual(enemy.action['elapsed_frames'], 18)
        self.assertNotIn('remaining_frames', enemy.action)
        self.assertEqual(enemy.action['remaining_kind'], '动画/能力回调决定')

    def test_spine_non_loop_track_has_exact_scaled_remaining_time(self):
        remaining = spine_track_remaining(
            0.0, 3.0, 1.5, entry_scale=1.0,
            state_scale=1.0, skeleton_scale=2.0, loop=False)
        self.assertAlmostEqual(remaining, 0.75)
        self.assertIsNone(spine_track_remaining(
            0.0, 3.0, 1.5, 1.0, 1.0, 1.0, loop=True))

    def test_enemy_attack_uses_spine_track_and_marks_rule_snapshot(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        reader = EnemyReader(mc=FakeMem())
        enemy = EnemyInfo(0x1000)
        enemy.state_id = gs.EnemyState.ATTACK
        enemy.action = {
            'casting': True, 'cast_start_frame': 100,
            'animation_remaining': 1.2, 'animation_exact': True,
        }
        reader._finalize_enemy_action(
            enemy, now=5.0, frame=130, frame_duration=1 / 30)
        self.assertAlmostEqual(enemy.action['remaining'], 1.2)
        self.assertEqual(enemy.action['remaining_frames'], 36)
        self.assertEqual(enemy.action['clock_source'], 'spine_track')
        self.assertEqual(enemy.action['next_action_confidence'], 'rule_partial')
        self.assertIn('规则候选', enemy.action['next_action'])
        self.assertIn('当前动作尚未结束', enemy.action['next_action_detail'])

    def test_enemy_on_cooldown_skill_is_not_reported_as_next_action(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        reader = EnemyReader(mc=FakeMem())
        enemy = EnemyInfo(0x1000)
        enemy.state_id = gs.EnemyState.MOVE
        enemy.skills = [('短CD技能', 1.0, 10.0), ('长CD技能', 8.0, 20.0)]
        enemy.skills_detail = [
            {'name': '短CD技能', 'remaining': 1.0, 'period': 10.0,
             'priority': 5, 'max_triggers': 0, 'trigger_count': 0,
             'has_trigger': False, 'family_mask': gs.AbilityFamilyMask.ATTACK},
            {'name': '长CD技能', 'remaining': 8.0, 'period': 20.0,
             'priority': 9, 'max_triggers': 0, 'trigger_count': 0,
             'has_trigger': False, 'family_mask': gs.AbilityFamilyMask.ATTACK},
        ]
        enemy.action = {
            'attack_base': {'cd_remaining': 0.0},
            'attack_trigger_ready': True,
            'attack_trigger_reason': '测试目标有效',
            'combat_ability_picked': False,
        }
        reader._finalize_enemy_action(
            enemy, now=5.0, frame=130, frame_duration=1 / 30)
        # 原始 _PickAbility 只检查最高优先级组；其 CD 未就绪后直接兜底，
        # 不会继续选择低优先级但 CD 更短的技能。
        self.assertNotIn('短CD技能', enemy.action['next_action'])
        self.assertNotIn('长CD技能', enemy.action['next_action'])
        self.assertEqual(enemy.action['next_action'], '普通攻击')
        self.assertEqual(enemy.action['next_action_confidence'], 'rule_calculated')
        self.assertIn('priority=9', enemy.action['next_action_detail'])

    def test_enemy_attack_lane_candidate_uses_highest_priority(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        reader = EnemyReader(mc=FakeMem())
        enemy = EnemyInfo(0x1000)
        enemy.state_id = gs.EnemyState.MOVE
        enemy.skills_detail = [
            {'name': '低优先技能', 'remaining': 0.0, 'period': 10.0,
             'priority': 1, 'max_triggers': 0, 'trigger_count': 0,
             'has_trigger': False, 'family_mask': gs.AbilityFamilyMask.ATTACK},
            {'name': '高优先技能', 'remaining': 0.0, 'period': 30.0,
             'priority': 9, 'max_triggers': 3, 'trigger_count': 1,
             'has_trigger': True, 'trigger_ready': True,
             'trigger_type': 'SelectorTrigger',
             'trigger_reason': '已有有效目标',
             'family_mask': gs.AbilityFamilyMask.ATTACK},
        ]
        enemy.action = {'combat_ability_picked': False}
        reader._finalize_enemy_action(
            enemy, now=5.0, frame=130, frame_duration=1 / 30)
        self.assertEqual(enemy.action['next_action'], '技能：高优先技能')
        self.assertEqual(enemy.action['next_action_confidence'], 'rule_calculated')
        self.assertIn('priority=9', enemy.action['next_action_detail'])
        self.assertNotIn('低优先技能', enemy.action['next_action'])

    def test_enemy_exhausted_skill_is_not_inferred(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        reader = EnemyReader(mc=FakeMem())
        enemy = EnemyInfo(0x1000)
        enemy.state_id = gs.EnemyState.MOVE
        enemy.skills_detail = [
            {'name': '次数用尽技能', 'remaining': 0.0, 'period': 10.0,
             'priority': 9, 'max_triggers': 2, 'trigger_count': 2,
             'has_trigger': False, 'family_mask': gs.AbilityFamilyMask.ATTACK},
        ]
        enemy.action = {
            'combat_ability_picked': False,
            'attack_base': {'cd_remaining': 0.0},
            'attack_trigger_ready': True,
            'attack_trigger_reason': '测试目标有效',
        }
        reader._finalize_enemy_action(
            enemy, now=5.0, frame=130, frame_duration=1 / 30)
        self.assertNotIn('次数用尽技能', enemy.action['next_action'])
        self.assertEqual(enemy.action['next_action'], '普通攻击')
        self.assertEqual(enemy.action['next_action_confidence'], 'rule_calculated')

    def test_enemy_ready_skill_candidate_notes_trigger_gate(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        reader = EnemyReader(mc=FakeMem())
        enemy = EnemyInfo(0x1000)
        enemy.state_id = gs.EnemyState.MOVE
        enemy.skills_detail = [
            {'name': '触发器技能', 'remaining': 0.0, 'period': 10.0,
             'priority': 3, 'max_triggers': 0, 'trigger_count': 0,
             'has_trigger': True, 'family_mask': gs.AbilityFamilyMask.ATTACK},
        ]
        enemy.action = {'combat_ability_picked': False}
        reader._finalize_enemy_action(
            enemy, now=5.0, frame=130, frame_duration=1 / 30)
        self.assertEqual(enemy.action['next_action'],
                         '条件待判：触发器技能；否则普通攻击')
        self.assertEqual(enemy.action['next_action_confidence'], 'rule_partial')
        self.assertIn('TargetTrigger', enemy.action['next_action_detail'])

    def test_enemy_blocked_uses_combat_lane_and_ignores_attack_only_skill(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        reader = EnemyReader(mc=FakeMem())
        enemy = EnemyInfo(0x1000)
        enemy.state_id = gs.EnemyState.MOVE
        enemy.skills_detail = [
            {'name': '普攻技能', 'remaining': 0.0, 'period': 10.0,
             'priority': 99, 'max_triggers': 0, 'trigger_count': 0,
             'has_trigger': False, 'family_mask': gs.AbilityFamilyMask.ATTACK},
            {'name': '阻挡技能', 'remaining': 0.0, 'period': 20.0,
             'priority': 2, 'max_triggers': 0, 'trigger_count': 0,
             'has_trigger': False, 'family_mask': gs.AbilityFamilyMask.COMBAT},
        ]
        enemy.action = {
            'blocker_addr': 0x2000, 'combat_ability_picked': False,
            'combat_base': {'cd_remaining': 0.0},
        }
        reader._finalize_enemy_action(
            enemy, now=5.0, frame=130, frame_duration=1 / 30)
        # 最高优先级先于 family 锁组；priority=99 的 ATTACK 技能在 COMBAT
        # 流程不通过后，客户端直接兜底，不会继续看 priority=2。
        self.assertEqual(enemy.action['next_action'], '基础战斗能力')
        self.assertNotIn('普攻技能', enemy.action['next_action'])
        self.assertNotIn('阻挡技能', enemy.action['next_action'])

    def test_enemy_picked_combat_ability_is_confirmed_next_action(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        reader = EnemyReader(mc=FakeMem())
        enemy = EnemyInfo(0x1000)
        enemy.state_id = gs.EnemyState.MOVE
        enemy.action = {
            'combat_ability_picked': True,
            'combat_wrapper_ability_addr': 0x2000,
        }
        reader._finalize_enemy_action(
            enemy, now=5.0, frame=130, frame_duration=1 / 30)
        self.assertEqual(enemy.action['next_action_confidence'], 'confirmed')
        self.assertIn('战斗能力', enemy.action['next_action'])

    def test_current_combat_pick_is_not_mislabeled_as_next_action(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        reader = EnemyReader(mc=FakeMem())
        enemy = EnemyInfo(0x1000)
        enemy.state_id = gs.EnemyState.COMBAT
        enemy.action = {
            'casting': True,
            'combat_ability_picked': True,
            'combat_wrapper_ability_addr': 0x2000,
            'combat_ability_addr': 0x2000,
        }
        reader._finalize_enemy_action(
            enemy, now=5.0, frame=130, frame_duration=1 / 30)
        self.assertNotEqual(enemy.action['next_action_confidence'], 'confirmed')
        self.assertIn('当前动作尚未结束', enemy.action['next_action_detail'])

    def test_current_attack_snapshot_does_not_choose_lower_priority_ready_skill(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        reader = EnemyReader(mc=FakeMem())
        enemy = EnemyInfo(0x1000)
        enemy.state_id = gs.EnemyState.ATTACK
        enemy.skills_detail = [
            {'name': '高优先冷却技能', 'remaining': 10.0, 'period': 30.0,
             'priority': 1, 'max_triggers': 0, 'trigger_count': 0,
             'has_trigger': True, 'trigger_ready': None,
             'family_mask': gs.AbilityFamilyMask.ATTACK},
            {'name': '低优先就绪技能', 'remaining': 0.0, 'period': 20.0,
             'priority': 0, 'max_triggers': 0, 'trigger_count': 0,
             'has_trigger': True, 'trigger_ready': True,
             'family_mask': gs.AbilityFamilyMask.ATTACK},
        ]
        enemy.action = {
            'attack_base': {'cd_remaining': 0.0},
            'attack_trigger_ready': True,
            'attack_trigger_reason': '已有有效目标',
        }
        reader._finalize_enemy_action(
            enemy, now=5.0, frame=130, frame_duration=1 / 30)
        self.assertEqual(enemy.action['next_action'], '普通攻击')
        self.assertEqual(enemy.action['next_action_confidence'], 'rule_snapshot')
        self.assertNotIn('低优先就绪技能', enemy.action['next_action'])

    def test_same_priority_passed_skills_are_rng_candidates(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value >= 0x1000

        reader = EnemyReader(mc=FakeMem())
        enemy = EnemyInfo(0x1000)
        enemy.state_id = gs.EnemyState.MOVE
        enemy.skills_detail = [
            {'name': name, 'remaining': 0.0, 'period': 10.0,
             'priority': 4, 'max_triggers': 0, 'trigger_count': 0,
             'has_trigger': False,
             'family_mask': gs.AbilityFamilyMask.ATTACK}
            for name in ('技能甲', '技能乙')]
        enemy.action = {}
        reader._finalize_enemy_action(
            enemy, now=5.0, frame=130, frame_duration=1 / 30)
        self.assertEqual(enemy.action['next_action'], '随机择一：技能甲 / 技能乙')
        self.assertEqual(enemy.action['next_action_confidence'], 'rule_candidates')
        self.assertIn('战斗 RNG', enemy.action['next_action_detail'])

    def test_dump_parser_tracks_namespace_fields_and_enum_values(self):
        source = (
            '// Namespace: Torappu.Battle\n'
            'public abstract class Entity : Object\n'
            '{\n'
            '    private FP m_hp; // 0x40\n'
            '    private string <id>k__BackingField; // 0x148\n'
            '}\n'
            '// Namespace: Torappu\n'
            'public enum AbnormalFlag\n'
            '{\n'
            '    public int value__; // 0x0\n'
            '    public const AbnormalFlag GROUND_BOUND = 45;\n'
            '    public const AbnormalFlag E_NUM = 46;\n'
            '}\n')
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / 'dump.cs'
            path.write_text(source, encoding='utf-8')
            classes, enums = parse_dump(path)
        self.assertEqual(classes[('Torappu.Battle', 'Entity')]['m_hp'], 0x40)
        self.assertEqual(classes[('Torappu.Battle', 'Entity')]
                         ['<id>k__BackingField'], 0x148)
        self.assertEqual(enums[('Torappu', 'AbnormalFlag')]['E_NUM'], 46)

    def test_explicit_new_table_wins_over_later_old_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            new_dir, old_dir, output = root / 'new', root / 'old', root / 'out'
            new_dir.mkdir(); old_dir.mkdir()
            (new_dir / 'enemy_databaseaaaaaa.dat').write_bytes(b'new-data')
            (old_dir / 'enemy_databasebbbbbb.bin').write_bytes(b'old-data')
            copied = extract_preunpacked([new_dir, old_dir], output)
            self.assertEqual([path.name for path in copied],
                             ['enemy_databaseaaaaaa.bin'])
            self.assertEqual(copied[0].read_bytes(), b'new-data')

    def test_runtime_name_updates_all_pending_same_id(self):
        reader = EnemyReader(mc=object())
        reader._db = {}
        reader._set_spawn_plan([
            {'key': 'enemy_new'}, {'key': 'enemy_new'}, {'key': 'enemy_other'},
        ])
        name, code = reader._remember_enemy_name('enemy_new', '新版敌人')
        self.assertEqual((name, code), ('新版敌人', ''))
        self.assertEqual([row['info'].name for row in reader._spawn_plan],
                         ['新版敌人', '新版敌人', 'enemy_other'])

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
        self.assertEqual(enemy.effective_max_ep, 2000.0)
        self.assertEqual(enemy.element_damage(gs.ElementType.SANITY),
                         (675.0, 1325.0, 2000.0))

    def test_slow_fallback_refreshes_element_damage_instead_of_freezing_snapshot(self):
        ep_ptr = 0x2000
        data = bytearray(gs.Il2CppArray.ITEMS + gs.ElementType.E_NUM * 8)
        struct.pack_into('<i', data, gs.Il2CppArray.MAX_LENGTH, gs.ElementType.E_NUM)
        values = (2000.0, 1325.0, 2000.0, 2000.0, 2000.0, 2000.0)
        for idx, value in enumerate(values):
            struct.pack_into(
                '<Q', data, gs.Il2CppArray.ITEMS + idx * 8,
                int(value * gs.FP_ONE))

        class FakeMemory:
            @staticmethod
            def is_ptr(value):
                return value == ep_ptr

            @staticmethod
            def read(addr, _size):
                return bytes(data) if addr == ep_ptr else None

        reader = EnemyReader(mc=FakeMemory())
        enemy = EnemyInfo(0x1000)
        enemy.ep_ptr = ep_ptr
        reader._runtime_snapshot[enemy.addr] = {
            'ep_remaining': {idx: 2000.0 for idx in range(gs.ElementType.E_NUM)},
        }
        self.assertTrue(reader._refresh_ep_runtime_slow(enemy))
        self.assertEqual(enemy.element_damage(gs.ElementType.SANITY),
                         (675.0, 1325.0, 2000.0))

    def test_fast_poll_snapshot_reports_live_channel_backend(self):
        reader = EnemyReader(mc=object())

        class FakeChannel:
            mode = 'srv'

        reader._chan = FakeChannel()
        reader._poll_fast_impl = lambda: {'ok': True}
        snapshot = reader.poll_fast()
        self.assertEqual(snapshot['read_mode'], 'fast')
        self.assertEqual(snapshot['read_backend'], 'srv')

    def test_mouse_king_legacy_magic_shield_sums_three_live_segments(self):
        buffs = []
        for index in 'abc':
            buffs.append({
                'addr': 0x1000 + len(buffs) * 0x100,
                'key': f'mousek_shield[{index}]',
                'enabled': True,
                'valid': True,
                'finished': False,
                'blackboard': [{
                    'key': 'dynamic', 'value': 4667.0,
                    'value_addr': 0x5000 + len(buffs) * 0x100,
                }],
            })
        total, mask, sources = summarize_custom_shields(
            buffs, 'enemy_1509_mousek')
        self.assertEqual(total, 14001.0)
        self.assertEqual(mask, 4)
        self.assertEqual(len(sources), 3)

    def test_finished_custom_shield_segment_is_not_counted(self):
        buff = {
            'addr': 0x1000, 'key': 'mousek_shield[a]',
            'enabled': True, 'valid': True, 'finished': True,
            'blackboard': [{'key': 'dynamic', 'value': 4667.0,
                            'value_addr': 0x5000}],
        }
        total, mask, sources = summarize_custom_shields(
            [buff], 'enemy_1509_mousek')
        self.assertEqual((total, mask), (0.0, 0))
        self.assertFalse(sources[0]['active'])

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

    def test_spawn_eta_adds_off_map_route_entry_time(self):
        reader = EnemyReader(mc=object())
        reader._route_meta = {
            0: {'start': (2, 11), 'entry': (2, 9), 'distance': 2.0,
                'fixed_wait': 0.0, 'diagonal': False}}
        reader._level_enemy_meta = {
            'enemy_a': {'move_speed': 0.5, 'delay_to_born': 0.0}}
        reader._set_spawn_plan([{
            'key': 'enemy_a', 'action_ptr': 0x1000, 'spawn_index': 0,
            'route_index': 0, 'wave_index': 0, 'fragment_index': 0,
        }])
        reader._fragment_start_time = 50.0
        reader._action_queue_entries = [{
            'action_ptr': 0x1000, 'occurrence': 0, 'time_offset': 10.0,
        }]
        rows = reader._apply_spawn_timing(
            [reader._spawn_plan[0]['info']], scheduler_time=55.25)
        self.assertAlmostEqual(rows[0].spawn_eta, 8.75)
        self.assertIn('4.0 秒进入地图', rows[0].spawn_condition)

    def test_spawned_enemy_stays_pending_until_first_route_entry(self):
        reader = EnemyReader(mc=object())
        reader._route_meta = {
            0: {'start': (2, 11), 'entry': (2, 9), 'distance': 2.0,
                'fixed_wait': 0.0, 'diagonal': False}}
        reader._level_enemy_meta = {'enemy_a': {'move_speed': 0.5}}
        reader._set_spawn_plan([{'key': 'enemy_a', 'route_index': 0}])
        enemy = EnemyInfo(0x1000)
        enemy.eid = 'enemy_a'
        enemy.alive = True
        enemy.mspd = 0.5
        enemy.pos_x, enemy.pos_y = 10.0, 2.0
        rows = reader._merge_enemy_roster([enemy], 1)
        self.assertEqual(rows[0].lifecycle, 'pending')
        self.assertAlmostEqual(rows[0].spawn_eta, 2.0)
        enemy.pos_x = 8.95
        rows = reader._merge_enemy_roster([enemy], 1)
        self.assertEqual(rows[0].lifecycle, 'active')

    def test_obscured_float_v2_byte_swap(self):
        # 现网 Faust moveSpeed=0.5 的 AttributesData 原始字节。
        self.assertAlmostEqual(gs.decrypt_obscured_float(
            0x001DD4F8, 0x3FD41DF8), 0.5)

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


class FastPollRetryTests(unittest.TestCase):
    """同帧补读: 通道瞬态失败不应被渲染成敌人消失或整帧失效。"""

    EP = 0x7000001000
    LIST = 0x7000002000
    ITEMS = 0x7000003000

    @classmethod
    def _enemy_block(cls, hp=5000.0):
        block = bytearray(gs.EnemyFields.READ_SIZE)
        struct.pack_into('<Q', block, gs.EntityFields.M_HP, int(hp * gs.FP_ONE))
        return bytes(block)

    @classmethod
    def _list_header(cls, cnt=1):
        head = bytearray(0x20)
        struct.pack_into('<Q', head, gs.ListInternal.ITEMS, cls.ITEMS)
        struct.pack_into('<i', head, gs.ListInternal.SIZE, cnt)
        struct.pack_into('<i', head, gs.ListInternal.VERSION, 1)
        return bytes(head)

    def _make_reader(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and 0x1000 <= value < 0x800000000000

        reader = EnemyReader(mc=FakeMem())
        reader.list_addr = self.LIST
        reader._names[self.EP] = ('enemy_x', '敌人X', '')
        reader._attr_snapshot[self.EP] = {gs.AttributeType.MAX_HP: 5000.0}
        reader._runtime_snapshot[self.EP] = {}
        reader._f_ptrs = [self.EP]
        return reader

    def _flaky_channel(self, fail_all_once):
        block, head, arr = (self._enemy_block(), self._list_header(),
                            struct.pack('<Q', self.EP))
        state = {'fail_all_once': fail_all_once, 'calls': 0}
        ep, list_addr, items_addr = self.EP, self.LIST, self.ITEMS

        class FlakyChannel:
            mode = 'srv'

            @staticmethod
            def batch_read(reqs):
                state['calls'] += 1
                if state['fail_all_once']:
                    state['fail_all_once'] = False
                    return [None] * len(reqs)   # 整批瞬态失败一次
                out = []
                for addr, _size in reqs:
                    if addr == list_addr:
                        out.append(head)
                    elif addr == items_addr + gs.Il2CppArray.ITEMS:
                        out.append(arr)
                    elif addr <= ep < addr + _size:
                        out.append(block)
                    else:
                        out.append(None)
                return out

        return FlakyChannel(), state

    def test_transient_failures_are_reread_in_the_same_frame(self):
        reader = self._make_reader()
        reader._fast_tick = 4          # 本帧 tick=5, 触发 List 头读取
        chan, state = self._flaky_channel(fail_all_once=True)
        reader._chan = chan
        snap = reader._poll_fast_impl()
        self.assertTrue(snap['ok'])
        self.assertEqual(snap['msg'], '')
        self.assertEqual(len(snap['enemies']), 1)
        self.assertEqual(snap['enemies'][0].hp, 5000.0)
        self.assertEqual(reader._stale_cnt, 0)
        roster_ids = [enemy.roster_id for enemy in snap['enemies']]

        # 下一帧再来一次整批瞬态失败: 同帧补读成功, 身份与位置不变
        state['fail_all_once'] = True
        reader._fast_tick = 6          # tick=7 稳态帧, 只读敌人簇
        snap2 = reader._poll_fast_impl()
        self.assertTrue(snap2['ok'])
        self.assertEqual(
            [enemy.roster_id for enemy in snap2['enemies']], roster_ids)
        self.assertEqual(snap2['enemies'][0].hp, 5000.0)

    def test_enemy_unreadable_after_retry_is_missing_not_faked(self):
        class DeadChannel:
            mode = 'srv'

            @staticmethod
            def batch_read(reqs):
                return [None] * len(reqs)

        reader = self._make_reader()
        reader._fast_tick = 6          # tick=7 稳态帧, 只读敌人簇
        reader._chan = DeadChannel()
        snap = reader._poll_fast_impl()
        # 补读仍失败 = 本帧确实读不到: 帧有效但该敌人不渲染 (不编造数据)
        self.assertTrue(snap['ok'])
        self.assertEqual(snap['enemies'], [])

    def test_read_enemy_rereads_transient_block_failure(self):
        block = self._enemy_block()
        state = {'fail': True}

        class FlakyMem:
            @staticmethod
            def is_ptr(_value):
                return False

            @staticmethod
            def read(_addr, _size, timeout=30):
                if state['fail']:
                    state['fail'] = False
                    return None
                return block

        reader = EnemyReader(mc=FlakyMem())
        reader._names[self.EP] = ('enemy_x', '敌人X', '')
        info = reader._read_enemy(self.EP, with_runtime=False)
        self.assertTrue(info.alive)
        self.assertEqual(info.hp, 5000.0)


class BuffSourceNameTests(unittest.TestCase):
    """Buff 来源实体名称解析: 敌人走 _names, 干员/召唤物读 Entity.id。"""

    SRC = 0x7000005000
    IDP = 0x7000006000

    @classmethod
    def _fake_mem(cls, text='char_4235_thumpy'):
        id_blk = bytearray(gs.EntityFields.ID + 8)
        struct.pack_into('<Q', id_blk, gs.EntityFields.ID, cls.IDP)
        str_blk = bytearray(gs.Il2CppString.CHARS + 512 * 2)
        encoded = text.encode('utf-16-le')
        struct.pack_into('<i', str_blk, gs.Il2CppString.LENGTH, len(text))
        str_blk[gs.Il2CppString.CHARS:gs.Il2CppString.CHARS + len(encoded)] = encoded
        src, idp = cls.SRC, cls.IDP

        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and 0x1000 <= value < 0x800000000000

            @staticmethod
            def read(addr, _size, timeout=30):
                if addr == src:
                    return bytes(id_blk)
                if addr == idp:
                    return bytes(str_blk)
                return None

        return FakeMem

    def test_resolves_character_entity_via_char_names(self):
        class CountingMem(self._fake_mem()):
            reads = 0

            def read(self_, addr, _size, timeout=30):
                self_.reads += 1
                return super().read(addr, _size, timeout)

        mc = CountingMem()
        reader = EnemyReader(mc=mc)
        reader._db = {}
        reader._char_names = {'char_4235_thumpy': '珊比'}
        names = reader._resolve_buff_source_names([self.SRC])
        self.assertEqual(names[self.SRC], '珊比')
        # 第二次命中地址缓存, 不再读内存
        before = mc.reads
        self.assertEqual(
            reader._resolve_buff_source_names([self.SRC])[self.SRC], '珊比')
        self.assertEqual(mc.reads, before)

    def test_enemy_source_hits_names_without_extra_reads(self):
        class FakeMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value > 0

            @staticmethod
            def read(_addr, _size, timeout=30):
                raise AssertionError('敌人来源命中 _names, 不应再读内存')

        reader = EnemyReader(mc=FakeMem())
        reader._names[self.SRC] = ('enemy_x', '敌人X', '')
        self.assertEqual(
            reader._resolve_buff_source_names([self.SRC])[self.SRC], '敌人X')

    def test_unknown_entity_falls_back_to_id_text(self):
        reader = EnemyReader(mc=self._fake_mem('enemy_9999_unknown')())
        reader._db = {}
        reader._char_names = {}
        names = reader._resolve_buff_source_names([self.SRC])
        self.assertEqual(names[self.SRC], 'enemy_9999_unknown')

    def test_read_strings_retries_failed_read_once(self):
        text = 'conveyor_speed'
        str_blk = bytearray(gs.Il2CppString.CHARS + 512 * 2)
        encoded = text.encode('utf-16-le')
        struct.pack_into('<i', str_blk, gs.Il2CppString.LENGTH, len(text))
        str_blk[gs.Il2CppString.CHARS:gs.Il2CppString.CHARS + len(encoded)] = encoded
        state = {'fail': True}
        idp = self.IDP

        class FlakyMem:
            @staticmethod
            def is_ptr(value):
                return isinstance(value, int) and value > 0

            @staticmethod
            def read(addr, _size, timeout=30):
                if addr != idp:
                    return None
                if state['fail']:
                    state['fail'] = False
                    return None
                return bytes(str_blk)

        reader = EnemyReader(mc=FlakyMem())
        out = reader._read_strings([self.IDP])
        self.assertEqual(out[self.IDP], 'conveyor_speed')


if __name__ == '__main__':
    unittest.main()
