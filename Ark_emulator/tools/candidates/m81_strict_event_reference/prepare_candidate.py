from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m77_event_storage_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m81_strict_event_reference_candidate'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
assert core(BASE)=='a12af98ddcd49dafcd483fde4abd9644850f4aa211cad1fa25c17bad3cf84031'
if not OUT.exists():shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
journal=(BASE/'ark_sim/kernel/journal.py').read_text(encoding='utf8')
helpers='''def _unique_pairs(items):
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


'''
assert journal.count('class DiskEventRecords:')==1;journal=journal.replace('class DiskEventRecords:',helpers+'class DiskEventRecords:')
journal=journal.replace('return readonly(json.loads(line))','return readonly(_strict_record(line))')
assert journal.count('''            digest = hashlib.sha256()
            with path.open("rb") as source:''')==1
journal=journal.replace('''            digest = hashlib.sha256()
            with path.open("rb") as source:''','''            digest = hashlib.sha256()
            last_time=0
            with path.open("rb") as source:''')
journal=journal.replace('''                    json.loads(line)
                    journal._file.write(line)''','''                    record=_strict_record(line,previous_id=len(journal),previous_time=last_time)
                    last_time=record['time']
                    if journal._file.write(line)!=len(line):raise OSError('Short event reference branch write')''')
journal=journal.replace('''            journal._file.close()
            destination.unlink(missing_ok=True)''','''            journal.discard()''')
assert journal.count('    def __del__(self):')==1
journal=journal.replace('    def __del__(self):','''    def discard(self):
        try:self._file.close()
        finally:self.path.unlink(missing_ok=True)

    def __del__(self):''')
raw=(BASE/'ark_sim/kernel/journal.py').read_bytes()
(OUT/'ark_sim/kernel/journal.py').write_bytes((journal.replace('\n','\r\n') if b'\r\n' in raw else journal).encode('utf8'))
events=(BASE/'ark_sim/kernel/events.py').read_text(encoding='utf8')
marker='            previous = 0\n';assert events.count(marker)==1
prefix,body=events.split(marker,1)
body=marker+body
events=prefix+'            try:\n'+''.join('    '+line if line.strip() else line for line in body.splitlines(True))+'''            except BaseException:
                if isinstance(records,DiskEventRecords):records.discard()
                raise
'''
raw=(BASE/'ark_sim/kernel/events.py').read_bytes()
(OUT/'ark_sim/kernel/events.py').write_bytes((events.replace('\n','\r\n') if b'\r\n' in raw else events).encode('utf8'))
print(json.dumps({'root':str(OUT),'core':core(OUT),'files':['kernel/journal.py','kernel/events.py']}))
