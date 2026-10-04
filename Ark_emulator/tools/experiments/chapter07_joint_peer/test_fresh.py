import json
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.experiments.chapter07_joint_peer.test_joint_rejection import package,make,capture,children,INPUTS,CAPTURES
ROOT=Path(__file__).resolve().parents[3]
def test_waiting_callback_late_fault_rolls_back_live_ally_and_all_scopes():
 p=package();p['rules'].append({'id':'rule/j/fault','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'bad','expression':'1/0'}],'output':'nodes.bad'}});p['abilities'][0]['activation']['on_start']=[{'op':'modify_resource','target':3,'resource':'hp','delta':-11},{'op':'damage','target':3,'damage_type':'true','rules':{'damage.pipeline':'rule/j/fault'}}]
 s=make(p);s.advance(29);before=s.ctx.resources.current('ally','hp')
 with pytest.raises(Exception):s.advance(1)
 capture(s,'joint_callback_fault');assert s.ctx.resources.current('ally','hp')==before and not s.ctx.get('owner',('runtime','casts')) and not s.ctx.waiting_actions._scopes and s.session.current_task is None
 assert len(children(s,'owner'))==len(children(s,'ally'))==1
def test_cancelled_rebirth_finish_job_revokes_self_and_ally_lease():
 s=make();s.advance(2);task=s.ctx.get('owner',('runtime','rebirth','task'));s.session.cancel(task);s.ctx.buffs.reconcile();capture(s,'finishjob_revoked');assert not children(s,'owner') and not children(s,'ally')
def test_actual_source_boss_waiting_self_bonus_and_one_immo_packet_disk_head(tmp_path):
 p=json.loads((ROOT/'packages/campaign/chapter07_boss/patrt/combined.mechanism.v2.json').read_text(encoding='utf8'));boss=p['entities'][0]['id']
 p['entities'] += [{'id':'unit/j/recipient','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':90000,'atk':7}},'resources':{'hp':{'initial':90000,'capacity':90000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{}}},{'id':'unit/j/sourcecontroller','kind':'entity','components':{'abilities':['ability/j/sourcekill'],'spatial':{}}}]
 p['abilities'].append({'id':'ability/j/sourcekill','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'modify_resource','target':2,'resource':'hp','value':0}]},'timeline':[]})
 p['scenarioDraft']={'id':'scene/j/actual_source','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':3},'initialEntities':[{'definition':boss,'instanceAlias':'boss','position':{'row':0,'col':0}},{'definition':'unit/j/recipient','instanceAlias':'recipient','position':{'row':0,'col':1}},{'definition':'unit/j/sourcecontroller','instanceAlias':'director','position':{'row':0,'col':2}}]}
 INPUTS.append(p);s=Engine.create(Compiler().compile(p),seed=7013);s.submit({'action':'skill','source':'director','ability':'ability/j/sourcekill'},at=5);s.advance(6)
 assert s.ctx.resources.current('boss','hp')==0 and s.ctx.alive('boss') and not s.ctx.active('boss')
 bossrows=s.ctx.get('boss',('buffs','instances'));assert any(b['definition'].endswith('/strength') and b.get('aura_leases') for b in bossrows)
 pin=write_ordered(tmp_path/'source6.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'source6.json',pin));s.advance(30);r.advance(30);h=replay(s.program,s.export_replay());capture(s,'source_boss_self_immo')
 assert s.checkpoint()==r.checkpoint()==h.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(h.session.events))
 hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload'].get('ability','').endswith('/immo_action')];assert len(hits)==1
 # Actual source1600, reborning .2 and retainedstrength .2, true .0521.
 assert hits[0]['payload']['amount']==pytest.approx(1600*(1+.2+.2)*.0521) and s.ctx.resources.current('recipient','hp')==pytest.approx(90000-116.704)
