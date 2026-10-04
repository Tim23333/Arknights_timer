from copy import deepcopy
import pytest
from tools.chapter08_wave_track.test_track_v6 import make,package,request,proof

def test_retired_before_nextwave_never_transferred_no_birth_skipped_CPP11():
 p=package();p['abilities'][1].pop('selector');p['abilities'][1]['activation']['on_start'][0]['target']=3;pr,s,p=make(p);s.submit({'action':'skill','source':'director','ability':'ability/track/retire'},at=11);proof(pr,s,p,'retired_before_transfer_v6',11,45);state=s.ctx.state()['timeline'];assert not [e for e in s.session.events if e['type']=='timeline.source_transferred'];assert state['tracking_requests']['0']['status']=='retired' and not s.ctx.alive('boss');assert s.ctx.alive('old_other') and s.ctx.alive('next_other') and s.ctx.state()['pending_waves']==0

def test_false_flag_old_managed_member_not_migrated_no_newtracking_fields():
 pr,s,p=make(package(False));proof(pr,s,p,'old_false_policy',15,45);state=s.ctx.state()['timeline'];assert state['members'][str(s.session.world.resolve('boss'))]['wave']==0 and 'tracking_requests' not in state and state['done']

def test_actual_lastwave_no_phantomwave_or_spawn_finished_tracking_ledger():
 p=package();p['scenarioDraft']['timeline']['waves']=p['scenarioDraft']['timeline']['waves'][:1];pr,s,p=make(p);proof(pr,s,p,'last_wave',15,45);state=s.ctx.state()['timeline'];assert state['done'] and state['wave_index']==1 and state['tracking_requests']['0']['status']=='no_next_wave';assert not [e for e in s.session.events if e['type']=='timeline.source_transferred'];assert s.ctx.alive('boss') and s.ctx.state()['pending_waves']==0

def test_unmanaged_actor_rejected_with_actual_rejection_event_not_grant():
 pr,s,p=make();s.advance(6);assert s.ctx.timeline.finish_current('director',request()) is False;assert not s.ctx.state()['timeline'].get('tracking_requests');assert s.session.events[-1]['type']=='timeline.finish_rejected'

def test_request_schedule_fault_restores_allstores_events_jobs_RNG(monkeypatch):
 pr,s,p=make();s.advance(40);before=s.checkpoint();old=s.session.schedule
 def broken(kind,*args,**kwargs):
  if kind=='domain.timeline.signal':raise RuntimeError('wave_schedule_fault')
  return old(kind,*args,**kwargs)
 monkeypatch.setattr(s.session,'schedule',broken)
 with pytest.raises(RuntimeError,match='wave_schedule_fault'):s.ctx.timeline.finish_current('boss',request())
 assert s.checkpoint()==before

def test_transfer_callback_fault_atomic_domain_rolls_back_membership_events_jobs_RNG(monkeypatch):
 pr,s,p=make();s.advance(22);before=s.checkpoint();old=s.ctx.emit
 def broken(event,*args,**kwargs):
  result=old(event,*args,**kwargs)
  if event=='timeline.source_transferred':raise RuntimeError('transfer_callback_fault')
  return result
 monkeypatch.setattr(s.ctx,'emit',broken)
 with pytest.raises(RuntimeError,match='transfer_callback_fault'):
  with s.session.atomic():
   state=s.ctx.timeline._state();state['wave_index']=1;state['phase']='wave_entry';s.ctx.timeline._tracking_entry(state)
 assert s.checkpoint()==before

@pytest.mark.parametrize('field',['lifecycle_generation','death_generation'])
def test_persisted_bool_incarnation_not_equal_to_zero(field):
 pr,s,p=make();s.advance(22);state=s.ctx.timeline._state();state['tracking_requests']['0']['incarnation'][field]=False;state['wave_index']=1;before=s.checkpoint()
 with pytest.raises(ValueError,match='tracking incarnation'):
  with s.session.atomic():s.ctx.timeline._tracking_entry(state)
 assert s.checkpoint()==before

def test_changed_real_integer_incarnation_does_not_transfer_same_oldhandle():
 pr,s,p=make();s.advance(22);ref=s.session.world.resolve('boss');s.ctx.set(ref,('runtime','lifecycle_generation'),1);state=s.ctx.timeline._state();state['wave_index']=1
 with s.session.atomic():state=s.ctx.timeline._tracking_entry(state)
 assert state['tracking_requests']['0']['status']=='source_invalidated' and state['members'][str(ref)]['wave']==0
