"""Independent immutable journal/cache boundaries in actual frozen75fd."""
import json,sys,math,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m27_event_intern_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.kernel import Session
from ark_sim.kernel.events import EventLog
from ark_sim.kernel.interning import PayloadInterner
from ark_sim.contracts import thaw,freeze
from ark_sim.contracts.models import FrozenMapping
from ark_sim.tools.replay import replay
from tools.campaign_streaming_evidence import write_canonical
INPUTS=[]
def test_original_json_scalar_subclasses_order_signedzero_and_aliases():
 class SpoofInt(int):
  def __int__(self):return 999
 class SpoofFloat(float):
  def __float__(self):return float('inf')
 class SpoofString(str):
  def __str__(self):return 'spoof'
 leaf={'x':SpoofInt(7),'y':[True,1,1.0,SpoofFloat(-0.0),SpoofString('actual')]};payload={'second':leaf,'first':leaf}
 expected=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False);log=EventLog();log.emit('data',payload,0);leaf['x']=99
 stored=log.records[0]['payload'];assert stored['second'] is stored['first']
 assert json.dumps(thaw(stored),ensure_ascii=False,separators=(',',':'),allow_nan=False)==expected
 log.emit('same',json.loads(expected),1,cause=1);assert log.records[1]['payload'] is stored
 assert math.copysign(1,stored['second']['y'][3])==-1

def test_warm_cache_invalid_input_cannot_add_records_or_mutate_cache():
 log=EventLog();log.emit('warm',{'warm':[1,False,-0.0]},0);before=log.snapshot();stats=log._payload_interner.statistics()
 for payload in (FrozenMapping({'warm':freeze([1,False,-0.0]),'bad':object()}),{'warm':[1,False,-0.0],'bad':float('inf')}):
  with pytest.raises((ValueError,TypeError)):log.emit('bad',payload,1)
  assert log.snapshot()==before and log._payload_interner.statistics()==stats
 with pytest.raises(ValueError):log.emit('badcause',{'warm':[1]},1,cause=99)
 assert log.snapshot()==before and log._payload_interner.statistics()==stats

def test_forced_collision_preserves_nested_types_values_and_field_order():
 log=EventLog();log._payload_interner._fingerprint=lambda *args:b'C'*32
 values=[{'z':[False,0,0.0,-0.0],'a':{'v':1}},{'a':{'v':1.0},'z':[0,False,-0.0,0.0]}, {'z':[True,1,1.0,0.0],'a':{'v':2}}]
 for n,value in enumerate(values):log.emit('typed',value,n)
 assert [json.dumps(thaw(e['payload']),separators=(',',':')) for e in log.records]==[json.dumps(x,separators=(',',':')) for x in values]
 assert log._payload_interner.statistics()['hash_collisions_checked']>0

def test_eviction_is_only_performance_state_history_and_iterator_detached():
 log=EventLog();log._payload_interner=PayloadInterner(max_entries=1,max_weight=1024)
 for n in range(16):log.emit('many',{'n':n,'operand':[{'value':n,'typed':[True,1,-0.0]}]},n)
 stable=log.iter_records(4);before=thaw(log.records);log._payload_interner.clear();log.emit('last',{'n':16},16)
 assert [thaw(e) for e in stable]==before[4:]
 assert log._payload_interner.statistics()['entries']<=1 and log._payload_interner.weight<=1024
 assert thaw(log.records[:16])==before

def test_nested_real_transaction_jobs_rng_world_alias_and_cause_rollback():
 s=Session();s.emit('base',{'v':[7]});before=s.checkpoint()
 with pytest.raises(ValueError):
  with s.atomic():
   s.world.create('test',components={});s.random.sample('imp');s.schedule('dummy',{'v':[1]},2)
   with s.atomic():s.emit('inner',{'v':[7]},cause=1)
   raise ValueError('rollback')
 assert s.checkpoint()==before
 s.emit('retry',{'v':[7]},cause=1);assert [e['id'] for e in s.events]==[1,2] and s.events[1]['cause']==1

def program(resources=None):
 return {'entities':[{'id':'unit/actor','kind':'entity','components':{'attributes':{'base':{'max_hp':100}},'resources':resources or {'hp':{'initial':100,'capacity':100}},'spatial':{},'abilities':['ability/payload']}}], 'abilities':[{'id':'ability/payload','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at_seconds':.1,'effect':{'op':'emit','event':'peer.packet','payload':{'operands':[{'hp':100,'ratio':1.7,'typed':[False,0,0.0,-0.0]}]}}},{'at_seconds':.2,'effect':{'op':'emit','event':'peer.packet','payload':{'operands':[{'hp':100,'ratio':1.7,'typed':[False,0,0.0,-0.0]}]}}}]}], 'scenarioDraft':{'id':'scenario/storage_peer','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':1},'initialEntities':[{'definition':'unit/actor','instanceAlias':'actor','position':{'row':0,'col':0}}]}}
def make(p):
 raw=json.dumps(p,separators=(',',':')).encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':2704,'document':json.loads(raw)});return Engine.create(Compiler().compile(json.loads(raw)),seed=2704)
def test_actual_effect_packets_checkpoint_replay_with_identical_operands():
 s=make(program());s.submit({'action':'skill','source':'actor','ability':'ability/payload'},at=0);s.advance(4);r=Engine.restore(s.program,s.checkpoint());s.advance(4);r.advance(4)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
 packets=[e for e in s.session.events if e['type']=='peer.packet'];assert [e['time'] for e in packets]==[3,6]
 assert packets[0]['payload'] is packets[1]['payload']
 assert thaw(packets[0]['payload']['operands'])==[{'hp':100,'ratio':1.7,'typed':[False,0,0.0,-0.0]}]

def test_canonical_checkpoint_known_persistent_order_counterexample(tmp_path):
 resources={'hp':{'initial':100,'capacity':100},'z':{'initial':0,'capacity':10,'recovery_rate':1},'a':{'initial':0,'capacity':10,'recovery_rate':2}}
 s=make(program(resources));s.advance(1);cp=s.checkpoint();path=tmp_path/'cp.json';write_canonical(path,cp);r=Engine.restore(s.program,json.loads(path.read_bytes()));memory=Engine.restore(s.program,cp);s.advance(1);r.advance(1);memory.advance(1)
 assert s.snapshot()==memory.snapshot() and s.snapshot()!=r.snapshot()
 original=[e['payload']['resource'] for e in s.session.events if e['type']=='resource.changed' and e['time']==1]
 restored=[e['payload']['resource'] for e in r.session.events if e['type']=='resource.changed' and e['time']==1]
 assert original==['z','a'] and restored==['a','z']
 # Known tool-level failure is saved separately, not counted as durable success.
 out=ROOT/'validation/campaign/m27_roster_peer';out.mkdir(parents=True,exist_ok=True)
 (out/'durable_counterexample.json').write_text(json.dumps({'expected_equal':True,'actual_equal':False,'fixture':program(resources),'checkpoint':cp,'canonical_stored_checkpoint':json.loads(path.read_bytes()),'original_snapshot':s.snapshot(),'restored_snapshot':r.snapshot(),'in_memory_equal':True},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
