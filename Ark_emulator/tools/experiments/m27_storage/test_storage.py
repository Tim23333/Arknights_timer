import sys,math
from pathlib import Path
import pytest
RUNTIME=Path(__file__).resolve().parents[3].parent/'unpack_work/campaign_m27_event_intern_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim.kernel.events import EventLog
from ark_sim.kernel.interning import PayloadInterner,exact_equal
from ark_sim.contracts import freeze,thaw
from ark_sim.contracts.models import FrozenMapping
from ark_sim.kernel import Session

def test_shared_across_events_all_payload_values_and_caller_detached():
    log=EventLog();first={'x':[{'HP':10,'flag':True,'v':-0.0}]};log.emit('one',first,0);first['x'][0]['HP']=99;log.emit('two',{'x':[{'HP':10,'flag':True,'v':-0.0}]},1,cause=1);a,b=log.records;assert a['payload'] is b['payload'];assert thaw(a['payload'])=={'x':[{'HP':10,'flag':True,'v':-0.0}]};assert math.copysign(1,a['payload']['x'][0]['v'])==-1
    with pytest.raises(TypeError):a['payload']['x'][0]['HP']=1
@pytest.mark.parametrize('left,right',[(True,1),(1,1.0),(0.0,-0.0),({'a':1,'b':2},{'b':2,'a':1})])
def test_typed_and_ordered_variants_not_merged(left,right):
    p=PayloadInterner();a=p.intern(freeze(left));b=p.intern(freeze(right));assert not exact_equal(a,b)
def test_forced_hash_collision_never_aliases_different_values():
    p=PayloadInterner();p._fingerprint=lambda kind,parts:b'x'*32;a=p.intern(freeze({'a':[1,True,-0.0]}));b=p.intern(freeze({'a':[2,1,0.0]}));assert thaw(a)=={'a':[1,True,-0.0]} and thaw(b)=={'a':[2,1,0.0]};assert not exact_equal(a,b)
@pytest.mark.parametrize('payload',[{'a':float('nan')},{'a':float('inf')},{1:'bad'},FrozenMapping({'a':object()})])
def test_invalid_json_still_rejected_before_intern(payload):
    log=EventLog()
    with pytest.raises((ValueError,TypeError)):log.emit('bad',payload,0)
    assert log.records==() and log._payload_interner.statistics()['entries']==0

def test_cycle_rejected_with_no_cached_subtree():
    root={};root['self']=root;log=EventLog()
    with pytest.raises(ValueError,match='cycle'):log.emit('bad',root,0)
    assert log.records==() and log._payload_interner.statistics()['entries']==0

def test_bounded_cache_eviction_clear_preserves_immutable_history():
    log=EventLog();log._payload_interner=PayloadInterner(max_entries=3,max_weight=4096)
    for i in range(50):log.emit('value',{'x':i},i)
    assert log._payload_interner.statistics()['entries']<=3 and log._payload_interner.weight<=4096;before=thaw(log.records);log._payload_interner.clear();assert thaw(log.records)==before

def test_restore_uses_independent_cache_and_all_values():
    a=EventLog();a.emit('x',{'v':[10,-0.0]},0);b=EventLog();b.restore(a.snapshot());assert exact_equal(a.records,b.records);assert a._payload_interner is not b._payload_interner;b.emit('y',{'v':[10,-0.0]},1);assert len(a.records)==1

def test_actual_atomic_rollback_discards_failed_journal_and_cache():
    s=Session();s.emit('valid',{'x':[1]},None);before=s.checkpoint()
    with pytest.raises(ZeroDivisionError):
        with s.atomic():s.random.sample('imp');s.emit('temporary',{'y':[2]},None);1/0
    assert s.checkpoint()==before;assert s._events._payload_interner.statistics()['entries']==0;s.emit('after',{'x':[1]},None);assert len(s.events)==2

def test_public_frozen_invalid_cycle_and_nonstring_key():
    from types import MappingProxyType
    for value in [FrozenMapping({1:'bad'}),FrozenMapping({'v':float('nan')})]:
        log=EventLog()
        with pytest.raises(ValueError):log.emit('bad',value,0)
        assert not log.records
    value=FrozenMapping({});object.__setattr__(value,'_data',MappingProxyType({'self':value}));log=EventLog()
    with pytest.raises(ValueError,match='cycle'):log.emit('bad',value,0)

def test_primitive_subclass_normalization_unchanged():
    class Text(str):
        def __str__(self):return 'spoof'
    class Int(int):
        def __int__(self):return 9
    class Float(float):
        def __float__(self):return float('nan')
    log=EventLog();log.emit('x',{Text('actual'):Text('value'),'int':Int(3),'float':Float(2.0)},0);p=log.records[0]['payload'];assert list(p)==['actual','int','float'];assert p['actual']=='value' and p['int']==3 and p['float']==2.0;assert type(p['int']) is int and type(p['float']) is float

def test_integer_digit_limit_validation_still_before_cache():
    limit=sys.get_int_max_str_digits()
    if not limit:pytest.skip('interpreter digit limit disabled')
    log=EventLog()
    with pytest.raises(ValueError):log.emit('x',{'value':10**(limit+1)},0)
    assert not log.records and log._payload_interner.statistics()['entries']==0

def test_unicode_lone_surrogate_payload_acceptance_matches_prior_boundary():
    log=EventLog();text='\ud800';log.emit('x',{'text':text},0);log.emit('x',{'text':text},1);assert log.records[0]['payload']['text']==text and log.records[0]['payload'] is log.records[1]['payload']
    # The existing canonical UTF-8 exporter may reject this later; emit never did.
    with pytest.raises(UnicodeEncodeError):text.encode('utf8')

def test_restore_validates_whole_input_before_state_or_cache_swap():
    log=EventLog();log.emit('kept',{'x':[1]},0);before=log.snapshot();stats=log._payload_interner.statistics();bad=log.snapshot();bad['records'].append({'id':2,'type':'x','payload':{'ok':[1]},'time':-1,'cause':None});bad['next_id']=3
    with pytest.raises(ValueError):log.restore(bad)
    assert log.snapshot()==before and log._payload_interner.statistics()==stats
    bad=log.snapshot();bad['records'][0]['payload']=FrozenMapping({'bad':float('nan')})
    with pytest.raises(ValueError):log.restore(bad)
    assert log.snapshot()==before and log._payload_interner.statistics()==stats

def test_new_digit_limit_and_error_on_cache_hit_cannot_bypass_validation():
    original=sys.get_int_max_str_digits();log=EventLog()
    try:
        sys.set_int_max_str_digits(0);large=10**5000;log.emit('large',{'large':large},0);stats=log._payload_interner.statistics();sys.set_int_max_str_digits(4300)
        with pytest.raises(ValueError):log.emit('large',{'large':large},1)
        assert len(log.records)==1 and log._payload_interner.statistics()==stats
    finally:sys.set_int_max_str_digits(original)

def test_small_actual_program_checkpoint_and_command_replay():
    from ark_sim import Compiler,Engine
    from ark_sim.tools.replay import replay
    package={'entities':[{'id':'unit/actor','kind':'entity','components':{'attributes':{'base':{'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100}},'spatial':{},'abilities':['ability/test']}}],'abilities':[{'id':'ability/test','kind':'ability','activation':{'mode':'manual'},'duration_seconds':.2,'timeline':[{'at_seconds':.1,'effect':{'op':'emit','event':'full.payload','payload':{'nested':[{'values':[1,True,-0.0,'keep']}]}}}]}],'scenarioDraft':{'id':'scenario/storage','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'initialEntities':[{'definition':'unit/actor','instanceAlias':'actor','position':{'row':0,'col':0}}],'objectives':{}}}
    s=Engine.create(Compiler().compile(package),seed=27);s.submit({'action':'skill','source':'actor','ability':'ability/test'},at=0);s.advance(4);cp=s.checkpoint();r=Engine.restore(s.program,cp);s.advance(8);r.advance(8);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();assert s.session._events._payload_interner is not r.session._events._payload_interner
