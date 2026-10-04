"""Full canonical evidence with bounded immutable encoding reuse."""
import hashlib
from pathlib import Path
from tools.campaign_canonical_encoder import CanonicalEncoder


def canonical_hash(value,encoder=None):
    encoder=encoder or CanonicalEncoder();result=hashlib.sha256()
    for part in encoder.chunks(value):result.update(part)
    return result.hexdigest()


def write_canonical(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);encoder=CanonicalEncoder()
    with path.open('wb') as file:
        pending=bytearray()
        for part in encoder.chunks(value):
            pending.extend(part)
            if len(pending)>=65536:file.write(pending);pending.clear()
        pending.extend(b'\n');file.write(pending)


def observations(sim):
    events=sim.session.events;encoder=CanonicalEncoder()
    snapshot={'time':sim.session.time,'seconds':sim.session.time*sim.session.quantum,
        'scenario':sim.program.scenario['id'],'program_fingerprint':sim.program.fingerprint,
        'runtime_fingerprint':sim.runtime_fingerprint,'entities':sim.session.world.entities(),
        'state':sim.ctx.state(),'events':events}
    state={'time':sim.session.time,'quantum':sim.session.quantum,'world':sim.session.world.snapshot(),
        'scheduler':sim.session.scheduler.snapshot(),'random':sim.session.random.snapshot(),
        'reaction_budget':sim.session.reaction_budget,'program_fingerprint':sim.program.fingerprint,
        'runtime_fingerprint':sim.runtime_fingerprint}
    return {'snapshot':canonical_hash(snapshot,encoder),'events':canonical_hash(events,encoder),'event_count':len(events),
        'continuation_state':canonical_hash(state,encoder)}


def export_events(path,sim):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);encoder=CanonicalEncoder();result=hashlib.sha256();count=0
    with path.open('wb') as file:
        pending=bytearray()
        events=sim.session.events;count=len(events)
        for part in encoder.records(events):
            pending.extend(part)
            if len(pending)>=65536:file.write(pending);result.update(pending);pending.clear()
        file.write(pending);result.update(pending)
    return {'path':str(path),'sha256':result.hexdigest(),'events':count,'encoding':'canonical UTF-8 JSONL; full payloads',
        'encoder_cache':encoder.statistics()}
