"""Offline endpoint equality expectations; no device/service reader."""
import sys,struct
from pathlib import Path
import pytest
LIVE=Path(__file__).resolve().parents[3].parent/'tools/ak_live_rng';sys.path.insert(0,str(LIVE))
from rng_engines import DotNetRandom,MT19937,recover_advanced
from tracker import EngineTracker
class FakeReader:
 def __init__(self,state):self.state=state
 def read(self,addr,size):return struct.pack('<56i',*self.state.seeds) if addr==100 else struct.pack('<ii',self.state.inext,self.state.inextp)
 def read_many(self,requests):return [self.read(a,s) for a,s in requests]
def tracker(state):return EngineTracker(FakeReader(state),{'kind':'knuth','array':100,'cursor_addr':200})
@pytest.mark.parametrize('separation',[21,31])
@pytest.mark.parametrize('count',[1,37,120])
def test_legitimate_complete_snapshot_recovery(separation,count):
 original=DotNetRandom(seeds=[0]+[(i*123457)%2147483647 for i in range(1,56)],inext=0,inextp=separation);observed=original.clone();expected=[observed.next_int() for _ in range(count)];result=recover_advanced(original,(observed.seeds,observed.inext,observed.inextp),max_steps=count);assert result==(count,expected);assert original.inext==0 and original.inextp==separation
@pytest.mark.parametrize('separation',[21,31])
def test_tracker_real_advanced_recovers_full_state(separation):
 original=DotNetRandom(seeds=DotNetRandom(0).seeds,inext=0,inextp=separation);t=tracker(original);assert t.poll()==[];observed=original.clone();expected=[observed.next_int() for _ in range(70)];t.reader.state=observed;got=t.poll();assert [row[1] for row in got]==expected and t.status=='ok';assert t._same_state(t.state,observed)
def test_valid32_cursor_not_illegal_but_wrong_endpoint_rejected():
 original=DotNetRandom(0);predicted=original.clone();predicted.next_int();observed=DotNetRandom(seeds=predicted.seeds,inext=1,inextp=32);t=tracker(original);assert t.poll()==[];t.reader.state=observed;read=t.read_state();assert read is not None and read.inextp==32;assert not predicted.matches(observed.seeds,1,32);assert recover_advanced(original,EngineTracker._observed_key(observed),max_steps=1) is None;assert t.poll() is None and t.status=='lost' and t.total==0;assert t.state.inext==0 and t.state.inextp==21
def test_partial_endpoint_is_explicit_error():
 e=DotNetRandom(0)
 with pytest.raises(ValueError,match='complete'):recover_advanced(e,(e.seeds,e.inext))
def test_mt_cross_twist_path_unchanged():
 e=MT19937(seed=999);original=e.clone();expected=[e.next_uint32() for _ in range(700)];assert recover_advanced(original,(e.mt,e.mti),max_steps=700)==(700,expected)
