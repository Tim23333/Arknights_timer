import hashlib
from pathlib import Path

import pytest

from ark_sim import Compiler,Engine
from ark_sim.contracts import freeze,digest
from tools.campaign_canonical_encoder import CanonicalEncoder
from tools import campaign_streaming_evidence as old
from tools import campaign_streaming_evidence_v2 as new


@pytest.mark.parametrize('value',[None,True,1,1.0,-0.0,1.2,'中文\n"\\🙂',{'z':[False,1,1.0],'a':{'data':[]}}])
def test_cached_bytes_exact_canonical_digest(value):
    encoder=CanonicalEncoder()
    for candidate in [value,freeze(value)]:
        raw=b''.join(encoder.chunks(candidate))
        assert raw==''.join(old.chunks(candidate)).encode('utf8')
        assert hashlib.sha256(raw).hexdigest()==digest(candidate)
    assert encoder.statistics()['encoded_bytes']<=encoder.max_bytes


def test_mutable_data_not_cached_and_lru_disabled_limits_preserve_bytes():
    source={'value':[1]};encoder=CanonicalEncoder();first=b''.join(encoder.chunks(source));source['value'].append(2)
    assert b''.join(encoder.chunks(source))!=first
    frozen=freeze({'x':{'text':'a'*1000},'y':[1,2]})
    for entries,limit,item in [(0,0,0),(1,4,2),(4,128,64)]:
        cache=CanonicalEncoder(entries,limit,item)
        assert b''.join(cache.chunks(frozen))==''.join(old.chunks(frozen)).encode('utf8')
        stats=cache.statistics();assert stats['entries']<=entries and stats['encoded_bytes']<=limit


def test_shared_immutable_payload_cache_hits_without_collapsing_event_order():
    payload=freeze({'numeric':[1,1.0,-0.0],'nested':{'text':'source'}})
    records=freeze([{'id':1,'payload':payload},{'id':2,'payload':payload}])
    encoder=CanonicalEncoder();raw=b''.join(encoder.records(records))
    assert raw==b''.join((''.join(old.chunks(r))+'\n').encode('utf8') for r in records)


def test_actual_runtime_state_events_journal_and_query_free_readonly(tmp_path):
    p={'entities':[{'id':'unit/test','kind':'entity','components':{'spatial':{},'attributes':{'base':{'max_hp':10}},'resources':{'hp':{'initial':10,'capacity':10}}}}],
       'scenarioDraft':{'id':'scene/test/canonical','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'objectives':{},
           'initialEntities':[{'definition':'unit/test','position':{'row':0,'col':0}}]}}
    s=Engine.create(Compiler().compile(p),seed=99);s.advance(8);before=s.checkpoint()
    assert new.observations(s)==old.observations(s)
    a=tmp_path/'old.jsonl';b=tmp_path/'new.jsonl';oa=old.export_events(a,s);nb=new.export_events(b,s)
    assert a.read_bytes()==b.read_bytes() and oa['sha256']==nb['sha256'] and oa['events']==nb['events']
    assert s.checkpoint()==before


def test_non_finite_and_non_string_keys_rejected_without_caching():
    for value in [{'hp':float('nan')},{'hp':float('inf')},{1:'bad'}]:
        with pytest.raises(ValueError):b''.join(CanonicalEncoder().chunks(value))


def test_malformed_public_frozen_wrapper_never_caches_mutable_descendants():
    from ark_sim.contracts.models import FrozenTuple
    child=[];wrapper=tuple.__new__(FrozenTuple,(child,));encoder=CanonicalEncoder()
    assert b''.join(encoder.chunks(wrapper))==b'[[]]'
    child.append(7)
    assert b''.join(encoder.chunks(wrapper))==b'[[7]]'
    assert all(entry[0] is not wrapper for entry in encoder.cache.values())


def test_malformed_cycle_is_rejected_and_small_validation_bound_stays_correct():
    from ark_sim.contracts.models import FrozenTuple
    child=[];wrapper=tuple.__new__(FrozenTuple,(child,));child.append(wrapper)
    with pytest.raises((ValueError,RecursionError)):b''.join(CanonicalEncoder().chunks(wrapper))
    value=freeze([{'index':i,'data':list(range(7))} for i in range(100)])
    cache=CanonicalEncoder(max_entries=2,max_bytes=32,max_item_bytes=16)
    assert b''.join(cache.chunks(value))==''.join(old.chunks(value)).encode('utf8')
    assert cache.statistics()['entries']<=2


def test_malformed_frozen_mapping_with_retained_mutable_backing_is_not_cached():
    from ark_sim.contracts.models import FrozenMapping
    wrapper=object.__new__(FrozenMapping);backing={'k':1};object.__setattr__(wrapper,'_data',backing)
    encoder=CanonicalEncoder();assert b''.join(encoder.chunks(wrapper))==b'{"k":1}'
    backing['k']=2;assert b''.join(encoder.chunks(wrapper))==b'{"k":2}'
    backing['k']=float('nan')
    with pytest.raises(ValueError):b''.join(encoder.chunks(wrapper))


def test_public_proxy_of_mutable_dictionary_changes_between_calls_are_observed():
    from ark_sim.contracts.models import FrozenMapping
    from types import MappingProxyType
    wrapper=object.__new__(FrozenMapping);backing={'k':1};object.__setattr__(wrapper,'_data',MappingProxyType(backing))
    encoder=CanonicalEncoder();assert b''.join(encoder.chunks(wrapper))==b'{"k":1}'
    backing['k']=2;assert b''.join(encoder.chunks(wrapper))==b'{"k":2}'
    backing['k']=float('nan')
    with pytest.raises(ValueError):b''.join(encoder.chunks(wrapper))


def test_generator_holds_own_detached_backing_between_yields():
    from ark_sim.contracts.models import FrozenMapping
    from types import MappingProxyType
    wrapper=object.__new__(FrozenMapping);backing={'k':1};object.__setattr__(wrapper,'_data',MappingProxyType(backing))
    encoder=CanonicalEncoder();stream=encoder.records([wrapper]);first=next(stream);backing['k']=2
    assert first+b''.join(stream)==b'{"k":1}\n'
    assert b''.join(encoder.chunks(wrapper))==b'{"k":2}'
