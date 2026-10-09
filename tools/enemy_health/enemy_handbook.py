"""Enemy handbook codes from the loaded IL2CPP DB, never from local data files.

The DB owns immutable metadata, not current enemy HP or position. Discovery is
scan-time work; a verified DB/group reference and Dictionary version allow reuse
across stages within the same game process. No disk address/value cache is used.
"""
from __future__ import annotations

import struct


class EnemyHandbook:
    """Validate and cache the game's loaded enemyId → enemyIndex dictionary.

    Use during enemy bootstrap, not the frame loop. A missing/invalid DB returns
    no codes, never local-file fallbacks. The caller owns the memory channel.
    Candidate offsets were verified in the 2026-10-08 live-memory probe; object
    classes, dictionary bounds, ID equality and stable headers remain mandatory.
    """

    def __init__(self, mc):
        self.mc = mc
        self._process = None
        self._db = self._slot = self._group = 0
        self._signature = None
        self._codes = {}
        self.reason = 'handbook_not_located'

    def _batch(self, requests):
        # Chunk below memsrv's 8192-request ceiling, including large future DBs.
        result = []
        for start in range(0, len(requests), 1024):
            result.extend(self.mc.channel().batch_read(
                requests[start:start + 1024], remember=False, force_live=True))
        return result

    @staticmethod
    def _ptr(raw, offset=0):
        return struct.unpack_from('<Q', raw, offset)[0]

    def _types(self, objects):
        # deploy_tracker imports enemy_health's package entrypoint. Resolve its
        # optional scanner only during IO, after both packages have initialized.
        from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader
        locator = DeployTrackerReader(self.mc)
        result = {}
        for start in range(0, len(objects), 1024):
            result.update(locator._klass_names_batch(
                objects[start:start + 1024], read_many=self._batch))
        return result

    def _header(self, group):
        if self.mc.read_klass_name(group) != 'EnemyHandBookDataGroup':
            return None
        raw = self.mc.read(group, 0x28)
        if not raw:
            return None
        dictionary = self._ptr(raw, 0x18)
        if not self.mc.is_ptr(dictionary) or self.mc.read_klass_name(dictionary) != 'Dictionary`2':
            return None
        raw = self.mc.read(dictionary, 0x30)
        if not raw:
            return None
        entries = self._ptr(raw, 0x18)
        count, free_list, free_count, version = struct.unpack_from('<iiii', raw, 0x20)
        if (not self.mc.is_ptr(entries) or not 0 < count <= 10000
                or not 0 <= free_count <= count or not -1 <= free_list < count):
            return None
        array = self.mc.read(entries, 0x20)
        if not array:
            return None
        capacity = struct.unpack_from('<i', array, 0x18)[0]
        if not count <= capacity <= 20000:
            return None
        return dictionary, entries, count, free_count, version

    def _read_codes(self, group, signature):
        _, entries, count, free_count, _ = signature
        raw = self.mc.read(entries + 0x20, count * 0x18)
        if not raw or len(raw) != count * 0x18:
            return None
        pairs = []
        for index in range(count):
            offset = index * 0x18
            if struct.unpack_from('<i', raw, offset)[0] < 0:
                continue
            key, record = self._ptr(raw, offset + 8), self._ptr(raw, offset + 0x10)
            if not self.mc.is_ptr(key) or not self.mc.is_ptr(record):
                return None
            pairs.append((key, record))
        types = self._types([record for _, record in pairs])
        requests = [(record, 0x20) for _, record in pairs]
        fields = []
        for (key, record), block in zip(pairs, self._batch(requests)):
            if types.get(record) != 'EnemyHandBookData' or not block or len(block) < 0x20:
                return None
            fields.append((key, self._ptr(block, 0x10), self._ptr(block, 0x18)))
        addresses = sorted({address for row in fields for address in row})
        string_types = self._types(addresses)
        if any(string_types.get(address) != 'String' for address in addresses):
            return None
        texts = {}
        for address, block in zip(addresses, self._batch([(a, 0x100) for a in addresses])):
            if not block or len(block) < 0x100:
                return None
            length = struct.unpack_from('<i', block, 0x10)[0]
            if not 0 <= length <= 118:
                return None
            try:
                texts[address] = block[0x14:0x14 + length * 2].decode('utf-16-le')
            except UnicodeDecodeError:
                return None
        result = {}
        for key, enemy_id, code in fields:
            eid = texts[enemy_id]
            if not eid.startswith('enemy_') or texts[key] != eid or eid in result:
                return None
            result[eid] = texts[code]
        # A partially read/mutating table is not a valid replacement for metadata.
        if len(result) != count - free_count or self._header(group) != signature:
            return None
        return result

    def load(self, *, locate=True, log=print):
        """Return validated codes; optionally disallow expensive discovery on re-enable.

        This does not follow enemy runtime attributes or borrow a newer frame
        number. Revalidate ownership and version before using process-static data.
        """
        process = (self.mc.adb_serial, self.mc.package, self.mc.pid)
        if process != self._process:
            self._process = process
            self._db = self._slot = self._group = 0
            self._signature = None
            self._codes = {}
        if self._db and self.mc.read_klass_name(self._db) == 'EnemyHandBookDB':
            reference = self.mc.read(self._db + self._slot, 8)
            signature = self._header(self._group) if reference and self._ptr(reference) == self._group else None
            if signature is not None:
                if signature == self._signature:
                    return dict(self._codes)
                codes = self._read_codes(self._group, signature)
                if codes is not None:
                    self._signature, self._codes = signature, codes
                    self.reason = ''
                    return dict(codes)
        self._codes = {}
        self._signature = None
        self.reason = 'handbook_not_loaded_or_layout_changed'
        if not locate:
            return {}
        from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader
        locator = DeployTrackerReader(self.mc)
        locator._channel = self.mc.channel()
        locator.set_status_callback(log)
        objects = locator._scan_class_objects(
            ('EnemyHandBookDB', 'EnemyHandBookDataGroup'), namespace='Torappu') or {}
        groups = objects.get('EnemyHandBookDataGroup', set())
        for db in sorted(objects.get('EnemyHandBookDB', ())):
            block = self.mc.read(db, 0x180)
            if not block:
                continue
            # Generic ConstTable.m_data offsets in dump.cs are placeholder 0.
            # Locate the DB's actual reference slot, then validate the full chain.
            for slot in range(0x10, len(block) - 7, 8):
                group = self._ptr(block, slot)
                if group not in groups:
                    continue
                signature = self._header(group)
                codes = self._read_codes(group, signature) if signature is not None else None
                reference = self.mc.read(db + slot, 8)
                if codes is not None and reference and self._ptr(reference) == group:
                    self._db, self._slot, self._group = db, slot, group
                    self._signature, self._codes = signature, codes
                    self.reason = ''
                    return dict(codes)
        return {}
