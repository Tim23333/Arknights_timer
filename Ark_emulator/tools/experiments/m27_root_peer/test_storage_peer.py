"""Independent storage/transaction boundaries for the frozen interning core."""
from pathlib import Path
import sys
import math
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m27_event_intern_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim.kernel import Session
from ark_sim.kernel.events import EventLog
from ark_sim.kernel.interning import PayloadInterner
from ark_sim.contracts import thaw


def test_nested_savepoint_failure_preserves_outer_event_and_old_immutable_view():
    s=Session();s.emit('original',{'values':[1,True,-0.0]});old=s.events[0]['payload']
    with s.atomic():
        s.emit('outer',{'values':[1,True,-0.0]})
        try:
            with s.atomic():
                s.random.sample('game');s.emit('inner',{'values':[3]});raise ValueError('fail inner')
        except ValueError:pass
        s.emit('after_inner',{'values':[1,True,-0.0]})
    assert [e['type'] for e in s.events]==['original','outer','after_inner']
    assert [e['id'] for e in s.events]==[1,2,3] and s.random.samples==()
    assert thaw(old)=={'values':[1,True,-0.0]} and math.copysign(1,old['values'][2])==-1
    with pytest.raises(TypeError):old['values'][0]=99


def test_outer_failure_after_successful_inner_preserves_full_checkpoint():
    s=Session();s.emit('original',{'x':[1]});before=s.checkpoint()
    with pytest.raises(RuntimeError):
        with s.atomic():
            with s.atomic():s.emit('inner_ok',{'x':[1]});s.random.sample('inner')
            s.emit('outer_bad',{'x':[2]});raise RuntimeError('abort outer')
    assert s.checkpoint()==before
    s.emit('retry',{'x':[1]});assert [e['id'] for e in s.events]==[1,2]


def test_zero_budget_and_tiny_budget_keep_same_complete_journal_values():
    a,b=EventLog(),EventLog();a._payload_interner=PayloadInterner(max_entries=0,max_weight=0);b._payload_interner=PayloadInterner(max_entries=2,max_weight=2048)
    for n in range(30):
        payload={'n':n,'nested':[{'bits':[False,0,0.0,-0.0],'text':'中文'}]}
        for log in (a,b):log.emit('sample',payload,n,cause=n if n else None)
    assert thaw(a.records)==thaw(b.records)
    assert b._payload_interner.weight<=2048 and len(b._payload_interner._entries)<=2
    before=thaw(b.records);b._payload_interner.clear();assert thaw(b.records)==before


def test_checkpoint_source_is_detached_after_restore_with_shared_subtrees():
    a=EventLog();a.emit('one',{'shared':[{'hp':10}]},0);a.emit('two',{'shared':[{'hp':10}]},1,cause=1)
    cp=a.snapshot();b=EventLog();b.restore(cp);cp['records'][0]['payload']['shared'][0]['hp']=999
    assert b.records[0]['payload']['shared'][0]['hp']==10
    assert b.records[0]['payload'] is b.records[1]['payload']
    b.emit('three',{'shared':[{'hp':10}]},2,cause=2);assert len(a.records)==2
