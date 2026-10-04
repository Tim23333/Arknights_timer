import json,pytest
from tools.chapter08_wave_track.test_track_v6 import package,make,proof,OUT

def watched(fault=True):
 p=package();p['entities'][2]['components']['resources']={'audit':{'initial':5,'capacity':10}};p['entities'][2]['components']['buffs']={'initial':['buff/track/watch']};effects=[{'op':'modify_resource','target':'source','resource':'audit','value':7},{'op':'emit','event':'source.beforefault'},{'op':'random','stream':'tracking.callback.rng','probability':1,'on_success':[{'op':'emit','event':'source.rngdraw'}],'on_failure':[]}]
 if fault:effects.append({'op':'modify_resource','target':'source','resource':'absent','delta':1})
 p['buffs'].append({'id':'buff/track/watch','kind':'buff','events':[{'event':'timeline.source_transferred','effects':effects}]});return p

def test_current_queued_callback_body_rollback_keeps_transfer_no_fake_failed_replay():
 pr,s,p=make(watched());s.advance(22);before=s.checkpoint()
 with pytest.raises(Exception):s.advance(3)
 assert s.ctx.state()['timeline']['members']['3']['wave']==1 and len([e for e in s.session.events if e['type']=='timeline.source_transferred'])==1;assert s.ctx.resources.current('director','audit')==5;assert not [e for e in s.session.events if e['type'] in ('source.beforefault','source.rngdraw')];assert not [t for t in s.session.scheduler.pending if t['kind']=='event_reaction' and t['payload']['event'] in ('source.beforefault','source.rngdraw')]
 after=s.checkpoint();assert before['kernel']['random']==after['kernel']['random']
 assert after['kernel']['failure'] is not None
 with pytest.raises(RuntimeError,match='execution has failed'):s.advance(1)
 d=OUT/'queued_failure_v5';d.mkdir(parents=True,exist_ok=True);(d/'actual.json').write_text(json.dumps({'input':p,'before':before,'failed_after':after,'failed_process_not_replayed':True},indent=2),encoding='utf8')

def test_successful_reaction_keeps_realresource_RNG_events_CPP25_head():
 pr,s,p=make(watched(False));s.submit({'action':'skill','source':'director','ability':'ability/track/retire'},at=60);proof(pr,s,p,'queued_success_v5',25,70);assert s.ctx.resources.current('director','audit')==7;assert len([e for e in s.session.events if e['type']=='source.beforefault'])==1 and len([e for e in s.session.events if e['type']=='source.rngdraw'])==1

def test_false_only_timeline_not_opted_into_new_callback_policy():
 pr,s,p=make(package(False));s.advance(15);assert 'tracking_requests' not in s.ctx.state()['timeline']
