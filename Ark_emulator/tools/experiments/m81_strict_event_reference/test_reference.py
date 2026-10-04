import json,hashlib,copy
from pathlib import Path
import pytest
from ark_sim.kernel.events import EventLog
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
CASES=[]
def ref(tmp,lines,next_id=None):
 path=tmp/'sealed.jsonl';raw=b''.join((x+'\n').encode() for x in lines);path.write_bytes(raw);return {'reference':{'schema':'ark-sim/event-journal-reference/v1','path':str(path.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'count':len(lines)},'next_id':len(lines)+1 if next_id is None else next_id}
BAD=[
 ('duplicate_time','{"id":1,"type":"x","payload":{},"time":9,"time":0,"cause":null}'),
 ('duplicate_id','{"id":99,"id":1,"type":"x","payload":{},"time":0,"cause":null}'),
 ('duplicate_payload','{"id":1,"type":"x","payload":{"bad":1},"payload":{},"time":0,"cause":null}'),
 ('nested_payload','{"id":1,"type":"x","payload":{"nested":{"n":1,"n":2}},"time":0,"cause":null}'),
 ('array_nested','{"id":1,"type":"x","payload":[{"n":1,"n":2}],"time":0,"cause":null}'),
 ('nan','{"id":1,"type":"x","payload":{"n":NaN},"time":0,"cause":null}'),
 ('infinity','{"id":1,"type":"x","payload":{"n":Infinity},"time":0,"cause":null}'),
 ('negative_infinity','{"id":1,"type":"x","payload":{"n":-Infinity},"time":0,"cause":null}'),
 ('bool_id','{"id":true,"type":"x","payload":{},"time":0,"cause":null}'),
 ('bool_time','{"id":1,"type":"x","payload":{},"time":false,"cause":null}'),
 ('bool_cause','{"id":1,"type":"x","payload":{},"time":0,"cause":true}'),
 ('self_cause','{"id":1,"type":"x","payload":{},"time":0,"cause":1}'),
 ('missing','{"id":1,"type":"x","payload":{},"time":0}'),
 ('not_record','[]'),
 ('float_time','{"id":1,"type":"x","payload":{},"time":0.0,"cause":null}'),
]
GOOD='{"id":1,"type":"ok","payload":{"z":-0.0,"a":1.0,"i":7},"time":0,"cause":null}'
@pytest.mark.parametrize('name,line',BAD)
def test_rehashed_bad_record_rejected_before_half_branch_adoption(name,line,tmp_path):
 data=ref(tmp_path,[line]);log=EventLog();log.emit('existing',{'untouched':True},0);before=log.snapshot();before_files=set(tmp_path.glob('*.branch-*'))
 with pytest.raises((TypeError,ValueError)):log.restore(data)
 assert log.snapshot()==before and set(tmp_path.glob('*.branch-*'))==before_files
 CASES.append({'name':name,'actual_reference':data,'actual_file_sha256':hashlib.sha256((tmp_path/'sealed.jsonl').read_bytes()).hexdigest(),'expected':'reject; prior log and branch set unchanged'})

@pytest.mark.parametrize('second',[
 '{"id":3,"type":"x","payload":{},"time":1,"cause":null}',
 '{"id":2,"type":"x","payload":{},"time":-1,"cause":null}',
 '{"id":2,"type":"x","payload":{},"time":1,"cause":2}',
 '{"id":2,"type":"x","payload":{"inner":{"dup":1,"dup":2}},"time":1,"cause":1}',
])
def test_valid_prefix_followed_by_bad_record_discards_all_new_branch(second,tmp_path):
 data=ref(tmp_path,[GOOD,second]);before=set(tmp_path.glob('*.branch-*'));log=EventLog()
 with pytest.raises((ValueError,TypeError)):log.restore(data)
 assert log.records==() and set(tmp_path.glob('*.branch-*'))==before
 CASES.append({'name':'late_invalid','actual_reference':data,'expected':'whole staging branch cleaned, no half accepted prefix'})


def test_cross_record_time_regression_discards_branch(tmp_path):
 data=ref(tmp_path,['{"id":1,"type":"x","payload":{},"time":4,"cause":null}','{"id":2,"type":"y","payload":{},"time":3,"cause":1}'])
 with pytest.raises(ValueError,match='nondecreasing'):EventLog().restore(data)
 assert not list(tmp_path.glob('*.branch-*'))


def test_bad_next_id_after_valid_physical_copy_cleans_branch_and_keeps_old_log(tmp_path):
 data=ref(tmp_path,[GOOD],next_id=9);log=EventLog();log.emit('before',{},0);before=log.snapshot()
 with pytest.raises(ValueError,match='next'):log.restore(data)
 assert log.snapshot()==before and not list(tmp_path.glob('*.branch-*'))


def test_valid_reference_order_numbers_unicode_and_source_immutable(tmp_path):
 data=ref(tmp_path,[GOOD,'{"id":2,"type":"y","payload":{"second":"雪"},"time":1,"cause":1}']);raw=(tmp_path/'sealed.jsonl').read_bytes();log=EventLog();log.restore(copy.deepcopy(data));assert list(log.records[0]['payload'])==['z','a','i'] and type(log.records[0]['payload']['a']) is float and type(log.records[0]['payload']['i']) is int
 log.emit('branch',{'n':1},2,cause=2);assert (tmp_path/'sealed.jsonl').read_bytes()==raw and log.records[-1]['id']==3
