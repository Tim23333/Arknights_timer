"""Memory-only handbook regression tests; no emulator, DB file or file fallback."""
import struct
import unittest
from unittest.mock import patch

from tools.enemy_health.enemy_handbook import EnemyHandbook


class Memory:
    pid, adb_serial, package = 77, 'test-device', 'test-game'

    def __init__(self):
        self.blocks = {}
        self.types = {}
        self.calls = 0

    @staticmethod
    def is_ptr(address):
        return isinstance(address, int) and address >= 0x1000

    def read(self, address, size):
        self.calls += 1
        for start, raw in self.blocks.items():
            if start <= address and address + size <= start + len(raw):
                return bytes(raw[address - start:address - start + size])
        return None

    def read_klass_name(self, address):
        return self.types.get(address)

    def channel(self):
        return self

    def batch_read(self, requests, **kwargs):
        return [self.read(address, size) for address, size in requests]

    def object(self, address, name, size):
        # Real klass/name pointer layout is consumed by the existing batch type
        # resolver; only the external scanning boundary is mocked in these tests.
        klass = 0x100000 + len(self.types) * 0x1000
        header = bytearray(0x20)
        struct.pack_into('<Q', header, 0x10, klass + 0x100)
        self.blocks[klass] = header
        self.blocks[klass + 0x100] = name.encode() + bytes(64 - len(name))
        raw = bytearray(size)
        struct.pack_into('<Q', raw, 0, klass)
        self.blocks[address] = raw
        self.types[address] = name
        return raw

    def string(self, address, value):
        raw = self.object(address, 'String', 0x100)
        struct.pack_into('<i', raw, 0x10, len(value))
        text = value.encode('utf-16-le')
        raw[0x14:0x14 + len(text)] = text


class HandbookTests(unittest.TestCase):
    def setUp(self):
        self.mc = Memory()
        db = self.mc.object(0x1000, 'EnemyHandBookDB', 0x180)
        struct.pack_into('<Q', db, 0x50, 0x2000)
        group = self.mc.object(0x2000, 'EnemyHandBookDataGroup', 0x28)
        struct.pack_into('<Q', group, 0x18, 0x3000)
        dictionary = self.mc.object(0x3000, 'Dictionary`2', 0x30)
        struct.pack_into('<Qiiii', dictionary, 0x18, 0x4000, 1, -1, 0, 1)
        entries = self.mc.object(0x4000, 'Entry[]', 0x38)
        struct.pack_into('<i', entries, 0x18, 1)
        struct.pack_into('<iiQQ', entries, 0x20, 1, -1, 0x6000, 0x5000)
        record = self.mc.object(0x5000, 'EnemyHandBookData', 0x20)
        struct.pack_into('<QQ', record, 0x10, 0x6000, 0x7000)
        self.mc.string(0x6000, 'enemy_1507_mephi')
        self.mc.string(0x7000, 'MP')
        self.handbook = EnemyHandbook(self.mc)
        self.scan = patch('tools.deploy_tracker.ak_deploy_reader.DeployTrackerReader._scan_class_objects',
            return_value={'EnemyHandBookDB': {0x1000}, 'EnemyHandBookDataGroup': {0x2000}})

    def test_memory_chain_and_cache_validation(self):
        with self.scan as scan:
            self.assertEqual(self.handbook.load(log=lambda _: None), {'enemy_1507_mephi': 'MP'})
            scan.assert_called_once_with(('EnemyHandBookDB', 'EnemyHandBookDataGroup'), namespace='Torappu')
            self.assertEqual(self.handbook.load(locate=False), {'enemy_1507_mephi': 'MP'})
            self.assertEqual(scan.call_count, 1)

    def test_dictionary_key_must_match_record_id(self):
        self.mc.string(0x8000, 'enemy_wrong')
        struct.pack_into('<Q', self.mc.blocks[0x4000], 0x28, 0x8000)
        with self.scan:
            self.assertEqual(self.handbook.load(log=lambda _: None), {})

    def test_failed_read_and_process_change_cannot_reuse_old_code(self):
        with self.scan:
            self.assertEqual(self.handbook.load(log=lambda _: None)['enemy_1507_mephi'], 'MP')
        self.mc.blocks.pop(0x2000)
        self.assertEqual(self.handbook.load(locate=False), {})
        self.mc.pid = 78
        self.assertEqual(self.handbook.load(locate=False), {})

    def test_header_change_invalidates_cached_values_and_requires_complete_read(self):
        with self.scan:
            self.handbook.load(log=lambda _: None)
        struct.pack_into('<i', self.mc.blocks[0x3000], 0x2C, 2)
        self.mc.blocks.pop(0x7000)
        self.assertEqual(self.handbook.load(locate=False), {})

    def test_unlocated_reenable_does_not_start_a_full_memory_scan(self):
        with self.scan as scan:
            self.assertEqual(self.handbook.load(locate=False), {})
            scan.assert_not_called()


if __name__ == '__main__':
    unittest.main()
