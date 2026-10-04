from tools.experiments.chapter06_input_target_peer.test_source_correct import fixture,make,event,capture
def test_snbow_source_two_real_blocker_does_not_lose_to_extreme_other_taunt():
 p,c=fixture('snbow',two=True)
 for d in p['definitions']:
  if d['id']=='unit/peer/tank2':d['components']['attributes']['base']['taunt_level']=10**9
 s=make(p,c);s.advance(90);capture(s,'snbow_native_source2_blocker_taunt')
 assert s.ctx.spatial.blocked_by('adversary')==s.session.world.resolve('tank')
 hits=event(s,'damage.accepted');assert len(hits)==2 and all(e['payload']['target']==s.session.world.resolve('tank') for e in hits)
