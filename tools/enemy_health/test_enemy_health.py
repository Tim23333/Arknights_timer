# -*- coding: utf-8 -*-
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.enemy_health import game_structs as gs
from tools.enemy_health.enemy_reader import (
    EnemyInfo, EnemyReader, summarize_custom_shields,
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

    def test_all_current_attributes_are_declared(self):
        self.assertEqual(gs.AttributeType.E_NUM, 38)
        self.assertEqual({idx for idx, _, _ in gs.ATTRIBUTE_DEFS},
                         set(range(0, 9)) | set(range(13, 38)))

    def test_august_offsets_and_new_abnormal_flag_are_loaded(self):
        self.assertEqual(gs.EntityFields.M_ATTRIBUTES, 0xB0)
        self.assertEqual(gs.EntityFields.ID, 0x148)
        self.assertEqual(gs.EnemyFields.DATA, 0x510)
        self.assertEqual(gs.EnemyFields.READ_SIZE, 0x548)
        self.assertEqual(gs.BuffFields.IS_ACTUALLY_ENABLED, 0x1ED)
        self.assertEqual(gs.AbnormalFlag.E_NUM, 46)
        self.assertEqual(gs.ABNORMAL_FLAG_CN_NAMES[45], '地面束缚')

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
