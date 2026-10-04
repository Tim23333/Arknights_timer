import pytest
from tools.chapter08_wave_track.test_track_v6 import make,package,request,proof

def test_exact_root_primitive_false_to_true_same_actor_upgrades_once_no_double_finish():
 p=package(False);pr,s,p=make(p);s.advance(6);source=s.session.world.resolve('boss');assert s.ctx.timeline.finish_current(source,request(False)) is True;assert s.ctx.timeline.finish_current(source,request(True)) is True;state=s.ctx.state()['timeline'];assert state['finish_requests']['0']['parameters']['track_source_at_next_wave'] is True and state['tracking_requests']['0']['source']==source;before=s.checkpoint();assert s.ctx.timeline.finish_current(source,request(True)) is False and s.ctx.timeline.finish_current(source,request(False)) is False;assert s.checkpoint()==before
 s.submit({'action':'skill','source':'director','ability':'ability/track/retire'},at=60);s.advance(65);assert len([e for e in s.session.events if e['type']=='timeline.finish_requested'])==1 and len([e for e in s.session.events if e['type']=='timeline.source_transferred'])==1

def test_two_actual_buff_callbacks_false_then_true_preserve_BSON_intent_CPP15_head():
 p=package(False);p['buffs'][0]['on_remove']=[request(False),request(True)];pr,s,p=make(p);s.submit({'action':'skill','source':'director','ability':'ability/track/retire'},at=60);proof(pr,s,p,'source_callbacks_upgrade',15,70);state=s.ctx.state()['timeline'];assert state['tracking_requests']['0']['status']=='retired';assert len([e for e in s.session.events if e['type']=='timeline.finish_requested'])==1 and len([e for e in s.session.events if e['type']=='timeline.source_tracking_requested'])==1 and len([e for e in s.session.events if e['type']=='timeline.source_transferred'])==1

def test_true_then_false_never_downgrades_or_changes_first_request():
 pr,s,p=make();s.advance(12);before=s.checkpoint();assert s.ctx.timeline.finish_current('boss',request(False)) is False;assert s.checkpoint()==before and s.ctx.state()['timeline']['finish_requests']['0']['parameters']['track_source_at_next_wave'] is True

def test_foreign_current_managed_actor_cannot_upgrade_other_request():
 p=package(False);actions=p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'];late=actions[1].copy();late['spawn']=dict(late['spawn'],instanceAlias='late_other');actions[1]['delay_seconds']=1/30;actions.append(late);pr,s,p=make(p);s.advance(6);assert s.ctx.timeline.finish_current('boss',request(False));s.advance(2);assert s.ctx.timeline.finish_current('old_other',request(True)) is False;assert not s.ctx.state()['timeline'].get('tracking_requests') and s.ctx.state()['timeline']['finish_requests']['0']['source']==s.session.world.resolve('boss');assert s.session.events[-1]['type']=='timeline.finish_rejected'

@pytest.mark.parametrize('stamp',[True,1])
def test_upgrade_sameUID_requires_typed_same_original_lifecycle_generation(stamp):
 pr,s,p=make(package(False));s.advance(6);assert s.ctx.timeline.finish_current('boss',request(False));state=s.ctx.timeline._state();state['finish_requests']['0']['lifecycle_generation']=stamp;s.ctx.timeline._save(state);assert s.ctx.timeline.finish_current('boss',request(True)) is False and not s.ctx.state()['timeline'].get('tracking_requests')

def test_upgrade_callback_fault_rolls_back_original_false_request_and_allstores(monkeypatch):
 pr,s,p=make(package(False));s.advance(6);assert s.ctx.timeline.finish_current('boss',request(False));before=s.checkpoint();old=s.ctx.emit
 def broken(event,*args,**kwargs):
  result=old(event,*args,**kwargs)
  if event=='timeline.source_tracking_requested':raise RuntimeError('upgrade_callback_fault')
  return result
 monkeypatch.setattr(s.ctx,'emit',broken)
 with pytest.raises(RuntimeError,match='upgrade_callback_fault'):s.ctx.timeline.finish_current('boss',request(True))
 assert s.checkpoint()==before
