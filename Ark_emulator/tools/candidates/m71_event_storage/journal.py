"""Opt-in owned JSONL journal. Offsets and checksums remain resident between reads.

This is a private EventLog container, not a general mutable sequence. Each
append serializes the complete validated value; no object identity cache exists.
"""
from array import array
from pathlib import Path
import hashlib
import json
import uuid

from ._data import _plain, readonly


class DiskEventRecords:
    SCHEMA = "ark-sim/event-journal-reference/v1"

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("x+b")
        self._offsets = array("Q", [0])
        self._hashes = bytearray()

    def __len__(self):
        return len(self._offsets) - 1

    def append(self, record):
        line = json.dumps(_plain(record), ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False).encode("utf8", "backslashreplace") + b"\n"
        self._file.seek(self._offsets[-1])
        start = self._offsets[-1]
        try:
            if self._file.write(line) != len(line):
                raise OSError("Short event journal write")
            self._file.flush()
        except BaseException:
            # Logical end has not advanced. No rollback IO is necessary, even
            # if the write/flush failure persists. Future writes reuse this tail.
            raise
        self._offsets.append(start + len(line))
        self._hashes.extend(hashlib.sha256(line).digest())

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self))) ]
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        line = self._read_line(index)
        return readonly(json.loads(line))

    def _read_line(self, index):
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self._file.seek(self._offsets[index])
        line = self._file.read(self._offsets[index + 1] - self._offsets[index])
        if (len(line) != self._offsets[index + 1] - self._offsets[index] or
                hashlib.sha256(line).digest() != self._hashes[index * 32:(index + 1) * 32]):
            raise ValueError("Event journal truncated or corrupted")
        return line

    def extend(self, records):
        start = len(self)
        try:
            for record in records:
                self.append(record)
        except BaseException:
            del self[start:]
            raise

    def __iter__(self):
        for index in range(len(self)):
            yield self[index]

    def __delitem__(self, index):
        if not isinstance(index, slice) or index.stop is not None or index.step not in (None, 1):
            raise TypeError("Only event journal tail rollback is supported")
        start = index.indices(len(self))[0]
        # Rollback only the owned index: no disk IO can interrupt restoration
        # of world/scheduler/RNG. Aborted physical tail is excluded from every
        # read/export/checkpoint and can be overwritten by a future append.
        del self._offsets[start + 1:]
        del self._hashes[start * 32:]

    def export(self, path):
        path = Path(path).resolve()
        if path == self.path:
            raise ValueError("Export destination must differ from the active journal")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file.flush()
        digest = hashlib.sha256()
        with path.open("xb") as destination:
            for index in range(len(self)):
                line = self._read_line(index)
                destination.write(line)
                digest.update(line)
        return {"path": str(path), "sha256": digest.hexdigest(), "bytes": self._offsets[-1],
                "count": len(self)}

    def reference(self):
        # A sealed copy is necessary: live appends/rollback must not invalidate
        # a checkpoint already returned to its caller.
        path = self.path.with_name(self.path.name + ".checkpoint-" + uuid.uuid4().hex)
        return {"schema": self.SCHEMA, **self.export(path)}

    @classmethod
    def from_reference(cls, reference):
        if reference.get("schema") != cls.SCHEMA:
            raise ValueError("Unsupported event journal reference")
        path = Path(reference["path"])
        if not path.is_absolute():
            raise ValueError("Event journal reference path must be absolute")
        destination = path.with_name(path.name + ".branch-" + uuid.uuid4().hex)
        journal = cls(destination)
        try:
            digest = hashlib.sha256()
            with path.open("rb") as source:
                # Read actual bytes into a fresh independent branch; never trust
                # offsets, a live handle, or metadata from the producing session.
                for line in source:
                    if not line.endswith(b"\n"):
                        raise ValueError("Event journal reference has an incomplete line")
                    digest.update(line)
                    json.loads(line)
                    journal._file.write(line)
                    journal._offsets.append(journal._offsets[-1] + len(line))
                    journal._hashes.extend(hashlib.sha256(line).digest())
            journal._file.flush()
            if (digest.hexdigest() != reference["sha256"] or
                    journal._offsets[-1] != reference["bytes"] or len(journal) != reference["count"]):
                raise ValueError("Event journal reference digest/size/count mismatch")
            return journal
        except BaseException:
            journal._file.close()
            destination.unlink(missing_ok=True)
            raise

    def __del__(self):
        file = getattr(self, "_file", None)
        if file is not None:
            file.close()
