from pathlib import Path
from copy import deepcopy
import json,pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[2];MODULE=ROOT/'packages/campaign/chapter08_consumers/uterer/module.v1.reference.json'
INPUTS=[];CAPTURES=[]
def package(defense=337,speed=1):
 m=json.loads(MODULE.read_bytes());unit=m['entities'][0]['id'];return {'schemaVersion':2,'manifest':{'id':'package/peer/ch8uterer','requires':['preset/ark_standard']},'entities':[{'id':'unit/peer/blocker','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':9000,'atk':3500,'def':defense,'mres':17,'block_count':1}},'resources':{'hp':{'initial':9000,'capacity':9000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'deployable':{'base_cost':0,'terrain':'ground','capacity':1,'refund_ratio':0},'lifecycle':{'policy':'policy/ark_lifecycle'},'spatial':{},'abilities':['ability/peer/kill']}}],'abilities':[{'id':'ability/peer/kill','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'true','scale':1,'target':2}]},'timeline':[]}],'scenarioDraft':{'id':'scene/peer/uterer','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':6},'parameters':{'deploy_capacity':1},'resources':{'dp':{'initial':7,'capacity':7},'life':{'initial':99999,'capacity':99999}},'objectives':{},'dependencies':['unit/peer/blocker'],'initialEntities':[{'definition':unit,'instanceAlias':'enemy','position':{'row':1,'col':1},'components':{'attributes':{'base':{'attack_speed_ratio':speed}}},'route':{'motionMode':'WALK','startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':5},'checkpoints':[]}}]}}
def make(p):INPUTS.append(deepcopy(p));s=Engine.create(Compiler().compile(p,packages=[str(MODULE)]),seed=81617);s.submit({'action':'deploy','definition':'unit/peer/blocker','position':{'row':1,'col':1},'alias':'guard'},at=0);return s
def events(s,t):return [e for e in s.session.events if e['type']==t]
def capture(s,k):CAPTURES.append({'case':k,'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'commands':s.export_replay()})
@pytest.mark.parametrize('defense,expected',[(337,43),(277,103),(9000,19)])
def test_native_atk380_unequal_defense_and_minimum_damage(defense,expected):
 s=make(package(defense));s.advance(61);capture(s,'native_def_'+str(defense));hits=[e for e in events(s,'damage.accepted') if e['payload']['source']==2];starts=[e for e in events(s,'ability.started') if e['payload']['source']==2];assert len(hits)>=2 and hits[0]['time']==starts[0]['time']+12 and hits[1]['time']-hits[0]['time']==45 and all(e['payload']['amount']==expected for e in hits)
def test_actual_aspeed4_source_event3_relative_and_disk_head(tmp_path):
 s=make(package(337,4));s.advance(2);pin=write_ordered(tmp_path/'uterer2.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'uterer2.json',pin));s.advance(15);r.advance(15);h=replay(s.program,s.export_replay());capture(s,'speed4_cp_head');assert s.checkpoint()==r.checkpoint()==h.checkpoint();hits=[e for e in events(s,'damage.accepted') if e['payload']['source']==2];starts=[e for e in events(s,'ability.started') if e['payload']['source']==2];assert hits and hits[0]['time']==starts[0]['time']+3 and hits[0]['payload']['amount']==43
def test_real_guard_withdraw_before_first_hit_cancels_and_enemy_keeps_route():
 s=make(package());s.submit({'action':'withdraw','source':'guard'},at=5);s.advance(85);capture(s,'withdraw_and_route');assert not events(s,'damage.accepted') and events(s,'entity.exited') and not s.ctx.active('guard') and s.ctx.resources.current('system/battle','dp')==7
def test_real_public_source_hp3500_death_cancels_queued_melee_packet():
 s=make(package());s.submit({'action':'skill','source':'guard','ability':'ability/peer/kill'},at=5);s.advance(20);capture(s,'source_death');hits=events(s,'damage.accepted');assert len(hits)==1 and hits[0]['payload']['source']!=2 and hits[0]['payload']['amount']==3500 and not s.ctx.alive('enemy') and s.ctx.resources.current('guard','hp')==9000
