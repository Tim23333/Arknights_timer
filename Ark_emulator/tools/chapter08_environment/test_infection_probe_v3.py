from pathlib import Path
from copy import deepcopy
import json
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_environment.policies_v1 import providers
ROOT=Path(__file__).resolve().parents[2];MODULE=ROOT/'packages/campaign/chapter08_consumers/environment/infection.module.v3.json';INPUTS=[];CAPTURES=[]
def package():
 m=json.loads(MODULE.read_bytes());profile=m['manifest']['metadata']['tile_profile'];board=profile['expected_blackboard'];tiles=[{'tileKey':'tile_floor','buildableType':1,'passableMask':1,'heightType':0} for _ in range(3)];tiles[1]={'tileKey':'tile_infection','buildableType':0,'passableMask':3,'heightType':0,'blackboard':board,'effects':None}
 return {'schemaVersion':2,'manifest':{'id':'package/ch8/environment/infection_probe','requires':['preset/ark_standard']},'entities':[{'id':'unit/peer/recipient','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':100000,'atk':200,'def':137,'mres':27,'attack_speed_ratio':1}},'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}},{'id':'unit/peer/director','kind':'entity','components':{'abilities':['ability/peer/leave','ability/peer/return'],'spatial':{}}}],'abilities':[{'id':'ability/peer/leave','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':2,'position':{'row':0,'col':2}}]},'timeline':[]},{'id':'ability/peer/return','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':2,'position':{'row':0,'col':1}}]},'timeline':[]}],'scenarioDraft':{'id':'scene/peer/infection','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':3,'tiles':tiles,'tile_mechanics':{'tile_infection':profile}},'initialEntities':[{'definition':'unit/peer/recipient','instanceAlias':'actor','position':{'row':0,'col':1}},{'definition':'unit/peer/director','instanceAlias':'director','position':{'row':0,'col':0}}]}}
def test_actual_source_180_none_damage_and_stats_survive_leave_without_refresh_cp_head(tmp_path):
 p=package();INPUTS.append(deepcopy(p));reg=providers();s=Engine.create(Compiler(providers=reg).compile(p,packages=[str(MODULE)]),providers=reg,seed=816180);s.submit({'action':'skill','source':'director','ability':'ability/peer/leave'},at=31);s.submit({'action':'skill','source':'director','ability':'ability/peer/return'},at=61);s.advance(29)
 pin=write_ordered(tmp_path/'infection29.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'infection29.json',pin),providers=reg);s.advance(65);r.advance(65);head=replay(s.program,s.export_replay(),providers=reg);CAPTURES.append({'case':'infection94','checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'commands':s.export_replay()});assert s.checkpoint()==r.checkpoint()==head.checkpoint()
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[30,60,90] and all(e['payload']['source'] is None and e['payload']['amount']==180 for e in hits)
 infection=[b for b in s.ctx.get('actor',('buffs','instances')) if b['definition']=='buff/ch8/environment/tile_infection'];assert len(infection)==1 and infection[0]['expires_at']==9000 and s.ctx.resources.current('actor','hp')==99460
 assert s.ctx.attributes.value('actor','atk')==300 and s.ctx.attributes.value('actor','attack_speed_ratio')==1.5
