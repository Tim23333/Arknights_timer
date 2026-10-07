"""Opt-in owned JSONL journal. Offsets and checksums remain resident between reads.

This is a private EventLog container, not a general mutable sequence. Each
append serializes the complete validated value; no object identity cache exists.
"""
from array import array
from collections.abc import Mapping
from pathlib import Path
import hashlib
import json
import uuid

from ._data import _plain, readonly


def _unique_pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ValueError('Event reference contains duplicate JSON object keys')
        result[key]=value
    return result


def _strict_record(line, previous_id=None, previous_time=None):
    from .events import freeze_event_payload
    from ._data import integer,name
    record=json.loads(line,object_pairs_hook=_unique_pairs)
    freeze_event_payload(record)
    if not isinstance(record,Mapping) or not {'id','type','payload','time','cause'}<=set(record):
        raise ValueError('Event reference lacks required record fields')
    identifier=integer(record['id'],'event reference ID',1)
    name(record['type'],'event reference type')
    time=integer(record['time'],'event reference time',0)
    if previous_id is not None and identifier!=previous_id+1:raise ValueError('Event reference IDs must be contiguous')
    if previous_time is not None and time<previous_time:raise ValueError('Event reference times must be nondecreasing')
    cause=record['cause']
    if cause is not None:
        integer(cause,'event reference cause',1)
        if cause>=identifier:raise ValueError('Event reference cause must precede event')
    return record


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
        return readonly(_strict_record(line))

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
        if (not isinstance(reference, Mapping) or set(reference)!={'schema','path','sha256','bytes','count'}
                or reference.get('schema') != cls.SCHEMA):
            raise ValueError("Unsupported event journal reference fields/schema")
        for key in ('bytes','count'):
            if type(reference[key]) is not int or reference[key] < 0:
                raise ValueError('Event journal reference '+key+' must be a nonnegative integer')
        digest_value=reference['sha256']
        if type(digest_value) is not str or len(digest_value)!=64 or any(c not in '0123456789abcdef' for c in digest_value):
            raise ValueError('Event journal reference SHA256 must be canonical lowercase hex')
        if type(reference['path']) is not str or not reference['path']:
            raise ValueError('Event journal reference path must be nonempty absolute string')
        path = Path(reference["path"])
        if not path.is_absolute():
            raise ValueError("Event journal reference path must be absolute")
        destination = path.with_name(path.name + ".branch-" + uuid.uuid4().hex)
        journal = cls(destination)
        try:
            digest = hashlib.sha256()
            last_time=0
            with path.open("rb") as source:
                # Read actual bytes into a fresh independent branch; never trust
                # offsets, a live handle, or metadata from the producing session.
                for line in source:
                    if not line.endswith(b"\n"):
                        raise ValueError("Event journal reference has an incomplete line")
                    digest.update(line)
                    record=_strict_record(line,previous_id=len(journal),previous_time=last_time)
                    last_time=record['time']
                    if journal._file.write(line)!=len(line):raise OSError('Short event reference branch write')
                    journal._offsets.append(journal._offsets[-1] + len(line))
                    journal._hashes.extend(hashlib.sha256(line).digest())
            journal._file.flush()
            if (digest.hexdigest() != reference["sha256"] or
                    journal._offsets[-1] != reference["bytes"] or len(journal) != reference["count"]):
                raise ValueError("Event journal reference digest/size/count mismatch")
            return journal
        except BaseException:
            journal.discard()
            raise

    def discard(self):
        try:self._file.close()
        finally:self.path.unlink(missing_ok=True)

    def __del__(self):
        file = getattr(self, "_file", None)
        if file is not None:
            file.close()
