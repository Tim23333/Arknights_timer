from copy import deepcopy
import pytest
from tools.experiments.chapter06_input_target_peer.test_source_correct import fixture,make,skill,event,capture,module
def test_snmage_real_blocker_does_not_lose_to_other_target_taunt_one_billion():
 p,c=fixture('snmage_v2',two=True)
 for d in p['definitions']:
  if d['id']=='unit/peer/tank2':d['components']['attributes']['base']['taunt_level']=10**9
 s=make(p,c);s.advance(150);capture(s,'snmage_blocker_extreme_taunt')
 assert s.ctx.spatial.blocked_by('adversary')==s.session.world.resolve('tank')
 hits=event(s,'damage.accepted');assert len(hits)==2 and all(e['payload']['target']==s.session.world.resolve('tank') for e in hits)
@pytest.mark.parametrize('name,index,expected',[('melee_v2',1,509),('frozen_melee',0,614),('frozen_melee',1,2044)])
def test_source_silence_cannot_remove_native_unsilenceable_target_frozen_passive(name,index,expected):
 uid=module(name)['entities'][index]['id'];p,c=fixture(name,uid);s=make(p,c);skill(s,'silence_source',0);skill(s,'freeze_target',5);s.advance(36);capture(s,uid+'_source_silence_target_frozen')
 assert event(s,'damage.accepted')[0]['payload']['amount']==expected
def test_snmage_source_death_after_true_cold_launch_preserves_damage_and_cold():
 p,c=fixture('snmage_v2');s=make(p,c);skill(s,'kill_source',261);s.advance(266);capture(s,'snmage_actual_cold_death_launch')
 launches=event(s,'projectile.launched');hits=event(s,'damage.accepted');assert len(launches)==3 and len(hits)==3 and hits[-1]['payload']['amount']==332
 assert s.ctx.resources.current('adversary','hp')==0 and not s.ctx.active('adversary')
 assert [b['definition'] for b in s.ctx.get('tank',('buffs','instances'),[])]==['buff/ch6/cold/e2c_cold']
