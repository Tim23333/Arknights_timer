"""Durable checkpoint JSON preserves object insertion order for continuation.

Canonical sorting is valid for value hashes, but World component iteration
order is execution state. Persisted checkpoints must not reorder it.
"""
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path


def chunks(value):
    if isinstance(value,Mapping):
        if any(type(key) is not str for key in value):raise ValueError('Checkpoint object keys must be strings')
        yield '{'
        for index,(key,item) in enumerate(value.items()):
            if index:yield ','
            yield json.dumps(key,ensure_ascii=False,allow_nan=False);yield ':';yield from chunks(item)
        yield '}'
    elif isinstance(value,(list,tuple)):
        yield '['
        for index,item in enumerate(value):
            if index:yield ','
            yield from chunks(item)
        yield ']'
    else:yield json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)


def write_ordered(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);digest=hashlib.sha256()
    with path.open('wb') as file:
        buffer=bytearray()
        for chunk in chunks(value):
            buffer.extend(chunk.encode('utf8'))
            if len(buffer)>=65536:file.write(buffer);digest.update(buffer);buffer.clear()
        buffer.extend(b'\n');file.write(buffer);digest.update(buffer)
    return digest.hexdigest()


def load_bound(path,expected_sha256):
    raw=Path(path).read_bytes()
    actual=hashlib.sha256(raw).hexdigest()
    if actual!=expected_sha256:raise ValueError('Durable checkpoint bytes changed')
    return json.loads(raw)
