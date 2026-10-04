import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_wave_track_v4_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
MODULE=ROOT/'packages/campaign/chapter08_stage_controls/controls.module.v1.json';SOURCE=ROOT/'packages/campaign/chapter08_stage_controls/source/story_opera.source.v1.json';OUT=ROOT/'validation/campaign/chapter08_stage_controls_independent_v1';INPUTS=[]
STORY='control/ch8/source/story/main_08-17';X='control/ch8/source/opera/blast_effect_x';Y='control/ch8/source/opera/blast_effect_y'
def action(definition,alias,at,blocking=False):return {'kind':'control','definition':definition,'instanceAlias':alias,'delay_seconds':at/30,'managed':True,'blocks_wave':blocking,'blocks_fragment':False}
def package(actions):
 return {'schemaVersion':2,'manifest':{'id':'package/peer/stagecontrol','requires':['preset/ark_standard']},'entities':[{'id':'unit/peer/body','kind':'entity','components':{'attributes':{'base':{'max_hp':3000,'atk':371,'def':127,'mres':83}},'resources':{'hp':{'initial':2345,'capacity':3000,'role':'health'},'sp':{'initial':13,'capacity':50}},'buffs':{'initial':['buff/peer/static']},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}],'buffs':[{'id':'buff/peer/static','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':7}]}],'scenarioDraft':{'id':'scene/peer/control','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':3},'objectives':{},'initialEntities':[{'definition':'unit/peer/body','instanceAlias':'body','position':{'row':0,'col':0}}],'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':actions}]}]}}}
def make(p):
 INPUTS.append(p);pr=Compiler().compile(p,packages=[str(MODULE)]);return pr,Engine.create(pr,seed=81983)
def proof(pr,s,p,name,end):
 d=OUT/name;d.mkdir(parents=True,exist_ok=True);f=d/'checkpoint.json';h=write_ordered(f,s.checkpoint());r=Engine.restore(pr,load_bound(f,h));delta=end-s.session.time;s.advance(delta);r.advance(delta);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay()).checkpoint();(d/'evidence.json').write_text(json.dumps({'input':p,'cp_sha':h,'checkpoint':s.checkpoint()},indent=2),encoding='utf8');return s
def unchanged(s,before):
 after=s.ctx.entity('body');assert after==before['body'];assert s.ctx.spatial.grid.tile(0,0)==before['tile'];assert s.checkpoint()['kernel']['random']==before['rng']
def baseline(s):return {'body':s.ctx.entity('body'),'tile':s.ctx.spatial.grid.tile(0,0),'rng':s.checkpoint()['kernel']['random']}

def test_two_concurrent_real_Opera_independent0_6_9_90_rawparams_CP12_head_no_body_RNG_effect():
 p=package([action(X,'x',4),action(Y,'y',10)]);pr,s=make(p);before=baseline(s);s.advance(12);proof(pr,s,p,'concurrent_opera',110);src=json.loads(SOURCE.read_bytes());observed=[e for e in s.session.events if e['type']=='source.opera.node.observed'];assert len(observed)==6
 for key,start in [('blast_effect_x',4),('blast_effect_y',10)]:
  rows=[e for e in observed if e['payload']['key']==key];assert [e['time'] for e in rows]==[start,start+6,start+9];raw=src['opera']['commands'][key]['parsed_nodes'];assert all(e['payload']['source_node']==raw[e['payload']['node_index']] for e in rows)
 assert [(e['time'],e['payload']['key']) for e in s.session.events if e['type']=='source.opera.completed']==[(94,'blast_effect_x'),(100,'blast_effect_y')];unchanged(s,before)

def test_eight_actual_ACK_irregular_times_and_fade9_blocks_until_last_ACK_CP39_head():
 p=package([action(STORY,'story',7,True)]);pr,s=make(p);before=baseline(s);times=[20,21,25,30,31,38,49,55]
 for time in times:
  s.advance(time-s.session.time);row=s.ctx.controls.instance('story');assert row['status']=='running' and row['waiting_step'] is not None;s.submit({'action':'control_ack','control':row['id'],'step':row['waiting_step']},at=time);s.advance(1)
  if time==38:
   d=OUT/'story_mid';d.mkdir(parents=True,exist_ok=True);f=d/'checkpoint.json';h=write_ordered(f,s.checkpoint());saved=(f,h)
 assert s.ctx.controls.instance('story')['status']=='running';s.advance(7);assert s.ctx.controls.instance('story')['status']=='running';s.advance(2);assert s.ctx.controls.instance('story')['status']=='complete';assert [(e['time'],e['payload']['index']) for e in s.session.events if e['type']=='source.story.popup.observed']==list(zip([7]+times[:-1],range(8)));assert [e['time'] for e in s.session.events if e['type']=='control.completed']==[64];assert len([e for e in s.session.events if e['type']=='command.accepted'])==8;unchanged(s,before);assert s.checkpoint()==replay(pr,s.export_replay()).checkpoint()
 # The diskCP39 retains only commands submitted before39; replay identical future public acknowledgements.
 f,h=saved;r=Engine.restore(pr,load_bound(f,h))
 for time in [49,55]:
  r.advance(time-r.session.time);row=r.ctx.controls.instance('story');r.submit({'action':'control_ack','control':row['id'],'step':row['waiting_step']},at=time);r.advance(1)
 r.advance(s.session.time-r.session.time);assert r.checkpoint()==s.checkpoint();(OUT/'story_mid/evidence.json').write_text(json.dumps({'input':p,'cp_sha':h,'checkpoint':s.checkpoint()},indent=2),encoding='utf8')

def test_missing_ACK_keeps_native_block_no_clock_auto_skip_and_wrongstep_reject():
 p=package([action(STORY,'story',3,True)]);pr,s=make(p);s.advance(8);row=s.ctx.controls.instance('story');s.submit({'action':'control_ack','control':row['id'],'step':row['waiting_step']+1},at=8);s.advance(1);proof(pr,s,p,'missing_ack',200);assert s.ctx.controls.instance('story')['waiting_step']==1 and not s.ctx.state()['timeline']['done'];assert len([e for e in s.session.events if e['type']=='source.story.popup.observed'])==1 and len([e for e in s.session.events if e['type']=='command.rejected'])==1
