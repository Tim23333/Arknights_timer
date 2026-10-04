"""Explicit disk-journal evidence consumer; old v9 helper is untouched.

Requires Session.enable_event_journal(). Reads every original encoded event.
Exports an owned file before hashing, allowing the simulation to continue later.
"""
from pathlib import Path
import hashlib
import json


def _canonical(value):
    from ark_sim.contracts.models import thaw
    return json.dumps(thaw(value), ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf8')


def _events(path):
    yield b'['
    with Path(path).open('rb') as source:
        for index, line in enumerate(source):
            if not line.endswith(b'\n'):
                raise ValueError('Incomplete event export')
            if index:
                yield b','
            # Storage preserves mapping insertion order for public reads;
            # evidence hashes still use the established sorted canonical form.
            yield _canonical(json.loads(line))
    yield b']'


def observations(sim, events_path):
    from ark_sim.contracts.models import digest
    exported = sim.session.export_events_jsonl(events_path)
    event_digest = hashlib.sha256()
    for chunk in _events(events_path):
        event_digest.update(chunk)
    fields = {'time': sim.session.time, 'seconds': sim.session.time*sim.session.quantum,
        'scenario': sim.program.scenario['id'], 'program_fingerprint': sim.program.fingerprint,
        'runtime_fingerprint': sim.runtime_fingerprint, 'entities': sim.session.world.entities(),
        'state': sim.ctx.state(), 'events': None}
    snapshot_digest = hashlib.sha256(b'{')
    for index, key in enumerate(sorted(fields)):
        if index:
            snapshot_digest.update(b',')
        snapshot_digest.update(_canonical(key) + b':')
        if key == 'events':
            for chunk in _events(events_path):
                snapshot_digest.update(chunk)
        else:
            snapshot_digest.update(_canonical(fields[key]))
    snapshot_digest.update(b'}')
    state = {'time': sim.session.time, 'quantum': sim.session.quantum,
        'world': sim.session.world.snapshot(), 'scheduler': sim.session.scheduler.snapshot(),
        'random': sim.session.random.snapshot(), 'reaction_budget': sim.session.reaction_budget,
        'program_fingerprint': sim.program.fingerprint, 'runtime_fingerprint': sim.runtime_fingerprint}
    return {'snapshot': snapshot_digest.hexdigest(), 'events': event_digest.hexdigest(),
        'event_count': exported['count'], 'continuation_state': digest(state), 'export': exported}


def write_checkpoint(sim, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = sim.checkpoint(event_reference=True)
    path.write_text(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True,
                              separators=(',', ':'), allow_nan=False)+'\n', encoding='utf8')
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'event_reference': checkpoint['kernel']['events']['reference']}
