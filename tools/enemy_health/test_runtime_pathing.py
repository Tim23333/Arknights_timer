# -*- coding: utf-8 -*-
import json
import struct
import unittest

from tools.enemy_health import game_structs as gs
from tools.enemy_health.enemy_reader import (
    EnemyInfo, EnemyReader, unavailable_pathing,
)
from tools.enemy_health.memcore import TcpChannel


def _fp(seconds):
    return int(round(float(seconds) * gs.FP_ONE)) & 0xFFFFFFFFFFFFFFFF


class _Memory:
    def __init__(self):
        self.blocks = {}

    def add(self, address, size):
        block = bytearray(size)
        self.blocks[address] = block
        return block

    def read(self, address, size):
        for base, block in self.blocks.items():
            if base <= address and address + size <= base + len(block):
                offset = address - base
                return bytes(block[offset:offset + size])
        return None


class _MemCore:
    @staticmethod
    def is_ptr(value):
        return isinstance(value, int) and value >= 0x1000


class _GuardedChannel:
    def __init__(self, memory, frame, *, mutate_identity=False,
                 guard_frame=None):
        self.memory = memory
        self.frame = frame
        self.mutate_identity = mutate_identity
        self.guard_frame = frame if guard_frame is None else guard_frame
        self.calls = 0
        self.last_operations = None

    def guarded_transaction_read(self, operations, guard_addr, guard_size=4,
                                 max_attempts=8):
        self.calls += 1
        self.last_operations = list(operations)
        values = []
        for op in operations:
            if op[0] == 'direct':
                _kind, address, size = op
                values.append(self.memory.read(address, size))
            elif op[0] == 'deref':
                _kind, ref, pointer_offset, addend, size = op
                source = values[ref]
                pointer = struct.unpack_from('<Q', source, pointer_offset)[0] \
                    if source and len(source) >= pointer_offset + 8 else 0
                values.append(self.memory.read(pointer + addend, size)
                              if pointer else None)
            elif op[0] == 'array_ptr':
                _kind, ref, array_offset, index_offset = op
                source = values[ref]
                array_ptr = struct.unpack_from('<Q', source, array_offset)[0] \
                    if source else 0
                index = struct.unpack_from('<i', source, index_offset)[0] \
                    if source else -1
                head = self.memory.read(array_ptr, gs.Il2CppArray.ITEMS)
                count = struct.unpack_from(
                    '<I', head, gs.Il2CppArray.MAX_LENGTH)[0] if head else 0
                pointer_data = (self.memory.read(
                    array_ptr + gs.Il2CppArray.ITEMS + index * 8, 8)
                    if 0 <= index < count else None)
                values.append(pointer_data)
            else:
                raise AssertionError(op)
        if self.mutate_identity:
            cursor_results = [index for index, op in enumerate(operations)
                              if op[0] == 'deref'
                              and op[-1] == gs.DirectionCursorFields.READ_SIZE]
            changed = bytearray(values[cursor_results[-1]])
            struct.pack_into('<i', changed, gs.BasicCursorFields.M_CURSOR, 1)
            values[cursor_results[-1]] = bytes(changed)
        guard = {
            'attempts': 1, 'start': self.guard_frame,
            'end': self.guard_frame, 'complete': True,
        }
        return values, guard


def _make_reader(*, frame=1234, mutate_identity=False, guard_frame=None):
    memory = _Memory()
    static_fields = 0x10000
    enemy_addr = 0x20000
    cursor_addr = 0x30000
    route_addr = 0x40000
    route_data_addr = 0x50000
    checkpoint_array_addr = 0x60000
    checkpoint_addr = 0x70000
    checkpoint_data_addr = 0x80000

    clock = memory.add(
        static_fields + gs.BattleControllerStaticFields.FIXED_FRAME_COUNT,
        gs.BattleControllerStaticFields.DELTA_PLAY_TIME_FP
        - gs.BattleControllerStaticFields.FIXED_FRAME_COUNT + 8)
    struct.pack_into('<I', clock, 0, frame)
    struct.pack_into('<Q', clock, 4, _fp(12.5))
    struct.pack_into(
        '<Q', clock,
        gs.BattleControllerStaticFields.DELTA_PLAY_TIME_FP
        - gs.BattleControllerStaticFields.FIXED_FRAME_COUNT,
        _fp(1.0 / 30.0))

    enemy = memory.add(
        enemy_addr + gs.EnemyFields.M_CURSOR,
        gs.EnemyFields.ROUTE_END_POS + 8 - gs.EnemyFields.M_CURSOR)
    struct.pack_into('<Q', enemy, 0, cursor_addr)
    struct.pack_into(
        '<Q', enemy,
        gs.EnemyFields.M_CACHED_ROUTE - gs.EnemyFields.M_CURSOR, route_addr)
    struct.pack_into(
        '<ii', enemy,
        gs.EnemyFields.ROUTE_END_POS - gs.EnemyFields.M_CURSOR, 5, 9)

    cursor = memory.add(cursor_addr, gs.DirectionCursorFields.READ_SIZE)
    struct.pack_into('<Q', cursor, gs.BasicCursorFields.M_ROUTE, route_addr)
    struct.pack_into('<i', cursor, gs.BasicCursorFields.M_CURSOR, 0)
    struct.pack_into(
        '<Q', cursor, gs.BasicCursorFields.M_CHECKPOINTS,
        checkpoint_array_addr)
    struct.pack_into(
        '<Q', cursor,
        gs.BasicCursorFields.SNAPSHOT + gs.SchedulerSnapshotFields.WAVE_START_TIME,
        _fp(8.0))
    struct.pack_into(
        '<Q', cursor,
        gs.BasicCursorFields.SNAPSHOT
        + gs.SchedulerSnapshotFields.FRAGMENT_START_TIME,
        _fp(10.0))
    struct.pack_into('<ii', cursor, gs.DirectionCursorFields.M_NEXT_GRID, 2, 7)

    route = memory.add(route_addr, gs.RouteFields.READ_SIZE)
    struct.pack_into('<Q', route, gs.RouteFields.M_DATA, route_data_addr)
    route_data = memory.add(route_data_addr, gs.RouteDataFields.READ_SIZE)
    struct.pack_into('<ii', route_data, gs.RouteDataFields.START_POSITION, 0, 0)
    struct.pack_into('<ii', route_data, gs.RouteDataFields.END_POSITION, 5, 9)
    struct.pack_into(
        '<Q', route_data, gs.RouteDataFields.CHECKPOINTS,
        checkpoint_array_addr)

    checkpoint_array = memory.add(checkpoint_array_addr, 0x28)
    struct.pack_into('<I', checkpoint_array, gs.Il2CppArray.MAX_LENGTH, 1)
    struct.pack_into(
        '<Q', checkpoint_array, gs.Il2CppArray.ITEMS, checkpoint_addr)
    checkpoint = memory.add(checkpoint_addr, gs.RuntimeCheckpointFields.READ_SIZE)
    struct.pack_into(
        '<Q', checkpoint, gs.RuntimeCheckpointFields.DATA, checkpoint_data_addr)
    checkpoint_data = memory.add(
        checkpoint_data_addr, gs.RouteCheckpointFields.READ_SIZE)
    struct.pack_into(
        '<i', checkpoint_data, gs.RouteCheckpointFields.TYPE,
        gs.RouteCheckpointType.WAIT_CURRENT_FRAGMENT_TIME)
    struct.pack_into('<f', checkpoint_data, gs.RouteCheckpointFields.TIME, 15.0)
    struct.pack_into('<ii', checkpoint_data, gs.RouteCheckpointFields.POSITION, 2, 7)

    reader = EnemyReader(mc=_MemCore())
    reader._chan = _GuardedChannel(
        memory, frame, mutate_identity=mutate_identity,
        guard_frame=guard_frame)
    reader._bc_static_fields = static_fields
    reader._fixed_frame_snap = frame
    reader._route_by_object = {
        route_addr: {
            'kind': 'main', 'index': 0, 'ordinal': 1,
            'global_index': 0, 'start': (0, 0), 'end': (5, 9),
            'route_data_ptr': route_data_addr, 'fingerprint': (),
        },
    }
    reader._route_by_data = {}
    reader._route_by_checkpoint_array = {}
    reader._route_by_fingerprint = {}
    reader._level_map_data = {}
    return reader, enemy_addr


class RuntimePathingTests(unittest.TestCase):
    def test_enemy_info_pathing_is_fresh_and_fail_closed(self):
        first = EnemyInfo(0x1000)
        second = EnemyInfo(0x2000)
        first.pathing['reason'] = 'changed'
        self.assertEqual(second.pathing['reason'], 'not_sampled')
        self.assertFalse(second.pathing['available'])
        self.assertFalse(unavailable_pathing('pending')['historical'])

    def test_all_paths_use_one_guarded_transaction_and_publish_no_pointer(self):
        reader, enemy_addr = _make_reader()
        info = EnemyInfo(enemy_addr)
        reader._refresh_pathing_chan([enemy_addr], {enemy_addr: info})

        self.assertEqual(reader._chan.calls, 1)
        self.assertEqual(len(reader._chan.last_operations), 17)
        pathing = info.pathing
        self.assertTrue(pathing['available'])
        self.assertTrue(pathing['consistent'])
        self.assertTrue(pathing['path_identity_stable'])
        self.assertEqual(pathing['sample_frame'], 1234)
        self.assertEqual(pathing['intent_end']['label'], 'F10')
        self.assertEqual(pathing['route']['label'], '主#1（A1→F10）')
        self.assertEqual(pathing['next_waypoint']['label'], 'C8')
        self.assertEqual(
            pathing['next_checkpoint']['type_name'],
            'WAIT_CURRENT_FRAGMENT_TIME')
        countdown = pathing['checkpoint_countdown']
        self.assertAlmostEqual(countdown['seconds'], 12.5, places=5)
        self.assertEqual(countdown['frames'], 375)
        self.assertTrue(countdown['exact'])
        self.assertEqual(countdown['source'], 'fragment_clock')
        public = json.dumps(pathing, ensure_ascii=False)
        for address in (enemy_addr, 0x30000, 0x40000, 0x50000,
                        0x60000, 0x70000, 0x80000):
            self.assertNotIn(str(address), public)

    def test_single_transaction_capacity_covers_reader_live_enemy_limit(self):
        reader, _enemy_addr = _make_reader()
        operations, _clock, layouts = reader._build_path_transaction(
            [0x20000 + index * 0x1000 for index in range(300)])
        self.assertEqual(len(layouts), 300)
        self.assertEqual(len(operations), 1 + 300 * 16)
        self.assertLessEqual(len(operations), TcpChannel.MAX_REQUESTS)

    def test_identity_change_rejects_both_chains_instead_of_using_old_path(self):
        reader, enemy_addr = _make_reader(mutate_identity=True)
        info = EnemyInfo(enemy_addr)
        info.pathing = {'available': True, 'route': {'label': '旧路线'}}
        reader._refresh_pathing_chan([enemy_addr], {enemy_addr: info})
        self.assertFalse(info.pathing['available'])
        self.assertFalse(info.pathing['consistent'])
        self.assertEqual(info.pathing['reason'], 'path_identity_changed')
        self.assertIsNone(info.pathing['route'])

    def test_guard_frame_must_equal_enemy_snapshot_frame(self):
        reader, enemy_addr = _make_reader(guard_frame=1235)
        info = EnemyInfo(enemy_addr)
        reader._refresh_pathing_chan([enemy_addr], {enemy_addr: info})
        self.assertFalse(info.pathing['available'])
        self.assertEqual(info.pathing['reason'], 'path_frame_mismatch')

    def test_missing_v5_capability_never_falls_back_to_host_pointer_walk(self):
        reader, enemy_addr = _make_reader()
        reader._chan = object()
        info = EnemyInfo(enemy_addr)
        reader._refresh_pathing_chan([enemy_addr], {enemy_addr: info})
        self.assertFalse(info.pathing['available'])
        self.assertEqual(info.pathing['reason'], 'path_guard_unavailable')

    def test_full_fingerprint_distinguishes_same_endpoint_routes(self):
        base = {
            'motionMode': 0, 'start': {'row': 0, 'col': 0},
            'end': {'row': 5, 'col': 9}, 'allowDiagonalMove': False,
            'checkpoints': [{
                'type': gs.RouteCheckpointType.MOVE, 'time': 0.0,
                'position': {'row': 2, 'col': 7},
                'reachOffset': {'x': 0.0, 'y': 0.0},
                'randomizeReachOffset': False, 'reachDistance': 0.1,
            }],
        }
        changed = dict(base)
        changed['checkpoints'] = [dict(base['checkpoints'][0])]
        changed['checkpoints'][0]['position'] = {'row': 3, 'col': 7}
        self.assertNotEqual(
            EnemyReader._route_fingerprint(base),
            EnemyReader._route_fingerprint(changed))

    def test_route_data_replacement_is_marked_runtime_modified(self):
        reader, _enemy_addr = _make_reader()
        route = reader._match_runtime_route(
            0x40000, 0x50008, 0x60008, 0, (0, 0), (5, 9))
        self.assertEqual(route['matched_by'], 'route_object')
        self.assertTrue(route['runtime_modified'])

        reader._route_by_object.clear()
        reader._route_by_checkpoint_array[0x60000] = {
            'kind': 'main', 'index': 0, 'ordinal': 1,
            'global_index': 0, 'start': (0, 0), 'end': (5, 9),
            'route_data_ptr': 0x50000,
        }
        cloned = reader._match_runtime_route(
            0x40008, 0x50008, 0x60000, 0, (0, 0), (5, 9))
        self.assertEqual(cloned['matched_by'], 'checkpoint_array')
        self.assertTrue(cloned['runtime_modified'])

    def test_extra_cached_and_unmatched_runtime_routes_are_not_mislabelled(self):
        reader, _enemy_addr = _make_reader()
        reader._route_by_object[0x41000] = {
            'kind': 'extra', 'index': 0, 'ordinal': 1,
            'global_index': 1, 'start': (0, 0), 'end': (5, 9),
            'route_data_ptr': 0x51000,
        }
        extra = reader._match_runtime_route(
            0x41000, 0x51000, 0x61000, 0, (0, 0), (5, 9))
        self.assertEqual(extra['kind'], 'extra')
        self.assertEqual(extra['label'], '额外#1（A1→F10）')
        cached = reader._match_runtime_route(
            0x42000, 0x52000, 0x62000, 0x40000, (0, 0), (4, 8))
        self.assertEqual(cached['matched_by'], 'cached_route')
        self.assertTrue(cached['runtime_modified'])
        runtime = reader._match_runtime_route(
            0x43000, 0x53000, 0x63000, 0, (1, 1), (4, 8))
        self.assertEqual(runtime['kind'], 'runtime')
        self.assertEqual(runtime['matched_by'], 'unmatched')

    def test_trace_cursor_presence_does_not_claim_active_diversion(self):
        reader, enemy_addr = _make_reader()
        enemy = reader._chan.memory.blocks[
            enemy_addr + gs.EnemyFields.M_CURSOR]
        struct.pack_into(
            '<Q', enemy,
            gs.EnemyFields.M_TRACE_TARGET_CURSOR - gs.EnemyFields.M_CURSOR,
            0x90000)
        info = EnemyInfo(enemy_addr)
        reader._refresh_pathing_chan([enemy_addr], {enemy_addr: info})
        self.assertTrue(info.pathing['available'])
        self.assertFalse(info.pathing['temporarily_diverted'])

    def test_intent_end_is_marked_when_it_targets_a_friendly_goal_tile(self):
        reader, enemy_addr = _make_reader()
        reader._level_map_data = {
            'rows': 6, 'cols': 10,
            'tiles': [
                {'row': row, 'col': col,
                 'tileKey': ('tile_end' if (row, col) == (0, 9)
                             else 'tile_road')}
                for row in range(6) for col in range(10)
            ],
        }
        info = EnemyInfo(enemy_addr)
        reader._refresh_pathing_chan([enemy_addr], {enemy_addr: info})
        self.assertEqual(info.pathing['intent_end']['tile_category'],
                         'friendly_goal')
        self.assertEqual(info.pathing['intent_end']['label'],
                         'F10（友方目标）')

    def test_all_clock_based_checkpoint_countdowns_use_runtime_frame_duration(self):
        reader, _enemy_addr = _make_reader()
        cursor = bytes(reader._chan.memory.blocks[0x30000])
        checkpoint_block = bytearray(gs.RuntimeCheckpointFields.READ_SIZE)
        struct.pack_into(
            '<Q', checkpoint_block, gs.WaitForSecondsCheckpointFields.M_TIME,
            _fp(4.25))
        cases = (
            (gs.RouteCheckpointType.WAIT_FOR_SECONDS, 99.0,
             4.25, 'runtime_wait_timer'),
            (gs.RouteCheckpointType.WAIT_FOR_PLAY_TIME, 15.0,
             2.5, 'play_clock'),
            (gs.RouteCheckpointType.WAIT_CURRENT_WAVE_TIME, 15.0,
             10.5, 'wave_clock'),
            (gs.RouteCheckpointType.WAIT_CURRENT_FRAGMENT_TIME, 15.0,
             12.5, 'fragment_clock'),
        )
        for cp_type, target, expected, source in cases:
            with self.subTest(cp_type=cp_type):
                countdown = reader._checkpoint_countdown(
                    {'type': cp_type, 'time': target},
                    bytes(checkpoint_block), cursor, 12.5, 1.0 / 30.0)
                self.assertAlmostEqual(countdown['seconds'], expected)
                self.assertEqual(countdown['frames'], round(expected * 30))
                self.assertTrue(countdown['exact'])
                self.assertEqual(countdown['source'], source)

        event = reader._checkpoint_countdown(
            {'type': gs.RouteCheckpointType.ALERT, 'time': None},
            bytes(checkpoint_block), cursor, 12.5, 1.0 / 30.0)
        self.assertIsNone(event['seconds'])
        self.assertFalse(event['exact'])
        self.assertEqual(event['source'], 'event_condition')

    def test_cursor_at_checkpoint_count_reports_route_end_without_stale_pointer(self):
        reader, enemy_addr = _make_reader()
        checkpoint_array = reader._chan.memory.blocks[0x60000]
        struct.pack_into(
            '<I', checkpoint_array, gs.Il2CppArray.MAX_LENGTH, 0)
        info = EnemyInfo(enemy_addr)
        reader._refresh_pathing_chan([enemy_addr], {enemy_addr: info})
        self.assertTrue(info.pathing['available'])
        self.assertEqual(
            info.pathing['next_checkpoint']['type_name'], 'ROUTE_END')
        self.assertIn('F10', info.pathing['next_checkpoint']['label'])
        self.assertIsNone(info.pathing['checkpoint_countdown']['seconds'])


if __name__ == '__main__':
    unittest.main()
