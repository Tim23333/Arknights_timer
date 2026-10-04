import sys,json,hashlib
from pathlib import Path
from types import MappingProxyType
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate'))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.contracts.models import FrozenMapping,FrozenTuple
from tools.campaign_canonical_encoder import CanonicalEncoder
from tools.campaign_streaming_evidence_v2 import export_events,observations
def canonical(v):return json.dumps(thaw(v),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')

def test_full_bytes_unicode_numeric_types_and_negative_zero():
    v={'中文':'a\x00\n😀','numbers':[True,1,1.,-0.,0.],'null':None};encoder=CanonicalEncoder()
    assert b''.join(encoder.chunks(v))==canonical(v)

def test_both_preserved_malformed_wrapper_failures_now_observe_mutable_data():
    child=[];t=tuple.__new__(FrozenTuple,(child,));e=CanonicalEncoder();assert b''.join(e.chunks(t))==b'[[]]';child.append(7);assert b''.join(e.chunks(t))==b'[[7]]'
    backing={'k':1};m=object.__new__(FrozenMapping);object.__setattr__(m,'_data',backing);assert b''.join(e.chunks(m))==b'{"k":1}';backing['k']=2;assert b''.join(e.chunks(m))==b'{"k":2}'

def test_record_owned_snapshot_stable_during_generator_yields_with_retained_proxy():
    backing={'k':1};m=object.__new__(FrozenMapping);object.__setattr__(m,'_data',MappingProxyType(backing));e=CanonicalEncoder();stream=e.records([m,m]);first=next(stream);backing['k']=2
    result=first+b''.join(stream);assert result==b'{"k":1}\n{"k":2}\n'

@pytest.mark.parametrize('value',[{1:'bad'},float('nan'),float('inf'),'\ud800'])
def test_invalid_data_is_not_silently_given_successful_bytes(value):
    with pytest.raises((ValueError,UnicodeError,TypeError)):b''.join(CanonicalEncoder().chunks(value))

def test_cycle_records_refuses_and_small_cache_never_changes_full_bytes():
    cycle=[];cycle.append(cycle)
    with pytest.raises(ValueError,match='cycle'):b''.join(CanonicalEncoder().records([cycle]))
    records=[{'data':[i,{'other':str(i)}]} for i in range(30)];e=CanonicalEncoder(max_entries=2,max_bytes=32,max_item_bytes=12)
    assert b''.join(e.records(records))==b''.join(canonical(v)+b'\n' for v in records)
    stats=e.statistics();assert stats['entries']<=2 and stats['encoded_bytes']<=32

def test_actual_engine_journal_export_and_readonly_observations(tmp_path):
    p={'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/a','kind':'entity','components':{'spatial':{},'attributes':{'base':{'max_hp':50}},'resources':{'hp':{'initial':50,'capacity':50,'role':'health'}}}}],
        'scenarioDraft':{'id':'scene/encoder/peer','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':1},'initialEntities':[{'definition':'unit/a','instanceAlias':'a','position':{'row':0,'col':0}}]}}
    s=Engine.create(Compiler().compile(p),seed=5019);s.advance(3);before=s.checkpoint();dest=tmp_path/'events.jsonl';report=export_events(dest,s)
    expected=b''.join(canonical(e)+b'\n' for e in s.session.events);assert dest.read_bytes()==expected and report['sha256']==hashlib.sha256(expected).hexdigest() and report['events']==len(s.session.events)
    observations(s);assert s.checkpoint()==before
    blocked=tmp_path/'directory';blocked.mkdir()
    with pytest.raises(OSError):export_events(blocked,s)
    assert s.checkpoint()==before
