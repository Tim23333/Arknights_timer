from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import pytest
from ark_sim.kernel import World,Session
from ark_sim.contracts import Intent,thaw
class HostileName(str):
 def __deepcopy__(self,memo):raise AssertionError('Metadata deepcopy hook must not run')
class ReverseName(HostileName):
 def __lt__(self,other):return str.__gt__(self,other)
def test_metadata_names_use_former_JSON_normalization_without_deepcopy_hooks():
 w=World();w.create(HostileName('unit/peer'),{'x':1},tags=[ReverseName('a'),ReverseName('b')],alias=HostileName('peer'));expected=World();expected.restore(w.snapshot());f=w._fork_validated();assert f.snapshot()==expected.snapshot() and type(f._entities[1]['definition_id']) is str and type(next(iter(f._aliases))) is str
def test_private_fork_and_consumed_adoption_never_alias_mutable_containers():
 w=World();ref=w.create('unit/peer',{'data':{'rows':[{'x':1}]}},alias='peer');old=w.get(ref);f=w._fork_validated();f.set(ref,('data','rows',0,'x'),2);assert w.get(ref)['components']['data']['rows'][0]['x']==1
 w._adopt_validated(f,preserve_views=True);assert old['components']['data']['rows'][0]['x']==1 and w.get(ref)['components']['data']['rows'][0]['x']==2
 f.create('unit/new',{'data':{'x':99}});assert len(w.entities())==1
 with pytest.raises(ValueError):w._adopt_validated(f,preserve_views=True)
def test_nested_atomic_outer_savepoint_and_inner_rollback_allstores():
 s=Session(seed=7);ref=s.world.create('unit/peer',{'data':{'x':1}},alias='peer');before=s.snapshot()
 with pytest.raises(ValueError):
  with s.atomic():
   s.commit([Intent('set',ref,('data','x'),2)]);middle=s.snapshot()
   with pytest.raises(TypeError):
    with s.atomic():
     s.commit([Intent('set',ref,('data','x'),3)]);s.random.sample('peer');s.emit('peer.inner',{});s.schedule('unused',{},10);raise TypeError('inner')
   assert s.snapshot()==middle;s.random.sample('outer');s.emit('peer.outer',{});raise ValueError('outer')
 assert s.snapshot()==before
@pytest.mark.parametrize('bad',[float('nan'),float('inf'),object(),{1:'notstring'}])
def test_public_set_invalid_values_and_failed_batch_keep_validation_and_original_state(bad):
 s=Session();ref=s.world.create('unit/peer',{'data':{'x':1}});before=s.snapshot()
 with pytest.raises((ValueError,TypeError)):
  s.commit([Intent('set',ref,('data','x'),2),Intent('set',ref,('data','bad'),bad)])
 assert s.snapshot()==before
def test_multithread_session_atomic_holds_serializable_counter():
 s=Session();ref=s.world.create('unit/peer',{'counter':0})
 def increment(_):
  for i in range(20):
   with s.atomic():s.commit([Intent('set',ref,('counter',),s.world.get(ref)['components']['counter']+1)])
 with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(increment,range(4)))
 assert s.world.get(ref)['components']['counter']==80 and s.world.version(ref)==81
def test_commit_preserves_unrelated_cached_view_and_single_revision():
 s=Session();a=s.world.create('unit/a',{'x':1});b=s.world.create('unit/b',{'x':2});cached=s.world.get(b);v=s.world.version(a);s.commit([Intent('set',a,('x',),3)]);assert s.world.get(b) is cached and s.world.version(a)==v+1
