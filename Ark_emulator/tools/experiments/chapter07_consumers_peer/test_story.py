import json
from ark_sim import Engine
from ark_sim.tools.replay import replay
from tools.control_driver.public_ack_v2 import PublicAckDriver
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.experiments.chapter07_consumers_peer.common import *
def test_story_v2_source_utf8_five_actual_acks_protect_fade_sidecar_disk_head(tmp_path):
 m=json.loads(STORY.read_text(encoding='utf8'));cid=m['controls'][0]['id'];p=package('story_source_v2');p['scenarioDraft']['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'max_wait_seconds':-1,'fragments':[{'actions':[{'kind':'control','definition':cid,'instanceAlias':'story','managed':True,'blocks_wave':True,'blocks_fragment':False}]}]},{'fragments':[{'actions':[{'kind':'effects','effects':[{'op':'emit','event':'peer.story.after'}]}]}]}]}
 s=create(p,[STORY]);d=PublicAckDriver(s)
 for _ in range(3):s.advance(1);d.observe()
 pin=write_ordered(tmp_path/'story3_sidecar.json',{'simulation':s.checkpoint(),'driver':d.checkpoint()});bundle=load_bound(tmp_path/'story3_sidecar.json',pin);r=Engine.restore(s.program,bundle['simulation'],providers=registry());rd=PublicAckDriver(r,bundle['driver'])
 for _ in range(42):s.advance(1);d.observe();r.advance(1);rd.observe()
 h=replay(s.program,s.export_replay(),providers=registry());capture(s,'story_v2_public');assert s.checkpoint()==r.checkpoint()==h.checkpoint() and d.checkpoint()==rd.checkpoint()
 actual=[e['payload'] for e in events(s,'source.story.row')];expected=[step['effects'][0]['payload'] for step in m['controls'][0]['steps'] if step['kind']=='effects' and step.get('effects') and step['effects'][0].get('event')=='source.story.row'];assert actual==expected and len(actual)==7
 ack=events(s,'control.acknowledged');awaits=events(s,'control.awaiting_ack');assert len(ack)==len(awaits)==len(d.submitted)==5 and [e['time'] for e in ack]==[2,4,6,8,25]
 assert awaits[-1]['time']-ack[-2]['time']==15 and events(s,'control.completed')[0]['time']-ack[-1]['time']==9 and not s.ctx.state().get('input_locks')
 assert len(events(s,'peer.story.after'))==1 and len(s.export_replay()['commands'])==5
