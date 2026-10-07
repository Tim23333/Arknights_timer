import pytest
from tools.experiments.chapter06_input_target_peer.test_source_correct import fixture,make,skill,event,capture,exact
def camouflage_control(p):
 p['definitions'].append({'id':'buff/peer/target_camo','kind':'buff','duration_seconds':10,'selection_flags':{'camouflage':True}})
 p['definitions'].append({'id':'ability/peer/camo_target','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':3,'buff':'buff/peer/target_camo'}]},'timeline':[]})
 for d in p['definitions']:
  if d['id']=='unit/peer/controller':d['components']['abilities'].append('ability/peer/camo_target')
def huge_other(p):
 for d in p['definitions']:
  if d['id']=='unit/peer/tank2':d['components']['attributes']['base']['taunt_level']=10**9
def test_normal_and_real_charged_cold_both_keep_same_actual_blocker_despite_huge_taunt(tmp_path):
 p,c=fixture('snmage_v2',two=True);huge_other(p);s=make(p,c);s.advance(130);exact(s,tmp_path,150);capture(s,'normal_cold_actual_blocker')
 hits=event(s,'damage.accepted');assert len(hits)==3 and all(e['payload']['target']==3 for e in hits)
 assert [e['payload']['ability'].split('/')[-1] for e in hits]==['normal','normal','coldattack']
 assert [e['payload']['target'] for e in event(s,'buff.applied') if e['payload']['buff']=='buff/ch6/cold/e2c_cold']==[3]
@pytest.mark.parametrize('name',['snmage_v2','snbow'])
def test_unqualified_real_blocker_blocks_fallback_then_withdraw_allows_new_target(name,tmp_path):
 p,c=fixture(name,two=True);huge_other(p);camouflage_control(p);s=make(p,c);skill(s,'camo_target',0);skill(s,'withdraw_target',50);s.advance(40)
 assert s.ctx.spatial.blocked_by('adversary')==3 and not event(s,'damage.accepted') and not [e for e in event(s,'ability.started') if e['payload']['source']==2]
 exact(s,tmp_path,50);capture(s,name+'_camo_no_fallback_release');hits=event(s,'damage.accepted');assert hits and all(e['payload']['target']==5 for e in hits)
def test_charged_cold_does_not_spend_or_fallback_when_blocker_turns_unselectable_before_opportunity():
 p,c=fixture('snmage_v2',two=True);huge_other(p);camouflage_control(p);s=make(p,c);skill(s,'camo_target',200);s.advance(260);capture(s,'charged_camo_gate')
 assert len(event(s,'damage.accepted'))==2 and all(e['payload']['target']==3 for e in event(s,'damage.accepted')) and s.ctx.resources.current('adversary','sp')==2
 assert not [e for e in event(s,'ability.started') if e['payload']['ability'].endswith('/coldattack')]
@pytest.mark.parametrize('name',['snmage_v2','snbow'])
def test_unblocked_original_qualification_rejects_air_then_selects_legal_ground(name):
 p,c=fixture(name,two=True);huge_other(p)
 for d in p['definitions']:
  if d['id']=='unit/peer/tank':d['components']['attributes']['base']['block_count']=0
  if d['id']=='unit/peer/tank2':d['components']['selection_state']['motion']=2
 s=make(p,c);s.advance(40);capture(s,name+'_unblocked_motion_policy');assert s.ctx.spatial.blocked_by('adversary') is None
 # Mage native targetMotion3 admits air; bow targetMotion1 rejects it.
 assert [e['payload']['target'] for e in event(s,'damage.accepted')]==([5] if name=='snmage_v2' else [3])
