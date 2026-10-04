"""Session-bound, actual-byte-validated observations; ordered v13 publication."""
from pathlib import Path
import hashlib,json,importlib.util
from collections.abc import Mapping

PARENT=Path(__file__).resolve().parents[1]/'m71_event_storage/campaign_streaming_evidence_v13.py'
_spec=importlib.util.spec_from_file_location('m77_preserved_v13',PARENT)
_v13=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_v13)
write_checkpoint=_v13.write_checkpoint
load_checkpoint=_v13.load_checkpoint

def _canonical(value):
    from ark_sim.contracts.models import thaw
    return json.dumps(thaw(value),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')

def _pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ValueError('Export event contains duplicate JSON object keys')
        result[key]=value
    return result

def _records(path):
    from ark_sim.kernel.events import freeze_event_payload
    from ark_sim.kernel._data import integer,name
    prior=0;prior_time=0
    with Path(path).open('rb') as source:
        for line in source:
            if not line.endswith(b'\n'):raise ValueError('Incomplete event export')
            record=json.loads(line,object_pairs_hook=_pairs)
            record=freeze_event_payload(record)
            if not isinstance(record,Mapping) or not {'id','type','payload','time','cause'}<=set(record):raise ValueError('Export event lacks required fields')
            current=integer(record['id'],'export event ID',1)
            if current!=prior+1:raise ValueError('Export event IDs must be contiguous')
            name(record['type'],'export event type');integer(record['time'],'export event time',0)
            if record['time']<prior_time:raise ValueError('Export event times must be nondecreasing')
            cause=record['cause']
            if cause is not None:
                integer(cause,'export cause',1)
                if cause>=current:raise ValueError('Export cause must precede event')
            prior=current;prior_time=record['time']
            yield line,record

def _file_sha(path):
    digest=hashlib.sha256();size=0
    with Path(path).open('rb') as source:
        while True:
            chunk=source.read(65536)
            if not chunk:break
            size+=len(chunk);digest.update(chunk)
    return digest.hexdigest(),size

def _boundary(session):
    return (session.time,session._events._next_id,dict(session.world._versions),
            session.scheduler._next_id,session.scheduler._next_seq,tuple(session.scheduler._tasks),
            dict(session.random._counts),len(session.random._samples))

def observations(sim,events_path):
    from ark_sim.contracts.models import digest
    session=sim.session
    # The same executor lock serializes advance, commits, export and all stores.
    with session._lock:
        if session._advancing or session._atomic_depth:raise RuntimeError('Observations require an idle session boundary')
        boundary=_boundary(session)
        exported=session.export_events_jsonl(events_path)
        if _boundary(session)!=boundary:raise RuntimeError('Session changed during observation')
        if (not isinstance(exported,Mapping) or set(exported)!={'path','sha256','bytes','count'}
                or type(exported['count']) is not int or exported['count']<0
                or type(exported['bytes']) is not int or exported['bytes']<0
                or type(exported['sha256']) is not str
                or type(exported['path']) is not str
                or not Path(exported['path']).is_absolute()
                or Path(exported['path']).resolve()!=Path(events_path).resolve()):
            raise ValueError('Event export metadata is invalid')
        fields={'time':session.time,'seconds':session.time*session.quantum,
            'scenario':sim.program.scenario['id'],'program_fingerprint':sim.program.fingerprint,
            'runtime_fingerprint':sim.runtime_fingerprint,'entities':session.world.entities(),
            'state':sim.ctx.state(),'events':None}
        state={'time':session.time,'quantum':session.quantum,'world':session.world.snapshot(),
            'scheduler':session.scheduler.snapshot(),'random':session.random.snapshot(),
            'reaction_budget':session.reaction_budget,'program_fingerprint':sim.program.fingerprint,
            'runtime_fingerprint':sim.runtime_fingerprint}
        event_digest=hashlib.sha256(b'[');snapshot_digest=hashlib.sha256(b'{')
        raw_digest=hashlib.sha256();size=0;count=0
        owned=session._events._records
        for index,key in enumerate(sorted(fields)):
            if index:snapshot_digest.update(b',')
            snapshot_digest.update(_canonical(key)+b':')
            if key=='events':
                snapshot_digest.update(b'[')
                for line,record in _records(events_path):
                    if (count>=len(owned) or len(line)!=owned._offsets[count+1]-owned._offsets[count]
                            or hashlib.sha256(line).digest()!=owned._hashes[count*32:(count+1)*32]):
                        raise ValueError('Event export differs from owned logical journal')
                    raw_digest.update(line);size+=len(line)
                    if count:event_digest.update(b',');snapshot_digest.update(b',')
                    canonical=_canonical(record);event_digest.update(canonical);snapshot_digest.update(canonical);count+=1
                snapshot_digest.update(b']')
            else:snapshot_digest.update(_canonical(fields[key]))
        event_digest.update(b']');snapshot_digest.update(b'}')
        actual_sha=raw_digest.hexdigest()
        if (actual_sha!=exported['sha256'] or size!=exported['bytes'] or count!=exported['count']
                or count!=len(session._events._records)):
            raise ValueError('Actual event export digest/size/count mismatch')
        # Reopen current pathname after parsing: detect replacement/rewrites
        # including mutations of an already consumed prefix during the scan.
        if _file_sha(events_path)!=(actual_sha,size):raise ValueError('Event export changed during observation')
        if _boundary(session)!=boundary:raise RuntimeError('Session changed during observation')
        return {'snapshot':snapshot_digest.hexdigest(),'events':event_digest.hexdigest(),
            'event_count':count,'continuation_state':digest(state),
            'export':{'path':str(Path(events_path).resolve()),'sha256':actual_sha,'bytes':size,'count':count}}
