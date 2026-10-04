import sys,threading,time,math
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.kernel.world import World
from ark_sim.kernel.session import Session
from ark_sim.contracts import Intent,thaw

def test_all_mutable_world_stores_detached_newviews_and_adopt_ownership_once():
 w=World();a=w.create('entity/peer',{'tree':{'items':[{'n':7},[1,2]],'empty':[]}},tags=['z','a'],alias='alpha');old=w.get(a);f=w._fork_validated();assert f._lock is not w._lock and f._entities is not w._entities and f._aliases is not w._aliases and f._versions is not w._versions and f._views=={};f._entities[a]['components']['tree']['items'][0]['n']=29;f._aliases['beta']=a;f._versions[a]+=1;f.create('entity/second',{'data':[8]},alias='new');assert w.resolve('alpha')==a and w._next_id==2 and old['components']['tree']['items'][0]['n']==7;assert 'beta' not in w._aliases;w._adopt_validated(f,preserve_views=True);assert w.resolve('beta')==a and w.get(a)['components']['tree']['items'][0]['n']==29;assert f._entities==f._aliases==f._versions==f._views=={} and not f._validated_fork
 f.create('entity/retainedfork',{'data':[999]},alias='after');assert 'after' not in w._aliases
 with pytest.raises(ValueError):w._adopt_validated(f,preserve_views=True)
 with pytest.raises(ValueError):w._adopt_validated(World(),preserve_views=True)

def test_alias_deletion_tombstone_versions_and_readonly_views_cache_exact():
 s=Session();a=s.world.create('entity/one',{'branch':{'x':[3,4]}},alias='a');b=s.world.create('entity/two',{'branch':{'x':[6,7]}},alias='b');va=s.world.get(a);vb=s.world.get(b);leaf=s.world.component_view(a,('branch',));s.commit([Intent('set',a,('branch','x',0),value=19)]);assert s.world.get(b) is vb and s.world.get(a) is not va;assert leaf['x'][0]==3;assert s.world.get(a)['components']['branch']['x'][0]==19
 with pytest.raises(TypeError):leaf['x'][0]=99
 version=s.world.version(a);s.commit([Intent('delete',a)]);assert s.world.version(a)==version+1 and 'a' not in s.world._aliases

@pytest.mark.parametrize('bad',[{'x':float('nan')},{'x':float('inf')},{1:'notstr'},object(),{'x':bytearray(b'bad')}])
def test_public_JSON_boundaries_still_reject_and_transaction_has_no_partial_prefix(bad):
 s=Session();a=s.world.create('entity',{'v':1},alias='a');before=s.checkpoint()
 with pytest.raises((ValueError,TypeError)):s.commit([Intent('set',a,('v',),value=8),Intent('set',a,('invalid',),value=bad)])
 assert s.checkpoint()==before
 with pytest.raises((ValueError,TypeError)):s.world.set(a,('invalid',),bad)
 assert s.checkpoint()==before

def test_nested_atomic_restores_allstores_allocators_alias_cache_events_RNG():
 s=Session(seed=933);a=s.world.create('entity',{'v':[1,2]},alias='a');before=s.checkpoint();view=s.world.get(a)
 with pytest.raises(RuntimeError):
  with s.atomic():
   s.world.set(a,('v',0),7);s.world.create('other',{'q':[]},alias='b');s.emit('peer.prefix',{'a':[1]});s.schedule('unknown',{'x':1},at=9);s.random.sample('peer.draw')
   with s.atomic():s.world.set(a,('v',1),19)
   raise RuntimeError('fault')
 assert s.checkpoint()==before;assert view['components']['v']==(1,2);assert s.world.get(a)['components']['v']==(1,2)

def test_session_RLock_shared_and_other_thread_cannot_see_atomic_partialwrite():
 s=Session();a=s.world.create('entity',{'n':11},alias='a');assert s.world._lock is s._lock;entered=threading.Event();attempt=threading.Event();release=threading.Event();finished=threading.Event();values=[]
 def writer():
  try:
   with s.atomic():
    s.world.set(a,('n',),31);assert s.world.resolve('a')==a;entered.set();assert release.wait(3);raise RuntimeError('rollback')
  except RuntimeError:pass
 def reader():
  assert entered.wait(3);attempt.set();values.append(s.world.get(a)['components']['n']);finished.set()
 t=threading.Thread(target=writer,daemon=True);r=threading.Thread(target=reader,daemon=True);t.start();r.start();assert attempt.wait(3);assert not finished.wait(.05);release.set();t.join(3);r.join(3);assert not t.is_alive() and not r.is_alive() and values==[11]
