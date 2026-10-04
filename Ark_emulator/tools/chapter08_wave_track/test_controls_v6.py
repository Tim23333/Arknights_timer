from copy import deepcopy
from tools.chapter08_wave_track.test_track_v6 import package,make,request,proof

def test_real_public_ack_not_skipped_tracking_after_control_and_delays_CP25_head():
 p=package();p['controls']=[{'id':'control/track/ack','kind':'control','clock_policy':'logical','ack_policy':'external','steps':[{'kind':'ack','key':'source/ack'}]}];p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'].append({'kind':'control','definition':'control/track/ack','instanceAlias':'ack','managed':True,'blocks_wave':True,'blocks_fragment':False});pr,s,p=make(p);s.advance(25);assert s.ctx.state()['timeline']['wave_index']==0 and s.ctx.state()['timeline']['tracking_requests']['0']['status']=='pending';waiting=next(e for e in s.session.events if e['type']=='control.awaiting_ack');cmd={'action':'control_ack','control':waiting['payload']['control'],'step':waiting['payload']['step']};s.submit(cmd,at=25);s.submit({'action':'skill','source':'director','ability':'ability/track/retire'},at=60)
 # CP at25 includes the genuine pending external acknowledgement command.
 from pathlib import Path
 from tools.chapter08_wave_track.test_track_v6 import OUT
 from tools.campaign_ordered_checkpoint import write_ordered,load_bound
 from ark_sim import Engine
 from ark_sim.tools.replay import replay
 import json
 d=OUT/'public_ack';d.mkdir(parents=True,exist_ok=True);f=d/'checkpoint.json';h=write_ordered(f,s.checkpoint());r=Engine.restore(pr,load_bound(f,h));s.advance(45);r.advance(45);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay()).checkpoint();transfers=[e for e in s.session.events if e['type']=='timeline.source_transferred'];assert len(transfers)==1 and transfers[0]['time']==28;births=[e for e in s.session.events if e['type']=='entity.created' and e['payload']['definition']=='unit/track/other'];assert [e['time'] for e in births]==[20,33];assert s.ctx.state()['pending_waves']==0 and s.ctx.state()['timeline']['done'];(d/'evidence.json').write_text(json.dumps({'input':p,'cp_sha':h,'checkpoint':s.checkpoint()},indent=2),encoding='utf8')

def test_battle_terminal_preserves_pendingtracking_and_originalbirthcounts():
 p=package();p['scenarioDraft']['objectives']={'type':'waves','life_resource':'life'};p['scenarioDraft']['resources']={'life':{'initial':1,'capacity':1}};p['entities'][2]['components']['abilities'].append('ability/track/defeat');p['abilities'].append({'id':'ability/track/defeat','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'modify_resource','target':'battle','resource':'life','value':0}]},'timeline':[]});pr,s,p=make(p);s.submit({'action':'skill','source':'director','ability':'ability/track/defeat'},at=12);proof(pr,s,p,'actual_terminal',11,14);state=s.ctx.state();assert state['finished'] and state['timeline']['done'] and state['timeline']['phase']=='stopped';assert state['timeline']['tracking_requests']['0']['status']=='terminal_cancelled' and state['pending_waves']==2;assert not [e for e in s.session.events if e['type']=='timeline.source_transferred']
