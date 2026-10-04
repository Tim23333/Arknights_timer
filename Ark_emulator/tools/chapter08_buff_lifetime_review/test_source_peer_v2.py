from pathlib import Path
from copy import deepcopy
import json
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_boss.dragon_fire_policies_v3 import providers as fire
from tools.chapter08_buff_lifetime.policies_v1 import providers as clock
ROOT=Path(__file__).resolve().parents[2];MODULE=ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v8.dynamic.json';INPUTS=[];CAPTURES=[]
REG={**fire(),**clock()};PARENT='buff/ch8/source/dragon_fire';CHILD=PARENT+'[damage]'
def package():
 m=json.loads(MODULE.read_bytes());return {'schemaVersion':2,'manifest':{'id':'package/peer/dragonclock','requires':['preset/ark_standard']},'buffs':[{'id':'buff/peer/resistance','kind':'buff','modifiers':[{'attribute':'one_minus_status_resistance','layer':'final_ratio','value':-.5}]}],'entities':[{'id':'unit/peer/fireowner','kind':'entity','components':{'attributes':{'base':{'max_hp':3131,'atk':493,'def':81,'mres':17}},'resources':{'hp':{'initial':3131,'capacity':3131,'role':'health'}},'spatial':{},'abilities':['ability/peer/fire','ability/peer/retire'],'lifecycle':{'policy':'policy/ark_lifecycle'}}},{'id':'unit/peer/firetarget','kind':'entity','components':{'attributes':{'base':{'max_hp':70000,'atk':217,'def':31,'mres':17,'one_minus_status_resistance':1}},'resources':{'hp':{'initial':70000,'capacity':70000,'role':'health'}},'spatial':{},'abilities':['ability/peer/resistance'],'lifecycle':{'policy':'policy/ark_lifecycle'}}}],'abilities':[{'id':'ability/peer/fire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'buff_application','target':3,'application_rule':'rule/ch8/dragon_fire/application','allowed':[PARENT,CHILD]}]},'timeline':[]},{'id':'ability/peer/resistance','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'self','buff':'buff/peer/resistance'}]},'timeline':[]},{'id':'ability/peer/retire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'self','parameters':{'reason':'peer_source_exit'}}]},'timeline':[]}],'scenarioDraft':{'id':'scene/peer/dragonclock','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':2},'initialEntities':[{'definition':'unit/peer/fireowner','instanceAlias':'fireowner','position':{'row':0,'col':0}},{'definition':'unit/peer/firetarget','instanceAlias':'firetarget','position':{'row':0,'col':1}}]}}
def make():
 p=package();INPUTS.append(deepcopy(p));program=Compiler(providers=REG).compile(p,packages=[str(MODULE)]);return Engine.create(program,providers=REG,seed=8819311)
def proof(s,tmp_path,split,end):
 s.advance(split);pin=write_ordered(tmp_path/'dragon.cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'dragon.cp.json',pin),providers=REG);s.advance(end-split);r.advance(end-split);h=replay(s.program,s.export_replay(),providers=REG);assert s.checkpoint()==r.checkpoint()==h.checkpoint();CAPTURES.append({'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'replay':s.export_replay()})
def test_source_nominal30_5_at11_resistance311_expiry619_child_cadence_and_damage_not_actor_atk(tmp_path):
 s=make();s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/fire'},at=11);s.submit({'action':'skill','source':'firetarget','ability':'ability/peer/resistance'},at=311);proof(s,tmp_path,310,630)
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[11+30*n for n in range(1,21)] and [e['payload']['amount'] for e in hits]==[50+6*n for n in range(1,21)]
 assert [e['time'] for e in s.session.events if e['type']=='buff.removed' and e['payload']['buff']==PARENT]==[619]
 rows=s.ctx.get('firetarget',('buffs','instances'));assert not any(b['definition']==PARENT for b in rows) and len([b for b in rows if b['definition']==CHILD])==1 and s.ctx.resources.current('firetarget','hp')==70000-sum(50+6*n for n in range(1,21))
def test_actual_source_retirement_keeps_existing_dynamic_parent_and_child_timers(tmp_path):
 s=make();s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/fire'},at=11);s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/retire'},at=21);proof(s,tmp_path,20,80)
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[41,71] and [e['payload']['amount'] for e in hits]==[56,62] and not s.ctx.active('fireowner')
 assert {b['definition'] for b in s.ctx.get('firetarget',('buffs','instances'))}=={PARENT,CHILD}

