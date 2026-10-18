"""有界、精确读取；不连接设备，不打开通道，不吞掉短读。"""

import struct


class ReadFailure(RuntimeError):
    """稳定理由码，不把地址带到公开接口。"""

    def __init__(self, reason="read_failed"):
        self.reason = reason
        super().__init__(reason)


class MemoryAccess:
    def __init__(self, memory, channel):
        self.mc, self.channel = memory, channel
        self.metadata = {}
        self._derived = set()

    def read_many(self, requests, *, structural_check=False):
        if not requests:
            return []
        # 默认请求加入既有 memsrv v5 计划；新地址按其拓扑失效规则处理。
        # Explicit addresses are resolved from the current parents each round.
        # Do not infer dependencies from unrelated nearby dynamic pointers:
        # fixed map/configuration reads otherwise become perpetual plan misses.
        options = (
            {"force_live": True, "remember": False}
            if structural_check else {"plan_direct": True}
        )
        values = self.channel.batch_read(requests, **options)
        if len(values) != len(requests) or any(
            raw is None or len(raw) != size for (_, size), raw in zip(requests, values)
        ):
            raise ReadFailure()
        return values

    def read(self, address, size):
        if not self.mc.is_ptr(address) or not 0 < size <= 4 * 1024 * 1024:
            raise ReadFailure("binding_invalid")
        return self.read_many([(address, size)])[0]

    def pointer(self, address):
        return struct.unpack("<Q", self.read(address, 8))[0]

    def read_code(self, address, size):
        """Read known library bytes, not object pointers or executable calls.

        MemCore.is_ptr deliberately accepts only rw heaps. ARM library bytes
        may be r-- on translated emulators; their whole range must be readable
        and owned by the expected libraries. Discovery never enters the hot
        frame plan and cannot weaken object/singleton ownership validation.
        """
        if not 0 < size <= 4096 or not any(
            start <= address and address + size <= end and 'r' in perms
            and name.endswith(('/libil2cpp.so', '/libunity.so'))
            for start, end, perms, name in self.mc.regions
        ):
            raise ReadFailure('binding_invalid')
        values = self.channel.batch_read([(address, size)], force_live=True, remember=False)
        if len(values) != 1 or values[0] is None or len(values[0]) != size:
            raise ReadFailure()
        return values[0]

    def integer(self, address):
        return struct.unpack("<i", self.read(address, 4))[0]

    def cstring(self, address):
        raw = self.read(address, 128)
        end = raw.find(b"\0")
        if end < 0:
            raise ReadFailure("unsupported_layout")
        try:
            return raw[:end].decode("ascii")
        except UnicodeError as error:
            raise ReadFailure("unsupported_layout") from error

    def identity(self, address, expected=None):
        klass = self.pointer(address)
        name, namespace = self.class_identity(klass)
        if expected is not None and name != expected:
            raise ReadFailure("unsupported_layout")
        return klass, name, namespace

    def class_identity(self, klass):
        if klass not in self.metadata:
            raw = self.read(klass + 0x10, 16)
            name, namespace = struct.unpack("<QQ", raw)
            self.metadata[klass] = (self.cstring(name), self.cstring(namespace))
        name, namespace = self.metadata[klass]
        return name, namespace

    def derived_identity(self, klass, expected, namespace):
        """Validate Android 2.7.81 class ancestry, with a bounded cycle guard.

        The object klass comes from this frame's already-read object header;
        process-scoped immutable metadata may be cached, gameplay values not.
        Il2CppClass.parent is +0x58 for this version's checked class layout.
        """
        key = (klass, expected, namespace)
        if key in self._derived:
            return
        current, seen = klass, set()
        for _ in range(32):
            if not current or current in seen:
                break
            seen.add(current)
            if self.class_identity(current) == (expected, namespace):
                self._derived.add(key)
                return
            current = self.pointer(current + 0x58)
        raise ReadFailure('unsupported_layout')

    def array(self, address, limit=16384):
        count = self.integer(address + 0x18)
        if not 0 <= count <= limit:
            raise ReadFailure("unsupported_layout")
        if not count:
            return []
        return list(struct.unpack(f"<{count}Q", self.read(address + 0x20, count * 8)))

    def string(self, address, limit=2048):
        if not address:
            return None
        # Immutable Il2CppString body is not cached by naked pointer: recycled
        # addresses must not revive a previous object's identity.
        count = self.integer(address + 0x10)
        if not 0 <= count <= limit:
            raise ReadFailure("unsupported_layout")
        try:
            return self.read(address + 0x14, count * 2).decode("utf-16-le") if count else ""
        except UnicodeError as error:
            raise ReadFailure() from error

    def strings(self, addresses, limit=2048):
        """Read distinct immutable strings in two batch phases, within this frame.

        No pointer-keyed cross-frame cache: a recycled address must be read again.
        Lengths remain bounded and every nonempty body must be complete.
        """
        addresses = list(dict.fromkeys(addresses))
        nonnull = [address for address in addresses if address]
        if any(not self.mc.is_ptr(address) for address in nonnull):
            raise ReadFailure('binding_invalid')
        lengths = [struct.unpack('<i', raw)[0] for raw in
                   self.read_many([(address + 0x10, 4) for address in nonnull])]
        if any(not 0 <= size <= limit for size in lengths):
            raise ReadFailure('unsupported_layout')
        bodies = iter(self.read_many([(address + 0x14, size * 2)
                                     for address, size in zip(nonnull, lengths) if size]))
        result = {address: None for address in addresses if not address}
        try:
            for address, size in zip(nonnull, lengths):
                result[address] = next(bodies).decode('utf-16-le') if size else ''
        except UnicodeError as error:
            raise ReadFailure() from error
        return result
