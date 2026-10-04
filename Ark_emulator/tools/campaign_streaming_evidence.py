"""Canonical JSON hashing/export without expanding the complete event tree.

Canonical bytes equal contracts.digest's sorted compact UTF-8 JSON for valid
JSON data. Event order and every payload value are retained.
"""
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path


def chunks(value):
    if isinstance(value,Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError('Canonical JSON requires string object keys')
        yield '{'
        for index,key in enumerate(sorted(value)):
            if index:yield ','
            yield json.dumps(key,ensure_ascii=False,allow_nan=False);yield ':'
            yield from chunks(value[key])
        yield '}'
    elif isinstance(value,(list,tuple)):
        yield '['
        for index,item in enumerate(value):
            if index:yield ','
            yield from chunks(item)
        yield ']'
    else:
        yield json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)


def canonical_hash(value):
    digest=hashlib.sha256()
    for chunk in chunks(value):digest.update(chunk.encode('utf8'))
    return digest.hexdigest()


def write_canonical(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    # Aggregate only a bounded byte buffer; retain all original JSON values.
    with path.open('wb') as file:
        pending=bytearray()
        for chunk in chunks(value):
            pending.extend(chunk.encode('utf8'))
            if len(pending)>=65536:file.write(pending);pending.clear()
        pending.extend(b'\n');file.write(pending)


def observations(sim):
    # Match Simulation.snapshot exactly, using immutable event references.
    events=sim.session.events
    snapshot={'time':sim.session.time,'seconds':sim.session.time*sim.session.quantum,
        'scenario':sim.program.scenario['id'],'program_fingerprint':sim.program.fingerprint,
        'runtime_fingerprint':sim.runtime_fingerprint,'entities':sim.session.world.entities(),
        'state':sim.ctx.state(),'events':events}
    state={'time':sim.session.time,'quantum':sim.session.quantum,'world':sim.session.world.snapshot(),
        'scheduler':sim.session.scheduler.snapshot(),'random':sim.session.random.snapshot(),
        'reaction_budget':sim.session.reaction_budget,'program_fingerprint':sim.program.fingerprint,
        'runtime_fingerprint':sim.runtime_fingerprint}
    return {'snapshot':canonical_hash(snapshot),'events':canonical_hash(events),'event_count':len(events),
            'continuation_state':canonical_hash(state)}


def export_events(path,sim):
    """JSONL complete immutable journal, in original contiguous ID order."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);digest=hashlib.sha256();count=0
    with path.open('wb') as file:
        for event in sim.session.events:
            pending=bytearray()
            for chunk in chunks(event):
                pending.extend(chunk.encode('utf8'))
                if len(pending)>=65536:file.write(pending);digest.update(pending);pending.clear()
            pending.extend(b'\n');file.write(pending);digest.update(pending);count+=1
    return {'path':str(path),'sha256':digest.hexdigest(),'events':count,'encoding':'canonical UTF-8 JSONL; full payloads'}
